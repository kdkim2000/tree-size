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

# Sentinel stored on a cached Node to flag that it was deleted since last scan.
_FLAG_DELETED: int = 0x8000


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


    # ------------------------------------------------------------------
    # M4-5 — incremental scan
    # ------------------------------------------------------------------

    def scan_incremental(
        self,
        path: Path,
        options: ScanOptions,
        cancel_token: CancelToken,
        on_node: Callable[[Node], None],
        on_progress: Callable[[ProgressEvent], None],
        last_scan_cache: dict[Path, Node] | None = None,
    ) -> ScanResult:
        """Scan *path* reusing cached nodes whose mtime and logical size are unchanged.

        Parameters
        ----------
        last_scan_cache:
            Flat mapping of ``Path → Node`` built from the previous scan's DB
            rows.  ``None`` is treated the same as an empty cache — a full scan
            is performed.  Directories are re-entered only when their mtime has
            changed, so unchanged subtrees are returned directly from cache.

        Deleted paths
        -------------
        Paths present in *last_scan_cache* but absent from the live filesystem
        are emitted via *on_node* with ``Node.flags | _FLAG_DELETED`` so
        callers (and the DB layer) can tombstone them.
        """
        start = time.monotonic()
        state = _ScanState()
        cache: dict[Path, Node] = last_scan_cache or {}
        root = self._scan_dir_incremental(
            path, None, options, cancel_token,
            on_node, on_progress, state, start, cache,
        )
        elapsed = time.monotonic() - start
        return ScanResult(
            root=root,
            total_files=state.total_files,
            total_bytes=state.total_bytes,
            elapsed_sec=elapsed,
            error_count=state.error_count,
        )

    def _scan_dir_incremental(
        self,
        path: Path,
        parent: Node | None,
        options: ScanOptions,
        cancel_token: CancelToken,
        on_node: Callable[[Node], None],
        on_progress: Callable[[ProgressEvent], None],
        state: _ScanState,
        start: float,
        cache: dict[Path, Node],
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

        live_paths: set[Path] = set()

        for entry in dir_entries:
            cancel_token.wait_if_paused()
            if cancel_token.is_cancelled():
                break

            entry_path = Path(entry.path)
            live_paths.add(entry_path)

            is_reparse = entry_is_reparse(entry)
            if is_reparse and not options.follow_symlinks:
                continue

            stat = safe_stat(entry)
            if stat is None:
                state.error_count += 1
                continue

            cached = cache.get(entry_path)

            if entry.is_dir(follow_symlinks=False):
                # For directories: re-enter if mtime changed or not cached.
                if (
                    cached is not None
                    and cached.is_dir
                    and int(stat.st_mtime) == int(cached.mtime)
                ):
                    # Subtree unchanged — reuse cached aggregate.
                    child = Node(
                        name=cached.name,
                        path=cached.path,
                        is_dir=True,
                        size_logical=cached.size_logical,
                        size_allocated=cached.size_allocated,
                        file_count=cached.file_count,
                        folder_count=cached.folder_count,
                        mtime=cached.mtime,
                        flags=cached.flags,
                        parent=node,
                    )
                    state.total_files += cached.file_count
                    state.total_bytes += cached.size_logical
                else:
                    child = self._scan_dir_incremental(
                        entry_path, node, options,
                        cancel_token, on_node, on_progress, state, start, cache,
                    )

                node.children.append(child)
                node.size_logical += child.size_logical
                node.size_allocated += child.size_allocated
                node.file_count += child.file_count
                node.folder_count += child.folder_count + 1

            else:
                # For files: reuse if both mtime and logical size are unchanged.
                if (
                    cached is not None
                    and not cached.is_dir
                    and int(stat.st_mtime) == int(cached.mtime)
                    and stat.st_size == cached.size_logical
                ):
                    child = Node(
                        name=cached.name,
                        path=cached.path,
                        is_dir=False,
                        size_logical=cached.size_logical,
                        size_allocated=cached.size_allocated,
                        file_count=1,
                        folder_count=0,
                        mtime=cached.mtime,
                        flags=cached.flags,
                        parent=node,
                    )
                else:
                    logical = stat.st_size
                    alloc = get_alloc_size(entry, options.measure_alloc_size)
                    flags = 0x2 if is_reparse else 0
                    child = Node(
                        name=entry.name,
                        path=entry_path,
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
                node.size_logical += child.size_logical
                node.size_allocated += child.size_allocated
                node.file_count += 1
                state.total_files += 1
                state.total_bytes += child.size_logical

            state.scanned += 1
            if state.scanned % _PROGRESS_INTERVAL == 0:
                on_progress(ProgressEvent(
                    current_path=entry_path,
                    total_files=state.total_files,
                    total_bytes=state.total_bytes,
                    elapsed_sec=time.monotonic() - start,
                ))

        # --- Emit tombstone nodes for entries deleted since last scan ---
        for cached_path, cached_node in cache.items():
            # Only direct children of this directory.
            if cached_path.parent != path:
                continue
            if cached_path not in live_paths:
                tombstone = Node(
                    name=cached_node.name,
                    path=cached_path,
                    is_dir=cached_node.is_dir,
                    size_logical=cached_node.size_logical,
                    size_allocated=cached_node.size_allocated,
                    file_count=cached_node.file_count,
                    folder_count=cached_node.folder_count,
                    mtime=cached_node.mtime,
                    flags=cached_node.flags | _FLAG_DELETED,
                    parent=node,
                )
                on_node(tombstone)
                logger.debug("Tombstoned deleted path: %s", cached_path)

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
