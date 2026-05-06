"""Filesystem probing — os.scandir + Win32 metadata."""
from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

from tree_size.utils.win32 import get_compressed_size, is_reparse_point


def iter_entries(path: Path) -> Iterator[os.DirEntry[str]]:
    """Yield DirEntry items under path. Raises OSError on access failure."""
    with os.scandir(str(path)) as scanner:
        yield from scanner


def get_alloc_size(entry: os.DirEntry[str], measure_alloc: bool) -> int:
    """Return the on-disk allocated size for a file entry.

    If measure_alloc is False or the Win32 call fails, falls back to st_size.
    """
    if not measure_alloc:
        try:
            return entry.stat(follow_symlinks=False).st_size
        except OSError:
            return 0

    path = Path(entry.path)
    compressed = get_compressed_size(path)
    if compressed is not None:
        return compressed

    try:
        stat = entry.stat(follow_symlinks=False)
        # Windows: st_size rounded up to cluster size (typically 4096 B)
        cluster = 4096
        return ((stat.st_size + cluster - 1) // cluster) * cluster
    except OSError:
        return 0


def entry_is_reparse(entry: os.DirEntry[str]) -> bool:
    """Return True if the entry is a reparse point (junction/symlink/mount)."""
    if sys.platform == "win32":
        return is_reparse_point(Path(entry.path))
    return entry.is_symlink()


def safe_stat(entry: os.DirEntry[str]) -> os.stat_result | None:
    """Return stat without following symlinks; None on any OS error."""
    try:
        return entry.stat(follow_symlinks=False)
    except OSError:
        return None
