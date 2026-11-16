"""Read-only Win32 identity/presence guard; no focus stealing or input blocking."""
import ctypes as C
from ctypes import wintypes as W


def identity(window_id):
    if not window_id.startswith('w-') or not window_id[2:].isdigit():
        raise ValueError('Use exact w-<HWND> from computer_windows')
    hwnd = int(window_id[2:])
    u = C.WinDLL('user32', use_last_error=True)
    k = C.WinDLL('kernel32', use_last_error=True)
    u.IsWindow.argtypes = [W.HWND]
    u.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
    if not u.IsWindow(hwnd):
        raise ValueError('WINDOW_GONE: list windows again')
    pid = W.DWORD()
    u.GetWindowThreadProcessId(hwnd, C.byref(pid))
    k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
    k.OpenProcess.restype = W.HANDLE
    k.CloseHandle.argtypes = [W.HANDLE]
    k.GetProcessTimes.argtypes = [W.HANDLE] + [C.POINTER(W.FILETIME)] * 4
    handle = k.OpenProcess(0x1000, False, pid.value)
    if not handle:
        raise OSError('Cannot inspect target process identity')
    times = [W.FILETIME() for _ in range(4)]
    try:
        if not k.GetProcessTimes(handle, *(C.byref(t) for t in times)):
            raise OSError('GetProcessTimes failed')
    finally:
        k.CloseHandle(handle)
    return dict(window_id=window_id, pid=pid.value,
                created=(times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)


def presence():
    u = C.WinDLL('user32', use_last_error=True)
    k = C.WinDLL('kernel32', use_last_error=True)
    class LastInput(C.Structure):
        _fields_ = [('cbSize', W.UINT), ('dwTime', W.DWORD)]
    li = LastInput(C.sizeof(LastInput), 0)
    if not u.GetLastInputInfo(C.byref(li)):
        raise OSError('Cannot inspect user input; refusing physical actions')
    k.GetTickCount.restype = W.DWORD
    u.GetForegroundWindow.restype = W.HWND
    hwnd = u.GetForegroundWindow()
    return dict(idle_seconds=((k.GetTickCount()-li.dwTime) & 0xffffffff)/1000,
                last_input=li.dwTime, foreground=f'w-{hwnd or 0}')


def guard_input(window_id, min_idle=5):
    state = presence()
    if state['idle_seconds'] < min_idle:
        raise RuntimeError('USER_ACTIVE: physical input deferred; use semantic actions or wait')
    if state['foreground'] != window_id:
        raise RuntimeError('FOCUS_CHANGED: target must already be foreground; no automatic focus stealing')
    return state
