import json
import multiprocessing as mp
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock
import sys
import native
import input_worker
from leases import Leases, Busy
from engine import Computer


def contender(root, queue):
    try:
        Leases(root).acquire('w-42','other',{'pid':42},30)
        queue.put('acquired')
    except Busy:
        queue.put('busy')


class LeaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.leases = Leases(self.tmp.name)
        self.lease = self.leases.acquire('w-42','one',{'pid':42},30)

    def test_two_processes_same_window_busy_other_window_available(self):
        q = mp.Queue()
        process = mp.Process(target=contender,args=(self.tmp.name,q))
        process.start()
        process.join(10)
        self.assertEqual(process.exitcode,0)
        self.assertEqual(q.get(timeout=2),'busy')
        self.assertEqual(self.leases.acquire('w-43','two',{},30)['owner'],'two')

    def test_wrong_owner_and_token_cannot_release(self):
        for owner,token in [('two',self.lease['token']),('one','wrong')]:
            with self.assertRaises(Busy):
                self.leases.release('w-42',owner,token)

    def test_identity_change_rejected(self):
        with self.assertRaisesRegex(Busy,'WINDOW_CHANGED'):
            self.leases.require('w-42','one',self.lease['token'],{'pid':43})

    def test_expired_inflight_operation_cannot_be_stolen(self):
        with self.leases.operation('w-42','one',self.lease['token']):
            with self.leases.db() as db:
                db.execute('UPDATE leases SET deadline=0')
            with self.assertRaises(Busy):
                self.leases.acquire('w-42','two',{},30)
        newer = self.leases.acquire('w-42','two',{},30)
        with self.assertRaises(Busy):
            self.leases.release('w-42','one',self.lease['token'])
        self.leases.release('w-42','two',newer['token'])

    def test_expired_owner_can_cleanup_but_not_renew(self):
        with self.leases.db() as db:
            db.execute('UPDATE leases SET deadline=0')
        with self.assertRaises(Busy):
            self.leases.renew('w-42','one',self.lease['token'])
        self.leases.release('w-42','one',self.lease['token'])


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.c = Computer(self.tmp.name)
        self.lease = self.c.leases.acquire('w-42','one',{'pid':42},30)
        self.args = ('one','w-42',self.lease['token'])

    @patch('engine.native.identity',return_value={'pid':42})
    @patch('engine.native.presence',return_value={'foreground':'w-42','idle_seconds':0})
    def test_active_user_blocks_semantic_write(self,*mocks):
        with self.assertRaisesRegex(RuntimeError,'USER_ACTIVE'), patch.object(self.c,'run') as run:
            self.c.action(*self.args,'click','@s123:e1')
        run.assert_not_called()

    @patch('engine.native.identity',return_value={'pid':42})
    def test_foreground_semantic_idle_boundary(self,*mocks):
        with patch('engine.native.presence',return_value={'foreground':'w-42','idle_seconds':4.999}), \
             patch.object(self.c,'run') as run:
            with self.assertRaisesRegex(RuntimeError,'USER_ACTIVE'):
                self.c.action(*self.args,'click','@s123:e1')
            run.assert_not_called()
        with patch('engine.native.presence',return_value={'foreground':'w-42','idle_seconds':5.0}), \
             patch.object(self.c,'run',return_value={'ok':True}) as run:
            self.assertTrue(self.c.action(*self.args,'click','@s123:e1')['ok'])
            self.assertNotIn('--headed',run.call_args.args[0])

    @patch('engine.native.identity',return_value={'pid':42})
    @patch('engine.native.presence',return_value={'foreground':'w-99','idle_seconds':0})
    def test_background_action_stdin_and_no_headed(self,*mocks):
        with patch.object(self.c,'run',return_value={'ok':True}) as run:
            self.c.action(*self.args,'set-value','@s123:e1','private text')
            args,kwargs = run.call_args
            self.assertEqual(args[0],['set-value','@s123:e1','--stdin'])
            self.assertEqual(kwargs['text'],'private text')

    def test_arbitrary_commands_refs_and_oversized_text_rejected(self):
        for action,ref,text in [('close-app','@s123:e1',None),('click','--headed',None),('set-value','@s123:e1','x'*131073)]:
            with self.assertRaises(ValueError):
                self.c.action(*self.args,action,ref,text)

    @patch('engine.native.identity',return_value={'pid':42})
    @patch('engine.native.guard_input',side_effect=RuntimeError('USER_ACTIVE'))
    def test_input_refused_releases_desktop_lock(self,*mocks):
        with self.assertRaisesRegex(RuntimeError,'USER_ACTIVE'), patch('engine.subprocess.run') as run:
            self.c.physical(*self.args,'key',value='enter')
        run.assert_not_called()
        self.assertNotIn('desktop-input',[r['resource'] for r in self.c.leases.status()])

    def test_input_macros_and_large_text_rejected(self):
        for action,value in [('key','{ctrl}a{enter}'),('text','a'*33)]:
            with self.assertRaises(ValueError):
                self.c.physical(*self.args,action,value=value)


class NativeGuardTests(unittest.TestCase):
    def test_foreground_and_recent_input_guard(self):
        for state, error in [({'idle_seconds':0,'foreground':'w-42'},'USER_ACTIVE'),
                             ({'idle_seconds':20,'foreground':'w-43'},'FOCUS_CHANGED')]:
            with patch('native.presence',return_value=state), self.assertRaisesRegex(RuntimeError,error):
                native.guard_input('w-42')

    def test_covered_point_never_clicks(self):
        service = MagicMock()
        user32 = MagicMock()
        user32.GetAncestor.return_value = 43
        payload = dict(window_id='w-42',identity={'pid':42},action='click',x=10,y=20)
        with patch.dict(sys.modules, {'windows_mcp.desktop.service':service}), \
             patch('input_worker.native.identity',return_value={'pid':42}), \
             patch('input_worker.native.guard_input'), \
             patch('input_worker.C.WinDLL',return_value=user32):
            with self.assertRaisesRegex(RuntimeError,'POINT_NOT_IN_TARGET'):
                input_worker.execute(payload)
        service.Desktop.click.assert_not_called()


if __name__ == '__main__':
    unittest.main()
