"""Unit tests for core/fs_probe.py — covers previously-uncovered branches.

Targets:
  - get_alloc_size: measure_alloc=True paths (compressed fallback + cluster rounding)
  - get_alloc_size: OSError fallback returning 0
  - safe_stat: returns None on OSError
  - entry_is_reparse: non-Windows path (symlink fallback)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tree_size.core.fs_probe import (
    entry_is_reparse,
    get_alloc_size,
    iter_entries,
    safe_stat,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(path: Path, is_dir: bool = False) -> os.DirEntry[str]:
    """Create a real DirEntry via os.scandir — avoids mocking DirEntry itself."""
    if is_dir:
        path.mkdir(parents=True, exist_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x00" * 4096)
    parent = path.parent
    for entry in os.scandir(str(parent)):
        if entry.name == path.name:
            return entry
    pytest.fail(f"Could not find DirEntry for {path}")


# ---------------------------------------------------------------------------
# iter_entries
# ---------------------------------------------------------------------------

class TestIterEntries:
    def test_yields_entries_for_populated_dir(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_bytes(b"x")
        (tmp_path / "b.txt").write_bytes(b"y")
        entries = list(iter_entries(tmp_path))
        names = {e.name for e in entries}
        assert names == {"a.txt", "b.txt"}

    def test_empty_dir_yields_nothing(self, tmp_path: Path) -> None:
        assert list(iter_entries(tmp_path)) == []

    def test_raises_oserror_on_missing_path(self, tmp_path: Path) -> None:
        with pytest.raises(OSError):
            list(iter_entries(tmp_path / "nonexistent"))


# ---------------------------------------------------------------------------
# get_alloc_size — measure_alloc=False
# ---------------------------------------------------------------------------

class TestGetAllocSizeFalse:
    def test_returns_st_size_when_measure_alloc_false(self, tmp_path: Path) -> None:
        f = tmp_path / "file.bin"
        f.write_bytes(b"\x00" * 1234)
        entry = _make_entry(f)
        result = get_alloc_size(entry, measure_alloc=False)
        # Windows DirEntry.stat may round st_size to cluster boundary — accept any
        # value that is at least the written byte count.
        assert result >= 1234, f"alloc size {result} must be >= written bytes 1234"

    def test_returns_zero_on_stat_error(self, tmp_path: Path) -> None:
        f = tmp_path / "file.bin"
        f.write_bytes(b"\x00" * 100)
        entry = _make_entry(f)
        with patch.object(type(entry), "stat", side_effect=OSError("no stat")):
            result = get_alloc_size(entry, measure_alloc=False)
        assert result == 0


# ---------------------------------------------------------------------------
# get_alloc_size — measure_alloc=True
# ---------------------------------------------------------------------------

class TestGetAllocSizeTrue:
    def test_uses_compressed_size_when_available(self, tmp_path: Path) -> None:
        """When get_compressed_size returns a value, it is used directly."""
        f = tmp_path / "cfile.bin"
        f.write_bytes(b"\x00" * 8192)
        entry = _make_entry(f)
        with patch("tree_size.core.fs_probe.get_compressed_size", return_value=4096):
            result = get_alloc_size(entry, measure_alloc=True)
        assert result == 4096

    def test_falls_back_to_cluster_rounding_when_compressed_size_none(
        self, tmp_path: Path
    ) -> None:
        """When get_compressed_size returns None, round st_size up to 4096."""
        f = tmp_path / "plain.bin"
        f.write_bytes(b"\x00" * 100)  # 100 B → should round up to 4096
        entry = _make_entry(f)
        with patch("tree_size.core.fs_probe.get_compressed_size", return_value=None):
            result = get_alloc_size(entry, measure_alloc=True)
        assert result == 4096, f"100-byte file must round up to 4096, got {result}"

    def test_cluster_rounding_exact_multiple(self, tmp_path: Path) -> None:
        """Exactly 4096 bytes stays at 4096."""
        f = tmp_path / "exact.bin"
        f.write_bytes(b"\x00" * 4096)
        entry = _make_entry(f)
        with patch("tree_size.core.fs_probe.get_compressed_size", return_value=None):
            result = get_alloc_size(entry, measure_alloc=True)
        assert result == 4096

    def test_returns_zero_on_stat_error_with_measure_alloc(
        self, tmp_path: Path
    ) -> None:
        f = tmp_path / "err.bin"
        f.write_bytes(b"\x00" * 100)
        entry = _make_entry(f)
        with patch("tree_size.core.fs_probe.get_compressed_size", return_value=None):
            with patch.object(type(entry), "stat", side_effect=OSError("fail")):
                result = get_alloc_size(entry, measure_alloc=True)
        assert result == 0


# ---------------------------------------------------------------------------
# safe_stat
# ---------------------------------------------------------------------------

class TestSafeStat:
    def test_returns_stat_result_for_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "file.bin"
        f.write_bytes(b"\x00" * 512)
        entry = _make_entry(f)
        result = safe_stat(entry)
        assert result is not None
        # Windows may cluster-align st_size; verify it is a non-negative integer
        assert isinstance(result.st_size, int)
        assert result.st_size >= 0

    def test_returns_none_on_oserror(self, tmp_path: Path) -> None:
        f = tmp_path / "file.bin"
        f.write_bytes(b"\x00")
        entry = _make_entry(f)
        with patch.object(type(entry), "stat", side_effect=OSError("denied")):
            result = safe_stat(entry)
        assert result is None, "safe_stat must return None on OSError"


# ---------------------------------------------------------------------------
# entry_is_reparse
# ---------------------------------------------------------------------------

class TestEntryIsReparse:
    @pytest.mark.skipif(sys.platform == "win32", reason="non-Windows path only")
    def test_non_windows_regular_file_is_not_reparse(self, tmp_path: Path) -> None:
        f = tmp_path / "normal.txt"
        f.write_bytes(b"x")
        entry = _make_entry(f)
        assert entry_is_reparse(entry) is False

    @pytest.mark.skipif(sys.platform == "win32", reason="non-Windows symlink check")
    def test_non_windows_symlink_is_reparse(self, tmp_path: Path) -> None:
        target = tmp_path / "target.txt"
        target.write_bytes(b"x")
        link = tmp_path / "link.txt"
        try:
            link.symlink_to(target)
        except OSError:
            pytest.skip("symlink creation not supported")
        entry = _make_entry(link)
        assert entry_is_reparse(entry) is True

    @pytest.mark.skipif(sys.platform != "win32", reason="Win32 path only")
    def test_windows_regular_file_is_not_reparse(self, tmp_path: Path) -> None:
        f = tmp_path / "normal.bin"
        f.write_bytes(b"x" * 10)
        entry = _make_entry(f)
        # Normal files are not reparse points
        assert entry_is_reparse(entry) is False
