"""Unit tests for the bottom-up aggregator (core/aggregator.py)."""
from __future__ import annotations

from pathlib import Path

from tree_size.core.aggregator import aggregate
from tree_size.core.node import Node


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _file(name: str, size: int, parent: Node | None = None) -> Node:
    n = Node(
        name=name,
        path=Path(f"/root/{name}"),
        is_dir=False,
        size_logical=size,
        size_allocated=size,
        file_count=1,
        folder_count=0,
        mtime=0.0,
        parent=parent,
    )
    if parent is not None:
        parent.children.append(n)
    return n


def _dir(name: str, parent: Node | None = None) -> Node:
    n = Node(
        name=name,
        path=Path(f"/root/{name}"),
        is_dir=True,
        size_logical=0,
        size_allocated=0,
        file_count=0,
        folder_count=0,
        mtime=0.0,
        parent=parent,
    )
    if parent is not None:
        parent.children.append(n)
    return n


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAggregate:
    def test_flat_directory_sums_sizes(self) -> None:
        root = _dir("root")
        _file("a.txt", 100, root)
        _file("b.txt", 200, root)
        aggregate(root)
        assert root.size_logical == 300, "root must sum children logical sizes"

    def test_flat_directory_counts_files(self) -> None:
        root = _dir("root")
        _file("a.txt", 100, root)
        _file("b.txt", 200, root)
        aggregate(root)
        assert root.file_count == 2

    def test_flat_directory_folder_count_zero(self) -> None:
        root = _dir("root")
        _file("a.txt", 100, root)
        aggregate(root)
        assert root.folder_count == 0

    def test_nested_directories_size_propagates(self) -> None:
        root = _dir("root")
        sub = _dir("sub", root)
        _file("a.txt", 1000, sub)
        _file("b.txt", 500, root)
        aggregate(root)
        assert sub.size_logical == 1000
        assert root.size_logical == 1500, "root must include sub-directory sizes"

    def test_nested_directories_file_count(self) -> None:
        root = _dir("root")
        sub = _dir("sub", root)
        _file("a.txt", 1000, sub)
        _file("b.txt", 500, root)
        aggregate(root)
        assert sub.file_count == 1
        assert root.file_count == 2

    def test_nested_directories_folder_count(self) -> None:
        root = _dir("root")
        sub = _dir("sub", root)
        _file("a.txt", 500, sub)
        aggregate(root)
        assert root.folder_count == 1, "root must count sub as a folder"

    def test_empty_directory_zeros(self) -> None:
        root = _dir("root")
        aggregate(root)
        assert root.size_logical == 0
        assert root.file_count == 0
        assert root.folder_count == 0

    def test_idempotent_single_call(self) -> None:
        root = _dir("root")
        _file("x.txt", 999, root)
        aggregate(root)
        assert root.size_logical == 999
        assert root.file_count == 1

    def test_idempotent_double_call(self) -> None:
        root = _dir("root")
        _file("x.txt", 999, root)
        aggregate(root)
        aggregate(root)
        assert root.size_logical == 999
        assert root.file_count == 1

    def test_deep_nesting_three_levels(self) -> None:
        root = _dir("root")
        level1 = _dir("l1", root)
        level2 = _dir("l2", level1)
        _file("deep.bin", 8192, level2)
        aggregate(root)
        assert level2.size_logical == 8192
        assert level1.size_logical == 8192
        assert root.size_logical == 8192
        assert root.file_count == 1
        # root has l1 as child dir; l1 has l2 — root.folder_count should be 2
        assert root.folder_count == 2
        assert level1.folder_count == 1

    def test_multiple_subdirs(self) -> None:
        root = _dir("root")
        sub_a = _dir("a", root)
        sub_b = _dir("b", root)
        _file("f1.txt", 100, sub_a)
        _file("f2.txt", 200, sub_b)
        _file("f3.txt", 50, sub_b)
        aggregate(root)
        assert sub_a.size_logical == 100
        assert sub_b.size_logical == 250
        assert root.size_logical == 350
        assert root.file_count == 3
        assert root.folder_count == 2

    def test_file_node_not_reset_by_aggregate(self) -> None:
        """aggregate only touches dir nodes — file nodes keep their original values."""
        root = _dir("root")
        f = _file("x.bin", 512, root)
        aggregate(root)
        assert f.size_logical == 512
        assert f.file_count == 1

    def test_allocated_size_also_aggregated(self) -> None:
        root = _dir("root")
        _file("a.bin", 100, root)
        _file("b.bin", 200, root)
        aggregate(root)
        assert root.size_allocated == 300
