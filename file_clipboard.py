"""Copy an existing file using the Windows shell clipboard format."""
import ctypes
from ctypes import wintypes
import os
import struct


def file_drop_data(path):
    return struct.pack('<IiiII', 20, 0, 0, 0, 1) + (os.path.abspath(path) + '\0\0').encode('utf-16-le')


def copy_file(path, owner):
    if os.name != 'nt':
        raise OSError('File clipboard is available on Windows.')
    if not os.path.isfile(path):
        raise FileNotFoundError('Video no longer exists.')
    user = ctypes.WinDLL('user32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalLock.restype = ctypes.c_void_p
    kernel.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalFree.restype = wintypes.HGLOBAL
    user.OpenClipboard.argtypes = [wintypes.HWND]
    user.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user.SetClipboardData.restype = wintypes.HANDLE
    data = file_drop_data(path)
    handle = kernel.GlobalAlloc(2, len(data))
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    opened = False
    try:
        pointer = kernel.GlobalLock(handle)
        if not pointer:
            raise ctypes.WinError(ctypes.get_last_error())
        ctypes.memmove(pointer, data, len(data))
        kernel.GlobalUnlock(handle)
        if not user.OpenClipboard(owner):
            raise OSError('Clipboard is busy. Try again.')
        opened = True
        if not user.EmptyClipboard() or not user.SetClipboardData(15, handle):
            raise ctypes.WinError(ctypes.get_last_error())
        handle = None  # Windows owns this memory now.
    finally:
        if opened:
            user.CloseClipboard()
        if handle:
            kernel.GlobalFree(handle)
