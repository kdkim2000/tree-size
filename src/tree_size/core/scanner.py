"""Synchronous recursive scanner — meant to be called from a QRunnable worker."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from tree_size.core.fs_probe import entry_is_reparse, get_alloc_size, iter_entries, safe_stat
from tree_size.core.node import (
    CancelToken,
    Node,
    ProgressEvent,
    ScanOptions,
    ScanResult,
)

logger = logging.getLogger(__name__)

_PROGRESS_INTERVAL = 500  # emit progress every N files


class Scanner:
    def scan(
        self,
        path: Path,
        options: ScanOptions,
        cancel_token: CancelToken,
        on_node: Callable[[Node], None],
        on_progress: Callable[[ProgressEvent], None],
    ) -> ScanResult:
        start = time.monotonic()
        state = _ScanState()
        root = self._scan_dir(path, None, options, cancel_token, on_node, on_progress, state, start)
        elapsed = time.monotonic() - start
        return ScanResult(
            root=root,
            total_files=state.total_files,
            total_bytes=state.total_bytes,
            elapsed_sec=elapsed,
            error_count=state.error_count,
        )

    def _scan_dir(
        self,
        path: Path,
        parent: Node | None,
        options: ScanOptions,
        cancel_token: CancelToken,
        on_node: Callable[[Node], None],
        on_progress: Callable[[ProgressEvent], None],
        state: _ScanState,
        start: float,
    ) -> Node:
        node = Node(
            name=path.name or str(path),
            path=path,
            is_dir=True,
            size_logical=0,
            size_allocated=0,
            file_count=0,
            folder_count=0,
            mtime=0.0,
            parent=parent,
        )

        try:
            dir_entries = list(iter_entries(path))
        except OSError:
            state.error_count += 1
            logger.warning("Cannot list directory: %s", path)
            on_node(node)
            return node

        for entry in dir_entries:
            cancel_token.wait_if_paused()
            if cancel_token.is_cancelled():
                break

            is_reparse = entry_is_reparse(entry)
            if is_reparse and not options.follow_symlinks:
                continue

            stat = safe_stat(entry)
            if stat is None:
                state.error_count += 1
                continue

            if entry.is_dir(follow_symlinks=False):
                child = self._scan_dir(
                    Path(entry.path), node, options,
                    cancel_token, on_node, on_progress, state, start,
                )
                node.children.append(child)
                node.size_logical += child.size_logical
                node.size_allocated += child.size_allocated
                node.file_count += child.file_count
                node.folder_count += child.folder_count + 1
            else:
                logical = stat.st_size
                alloc = get_alloc_size(entry, options.measure_alloc_size)
                flags = 0x2 if is_reparse else 0
                child = Node(
                    name=entry.name,
                    path=Path(entry.path),
                    is_dir=False,
                    size_logical=logical,
                    size_allocated=alloc,
                    file_count=1,
                    folder_count=0,
                    mtime=stat.st_mtime,
                    flags=flags,
                    parent=node,
                )
                node.children.append(child)
                node.size_logical += logical
                node.size_allocated += alloc
                node.file_count += 1
                state.total_files += 1
                state.total_bytes += logical

            state.scanned += 1
            if state.scanned % _PROGRESS_INTERVAL == 0:
                on_progress(ProgressEvent(
                    current_path=Path(entry.path),
                    total_files=state.total_files,
                    total_bytes=state.total_bytes,
                    elapsed_sec=time.monotonic() - start,
                ))

        try:
            dir_stat = path.stat()
            node.mtime = dir_stat.st_mtime
        except OSError:
            pass

        on_node(node)
        return node


class _ScanState:
    __slots__ = ("total_files", "total_bytes", "error_count", "scanned")

    def __init__(self) -> None:
        self.total_files = 0
        self.total_bytes = 0
        self.error_count = 0
        self.scanned = 0
