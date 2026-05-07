"""UI tests for LazyTreeModel."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from PySide6.QtCore import QModelIndex, Qt

from tree_size.core.node import Node
from tree_size.ui.tree_model import LazyTreeModel


def _make_node(
    name: str,
    is_dir: bool = False,
    size: int = 0,
    parent: Node | None = None,
) -> Node:
    n = Node(
        name=name,
        path=Path(f"/test/{name}"),
        is_dir=is_dir,
        size_logical=size,
        size_allocated=size,
        file_count=0 if is_dir else 1,
        folder_count=0,
        mtime=time.time(),
        parent=parent,
    )
    if parent is not None:
        parent.children.append(n)
    return n


def _build_tree() -> Node:
    """Build: root/ -> [dir_a/ -> [file1.txt, file2.txt], file_root.txt]"""
    root = _make_node("root", is_dir=True, size=1500)
    dir_a = _make_node("dir_a", is_dir=True, size=1000, parent=root)
    _make_node("file1.txt", size=600, parent=dir_a)
    _make_node("file2.txt", size=400, parent=dir_a)
    _make_node("file_root.txt", size=500, parent=root)
    dir_a.file_count = 2
    root.file_count = 3
    root.folder_count = 1
    return root


class TestLazyTreeModel:
    @pytest.fixture
    def model(self, qtbot: object) -> LazyTreeModel:  # type: ignore[type-arg]
        m = LazyTreeModel()
        return m

    def test_empty_model_row_count(self, model: LazyTreeModel) -> None:
        assert model.rowCount() == 0

    def test_column_count(self, model: LazyTreeModel) -> None:
        assert model.columnCount() == 7

    def test_set_root_row_count(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        # root has 2 children: dir_a and file_root.txt
        assert model.rowCount() == 2

    def test_clear_resets(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        model.clear()
        assert model.rowCount() == 0

    def test_index_valid(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        idx = model.index(0, 0)
        assert idx.isValid()

    def test_index_out_of_range(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        idx = model.index(99, 0)
        assert not idx.isValid()

    def test_data_display_name(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        idx = model.index(0, 0)
        name = model.data(idx, Qt.ItemDataRole.DisplayRole)
        # First child is whatever order children list has
        assert isinstance(name, str), "Name column must return a str"
        assert len(name) > 0, "Name must be non-empty"

    def test_data_display_size(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        idx = model.index(0, 1)  # Size column
        size_str = model.data(idx, Qt.ItemDataRole.DisplayRole)
        assert isinstance(size_str, str), "Size column must return a str"
        # Must contain a known unit suffix
        assert any(u in size_str for u in ["B", "KB", "MB", "GB"]), (
            f"Size string '{size_str}' does not contain a unit"
        )

    def test_header_data(self, model: LazyTreeModel) -> None:
        headers = [
            model.headerData(i, Qt.Orientation.Horizontal)
            for i in range(7)
        ]
        assert headers[0] == "Name", f"Column 0 header should be 'Name', got {headers[0]!r}"
        assert headers[1] == "Size", f"Column 1 header should be 'Size', got {headers[1]!r}"
        assert headers[6] == "Last Modified", (
            f"Column 6 header should be 'Last Modified', got {headers[6]!r}"
        )

    def test_parent_of_root_child_is_invalid(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        child_idx = model.index(0, 0)
        parent_idx = model.parent(child_idx)
        assert not parent_idx.isValid(), (
            "Parent of a top-level node must be an invalid QModelIndex"
        )

    def test_nested_row_count(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        # Find dir_a index (first child that is a directory)
        dir_a_idx = QModelIndex()
        for row in range(model.rowCount()):
            idx = model.index(row, 0)
            node: Node = idx.internalPointer()  # type: ignore[assignment]
            if node.is_dir:
                dir_a_idx = idx
                break
        assert dir_a_idx.isValid(), "Expected to find at least one directory child"
        assert model.rowCount(dir_a_idx) == 2, (
            "dir_a should have exactly 2 children (file1.txt + file2.txt)"
        )

    def test_add_node_and_flush(self, model: LazyTreeModel) -> None:
        root = _make_node("root", is_dir=True)
        model.set_root(root)
        child = _make_node("new.txt", size=100, parent=root)
        model.add_node(child)
        model.flush_pending()
        # After flush, model resets — row count reflects root's children
        assert model.rowCount() == 1, (
            "After flush_pending(), root should have 1 child visible"
        )

    def test_pct_of_parent_display(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        idx = model.index(0, 5)  # % of Parent column
        pct = model.data(idx, Qt.ItemDataRole.DisplayRole)
        assert isinstance(pct, str), "% of Parent column must return a str"

    def test_invalid_index_returns_none(self, model: LazyTreeModel) -> None:
        assert model.data(QModelIndex()) is None, (
            "data() for QModelIndex() must return None"
        )


class TestLazyTreeModelPostOrder:
    """Tests that verify correct behavior when nodes arrive in DFS post-order.

    The scanner emits nodes children-first; the true root (parent=None) arrives
    last.  These tests exercise the bug-fix that changed the add_node() guard
    from ``if self._root is None`` to ``if node.parent is None``.
    """

    @pytest.fixture
    def model(self, qtbot: object) -> LazyTreeModel:  # type: ignore[type-arg]
        return LazyTreeModel()

    @pytest.fixture
    def post_order_nodes(self) -> tuple[Node, Node, Node]:
        """Build a 3-node tree and return nodes in DFS post-order emission order.

        Tree layout:
            root/        (parent=None)
            └── dir_a/   (parent=root)
                └── file_b.txt (parent=dir_a)

        Post-order emission: file_b → dir_a → root
        """
        root = Node(
            name="root",
            path=Path("C:/test/root"),
            is_dir=True,
            size_logical=2048,
            size_allocated=4096,
            file_count=1,
            folder_count=1,
            mtime=0.0,
            parent=None,
        )
        dir_a = Node(
            name="dir_a",
            path=Path("C:/test/root/dir_a"),
            is_dir=True,
            size_logical=1024,
            size_allocated=2048,
            file_count=1,
            folder_count=0,
            mtime=0.0,
            parent=root,
        )
        file_b = Node(
            name="file_b.txt",
            path=Path("C:/test/root/dir_a/file_b.txt"),
            is_dir=False,
            size_logical=512,
            size_allocated=512,
            file_count=1,
            folder_count=0,
            mtime=0.0,
            parent=dir_a,
        )
        dir_a.children.append(file_b)
        root.children.append(dir_a)
        # Return in scanner emission order: deepest leaf first, root last.
        return file_b, dir_a, root

    def test_post_order_root_detection_sets_correct_root(
        self, model: LazyTreeModel, post_order_nodes: tuple[Node, Node, Node]
    ) -> None:
        """add_node() + flush_pending() must identify the node with parent=None
        as the root, even though it arrives last in the emission sequence."""
        file_b, dir_a, root_node = post_order_nodes

        # Emit in scanner post-order: children before parent.
        model.add_node(file_b)
        model.add_node(dir_a)
        model.add_node(root_node)
        model.flush_pending()

        assert model.root_node is root_node, (
            "root_node must be the node whose parent is None, not the first node received"
        )

    def test_post_order_root_row_count(
        self, model: LazyTreeModel, post_order_nodes: tuple[Node, Node, Node]
    ) -> None:
        """After post-order add_node() + flush_pending(), rowCount at the
        invisible root level must equal the number of root's direct children (1)."""
        file_b, dir_a, root_node = post_order_nodes

        model.add_node(file_b)
        model.add_node(dir_a)
        model.add_node(root_node)
        model.flush_pending()

        assert model.rowCount(QModelIndex()) == 1, (
            "Root should have exactly 1 visible child (dir_a); "
            f"got {model.rowCount(QModelIndex())}"
        )

    def test_post_order_full_tree_display(
        self, model: LazyTreeModel, post_order_nodes: tuple[Node, Node, Node]
    ) -> None:
        """The full two-level tree must be navigable after post-order emission.

        - Level 0 (children of root): 1 row — dir_a
        - Level 1 (children of dir_a): 1 row — file_b.txt
        """
        file_b, dir_a, root_node = post_order_nodes

        model.add_node(file_b)
        model.add_node(dir_a)
        model.add_node(root_node)
        model.flush_pending()

        root_row_count = model.rowCount(QModelIndex())
        assert root_row_count == 1, (
            f"Expected 1 child of root (dir_a), got {root_row_count}"
        )

        dir_a_index = model.index(0, 0, QModelIndex())
        assert dir_a_index.isValid(), "Index for dir_a must be valid"

        dir_a_node: Node = dir_a_index.internalPointer()  # type: ignore[assignment]
        assert dir_a_node.name == "dir_a", (
            f"Expected first child to be 'dir_a', got '{dir_a_node.name}'"
        )

        dir_a_row_count = model.rowCount(dir_a_index)
        assert dir_a_row_count == 1, (
            f"Expected 1 child of dir_a (file_b.txt), got {dir_a_row_count}"
        )

        file_b_index = model.index(0, 0, dir_a_index)
        assert file_b_index.isValid(), "Index for file_b.txt must be valid"

        file_b_node: Node = file_b_index.internalPointer()  # type: ignore[assignment]
        assert file_b_node.name == "file_b.txt", (
            f"Expected leaf node to be 'file_b.txt', got '{file_b_node.name}'"
        )
