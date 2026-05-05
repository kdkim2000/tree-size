"""Win32 API wrappers via ctypes — Windows-only helpers."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys
from pathlib import Path

_LONG_PATH_PREFIX = "\\\\?\\"
_UNC_PREFIX = "\\\\"

# GetCompressedFileSizeW returns this sentinel on error
_INVALID_FILE_SIZE = 0xFFFFFFFF


def to_long_path(path: Path) -> Path:
    r"""Prepend \\?\ prefix so Win32 accepts paths > MAX_PATH (260 chars)."""
    s = str(path)
    if s.startswith(_LONG_PATH_PREFIX):
        return path
    if s.startswith(_UNC_PREFIX):
        return Path(_LONG_PATH_PREFIX + "UNC\\" + s[2:])
    return Path(_LONG_PATH_PREFIX + s)


def get_compressed_size(path: Path) -> int | None:
    """Return allocated bytes for an NTFS-compressed file, or None on error.

    Falls back gracefully on non-Windows or if the Win32 call fails.
    """
    if sys.platform != "win32":
        return None

    GetCompressedFileSizeW = ctypes.windll.kernel32.GetCompressedFileSizeW
    GetCompressedFileSizeW.restype = ctypes.wintypes.DWORD
    GetCompressedFileSizeW.argtypes = [
        ctypes.wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.wintypes.DWORD),
    ]

    high = ctypes.wintypes.DWORD(0)
    low = GetCompressedFileSizeW(str(path), ctypes.byref(high))

    if low == _INVALID_FILE_SIZE and ctypes.GetLastError() != 0:
        return None

    return int((high.value << 32) | int(low))


def is_reparse_point(path: Path) -> bool:
    """Return True if path is a reparse point (symlink, junction, mount point)."""
    if sys.platform != "win32":
        return path.is_symlink()

    FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
    GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
    GetFileAttributesW.restype = ctypes.wintypes.DWORD
    GetFileAttributesW.argtypes = [ctypes.wintypes.LPCWSTR]

    attrs = GetFileAttributesW(str(path))
    if attrs == 0xFFFFFFFF:
        return False
    return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)
