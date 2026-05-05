"""Unit tests for Scanner using tmp_path real filesystem (no mocking)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tree_size.core.node import CancelToken, Node, ScanOptions
from tree_size.core.scanner import Scanner


# ---------------------------------------------------------------------------
# Helper: build a small known tree
# ---------------------------------------------------------------------------

def _make_tree(root: Path) -> None:
    """Create a predictable synthetic directory tree.

    Layout:
        root/
          a/
            file1.txt  (100 B)
            file2.txt  (200 B)
          b/
            nested/
              deep.txt (50 B)
          root.txt     (10 B)

    Total: 4 files, 360 bytes logical.
    Directories that on_node should receive: root, a, b, b/nested — 4 dir nodes.
    """
    (root / "a").mkdir()
    (root / "a" / "file1.txt").write_bytes(b"x" * 100)
    (root / "a" / "file2.txt").write_bytes(b"y" * 200)
    (root / "b").mkdir()
    (root / "b" / "nested").mkdir()
    (root / "b" / "nested" / "deep.txt").write_bytes(b"z" * 50)
    (root / "root.txt").write_bytes(b"r" * 10)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScannerBasic:
    def test_basic_scan_file_count(self, tmp_path: Path) -> None:
        _make_tree(tmp_path)
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        assert result.total_files == 4, f"expected 4 files, got {result.total_files}"

    def test_basic_scan_total_bytes(self, tmp_path: Path) -> None:
        _make_tree(tmp_path)
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        assert result.total_bytes == 360, f"expected 360 bytes, got {result.total_bytes}"

    def test_basic_scan_error_count_zero(self, tmp_path: Path) -> None:
        _make_tree(tmp_path)
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        assert result.error_count == 0

    def test_basic_scan_elapsed_nonnegative(self, tmp_path: Path) -> None:
        _make_tree(tmp_path)
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        assert result.elapsed_sec >= 0.0

    def test_result_root_is_node(self, tmp_path: Path) -> None:
        _make_tree(tmp_path)
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        assert isinstance(result.root, Node)
        assert result.root.is_dir

    def test_result_root_path_matches_scanned_path(self, tmp_path: Path) -> None:
        _make_tree(tmp_path)
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        assert result.root.path == tmp_path


class TestScannerEmptyDirectory:
    def test_empty_dir_zero_files(self, tmp_path: Path) -> None:
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        assert result.total_files == 0

    def test_empty_dir_zero_bytes(self, tmp_path: Path) -> None:
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        assert result.total_bytes == 0


class TestScannerOnNodeCallback:
    def test_on_node_receives_dir_nodes(self, tmp_path: Path) -> None:
        _make_tree(tmp_path)
        dir_nodes: list[Node] = []

        def _on_node(node: Node) -> None:
            if node.is_dir:
                dir_nodes.append(node)

        Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=_on_node,
            on_progress=lambda _: None,
        )
        # root, a, b, b/nested — 4 dir nodes
        dir_names = {n.name for n in dir_nodes}
        assert len(dir_nodes) == 4, f"expected 4 dir nodes, got {len(dir_nodes)}: {dir_names}"

    def test_on_node_root_is_last(self, tmp_path: Path) -> None:
        """Scanner uses post-order DFS: root node is delivered last."""
        _make_tree(tmp_path)
        received: list[Node] = []

        Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=received.append,
            on_progress=lambda _: None,
        )
        assert received[-1].path == tmp_path, "root node must be the last on_node call"


class TestScannerCancellation:
    def test_cancel_before_scan_returns_immediately(self, tmp_path: Path) -> None:
        _make_tree(tmp_path)
        token = CancelToken()
        token.cancel()
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            token,
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        # Must return without error; partial or zero results are both acceptable
        assert result.error_count == 0

    def test_cancel_result_total_bytes_nonnegative(self, tmp_path: Path) -> None:
        _make_tree(tmp_path)
        token = CancelToken()
        token.cancel()
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            token,
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        assert result.total_bytes >= 0


class TestScannerProgressCallback:
    def test_progress_callback_callable(self, tmp_path: Path) -> None:
        """on_progress must be callable and must not raise."""
        _make_tree(tmp_path)
        events: list[object] = []
        Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=events.append,
        )
        # With only 4 files, progress interval (500) may not fire — just verify no crash
        assert isinstance(events, list)


class TestScannerAccessibleFile:
    def test_accessible_file_counted(self, tmp_path: Path) -> None:
        (tmp_path / "accessible.txt").write_bytes(b"x" * 10)
        result = Scanner().scan(
            tmp_path,
            ScanOptions(measure_alloc_size=False),
            CancelToken(),
            on_node=lambda _: None,
            on_progress=lambda _: None,
        )
        assert result.error_count == 0
        assert result.total_files == 1
        assert result.total_bytes == 10
