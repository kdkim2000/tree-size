"""SQLite-backed cache for scan results.

Architecture notes
------------------
* WAL mode is enabled on every connection (R-A3).
* All writes are serialised through ``WriterQueue``; readers open their own
  per-thread connections (WAL allows concurrent readers).
* Parameterised queries only — no string concatenation into SQL (R-S3).
* ``pathlib.Path`` throughout; ``str(path)`` only at the SQLite boundary (R-A4).
"""
from __future__ import annotations

import logging
import queue
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tree_size.core.node import Node
from tree_size.persistence.migrations import run_migrations  # package __init__

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Writer-queue command types  (R-A3)
# ---------------------------------------------------------------------------

@dataclass
class _InsertScan:
    root_path: str
    started_at: int
    options_json: str
    result_holder: "list[int]"   # writer fills result_holder[0] with lastrowid


@dataclass
class _FinishScan:
    scan_id: int
    finished_at: int
    total_files: int
    total_bytes: int


@dataclass
class _InsertNodes:
    rows: list[tuple[Any, ...]]


# Sentinel — stops the writer loop cleanly.
_SHUTDOWN = object()


# ---------------------------------------------------------------------------
# Per-thread reader connection cache
# ---------------------------------------------------------------------------

_reader_local = threading.local()


def _get_reader_conn(db_path: str) -> sqlite3.Connection:
    """Return (and cache) one read-only connection per thread."""
    conn: sqlite3.Connection | None = getattr(_reader_local, "conn", None)
    if conn is None:
        # URI mode: ro + WAL-compatible immutable=0
        uri = f"file:{db_path}?mode=ro&immutable=0"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _reader_local.conn = conn
    return conn


# ---------------------------------------------------------------------------
# Writer loop (runs on its own daemon thread)
# ---------------------------------------------------------------------------

