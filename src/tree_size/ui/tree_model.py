"""LazyTreeModel — QAbstractItemModel backed by Node tree."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, cast

from PySide6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    Slot,
)

from tree_size.core.formatter import fmt_count, fmt_size
from tree_size.core.node import Node

logger = logging.getLogger(__name__)

_HEADERS = ["Name", "Size", "Allocated", "Files", "Folders", "% of Parent", "Last Modified"]
_COL_NAME = 0
_COL_SIZE = 1
_COL_ALLOC = 2
_COL_FILES = 3
_COL_FOLDERS = 4
_COL_PCT = 5
_COL_MTIME = 6


class LazyTreeModel(QAbstractItemModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._root: Node | None = None
        self._pending: list[Node] = []

    # ── public API ──────────────────────────────────────────────────────────

    def set_root(self, root: Node) -> None:
        self.beginResetModel()
        self._root = root
        self._pending.clear()
        self.endResetModel()

    def clear(self) -> None:
        self.beginResetModel()
        self._root = None
        self._pending.clear()
        self.endResetModel()

    @Slot(object)
    def add_node(self, node: Node) -> None:
        """Batch-accumulate nodes emitted by scanner; flush on timer."""
        self._pending.append(node)

    def flush_pending(self) -> None:
        """Call from a QTimer to batch-insert accumulated nodes."""
        if not self._pending or self._root is None:
            return
        # For simplicity at M1-B, reset the model after each flush.
        # M2-A will refine to incremental insertions.
        self._pending.clear()
        self.beginResetModel()
        self.endResetModel()

    # ── QAbstractItemModel overrides ─────────────────────────────────────────

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        node = self._node_from_index(QModelIndex(parent) if isinstance(parent, QPersistentModelIndex) else parent)
        if node is None:
            return 0
        return len(node.children)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return len(_HEADERS)

    def index(
        self,
        row: int,
        column: int,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> QModelIndex:
        idx = QModelIndex(parent) if isinstance(parent, QPersistentModelIndex) else parent
        if not self.hasIndex(row, column, idx):
            return QModelIndex()
        parent_node = self._node_from_index(idx)
        if parent_node is None or row >= len(parent_node.children):
            return QModelIndex()
        return self.createIndex(row, column, parent_node.children[row])

    def parent(self, index: QModelIndex) -> QModelIndex:  # type: ignore[override]
        if not index.isValid():
            return QModelIndex()
        node = cast(Node, index.internalPointer())
        p = node.parent
        if p is None or p is self._root:
            return QModelIndex()
        gp = p.parent
        if gp is None:
            return QModelIndex()
        try:
            row = gp.children.index(p)
        except ValueError:
            return QModelIndex()
        return self.createIndex(row, 0, p)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        idx = QModelIndex(index) if isinstance(index, QPersistentModelIndex) else index
        if not idx.isValid():
            return None
        node = cast(Node, idx.internalPointer())
        col = idx.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(node, col)
        if role == Qt.ItemDataRole.UserRole:
            return self._sort_key(node, col)
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(_HEADERS):
                return _HEADERS[section]
        return None

    # ── private helpers ──────────────────────────────────────────────────────

    def _node_from_index(self, index: QModelIndex) -> Node | None:
        if not index.isValid():
            return self._root
        return cast(Node, index.internalPointer())

    def _display(self, node: Node, col: int) -> str:
        if col == _COL_NAME:
            return node.name
        if col == _COL_SIZE:
            return fmt_size(node.size_logical)
        if col == _COL_ALLOC:
            return fmt_size(node.size_allocated)
        if col == _COL_FILES:
            return fmt_count(node.file_count)
        if col == _COL_FOLDERS:
            return fmt_count(node.folder_count)
        if col == _COL_PCT:
            p = node.parent
            if p and p.size_logical > 0:
                return f"{node.size_logical / p.size_logical * 100:.1f}%"
            return "—"
        if col == _COL_MTIME:
            if node.mtime:
                return datetime.fromtimestamp(node.mtime).strftime("%Y-%m-%d %H:%M")
            return "—"
        return ""

    def _sort_key(self, node: Node, col: int) -> int | float | str:
        if col in (_COL_SIZE, _COL_ALLOC):
            return node.size_logical
        if col == _COL_FILES:
            return node.file_count
        if col == _COL_FOLDERS:
            return node.folder_count
        if col == _COL_PCT:
            p = node.parent
            if p and p.size_logical > 0:
                return node.size_logical / p.size_logical
            return 0.0
        if col == _COL_MTIME:
            return node.mtime
        return node.name
