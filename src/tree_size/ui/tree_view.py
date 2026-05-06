"""TreeView widget: QTreeView + context menu + batch-flush support."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTreeView,
    QWidget,
)

from tree_size.core.node import Node
from tree_size.ui.tree_model import LazyTreeModel

logger = logging.getLogger(__name__)

_BATCH_INTERVAL_MS = 100  # flush pending nodes every 100 ms


class TreeView(QTreeView):
    # Emitted when the user triggers a file-system operation from the context menu.
    # Each signal carries the list of Path objects that are currently selected.
    deleteRequested = Signal(list)    # list[Path]
    openRequested = Signal(object)    # Path (single item — Explorer highlights it)
    copyPathRequested = Signal(object)  # Path

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = LazyTreeModel(parent=self)
        self.setModel(self._model)
        self._setup_columns()
        self._setup_timer()

    # ── setup ───────────────────────────────────────────────────────────────

    def _setup_columns(self) -> None:
        header = self.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 7):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setUniformRowHeights(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def _setup_timer(self) -> None:
        self._flush_timer = QTimer(parent=self)
        self._flush_timer.setInterval(_BATCH_INTERVAL_MS)
        self._flush_timer.timeout.connect(self._model.flush_pending)

    # ── public API ──────────────────────────────────────────────────────────

    def start_scan(self) -> None:
        self._model.clear()
        self._flush_timer.start()

    def stop_scan(self) -> None:
        self._flush_timer.stop()
        self._model.flush_pending()

    @property
    def tree_model(self) -> LazyTreeModel:
        return self._model

    # ── context menu ─────────────────────────────────────────────────────────

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        index = self.indexAt(event.pos())
        if not index.isValid():
            return

        # Collect all selected paths; fall back to the right-clicked row.
        selected_paths = self._selected_paths()
        if not selected_paths:
            node = cast(Node, index.internalPointer())
            selected_paths = [node.path]

        # Single-item for "Open in Explorer" is always the clicked row
        clicked_node = cast(Node, index.internalPointer())

        menu = QMenu(self)
        act_open = menu.addAction("Open in Explorer")
        act_copy = menu.addAction("Copy Path")
        menu.addSeparator()
        act_delete = menu.addAction(f"Delete ({len(selected_paths)} item(s))")

        action = menu.exec(self.mapToGlobal(event.pos()))

        if action is act_open:
            self.openRequested.emit(clicked_node.path)
        elif action is act_copy:
            self.copyPathRequested.emit(clicked_node.path)
        elif action is act_delete:
            self.deleteRequested.emit(selected_paths)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _selected_paths(self) -> list[Path]:
        """Return Path objects for every currently selected row."""
        paths: list[Path] = []
        for index in self.selectedIndexes():
            if index.column() != 0:
                continue
            node = cast(Node, index.internalPointer())
            paths.append(node.path)
        return paths
