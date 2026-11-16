"""One scoped entry point for native Windows computer use (CLI and MCP)."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from leases import Leases
import native

# All cooperating clients for this Windows user must share the same state directory.
STATE = Path(os.environ.get('COMPUTER_CONTROL_STATE') or
             str(Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'computer-control-mcp'))
BACKEND = Path(os.environ.get('COMPUTER_CONTROL_BACKEND') or
               str(Path(__file__).resolve().parent / 'vendor' / 'agent-desktop.exe'))
PYTHON = Path(sys.executable)
SEMANTIC = {'click', 'set-value', 'clear', 'select', 'toggle', 'check', 'uncheck', 'expand', 'collapse', 'scroll-to'}


class Computer:
    def __init__(self, root=STATE, backend=BACKEND):
        self.root = Path(root)
        self.leases = Leases(self.root / 'leases')
        self.backend = Path(backend)

    def run(self, args, token='read', text=None, timeout=35):
        env = {k:v for k,v in os.environ.items() if not k.startswith('AGENT_DESKTOP_')}
        env.update(AGENT_DESKTOP_HOME=str(self.root / 'backend'), PYTHONUTF8='1')
        session = 'pc-' + hashlib.sha256(token.encode()).hexdigest()[:24]
        command = [str(self.backend), '--session', session, *args]
        try:
            proc = subprocess.run(command, input=text, capture_output=True, encoding='utf-8',
                                  errors='replace', timeout=timeout, env=env,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except subprocess.TimeoutExpired:
            raise RuntimeError('BACKEND_TIMEOUT: child stopped; delivery may be unknown, observe before retry') from None
        try:
            result = json.loads(proc.stdout)
        except ValueError:
            raise RuntimeError(f'BACKEND_ERROR: exit {proc.returncode}; no JSON result') from None
        if proc.returncode and result.get('ok'):
            raise RuntimeError('BACKEND_ERROR: inconsistent process exit')
        return result

    def windows(self):
        return self.run(['list-windows'])

    def status(self):
        return dict(backend=str(self.backend), available=self.backend.is_file(),
                    presence=native.presence(), leases=self.leases.status(),
                    physical_policy='one foreground action, idle >=5s, exclusive desktop lease; never automatic focus',
                    coordination='cooperative; old raw tools and human input are not blocked')

    def acquire(self, owner, window_id, ttl=120):
        return self.leases.acquire(window_id, owner, native.identity(window_id), ttl)

    def observe(self, owner, window_id, token, depth=8):
        if not 1 <= depth <= 20:
            raise ValueError('depth must be 1..20')
        with self.leases.operation(window_id, owner, token, native.identity(window_id)):
            return self.run(['snapshot', '--window-id', window_id, '--max-depth', str(depth),
                             '--include-bounds', '--compact', '--timeout-ms', '10000'], token)

    def action(self, owner, window_id, token, action, ref, text=None):
        if action not in SEMANTIC:
            raise ValueError('Unsupported semantic action; see computer_action schema')
        if not re.fullmatch(r'@s[a-zA-Z0-9]+:e[0-9]+', ref):
            raise ValueError('Use a qualified ref from this lease\'s latest snapshot')
        if text is not None and (action != 'set-value' or len(text.encode('utf-8')) > 131072):
            raise ValueError('text is only for set-value (maximum 128 KiB)')
        if action == 'set-value' and text is None:
            raise ValueError('set-value requires text (empty string clears)')
        with self.leases.operation(window_id, owner, token, native.identity(window_id)):
            state = native.presence()
            if state['foreground'] == window_id and state['idle_seconds'] < 5:
                raise RuntimeError('USER_ACTIVE: target is being used; choose a background window or wait')
            args = [action, ref]
            if action == 'set-value':
                args.append('--stdin')
            # Never --headed: unsupported UIA patterns fail instead of silently stealing input.
            return self.run(args, token, text=text)

    def screenshot(self, owner, window_id, token):
        with self.leases.operation(window_id, owner, token, native.identity(window_id)):
            folder = self.root / 'captures'
            folder.mkdir(exist_ok=True)
            path = folder / (hashlib.sha256(token.encode()).hexdigest()[:12] + '-' + str(time.time_ns()) + '.png')
            result = self.run(['screenshot', '--window-id', window_id, str(path)], token)
            if result.get('ok') and path.is_file():
                result['capture_path'] = str(path)
            return result

    def physical(self, owner, window_id, token, action, x=None, y=None, value=None):
        """Bounded Windows-MCP fallback. No macros, held buttons, app launch or process kill."""
        if action not in {'click', 'right-click', 'key', 'text'}:
            raise ValueError('Physical action must be click, right-click, key or text')
        if action in {'click', 'right-click'} and (type(x) is not int or type(y) is not int):
            raise ValueError('click needs integer physical screen coordinates x,y')
        if action == 'key' and (not value or not re.fullmatch(r'[a-zA-Z0-9+_-]{1,60}', value)):
            raise ValueError('key needs a single chord such as ctrl+s or escape')
        if action == 'text' and (not isinstance(value, str) or len(value) > 32):
            raise ValueError('physical text: maximum 32 characters per call; prefer semantic set-value')
        with self.leases.operation(window_id, owner, token, native.identity(window_id)):
            desktop = self.leases.acquire('desktop-input', owner, {}, 10)
            try:
                with self.leases.operation('desktop-input', owner, desktop['token']):
                    native.guard_input(window_id)
                    payload = dict(window_id=window_id, identity=native.identity(window_id),
                                   action=action, x=x, y=y, value=value)
                    try:
                        proc = subprocess.run([str(PYTHON), '-X', 'utf8', '-B', str(Path(__file__).with_name('input_worker.py'))],
                                              input=json.dumps(payload), capture_output=True, encoding='utf-8',
                                              timeout=8, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    except subprocess.TimeoutExpired:
                        raise RuntimeError('INPUT_TIMEOUT: child stopped; inspect before retrying (delivery unknown)') from None
                    if proc.returncode:
                        raise RuntimeError('INPUT_REFUSED: ' + proc.stdout.strip()[:300])
                    return json.loads(proc.stdout)
            finally:
                self.leases.release('desktop-input', owner, desktop['token'])


def main():
    """JSON request on stdin keeps entered text and lease tokens out of process arguments."""
    request = json.load(sys.stdin)
    command = request.pop('command')
    computer = Computer()
    routes = {k:getattr(computer,k) for k in ('windows','status','acquire','observe','action','screenshot','physical')}
    routes.update(renew=computer.leases.renew, release=computer.leases.release)
    if command not in routes:
        raise ValueError('Unknown command')
    print(json.dumps(routes[command](**request), ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps(dict(ok=False,error=str(exc)), ensure_ascii=False))
        sys.exit(1)
