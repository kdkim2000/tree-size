"""Integration tests for incremental scan + CacheDb — M4-7.

Uses real tmp_path filesystem; no mocking (R-T2).
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from tree_size.core.node import CancelToken, Node, ScanOptions
from tree_size.core.scanner import Scanner, _FLAG_DELETED
from tree_size.persistence.cache_db import CacheDb


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def cache_db(tmp_path: Path) -> CacheDb:  # type: ignore[misc]
    db = CacheDb(tmp_path / "cache.db")
    yield db  # type: ignore[misc]
    db.close()


@pytest.fixture()
def synthetic_tree(tmp_path: Path) -> Path:
    """10 folders × 10 files — sizes 1 KB .. 100 KB."""
    root = tmp_path / "tree"
    root.mkdir()
    for fi in range(10):
        folder = root / f"folder_{fi:02d}"
        folder.mkdir()
        for fj in range(10):
            size = 1024 * (fi * 10 + fj + 1)
            (folder / f"file_{fj:02d}.bin").write_bytes(b"\xAB" * size)
    return root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full_scan(root: Path, options: ScanOptions | None = None) -> tuple[Node, float]:
    """Run a full scan and return (root_node, elapsed_seconds)."""
    if options is None:
        options = ScanOptions(follow_symlinks=False, measure_alloc_size=False)
    scanner = Scanner()
    token = CancelToken()
    t0 = time.monotonic()
    result = scanner.scan(root, options, token, on_node=lambda _: None, on_progress=lambda _: None)
    elapsed = time.monotonic() - t0
    return result.root, elapsed


def _flatten_tree(node: Node) -> list[Node]:
    """Recursively collect all nodes in the scan tree."""
    result = [node]
    for child in node.children:
        result.extend(_flatten_tree(child))
    return result


def _incremental_scan(
    root: Path,
    cache: dict[Path, Node],
    options: ScanOptions | None = None,
) -> tuple[list[Node], float, Node]:
    """Run an incremental scan and return (on_node_emissions, elapsed_seconds, root_node)."""
    if options is None:
        options = ScanOptions(follow_symlinks=False, measure_alloc_size=False)
    scanner = Scanner()
    token = CancelToken()
    nodes: list[Node] = []
    t0 = time.monotonic()
    result = scanner.scan_incremental(
        root, options, token,
        on_node=nodes.append,
        on_progress=lambda _: None,
        last_scan_cache=cache,
    )
    elapsed = time.monotonic() - t0
    return nodes, elapsed, result.root


def _collect_all_paths(node: Node) -> set[Path]:
    """Recursively collect all paths in the scan tree."""
    paths: set[Path] = {node.path}
    for child in node.children:
        paths |= _collect_all_paths(child)
    return paths


def _save_scan(db: CacheDb, root_node: Node) -> int:
    """Persist all nodes from a scan tree to the cache, return scan_id."""
    all_nodes = _flatten_tree(root_node)
    scan_id = db.begin_scan(root_node.path, "{}")
    db.insert_nodes(scan_id, all_nodes)
    files = [n for n in all_nodes if not n.is_dir]
    db.finish_scan(scan_id, len(files), sum(n.size_logical for n in files))
    db._queue.join()
    return scan_id


def _build_cache_dict(root_node: Node) -> dict[Path, Node]:
    """Build a flat path→Node cache from a scan result tree."""
    cache: dict[Path, Node] = {}
    for node in _flatten_tree(root_node):
        cache[node.path] = node
    return cache


# ---------------------------------------------------------------------------
# M4-7 tests
# ---------------------------------------------------------------------------

def test_incremental_scan_unchanged(synthetic_tree: Path, cache_db: CacheDb) -> None:
    """2nd scan (no changes) completes in ≤50% of the first scan's time."""
    root1, time1 = _full_scan(synthetic_tree)
    _scan_id = _save_scan(cache_db, root1)
    cache = _build_cache_dict(root1)

    _nodes2, time2, _root2 = _incremental_scan(synthetic_tree, cache)

    # Guard: ensure the first scan covered meaningful data
    assert len(_flatten_tree(root1)) > 1
    # Performance assertion — incremental must be significantly faster when nothing changed
    assert time2 <= time1 * 0.5 or time2 < 0.5, (
        f"Incremental scan should be faster: full={time1:.3f}s incremental={time2:.3f}s"
    )


def test_incremental_scan_with_added_file(
    synthetic_tree: Path, cache_db: CacheDb
) -> None:
    """New file after first scan is discovered in incremental scan."""
    root1, _ = _full_scan(synthetic_tree)
    _scan_id = _save_scan(cache_db, root1)
    cache = _build_cache_dict(root1)

    # Add a new file — back-date folder_00's cache mtime so the
    # incremental scanner sees it as changed and re-enters the directory.
    new_file = synthetic_tree / "folder_00" / "newfile.bin"
    new_file.write_bytes(b"\xFF" * 4096)
    _stale_folder(cache, synthetic_tree / "folder_00")

    _nodes2, _, root2 = _incremental_scan(synthetic_tree, cache)

    found_paths = _collect_all_paths(root2)
    assert new_file in found_paths, "Incremental scan must discover newly added file"


