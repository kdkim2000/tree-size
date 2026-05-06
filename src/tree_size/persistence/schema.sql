-- Tree-Size SQLite schema (canonical DDL)
-- Applied via migrations/001_initial.sql; do not execute directly in production.

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;   -- 256 MB
PRAGMA cache_size = -65536;     -- 64 MB
PRAGMA foreign_keys = ON;

-- Scan session (one row per root-path scan run)
CREATE TABLE IF NOT EXISTS scans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    root_path     TEXT    NOT NULL,
    started_at    INTEGER NOT NULL,   -- Unix epoch seconds
    finished_at   INTEGER,            -- NULL until scan completes
    options_json  TEXT,
    total_files   INTEGER,
    total_bytes   INTEGER
);

-- Every file and folder node captured during a scan.
-- size_logical / size_allocated on folders are recursive sums.
CREATE TABLE IF NOT EXISTS nodes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    parent_id       INTEGER          REFERENCES nodes(id) ON DELETE CASCADE,
    name            TEXT    NOT NULL,
    path            TEXT    NOT NULL,           -- full path; redundant but accelerates queries
    is_dir          INTEGER NOT NULL,           -- 0 = file, 1 = folder
    size_logical    INTEGER NOT NULL DEFAULT 0,
    size_allocated  INTEGER NOT NULL DEFAULT 0,
    file_count      INTEGER NOT NULL DEFAULT 0,
    folder_count    INTEGER NOT NULL DEFAULT 0,
    mtime           INTEGER NOT NULL,           -- Unix epoch seconds (truncated from float)
    flags           INTEGER NOT NULL DEFAULT 0, -- bit0: NTFS-compressed, bit1: reparse point
    UNIQUE (scan_id, path)
);

CREATE INDEX IF NOT EXISTS idx_nodes_parent    ON nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_nodes_scan_path ON nodes(scan_id, path);
CREATE INDEX IF NOT EXISTS idx_nodes_size      ON nodes(size_logical DESC);
