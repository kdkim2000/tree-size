"""Domain entities for the scan tree."""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Node:
    name: str
    path: Path
    is_dir: bool
    size_logical: int       # bytes reported by st_size
    size_allocated: int     # bytes actually used on disk (cluster-aligned or compressed)
    file_count: int         # files under this node (recursive)
    folder_count: int       # sub-folders under this node (recursive)
    mtime: float            # os.stat st_mtime
    flags: int = 0          # bit0=NTFS-compressed, bit1=reparse point
    parent: Node | None = field(default=None, repr=False)
    children: list[Node] = field(default_factory=list, repr=False)


@dataclass(slots=True)
class ProgressEvent:
    current_path: Path
    total_files: int
    total_bytes: int
    elapsed_sec: float


@dataclass(slots=True)
class ScanResult:
    root: Node
    total_files: int
    total_bytes: int
    elapsed_sec: float
    error_count: int


@dataclass
class ScanOptions:
    follow_symlinks: bool = False
    measure_alloc_size: bool = True
    max_workers: int = field(default_factory=lambda: os.cpu_count() or 1)


class CancelToken:
    """Thread-safe cancellation flag. Also supports pause/resume."""

    def __init__(self) -> None:
        self._cancelled = False
        self._paused = False
        self._lock = threading.Lock()
        self._resume_event = threading.Event()
        self._resume_event.set()  # initially running

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
        self._resume_event.set()  # unblock any waiting pause

    def pause(self) -> None:
        with self._lock:
            if not self._cancelled:
                self._paused = True
                self._resume_event.clear()

    def resume(self) -> None:
        with self._lock:
            self._paused = False
        self._resume_event.set()

    def is_cancelled(self) -> bool:
        return self._cancelled

    def wait_if_paused(self) -> None:
        """Block until resumed or cancelled. Call from scanner worker loop."""
        self._resume_event.wait()
