"""Integration tests: full scan workflow with real filesystem.

All tests use tmp_path (real files); no mocking.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tree_size.core.aggregator import aggregate
from tree_size.core.node import CancelToken, Node, ProgressEvent, ScanOptions
from tree_size.core.scanner import Scanner


# ---------------------------------------------------------------------------
# Tree builder
# ---------------------------------------------------------------------------

def _build_tree(root: Path) -> dict[str, int]:
    """Build a realistic directory tree; return {filename: size_bytes}."""
    sizes: dict[str, int] = {}

    (root / "docs").mkdir()
    (root / "docs" / "readme.txt").write_bytes(b"A" * 1024)
    sizes["readme.txt"] = 1024

    (root / "src").mkdir()
    (root / "src" / "main.py").write_bytes(b"B" * 512)
    sizes["main.py"] = 512
    (root / "src" / "utils.py").write_bytes(b"C" * 256)
    sizes["utils.py"] = 256

    (root / "data").mkdir()
    for i in range(10):
        fname = f"data_{i:03d}.bin"
        data = b"D" * (i * 100 + 100)
        (root / "data" / fname).write_bytes(data)
        sizes[fname] = len(data)

    return sizes


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScanWorkflow:
    def test_full_scan_total_files(self, tmp_path: Path) -> None:
        sizes = _build_tree(tmp_path)
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        expected_files = len(sizes)
        assert result.total_files == expected_files, (
            f"expected {expected_files} files, got {result.total_files}"
        )

    def test_full_scan_total_bytes(self, tmp_path: Path) -> None:
        sizes = _build_tree(tmp_path)
        expected_bytes = sum(sizes.values())
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        assert result.total_bytes == expected_bytes, (
            f"expected {expected_bytes} bytes, got {result.total_bytes}"
        )

    def test_full_scan_error_count_zero(self, tmp_path: Path) -> None:
        _build_tree(tmp_path)
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        assert result.error_count == 0

    def test_aggregator_logical_size_matches_scan_result(self, tmp_path: Path) -> None:
        _build_tree(tmp_path)
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        # Scanner already maintains root.size_logical live; re-aggregating must agree
        aggregate(result.root)
        assert result.root.size_logical == result.total_bytes, (
            "aggregated root.size_logical must match scan result total_bytes"
        )

    def test_aggregator_file_count_matches_scan_result(self, tmp_path: Path) -> None:
        _build_tree(tmp_path)
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        aggregate(result.root)
        assert result.root.file_count == result.total_files

    def test_symlink_not_followed_by_default(self, tmp_path: Path) -> None:
        """A symlink to a directory must be skipped when follow_symlinks=False."""
        target = tmp_path / "real_dir"
        target.mkdir()
        (target / "file.txt").write_bytes(b"X" * 100)
        link = tmp_path / "link_dir"
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("Symlink creation requires elevated privileges on this system")

        result = Scanner().scan(
            tmp_path,
            ScanOptions(follow_symlinks=False, measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        # Only real_dir/file.txt should be counted; link_dir (reparse point) is skipped
        assert result.total_files == 1, (
            f"symlink dir must be skipped, expected 1 file but got {result.total_files}"
        )

    def test_scan_produces_tree_structure(self, tmp_path: Path) -> None:
        """root.children must be populated with sub-directory nodes."""
        _build_tree(tmp_path)
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        child_names = {c.name for c in result.root.children}
        assert "docs" in child_names
        assert "src" in child_names
        assert "data" in child_names

    def test_scan_node_parent_references_set(self, tmp_path: Path) -> None:
        """Each child dir node must have a non-None parent after scan."""
        _build_tree(tmp_path)
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        for child in result.root.children:
            assert child.parent is result.root, (
                f"child '{child.name}' parent should be root"
            )

    def test_progress_events_contain_valid_fields(self, tmp_path: Path) -> None:
        """Any emitted ProgressEvent must have non-negative numeric fields."""
        # Create 600 files to guarantee at least one progress event (interval=500)
        bulk = tmp_path / "bulk"
        bulk.mkdir()
        for i in range(600):
            (bulk / f"f{i:04d}.bin").write_bytes(b"x")

        events: list[ProgressEvent] = []
        Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=events.append,
        )
        assert len(events) >= 1, "600 files must trigger at least one progress event"
        for ev in events:
            assert isinstance(ev, ProgressEvent)
            assert ev.total_files >= 0
            assert ev.total_bytes >= 0
            assert ev.elapsed_sec >= 0.0
            assert isinstance(ev.current_path, Path)

    def test_scan_with_single_file(self, tmp_path: Path) -> None:
        (tmp_path / "single.txt").write_bytes(b"Z" * 777)
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        assert result.total_files == 1
        assert result.total_bytes == 777

    def test_scan_deeply_nested(self, tmp_path: Path) -> None:
        """Scanner must handle deep directory nesting without stack overflow."""
        current = tmp_path
        depth = 20
        for i in range(depth):
            current = current / f"level_{i:02d}"
            current.mkdir()
        (current / "leaf.bin").write_bytes(b"L" * 256)

        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        assert result.total_files == 1
        assert result.total_bytes == 256

    def test_scan_uses_synthetic_tree_fixture(self, synthetic_tree: Path) -> None:
        """Verify the shared synthetic_tree fixture produces expected totals."""
        # 10 folders × 10 files = 100 files
        result = Scanner().scan(
            synthetic_tree,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        assert result.total_files == 100
        assert result.error_count == 0
        # Verify bytes: sum of 1024 * k for k in 1..100
        expected = sum(1024 * (folder_idx * 10 + file_idx + 1) for folder_idx in range(10) for file_idx in range(10))
        assert result.total_bytes == expected
