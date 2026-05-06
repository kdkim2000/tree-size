"""LazyTreeModel — QAbstractItemModel backed by Node tree."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, cast

import qtawesome as qta
from PySide6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    Slot,
)
from PySide6.QtGui import QIcon

from tree_size.core.filter import FilterEngine, FilterSpec
from tree_size.core.formatter import fmt_count, fmt_size
from tree_size.core.node import Node

logger = logging.getLogger(__name__)

# Icon cache keyed by (icon_name, color_hex).  Built lazily so that qtawesome
# is only imported when a QApplication is already running.
_icon_cache: dict[tuple[str, str], QIcon] = {}

_ICON_FOLDER = "fa.folder"
_ICON_FILE = "fa.file-o"
_ICON_COLOR_LIGHT = "#5a7a9a"   # muted blue-grey for folder on light bg
_ICON_COLOR_DARK = "#8ab0d0"    # lighter shade for dark bg
_ICON_FILE_COLOR_LIGHT = "#777777"
_ICON_FILE_COLOR_DARK = "#aaaaaa"

# Module-level theme flag so the model can pick the right icon palette.
_current_theme: str = "light"


def set_icon_theme(theme: str) -> None:
    """Called by MainWindow when the active theme changes."""
    global _current_theme
    _current_theme = theme
    _icon_cache.clear()   # force regeneration with new colours


def _get_icon(name: str, color: str) -> QIcon:
    key = (name, color)
    if key not in _icon_cache:
        _icon_cache[key] = qta.icon(name, color=color)
    return _icon_cache[key]


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
        self._filter_spec: FilterSpec | None = None
        # Flat list of nodes that passed the current filter; None = unfiltered.
        self._filtered_nodes: list[Node] | None = None

    # ── public API ──────────────────────────────────────────────────────────

    def set_root(self, root: Node) -> None:
        self.beginResetModel()
        self._root = root
        self._pending.clear()
        self._filtered_nodes = None
        self.endResetModel()

    def clear(self) -> None:
        self.beginResetModel()
        self._root = None
        self._pending.clear()
        self._filtered_nodes = None
        self.endResetModel()

    def set_filter(self, spec: FilterSpec | None) -> None:
        """Apply *spec* to the current tree and refresh the view.

        When *spec* is None or empty the unfiltered tree is restored.
        The filter runs synchronously on the UI thread; for trees up to a
        few hundred-thousand nodes this is comfortably under 100 ms.
        """
        self._filter_spec = spec
        if spec is not None and not spec.is_empty() and self._root is not None:
            engine = FilterEngine()
            all_nodes = self._collect_all_nodes(self._root)
            self._filtered_nodes = engine.apply(all_nodes, spec)
            logger.debug(
                "Filter applied: %d/%d nodes match",
                len(self._filtered_nodes),
                len(all_nodes),
            )
        else:
            self._filtered_nodes = None

        self.beginResetModel()
        self.endResetModel()

    @property
    def root_node(self) -> Node | None:
        """Return the current root Node, or None when the model is empty."""
        return self._root

    @Slot(object)
    def add_node(self, node: Node) -> None:
        """Accumulate nodes emitted by the scanner; the QTimer flushes them."""
        # Attach the first node as root if we don't have one yet
        if self._root is None:
            self._root = node
        self._pending.append(node)

    def flush_pending(self) -> None:
        """Batch-refresh the view after accumulating scanner nodes.

        A full model reset is cheap enough at M2A; incremental row
        insertion will be introduced in a later milestone when stable
        node-ordering is established.
        """
        if not self._pending or self._root is None:
            return
        self._pending.clear()
        self.beginResetModel()
        self.endResetModel()

    def remove_node(self, node: Node) -> None:
        """Remove *node* from the tree after a successful file deletion.

        Emits the standard beginRemoveRows / endRemoveRows pair so that
        connected views update without a full model reset.
        """
        parent_node = node.parent
        if parent_node is None:
            # Removing the root — just clear everything
            self.clear()
            return
        try:
            row = parent_node.children.index(node)
        except ValueError:
            logger.warning("remove_node: node not found in parent.children: %s", node.path)
            return

        parent_index = self._index_for_node(parent_node)
        self.beginRemoveRows(parent_index, row, row)
        parent_node.children.pop(row)
        self.endRemoveRows()

    # ── QAbstractItemModel overrides ─────────────────────────────────────────

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        p = cast(QModelIndex, parent)
        # Filtered mode: flat list — only the invisible root has children.
        if self._filtered_nodes is not None:
            if p.isValid():
                return 0
            return len(self._filtered_nodes)
        node = self._node_from_index(p)
        if node is None:
            return 0
        return len(node.children)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        return len(_HEADERS)

    def index(
        self,
        row: int,
        column: int,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),  # noqa: B008
    ) -> QModelIndex:
        idx = cast(QModelIndex, parent)
        if not self.hasIndex(row, column, idx):
            return QModelIndex()
        # Filtered mode: flat list — all nodes are at row depth 0.
        if self._filtered_nodes is not None:
            if idx.isValid():
                return QModelIndex()
            if row >= len(self._filtered_nodes):
                return QModelIndex()
            return self.createIndex(row, column, self._filtered_nodes[row])
        parent_node = self._node_from_index(idx)
        if parent_node is None or row >= len(parent_node.children):
            return QModelIndex()
        return self.createIndex(row, column, parent_node.children[row])

    def parent(self, index: QModelIndex) -> QModelIndex:  # type: ignore[override]
        if not index.isValid():
            return QModelIndex()
        # In filtered mode every node is a top-level item.
        if self._filtered_nodes is not None:
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
        idx = cast(QModelIndex, index)
        if not idx.isValid():
            return None
        node = cast(Node, idx.internalPointer())
        col = idx.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(node, col)
        if role == Qt.ItemDataRole.UserRole:
            return self._sort_key(node, col)
        if role == Qt.ItemDataRole.DecorationRole and col == _COL_NAME:
            return self._node_icon(node)
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(_HEADERS)
        ):
            return _HEADERS[section]
        return None

    # ── private helpers ──────────────────────────────────────────────────────

    def _node_from_index(self, index: QModelIndex) -> Node | None:
        if not index.isValid():
            return self._root
        return cast(Node, index.internalPointer())

    @staticmethod
    def _collect_all_nodes(root: Node) -> list[Node]:
        """Depth-first traversal; returns every node in the tree including root."""
        result: list[Node] = [root]
        stack = list(root.children)
        while stack:
            node = stack.pop()
            result.append(node)
            stack.extend(node.children)
        return result

    def _index_for_node(self, node: Node) -> QModelIndex:
        """Return the QModelIndex that corresponds to *node*.

        Returns an invalid (root-level) index when *node* is the root or
        has no parent, because the root is not represented as a visible row.
        """
        if node is self._root or node.parent is None:
            return QModelIndex()
        parent = node.parent
        try:
            row = parent.children.index(node)
        except ValueError:
            return QModelIndex()
        return self.createIndex(row, 0, node)

    @staticmethod
    def _node_icon(node: Node) -> QIcon:
        is_dark = _current_theme == "dark"
        if node.is_dir:
            color = _ICON_COLOR_DARK if is_dark else _ICON_COLOR_LIGHT
            return _get_icon(_ICON_FOLDER, color)
        color = _ICON_FILE_COLOR_DARK if is_dark else _ICON_FILE_COLOR_LIGHT
        return _get_icon(_ICON_FILE, color)

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
