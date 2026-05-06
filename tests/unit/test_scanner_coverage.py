"""Additional Scanner unit tests for previously-uncovered branches.

Covers:
  - OSError when listing a directory → error_count incremented (lines 72-76)
  - safe_stat returns None → error_count incremented (lines 89-90)
  - dir_stat OSError → node.mtime stays 0.0 (lines 137-138)
  - incremental scan: OSError on dir listing → error_count (lines 215-219)
  - incremental scan: safe_stat returns None → error_count (line 233)
  - incremental scan: progress interval fires (line 322)
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tree_size.core.node import CancelToken, ScanOptions
from tree_size.core.scanner import Scanner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OPT = ScanOptions(follow_symlinks=False, measure_alloc_size=False)


def _scan(root: Path) -> object:
    return Scanner().scan(
        root, _OPT, CancelToken(),
        on_node=lambda _: None,
        on_progress=lambda _: None,
    )


def _scan_inc(root: Path, cache: dict) -> object:  # type: ignore[type-arg]
    return Scanner().scan_incremental(
        root, _OPT, CancelToken(),
        on_node=lambda _: None,
        on_progress=lambda _: None,
        last_scan_cache=cache,
    )


# ---------------------------------------------------------------------------
# Full-scan OSError paths
# ---------------------------------------------------------------------------

class TestScannerOSErrorBranches:
    def test_inaccessible_subdirectory_increments_error_count(
        self, tmp_path: Path
    ) -> None:
        """When iter_entries raises OSError for a sub-dir, error_count goes up."""
        subdir = tmp_path / "secret"
        subdir.mkdir()
        (subdir / "file.bin").write_bytes(b"x")

        original_iter = __import__(
            "tree_size.core.fs_probe", fromlist=["iter_entries"]
        ).iter_entries

        def patched_iter(path: Path):  # type: ignore[no-untyped-def]
            if path == subdir:
                raise OSError("access denied")
            return original_iter(path)

        with patch("tree_size.core.scanner.iter_entries", side_effect=patched_iter):
            result = _scan(tmp_path)

        assert result.error_count >= 1, (
            "OSError on a sub-directory must increment error_count"
        )

    def test_stat_failure_increments_error_count(self, tmp_path: Path) -> None:
        """When safe_stat returns None for a file, error_count increases."""
        (tmp_path / "file.bin").write_bytes(b"x" * 100)

        with patch("tree_size.core.scanner.safe_stat", return_value=None):
            result = _scan(tmp_path)

        assert result.error_count >= 1, (
            "safe_stat returning None must increment error_count"
        )

    def test_dir_stat_oserror_does_not_crash(self, tmp_path: Path) -> None:
        """OSError on final path.stat() (dir mtime) must be silently ignored."""
        (tmp_path / "f.bin").write_bytes(b"x")

        original_stat = Path.stat

        def patched_stat(self, **kwargs):  # type: ignore[no-untyped-def]
            if self == tmp_path:
                raise OSError("no mtime")
            return original_stat(self, **kwargs)

        with patch.object(Path, "stat", patched_stat):
            result = _scan(tmp_path)

        # node.mtime falls back to 0.0 but scan completes without error
        assert result.error_count == 0
        assert result.root.mtime == 0.0


# ---------------------------------------------------------------------------
# Incremental-scan OSError paths
# ---------------------------------------------------------------------------

class TestIncrementalScanOSErrorBranches:
    def test_inaccessible_subdirectory_increments_error_count(
        self, tmp_path: Path
    ) -> None:
        subdir = tmp_path / "locked"
        subdir.mkdir()
        (subdir / "file.bin").write_bytes(b"x")

        original_iter = __import__(
            "tree_size.core.fs_probe", fromlist=["iter_entries"]
        ).iter_entries

        def patched_iter(path: Path):  # type: ignore[no-untyped-def]
            if path == subdir:
                raise OSError("access denied")
            return original_iter(path)

        with patch("tree_size.core.scanner.iter_entries", side_effect=patched_iter):
            result = _scan_inc(tmp_path, {})

        assert result.error_count >= 1, (
            "Incremental scan must increment error_count on OSError"
        )

    def test_stat_failure_increments_error_count(self, tmp_path: Path) -> None:
        (tmp_path / "file.bin").write_bytes(b"x" * 100)

        with patch("tree_size.core.scanner.safe_stat", return_value=None):
            result = _scan_inc(tmp_path, {})

        assert result.error_count >= 1

    def test_dir_stat_oserror_does_not_crash(self, tmp_path: Path) -> None:
        (tmp_path / "f.bin").write_bytes(b"x")

        original_stat = Path.stat

        def patched_stat(self, **kwargs):  # type: ignore[no-untyped-def]
            if self == tmp_path:
                raise OSError("no mtime")
            return original_stat(self, **kwargs)

        with patch.object(Path, "stat", patched_stat):
            result = _scan_inc(tmp_path, {})

        assert result.error_count == 0
        assert result.root.mtime == 0.0


# ---------------------------------------------------------------------------
# Progress interval in incremental scan
# ---------------------------------------------------------------------------

class TestIncrementalScanProgress:
    def test_progress_fires_in_incremental_scan(self, tmp_path: Path) -> None:
        """600+ files must trigger at least one on_progress call in incremental scan."""
        bulk = tmp_path / "bulk"
        bulk.mkdir()
        for i in range(600):
            (bulk / f"f{i:04d}.bin").write_bytes(b"x")

        events: list[object] = []
        Scanner().scan_incremental(
            tmp_path, _OPT, CancelToken(),
            on_node=lambda _: None,
            on_progress=events.append,
            last_scan_cache={},
        )
        assert len(events) >= 1, "600 files must trigger at least one progress event"