def _writer_loop(db_path: str, q: "queue.Queue[Any]") -> None:
    """Drain the writer queue and execute commands against a dedicated connection."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA mmap_size = 268435456")
    conn.execute("PRAGMA cache_size = -65536")

    try:
        while True:
            cmd = q.get()
            if cmd is _SHUTDOWN:
                break

            try:
                _dispatch(conn, cmd)
            except sqlite3.Error:
                logger.exception("WriterQueue command failed: %r", cmd)
            finally:
                q.task_done()
    finally:
        conn.close()


def _dispatch(conn: sqlite3.Connection, cmd: Any) -> None:
    match cmd:
        case _InsertScan(root_path, started_at, options_json, result_holder):
            cur = conn.execute(
                "INSERT INTO scans (root_path, started_at, options_json)"
                " VALUES (?, ?, ?)",
                (root_path, started_at, options_json or ""),
            )
            conn.commit()
            result_holder.append(cur.lastrowid)   # type: ignore[arg-type]

        case _FinishScan(scan_id, finished_at, total_files, total_bytes):
            conn.execute(
                "UPDATE scans"
                " SET finished_at=?, total_files=?, total_bytes=?"
                " WHERE id=?",
                (finished_at, total_files, total_bytes, scan_id),
            )
            conn.commit()

        case _InsertNodes(rows):
            # Batch upsert; ON CONFLICT REPLACE keeps the index unique
            conn.executemany(
                "INSERT OR REPLACE INTO nodes"
                " (scan_id, parent_id, name, path, is_dir,"
                "  size_logical, size_allocated, file_count, folder_count, mtime, flags)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            conn.commit()

        case _:
            logger.warning("Unknown writer command type: %r", type(cmd))


# ---------------------------------------------------------------------------
# Public CacheDb interface
# ---------------------------------------------------------------------------

_NODE_COLUMNS = (
    "name", "path", "is_dir",
    "size_logical", "size_allocated",
    "file_count", "folder_count",
    "mtime", "flags",
)

_SELECT_CHILDREN = (
    "SELECT name, path, is_dir, size_logical, size_allocated,"
    "       file_count, folder_count, mtime, flags"
    " FROM nodes"
    " WHERE scan_id = ? AND parent_id = ("
    "    SELECT id FROM nodes WHERE scan_id = ? AND path = ?"
    " )"
    " ORDER BY size_logical DESC"
)

_SELECT_NODE = (
    "SELECT name, path, is_dir, size_logical, size_allocated,"
    "       file_count, folder_count, mtime, flags"
    " FROM nodes"
    " WHERE scan_id = ? AND path = ?"
)

_SELECT_LAST_SCAN = (
    "SELECT id FROM scans"
    " WHERE root_path = ? AND finished_at IS NOT NULL"
    " ORDER BY finished_at DESC"
    " LIMIT 1"
)


def _row_to_node(row: sqlite3.Row) -> Node:
    return Node(
        name=row["name"],
        path=Path(row["path"]),
        is_dir=bool(row["is_dir"]),
        size_logical=row["size_logical"],
        size_allocated=row["size_allocated"],
        file_count=row["file_count"],
        folder_count=row["folder_count"],
        mtime=float(row["mtime"]),
        flags=row["flags"],
    )


class CacheDb:
    """Thread-safe SQLite cache.

    * ``begin_scan`` / ``finish_scan`` / ``insert_nodes`` — called from
      worker threads; commands are queued to the single writer.
    * ``get_children`` / ``get_node`` / ``get_last_scan`` — called from any
      thread; each thread gets its own read-only connection.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = str(db_path)
        # Ensure parent dir exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Apply schema migrations before opening reader/writer.
        run_migrations(db_path)

        self._queue: queue.Queue[Any] = queue.Queue()
        self._writer_thread = threading.Thread(
            target=_writer_loop,
            args=(self._db_path, self._queue),
            name="CacheDb-writer",
            daemon=True,
        )
        self._writer_thread.start()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Drain pending writes and shut down the writer thread."""
        self._queue.put(_SHUTDOWN)
        self._writer_thread.join(timeout=10)
        # Close any reader connection on *this* thread.
        conn: sqlite3.Connection | None = getattr(_reader_local, "conn", None)
        if conn is not None:
            conn.close()
            _reader_local.conn = None

    # ------------------------------------------------------------------
    # Scan session management
    # ------------------------------------------------------------------

    def begin_scan(self, root_path: Path, options_json: str) -> int:
        """Create a new scan row and return its ``scan_id``.

        Blocks until the write is committed so the caller has a valid id to
        pass to subsequent ``insert_nodes`` calls.
        """
        result_holder: list[int] = []
        cmd = _InsertScan(
            root_path=str(root_path),
            started_at=int(time.time()),
            options_json=options_json,
            result_holder=result_holder,
        )
        self._queue.put(cmd)
        # Wait for the writer to process this specific command.
        self._queue.join()
        if not result_holder:
            raise RuntimeError("begin_scan: writer did not return a scan_id")
        return result_holder[0]

    def finish_scan(self, scan_id: int, total_files: int, total_bytes: int) -> None:
        """Mark a scan as complete with aggregate totals."""
        self._queue.put(
            _FinishScan(
                scan_id=scan_id,
                finished_at=int(time.time()),
                total_files=total_files,
                total_bytes=total_bytes,
            )
        )

    def insert_nodes(self, scan_id: int, nodes: list[Node], parent_id: int | None = None) -> None:
        """Queue a bulk insert of *nodes* belonging to *scan_id*.

        ``parent_id`` is the DB id of the parent row (``None`` for root).
        Note: caller is responsible for inserting parent before children so
        the ``nodes.id`` foreign key is satisfied.
        """
        rows = [
            (
                scan_id,
                parent_id,
                n.name,
                str(n.path),
                1 if n.is_dir else 0,
                n.size_logical,
                n.size_allocated,
                n.file_count,
                n.folder_count,
                int(n.mtime),
                n.flags,
            )
            for n in nodes
        ]
        self._queue.put(_InsertNodes(rows=rows))

    # ------------------------------------------------------------------
    # Read API (multi-thread safe via per-thread connections)
    # ------------------------------------------------------------------

    def get_last_scan(self, root_path: Path) -> int | None:
        """Return the most recent *finished* scan id for *root_path*, or ``None``."""
        conn = _get_reader_conn(self._db_path)
        row = conn.execute(_SELECT_LAST_SCAN, (str(root_path),)).fetchone()
        return int(row["id"]) if row else None

    def get_node(self, scan_id: int, path: Path) -> Node | None:
        """Return the ``Node`` at *path* within *scan_id*, or ``None`` if not found."""
        conn = _get_reader_conn(self._db_path)
        row = conn.execute(_SELECT_NODE, (scan_id, str(path))).fetchone()
        return _row_to_node(row) if row else None

    def get_children(self, scan_id: int, parent_path: Path) -> list[Node]:
        """Return direct children of *parent_path* in *scan_id*, sorted by size desc."""
        conn = _get_reader_conn(self._db_path)
        rows = conn.execute(
            _SELECT_CHILDREN,
            (scan_id, scan_id, str(parent_path)),
        ).fetchall()
        return [_row_to_node(r) for r in rows]
