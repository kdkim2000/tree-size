"""UI tests for SearchBar and LazyTreeModel.set_filter integration."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from tree_size.core.filter import FilterSpec
from tree_size.core.node import Node
from tree_size.ui.search_bar import SearchBar
from tree_size.ui.tree_model import LazyTreeModel


# ── fixtures ──────────────────────────────────────────────────────────────────


def _make_node(
    name: str,
    is_dir: bool = False,
    size: int = 0,
    parent: Node | None = None,
    path: str | None = None,
) -> Node:
    n = Node(
        name=name,
        path=Path(path or f"C:/test/{name}"),
        is_dir=is_dir,
        size_logical=size,
        size_allocated=size,
        file_count=0 if is_dir else 1,
        folder_count=1 if is_dir else 0,
        mtime=time.time(),
        parent=parent,
    )
    if parent is not None:
        parent.children.append(n)
    return n


def _build_tree() -> Node:
    """
    root/
      images/
        photo.jpg       (500_000 bytes)
        screenshot.png  (200_000 bytes)
      videos/
        movie.mp4       (5_000_000 bytes)
      readme.txt        (1_000 bytes)
    """
    root = _make_node("root", is_dir=True, size=5_701_000)
    images = _make_node("images", is_dir=True, size=700_000, parent=root)
    _make_node("photo.jpg", size=500_000, parent=images)
    _make_node("screenshot.png", size=200_000, parent=images)
    videos = _make_node("videos", is_dir=True, size=5_000_000, parent=root)
    _make_node("movie.mp4", size=5_000_000, parent=videos)
    _make_node("readme.txt", size=1_000, parent=root)
    return root


# ── SearchBar tests ──────────────────────────────────────────────────────────


class TestSearchBar:
    @pytest.fixture
    def bar(self, qtbot: object) -> SearchBar:  # type: ignore[type-arg]
        widget = SearchBar()
        return widget

    def test_initial_filter_is_empty(self, bar: SearchBar) -> None:
        assert bar.filter_spec.is_empty()

    def test_name_pattern_reflected_in_spec(
        self, bar: SearchBar, qtbot: object  # type: ignore[type-arg]
    ) -> None:
        bar._name_input.setText("photo")
        assert bar.filter_spec.name_pattern == "photo"

    def test_regex_toggle_reflected_in_spec(
        self, bar: SearchBar, qtbot: object  # type: ignore[type-arg]
    ) -> None:
        bar._regex_check.setChecked(True)
        assert bar.filter_spec.use_regex is True

    def test_min_size_reflected_in_spec(
        self, bar: SearchBar, qtbot: object  # type: ignore[type-arg]
    ) -> None:
        bar._min_size.setValue(1)  # 1 MB
        assert bar.filter_spec.min_size == 1 * 1024 * 1024

    def test_ext_combo_all_returns_empty_list(self, bar: SearchBar) -> None:
        bar._ext_combo.setCurrentIndex(0)  # All
        assert bar.filter_spec.extensions == []

    def test_ext_combo_images_returns_ext_list(self, bar: SearchBar) -> None:
        bar._ext_combo.setCurrentIndex(1)  # Images
        exts = bar.filter_spec.extensions
        assert ".jpg" in exts
        assert ".png" in exts

    def test_filter_changed_signal_emitted(
        self, bar: SearchBar, qtbot: object  # type: ignore[type-arg]
    ) -> None:
        from pytestqt.plugin import QtBot  # type: ignore[import-untyped]

        bot = qtbot  # type: ignore[assignment]
        with bot.waitSignal(bar.filterChanged, timeout=500):  # type: ignore[attr-defined]
            bar._name_input.setText("test")

    def test_set_focus_on_name_input(
        self, bar: SearchBar, qtbot: object  # type: ignore[type-arg]
    ) -> None:
        # Just verify it does not raise; focus requires a visible window.
        bar.show()
        bar.set_focus_on_name_input()
        bar.hide()


# ── LazyTreeModel.set_filter tests ──────────────────────────────────────────


class TestLazyTreeModelFilter:
    @pytest.fixture
    def model(self, qtbot: object) -> LazyTreeModel:  # type: ignore[type-arg]
        return LazyTreeModel()

    def test_no_filter_shows_root_children(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        # root has 3 direct children: images/, videos/, readme.txt
        assert model.rowCount() == 3

    def test_empty_filter_spec_restores_unfiltered(
        self, model: LazyTreeModel
    ) -> None:
        root = _build_tree()
        model.set_root(root)
        model.set_filter(FilterSpec(name_pattern="photo"))
        model.set_filter(FilterSpec())  # empty
        assert model.rowCount() == 3

    def test_name_filter_reduces_rows(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        model.set_filter(FilterSpec(name_pattern="photo"))
        # Only photo.jpg should match (substring, case-insensitive)
        assert model.rowCount() == 1

    def test_name_filter_correct_node_name(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        model.set_filter(FilterSpec(name_pattern="photo"))
        idx = model.index(0, 0)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "photo.jpg"

    def test_extension_filter_images(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        model.set_filter(FilterSpec(extensions=[".jpg", ".jpeg", ".png"]))
        # photo.jpg + screenshot.png → 2 nodes
        assert model.rowCount() == 2

    def test_extension_filter_excludes_directories(
        self, model: LazyTreeModel
    ) -> None:
        root = _build_tree()
        model.set_root(root)
        model.set_filter(FilterSpec(extensions=[".jpg"]))
        for row in range(model.rowCount()):
            idx = model.index(row, 0)
            name = model.data(idx, Qt.ItemDataRole.DisplayRole)
            assert isinstance(name, str)
            assert name.endswith(".jpg")

    def test_min_size_filter(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        # Only movie.mp4 (5 MB) and the root/images dir (700 KB) exceed 400 KB.
        # min_size = 400_000 bytes
        model.set_filter(FilterSpec(min_size=400_000))
        rows = model.rowCount()
        assert rows >= 1  # at minimum movie.mp4

    def test_filtered_nodes_are_flat(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        model.set_filter(FilterSpec(name_pattern=".jpg"))
        # In filtered mode parent() always returns invalid index (flat list).
        idx = model.index(0, 0)
        assert idx.isValid()
        parent = model.parent(idx)
        assert not parent.isValid()

    def test_set_filter_none_restores_tree(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        model.set_filter(FilterSpec(name_pattern="photo"))
        model.set_filter(None)
        assert model.rowCount() == 3

    def test_regex_filter(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        # Regex: match names ending with .jpg or .png
        model.set_filter(FilterSpec(name_pattern=r"\.(jpg|png)$", use_regex=True))
        assert model.rowCount() == 2

    def test_invalid_regex_returns_zero_rows(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        # An unclosed bracket is an invalid regex.
        model.set_filter(FilterSpec(name_pattern="[invalid", use_regex=True))
        assert model.rowCount() == 0

    def test_set_root_clears_filter_state(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        model.set_filter(FilterSpec(name_pattern="photo"))
        # Setting a new root must clear filtered_nodes so we see the new tree.
        model.set_root(root)
        assert model._filtered_nodes is None

    def test_clear_clears_filter_state(self, model: LazyTreeModel) -> None:
        root = _build_tree()
        model.set_root(root)
        model.set_filter(FilterSpec(name_pattern="photo"))
        model.clear()
        assert model._filtered_nodes is None
        assert model.rowCount() == 0
