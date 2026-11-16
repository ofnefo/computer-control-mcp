"""Opt-in real fixture acceptance, never targets other application windows."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import sys
from engine import Computer
import native


def walk(value):
    if isinstance(value,dict):
        yield value
        for v in value.values():
            yield from walk(v)
    elif isinstance(value,list):
        for v in value:
            yield from walk(v)


def run():
    computer = Computer()
    windows = computer.windows()
    found = [n for n in walk(windows) if n.get('title') == 'Computer Control Acceptance Fixture' and 'id' in n]
    if len(found) != 1:
        raise RuntimeError('Start exactly one owned acceptance fixture first')
    window = found[0]['id']
    lease = computer.acquire('codex:computer-control-probe',window)
    args = ('codex:computer-control-probe',window,lease['token'])
    out = computer.root / 'acceptance.json'
    foreground_before = native.presence()['foreground']
    if foreground_before == window:
        computer.leases.release(window,args[0],lease['token'])
        raise RuntimeError('Fixture must be background for this acceptance test')
    point_before = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point_before))
    try:
        before = computer.observe(*args)
        (computer.root/'fixture-before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf-8')
        nodes = list(walk(before))
        edit = next(n for n in nodes if n.get('name') == 'Control input' and n.get('ref_id'))
        def ref(node):
            value=node['ref_id']
            return value if value.startswith('@') else '@'+value
        set_result = computer.action(*args,'set-value',ref(edit),'verified background')
        assert set_result['ok'],set_result
        fresh = computer.observe(*args)
        button = next(n for n in walk(fresh) if n.get('name') == 'Apply fixture' and n.get('ref_id'))
        click_result = computer.action(*args,'click',ref(button))
        assert click_result['ok'],click_result
        after = computer.observe(*args)
        assert 'applied: verified background' in json.dumps(after),after
        point_after = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point_after))
        foreground_after = native.presence()['foreground']
        receipt = dict(ok=True, window=window, pid=found[0]['pid'],
                       text='applied: verified background', foreground_before=foreground_before,
                       foreground_after=foreground_after,
                       cursor_before=[point_before.x,point_before.y],cursor_after=[point_after.x,point_after.y],
                       set_result=set_result,click_result=click_result)
        assert foreground_before == foreground_after,receipt
        assert receipt['cursor_before'] == receipt['cursor_after'],receipt
        capture = computer.screenshot(*args)
        receipt['capture']=capture
        out.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(receipt,ensure_ascii=False))
    finally:
        computer.leases.release(window,args[0],lease['token'])


if __name__ == '__main__':
    run()
