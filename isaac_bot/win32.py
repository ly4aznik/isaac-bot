"""Small dependency-free Win32 helpers used by the controller."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes


user32 = ctypes.WinDLL("user32", use_last_error=True)

KEYEVENTF_KEYUP = 0x0002
SW_RESTORE = 9
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
GWL_STYLE = -16
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
SWP_FRAMECHANGED = 0x0020
SWP_NOZORDER = 0x0004


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class INPUT_UNION(ctypes.Union):
    # INPUT's size is determined by its largest variant (MOUSEINPUT on x64).
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", INPUT_UNION)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
kernel32.Process32NextW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
user32.SetParent.argtypes = (wintypes.HWND, wintypes.HWND)
user32.SetParent.restype = wintypes.HWND
user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
user32.GetWindowLongW.restype = wintypes.LONG
user32.SetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.LONG)
user32.SetWindowLongW.restype = wintypes.LONG
user32.MoveWindow.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL)
user32.MoveWindow.restype = wintypes.BOOL


def find_process_by_name(name: str) -> int | None:
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        if kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            while True:
                if entry.szExeFile.casefold() == name.casefold():
                    return int(entry.th32ProcessID)
                if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    break
    finally:
        kernel32.CloseHandle(snapshot)
    return None


def embed_window(hwnd: int, parent_hwnd: int) -> int:
    """Reparent a top-level native window and return its original style."""
    old_style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    child_style = (old_style | WS_CHILD) & ~(WS_POPUP | WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
    user32.SetWindowLongW(hwnd, GWL_STYLE, child_style)
    if not user32.SetParent(hwnd, parent_hwnd):
        error = ctypes.get_last_error()
        if error:
            raise ctypes.WinError(error)
    user32.ShowWindow(hwnd, SW_RESTORE)
    return old_style


def resize_embedded_window(hwnd: int, width: int, height: int) -> None:
    user32.MoveWindow(hwnd, 0, 0, max(1, width), max(1, height), True)


def restore_embedded_window(hwnd: int, old_style: int) -> None:
    user32.SetParent(hwnd, 0)
    user32.SetWindowLongW(hwnd, GWL_STYLE, old_style)
    user32.SetWindowPos(hwnd, 0, 100, 100, 960, 540, SWP_NOZORDER | SWP_FRAMECHANGED)
    user32.ShowWindow(hwnd, SW_RESTORE)


def find_window_for_pid(pid: int) -> int:
    matches: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(hwnd: int, _lparam: int) -> bool:
        window_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value == pid and user32.IsWindowVisible(hwnd):
            matches.append(hwnd)
        return True

    user32.EnumWindows(callback, 0)
    return matches[0] if matches else 0


def wait_for_window(pid: int, timeout: float = 30.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        hwnd = find_window_for_pid(pid)
        if hwnd:
            return hwnd
        time.sleep(0.1)
    raise TimeoutError(f"Isaac did not create a visible window in {timeout:.0f}s")


def focus_window(hwnd: int) -> None:
    user32.ShowWindow(hwnd, SW_RESTORE)
    # Windows may return zero when foreground-lock rules deny the request even
    # though the subsequent SendInput call can activate the target normally.
    user32.SetForegroundWindow(hwnd)


def _send_key(vk: int, key_up: bool) -> None:
    event = INPUT(type=1, ki=KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if key_up else 0, 0, 0))
    if user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
        raise ctypes.WinError(ctypes.get_last_error())


def tap(vk: int, duration: float = 0.05) -> None:
    _send_key(vk, False)
    time.sleep(duration)
    _send_key(vk, True)


def release(vk: int) -> None:
    _send_key(vk, True)