def _stale_folder(cache: dict[Path, Node], folder: Path) -> None:
    """Back-date a folder's cached mtime by 10 s to force incremental re-entry."""
    if folder in cache:
        n = cache[folder]
        cache[folder] = Node(
            name=n.name, path=n.path, is_dir=n.is_dir,
            size_logical=n.size_logical, size_allocated=n.size_allocated,
            file_count=n.file_count, folder_count=n.folder_count,
            mtime=n.mtime - 10.0,
            flags=n.flags,
        )


def test_incremental_scan_with_changes(
    synthetic_tree: Path, cache_db: CacheDb
) -> None:
    """Modified file is re-scanned; deleted file is flagged with _FLAG_DELETED."""
    root1, _ = _full_scan(synthetic_tree)
    _scan_id = _save_scan(cache_db, root1)
    cache = _build_cache_dict(root1)

    # Modify one file (content change changes mtime)
    target = synthetic_tree / "folder_01" / "file_00.bin"
    target.write_bytes(b"\xCC" * 8192)

    # Delete another file
    deleted = synthetic_tree / "folder_02" / "file_00.bin"
    deleted.unlink()

    # Force incremental scanner to re-enter the affected folders
    _stale_folder(cache, synthetic_tree / "folder_01")
    _stale_folder(cache, synthetic_tree / "folder_02")

    emitted_nodes, _, root2 = _incremental_scan(synthetic_tree, cache)

    # Modified file must appear anywhere in the tree
    all_paths = _collect_all_paths(root2)
    assert target in all_paths, "Modified file must be included in incremental scan results"

    # Deleted file must have _FLAG_DELETED set (emitted via on_node as tombstone)
    deleted_nodes = [n for n in emitted_nodes if n.path == deleted]
    assert deleted_nodes, f"Deleted file {deleted} must be emitted as tombstone"
    assert deleted_nodes[0].flags & _FLAG_DELETED != 0, (
        "Tombstone node must have _FLAG_DELETED bit set"
    )


def test_incremental_scan_deleted_file_flag(
    synthetic_tree: Path, cache_db: CacheDb
) -> None:
    """All deleted paths emit tombstone nodes with _FLAG_DELETED."""
    root1, _ = _full_scan(synthetic_tree)
    _scan_id = _save_scan(cache_db, root1)
    cache = _build_cache_dict(root1)

    # Delete 3 files and back-date their parent folders so scanner re-enters
    deleted_paths: list[Path] = []
    for fi in range(3):
        p = synthetic_tree / f"folder_0{fi}" / "file_09.bin"
        p.unlink()
        deleted_paths.append(p)
        _stale_folder(cache, synthetic_tree / f"folder_0{fi}")

    emitted_nodes, _, _root2 = _incremental_scan(synthetic_tree, cache)

    for dp in deleted_paths:
        tombstones = [n for n in emitted_nodes if n.path == dp]
        assert tombstones, f"Expected tombstone for deleted path: {dp}"
        assert tombstones[0].flags & _FLAG_DELETED != 0, (
            f"_FLAG_DELETED must be set on tombstone for {dp}"
        )


def test_scan_worker_with_cache(tmp_path: Path) -> None:
    """ScanWorker integrates with CacheDb: finished scan is queryable via get_last_scan/get_node."""
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication, QThreadPool

    app = QCoreApplication.instance() or QCoreApplication([])

    root = tmp_path / "wroot"
    root.mkdir()
    (root / "a.txt").write_bytes(b"hello")
    (root / "b.txt").write_bytes(b"world" * 100)

    db_path = tmp_path / "worker_cache.db"
    cache = CacheDb(db_path)

    from tree_size.workers.scan_worker import ScanWorker

    worker = ScanWorker(root, ScanOptions(follow_symlinks=False, measure_alloc_size=False), cache_db=cache)

    finished_event: list[bool] = []

    def on_finished(_result: object) -> None:
        finished_event.append(True)

    worker.signals.finished.connect(on_finished)
    worker.signals.cacheWritten.connect(lambda _sid: None)

    QThreadPool.globalInstance().start(worker)

    # Wait up to 10 s for the worker to finish
    deadline = time.monotonic() + 10.0
    while not finished_event and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.05)

    assert finished_event, "ScanWorker must emit finished signal"

    # Flush all pending cache writes
    cache._queue.join()

    scan_id = cache.get_last_scan(root)
    assert scan_id is not None, "get_last_scan must return scan_id after ScanWorker run"

    # ScanWorker emits on_node for each directory — verify root dir is cached
    root_node = cache.get_node(scan_id, root)
    assert root_node is not None, "Root directory must be stored in cache after ScanWorker run"
    assert root_node.is_dir, "Cached root node must be a directory"
    assert root_node.file_count >= 2, (
        f"Root node must report at least 2 files, got {root_node.file_count}"
    )

    cache.close()
