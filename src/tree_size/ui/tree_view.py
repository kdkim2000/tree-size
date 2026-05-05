"""TreeView widget wrapping QTreeView with column config and batch update support."""
from __future__ import annotations

import logging

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTreeView, QWidget

from tree_size.ui.tree_model import LazyTreeModel

logger = logging.getLogger(__name__)

_BATCH_INTERVAL_MS = 100  # flush pending nodes every 100ms


class TreeView(QTreeView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = LazyTreeModel(parent=self)
        self.setModel(self._model)
        self._setup_columns()
        self._setup_timer()

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

    def start_scan(self) -> None:
        self._model.clear()
        self._flush_timer.start()

    def stop_scan(self) -> None:
        self._flush_timer.stop()
        self._model.flush_pending()

    @property
    def tree_model(self) -> LazyTreeModel:
        return self._model
