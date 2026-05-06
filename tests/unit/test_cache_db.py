"""Unit tests for CacheDb API — M4-6.

Coverage targets:
  __init__ / migrations, begin_scan, finish_scan, insert_nodes,
  get_last_scan, get_node, get_children, close, WAL concurrency,
  migration idempotency.
"""
from __future__ import annotations

import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from tree_size.core.node import Node
from tree_size.persistence.cache_db import CacheDb
from tree_size.persistence.migrations import run_migrations


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def db(tmp_path: Path) -> CacheDb:  # type: ignore[misc]
    cache = CacheDb(tmp_path / "cache.db")
    yield cache  # type: ignore[misc]
    cache.close()


def _make_node(
    path: Path,
    *,
    is_dir: bool = False,
    size: int = 1024,
    parent: Node | None = None,
) -> Node:
    return Node(
        name=path.name,
        path=path,
        is_dir=is_dir,
        size_logical=size,
        size_allocated=size,
        file_count=0 if is_dir else 1,
        folder_count=0,
        mtime=float(int(time.time())),
        flags=0,
        parent=parent,
    )


# ---------------------------------------------------------------------------
# __init__ + migration
# ---------------------------------------------------------------------------

def test_init_creates_db_file(tmp_path: Path) -> None:
    db_path = tmp_path / "sub" / "cache.db"
    cache = CacheDb(db_path)
    cache.close()
    assert db_path.exists(), "DB file must be created on init"


