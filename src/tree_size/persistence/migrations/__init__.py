"""Versioned schema migration runner for the SQLite cache database.

Each migration is a numbered SQL file within this package.
The ``migrations`` tracking table records which files have already been
applied, making every run idempotent.

R-A3: this module only bootstraps the schema; all subsequent writes go
through ``WriterQueue`` in ``cache_db``.
"""
from __future__ import annotations

import contextlib
import importlib.resources
import logging
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Ordered list of migration filenames.  Append new entries here when adding
# a new migration; never reorder or remove existing ones.
_MIGRATIONS: list[str] = [
    "001_initial.sql",
]

_BOOTSTRAP_DDL = """
CREATE TABLE IF NOT EXISTS migrations (
    version      INTEGER PRIMARY KEY,
    filename     TEXT    NOT NULL,
    executed_at  INTEGER NOT NULL
);
"""


def _migration_sql(filename: str) -> str:
    """Return the SQL text for *filename* from this package."""
    # importlib.resources works both from the source tree and inside a
    # PyInstaller bundle where files are extracted to a temp directory.
    pkg = importlib.resources.files(__name__)
    return (pkg / filename).read_text(encoding="utf-8")


def run_migrations(db_path: Path) -> None:
    """Apply all pending migrations to the database at *db_path*.

    Safe to call on every application start — already-applied migrations are
    skipped.  The connection used here is *not* shared with the writer queue;
    it is opened and closed within this function.
    """
    # WAL must be activated before any schema DDL so concurrent readers are
    # not blocked during the (typically fast) migration phase.
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")

        # Bootstrap the tracking table in its own transaction.
        conn.execute("BEGIN")
        conn.execute(_BOOTSTRAP_DDL)
        conn.execute("COMMIT")

        applied: set[str] = {
            row[0]
            for row in conn.execute("SELECT filename FROM migrations")
        }

        for version, filename in enumerate(_MIGRATIONS, start=1):
            if filename in applied:
                logger.debug("Migration already applied: %s", filename)
                continue

            logger.info("Applying migration %s", filename)
            sql = _migration_sql(filename)

            conn.execute("BEGIN")
            # Drive statements individually to keep transaction control here;
            # executescript() has implicit COMMIT behaviour we want to avoid.
            for statement in _split_statements(sql):
                conn.execute(statement)
            conn.execute(
                "INSERT INTO migrations (version, filename, executed_at) VALUES (?, ?, ?)",
                (version, filename, int(time.time())),
            )
            conn.execute("COMMIT")
            logger.info("Migration applied: %s", filename)

    except sqlite3.Error:
        logger.exception("Migration failed; rolling back")
        with contextlib.suppress(sqlite3.Error):
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def _split_statements(sql: str) -> list[str]:
    """Split a SQL script into individual non-empty, non-comment statements."""
    return [
        s.strip()
        for s in sql.split(";")
        if s.strip() and not s.strip().startswith("--")
    ]
