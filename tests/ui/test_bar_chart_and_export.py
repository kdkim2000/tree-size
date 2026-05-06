"""pytest-qt tests for BarChartPanel and ExportController (M3-1, M3-6)."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from tree_size.core.node import Node
from tree_size.ui.bar_chart import BarChartPanel


# ── helpers ───────────────────────────────────────────────────────────────────

def _node(
    name: str,
    size: int = 0,
    is_dir: bool = False,
    parent: Node | None = None,
) -> Node:
    n = Node(
        name=name,
        path=Path(f"C:/test/{name}"),
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
    """root (dir) with 12 children of varying sizes."""
    root = _node("root", size=10_000_000, is_dir=True)
    for i in range(12):
        _node(f"child_{i:02d}", size=(12 - i) * 500_000, is_dir=(i % 3 == 0), parent=root)
    return root


# ── BarChartPanel ─────────────────────────────────────────────────────────────

class TestBarChartPanel:
    @pytest.fixture
    def panel(self, qtbot: object) -> BarChartPanel:  # type: ignore[type-arg]
        w = BarChartPanel()
        return w

    def test_initial_title(self, panel: BarChartPanel) -> None:
        assert "Select" in panel._title.text()

    def test_set_node_none(self, panel: BarChartPanel) -> None:
        panel.set_node(None)
        assert panel._title.text() == "No selection"

    def test_set_node_no_children(self, panel: BarChartPanel) -> None:
        leaf = _node("leaf.txt", size=1024)
        panel.set_node(leaf)
        assert "no children" in panel._title.text().lower()

    def test_set_node_shows_top_10(self, panel: BarChartPanel) -> None:
        root = _build_tree()  # 12 children
        panel.set_node(root)
        # Title should mention "Top 10"
        assert "10" in panel._title.text()

    def test_set_node_updates_title_with_name(self, panel: BarChartPanel) -> None:
        root = _build_tree()
        panel.set_node(root)
        assert "root" in panel._title.text()

    def test_set_node_replaces_previous(self, panel: BarChartPanel) -> None:
        root = _build_tree()
        panel.set_node(root)
        panel.set_node(None)
        assert panel._title.text() == "No selection"

    def test_current_node_stored(self, panel: BarChartPanel) -> None:
        root = _build_tree()
        panel.set_node(root)
        assert panel._current_node is root


# ── ExportController ──────────────────────────────────────────────────────────

class TestExportController:
    @pytest.fixture
    def ctrl(self, qtbot: object) -> object:  # type: ignore[type-arg]
        from tree_size.controllers.export_controller import ExportController
        c = ExportController()
        return c

    def test_export_csv(
        self, ctrl: object, tmp_path: Path, qtbot: object  # type: ignore[type-arg]
    ) -> None:
        from tree_size.controllers.export_controller import ExportController
        assert isinstance(ctrl, ExportController)

        root = _build_tree()
        dest = tmp_path / "out.csv"

        completed: list[tuple[str, object]] = []
        ctrl.exportCompleted.connect(lambda msg, p: completed.append((msg, p)))

        ctrl.export(root, str(dest), "csv")

        assert dest.exists(), "CSV file should be created"
        assert len(completed) == 1, "exportCompleted should fire once"
        assert dest.stat().st_size > 0

    def test_export_json(
        self, ctrl: object, tmp_path: Path, qtbot: object  # type: ignore[type-arg]
    ) -> None:
        from tree_size.controllers.export_controller import ExportController
        assert isinstance(ctrl, ExportController)

        root = _build_tree()
        dest = tmp_path / "out.json"

        completed: list[tuple[str, object]] = []
        ctrl.exportCompleted.connect(lambda msg, p: completed.append((msg, p)))

        ctrl.export(root, str(dest), "json")

        assert dest.exists()
        assert len(completed) == 1

    def test_export_html(
        self, ctrl: object, tmp_path: Path, qtbot: object  # type: ignore[type-arg]
    ) -> None:
        from tree_size.controllers.export_controller import ExportController
        assert isinstance(ctrl, ExportController)

        root = _build_tree()
        dest = tmp_path / "out.html"

        completed: list[tuple[str, object]] = []
        ctrl.exportCompleted.connect(lambda msg, p: completed.append((msg, p)))

        ctrl.export(root, str(dest), "html")

        assert dest.exists()
        content = dest.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_export_unknown_format_emits_failed(
        self, ctrl: object, tmp_path: Path, qtbot: object  # type: ignore[type-arg]
    ) -> None:
        from tree_size.controllers.export_controller import ExportController
        assert isinstance(ctrl, ExportController)

        root = _build_tree()
        dest = tmp_path / "out.xyz"

        failed: list[tuple[str, object]] = []
        ctrl.exportFailed.connect(lambda msg, p: failed.append((msg, p)))

        ctrl.export(root, str(dest), "xyz")

        assert len(failed) == 1, "exportFailed should fire for unknown format"

    def test_export_non_node_root_is_silently_ignored(
        self, ctrl: object, tmp_path: Path
    ) -> None:
        from tree_size.controllers.export_controller import ExportController
        assert isinstance(ctrl, ExportController)

        completed: list[object] = []
        failed: list[object] = []
        ctrl.exportCompleted.connect(lambda *_: completed.append(True))
        ctrl.exportFailed.connect(lambda *_: failed.append(True))

        # Pass something that is not a Node
        ctrl.export("not a node", str(tmp_path / "x.csv"), "csv")

        assert not completed
        assert not failed  # silently ignored, not an error