def test_init_enables_wal(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.db"
    cache = CacheDb(db_path)
    cache.close()
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("PRAGMA journal_mode").fetchone()
    conn.close()
    assert row[0] == "wal", "WAL mode must be active after init"


# ---------------------------------------------------------------------------
# begin_scan
# ---------------------------------------------------------------------------

def test_begin_scan_returns_positive_int(db: CacheDb, tmp_path: Path) -> None:
    scan_id = db.begin_scan(tmp_path, "{}")
    assert isinstance(scan_id, int) and scan_id > 0


def test_begin_scan_monotone_increasing(db: CacheDb, tmp_path: Path) -> None:
    id1 = db.begin_scan(tmp_path, "{}")
    id2 = db.begin_scan(tmp_path, "{}")
    assert id2 > id1, "scan_id must be monotonically increasing"


# ---------------------------------------------------------------------------
# finish_scan
# ---------------------------------------------------------------------------

def test_finish_scan_records_totals(db: CacheDb, tmp_path: Path) -> None:
    scan_id = db.begin_scan(tmp_path, "{}")
    db.finish_scan(scan_id, total_files=42, total_bytes=99_000)
    # flush queue before reading
    db._queue.join()

    conn = sqlite3.connect(str(db._db_path))
    row = conn.execute(
        "SELECT finished_at, total_files, total_bytes FROM scans WHERE id=?",
        (scan_id,),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0] is not None, "finished_at must be set"
    assert row[1] == 42
    assert row[2] == 99_000


# ---------------------------------------------------------------------------
# insert_nodes / get_node / get_children
# ---------------------------------------------------------------------------

def test_insert_and_get_node(db: CacheDb, tmp_path: Path) -> None:
    scan_id = db.begin_scan(tmp_path, "{}")
    node = _make_node(tmp_path / "file.txt", size=2048)
    db.insert_nodes(scan_id, [node])
    db._queue.join()

    result = db.get_node(scan_id, tmp_path / "file.txt")
    assert result is not None
    assert result.size_logical == 2048
    assert result.name == "file.txt"
    assert result.parent is None, "get_node must return parent=None"


def test_get_node_missing_returns_none(db: CacheDb, tmp_path: Path) -> None:
    scan_id = db.begin_scan(tmp_path, "{}")
    db._queue.join()
    result = db.get_node(scan_id, tmp_path / "nonexistent.bin")
    assert result is None


def _insert_root_and_get_db_id(
    db: CacheDb, scan_id: int, root_path: Path
) -> Node:
    """Insert root node and return it (with parent=None)."""
    root_node = _make_node(root_path, is_dir=True, size=0)
    db.insert_nodes(scan_id, [root_node])
    db._queue.join()
    return root_node


def test_get_children_sorted_desc(db: CacheDb, tmp_path: Path) -> None:
    root_path = tmp_path / "root"
    root_path.mkdir()

    scan_id = db.begin_scan(root_path, "{}")
    root_node = _insert_root_and_get_db_id(db, scan_id, root_path)

    # Insert children with varying sizes, set root as parent
    sizes = [500, 3000, 1000]
    children_nodes = [
        _make_node(root_path / f"file_{i}.bin", size=sz, parent=root_node)
        for i, sz in enumerate(sizes)
    ]
    db.insert_nodes(scan_id, children_nodes)
    db._queue.join()

    children = db.get_children(scan_id, root_path)
    assert len(children) == 3
    sizes_returned = [c.size_logical for c in children]
    assert sizes_returned == sorted(sizes_returned, reverse=True), (
        "get_children must return nodes sorted by size_logical DESC"
    )


def test_get_children_root_parent_none(db: CacheDb, tmp_path: Path) -> None:
    root_path = tmp_path / "root"
    root_path.mkdir()

    scan_id = db.begin_scan(root_path, "{}")
    root_node = _insert_root_and_get_db_id(db, scan_id, root_path)

    child = _make_node(root_path / "child.txt", size=100, parent=root_node)
    db.insert_nodes(scan_id, [child])
    db._queue.join()

    children = db.get_children(scan_id, root_path)
    assert all(c.parent is None for c in children), (
        "get_children must return nodes with parent=None"
    )


# ---------------------------------------------------------------------------
# get_last_scan
# ---------------------------------------------------------------------------

def test_get_last_scan_none_for_unknown_path(db: CacheDb, tmp_path: Path) -> None:
    result = db.get_last_scan(tmp_path / "no_such_dir")
    assert result is None


def test_get_last_scan_returns_latest_finished(db: CacheDb, tmp_path: Path) -> None:
    id1 = db.begin_scan(tmp_path, "{}")
    db.finish_scan(id1, 10, 1000)
    db._queue.join()

    # Ensure distinct finished_at timestamps (integer seconds)
    time.sleep(1.1)

    id2 = db.begin_scan(tmp_path, "{}")
    db.finish_scan(id2, 20, 2000)
    db._queue.join()

    result = db.get_last_scan(tmp_path)
    assert result == id2, "get_last_scan must return the newest finished scan_id"


def test_get_last_scan_ignores_unfinished(db: CacheDb, tmp_path: Path) -> None:
    id1 = db.begin_scan(tmp_path, "{}")
    db.finish_scan(id1, 5, 500)
    db._queue.join()
    _id_unfinished = db.begin_scan(tmp_path, "{}")
    # do NOT call finish_scan for id2
    db._queue.join()

    result = db.get_last_scan(tmp_path)
    assert result == id1, "Unfinished scan must not be returned by get_last_scan"


# ---------------------------------------------------------------------------
# close — idempotent
# ---------------------------------------------------------------------------

def test_close_idempotent(tmp_path: Path) -> None:
    cache = CacheDb(tmp_path / "cache.db")
    cache.close()
    # Second close must not raise
    cache.close()


def test_close_joins_writer_within_10s(tmp_path: Path) -> None:
    cache = CacheDb(tmp_path / "cache.db")
    _scan_id = cache.begin_scan(tmp_path, "{}")
    start = time.monotonic()
    cache.close()
    elapsed = time.monotonic() - start
    assert elapsed < 10.0, f"close() must join writer within 10 s (took {elapsed:.2f}s)"
    assert not cache._writer_thread.is_alive(), "Writer thread must stop after close()"


# ---------------------------------------------------------------------------
# WAL concurrency — multiple reader threads
# ---------------------------------------------------------------------------

def test_wal_concurrent_readers(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.db"
    cache = CacheDb(db_path)

    scan_id = cache.begin_scan(tmp_path, "{}")
    node = _make_node(tmp_path / "shared.bin", size=512)
    cache.insert_nodes(scan_id, [node])
    cache.finish_scan(scan_id, 1, 512)
    cache._queue.join()

    errors: list[Exception] = []

    def reader_task() -> Node | None:
        return cache.get_node(scan_id, tmp_path / "shared.bin")

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(reader_task) for _ in range(5)]
        for fut in as_completed(futures):
            try:
                result = fut.result()
                assert result is not None, "Concurrent reader must find the node"
            except Exception as exc:
                errors.append(exc)

    cache.close()
    assert not errors, f"WAL concurrent read errors: {errors}"


# ---------------------------------------------------------------------------
# Migration idempotency
# ---------------------------------------------------------------------------

def test_run_migrations_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "mig.db"
    run_migrations(db_path)
    # Second call must not raise
    run_migrations(db_path)
