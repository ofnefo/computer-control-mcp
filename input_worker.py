"""Short-lived physical fallback using the existing Windows-MCP runtime, no clipboard."""
import ctypes as C
from ctypes import wintypes as W
import json
import sys
import native


def execute(p):
    # Import before the final presence check: dependency startup must not create a stale guard.
    from windows_mcp.desktop.service import Desktop
    if native.identity(p['window_id']) != p['identity']:
        raise RuntimeError('WINDOW_CHANGED')
    native.guard_input(p['window_id'])
    u = C.WinDLL('user32', use_last_error=True)
    hwnd = int(p['window_id'][2:])
    if p['action'] in {'click','right-click'}:
        u.WindowFromPoint.argtypes = [W.POINT]
        u.WindowFromPoint.restype = W.HWND
        u.GetAncestor.argtypes = [W.HWND,W.UINT]
        u.GetAncestor.restype = W.HWND
        hit = u.WindowFromPoint(W.POINT(p['x'],p['y']))
        if u.GetAncestor(hit,2) != hwnd:
            raise RuntimeError('POINT_NOT_IN_TARGET: window moved or is covered; observe again')
        Desktop.click(None, [p['x'],p['y']], 'left' if p['action']=='click' else 'right')
    elif p['action'] == 'key':
        Desktop.shortcut(None, p['value'])
    else:
        # Unicode SendInput is literal, does not replace the user's clipboard, and has no key syntax.
        class KEYBDINPUT(C.Structure):
            _fields_ = [('wVk',W.WORD),('wScan',W.WORD),('dwFlags',W.DWORD),('time',W.DWORD),('dwExtraInfo',C.c_size_t)]
        class MOUSEINPUT(C.Structure):
            _fields_ = [('dx',W.LONG),('dy',W.LONG),('mouseData',W.DWORD),('dwFlags',W.DWORD),('time',W.DWORD),('dwExtraInfo',C.c_size_t)]
        class UNION(C.Union):
            _fields_ = [('ki',KEYBDINPUT),('mi',MOUSEINPUT)]
        class INPUT(C.Structure):
            _anonymous_ = ('u',)
            _fields_ = [('type',W.DWORD),('u',UNION)]
        raw = p['value'].encode('utf-16-le')
        units = [int.from_bytes(raw[i:i+2],'little') for i in range(0,len(raw),2)]
        values = []
        for unit in units:
            for flags in (4,6):
                v = INPUT(type=1)
                v.ki = KEYBDINPUT(0,unit,flags,0,0)
                values.append(v)
        if values:
            inputs = (INPUT * len(values))(*values)
            if u.SendInput(len(values), inputs, C.sizeof(INPUT)) != len(values):
                raise RuntimeError('INPUT_INCOMPLETE: delivery unknown; inspect instead of repeating')
    return dict(ok=True, delivery='attempted', verify='Observe the target after this action')


if __name__ == '__main__':
    try:
        print(json.dumps(execute(json.load(sys.stdin))))
    except Exception as exc:
        print(str(exc))
        sys.exit(1)
