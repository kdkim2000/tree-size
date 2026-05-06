-- Migration 001: initial schema
-- Idempotent: all statements use IF NOT EXISTS.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS scans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    root_path     TEXT    NOT NULL,
    started_at    INTEGER NOT NULL,
    finished_at   INTEGER,
    options_json  TEXT,
    total_files   INTEGER,
    total_bytes   INTEGER
);

CREATE TABLE IF NOT EXISTS nodes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    parent_id       INTEGER          REFERENCES nodes(id) ON DELETE CASCADE,
    name            TEXT    NOT NULL,
    path            TEXT    NOT NULL,
    is_dir          INTEGER NOT NULL,
    size_logical    INTEGER NOT NULL DEFAULT 0,
    size_allocated  INTEGER NOT NULL DEFAULT 0,
    file_count      INTEGER NOT NULL DEFAULT 0,
    folder_count    INTEGER NOT NULL DEFAULT 0,
    mtime           INTEGER NOT NULL,
    flags           INTEGER NOT NULL DEFAULT 0,
    UNIQUE (scan_id, path)
);

CREATE INDEX IF NOT EXISTS idx_nodes_parent    ON nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_nodes_scan_path ON nodes(scan_id, path);
CREATE INDEX IF NOT EXISTS idx_nodes_size      ON nodes(size_logical DESC);
