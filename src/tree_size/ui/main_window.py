"""Main application window."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QModelIndex, Qt, Slot
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import QMainWindow, QMessageBox, QSplitter, QWidget

from tree_size.controllers.export_controller import ExportController
from tree_size.controllers.file_ops_controller import FileOpsController
from tree_size.controllers.scan_controller import ScanController
from tree_size.controllers.settings_service import SettingsService
from tree_size.core.filter import FilterSpec
from tree_size.core.node import ScanOptions
from tree_size.ui.bar_chart import BarChartPanel
from tree_size.ui.dialogs.confirm_delete import ConfirmDeleteDialog
from tree_size.ui.dialogs.export import ExportDialog
from tree_size.ui.dialogs.settings import SettingsDialog
from tree_size.ui.search_bar import SearchBar
from tree_size.ui.status_bar import StatusBar
from tree_size.ui.themes import theme_manager
from tree_size.ui.toolbar import Toolbar
from tree_size.ui.tree_model import set_icon_theme
from tree_size.ui.tree_view import TreeView

if TYPE_CHECKING:
    from tree_size.core.node import Node

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tree-Size")
        self.resize(1200, 750)
        self._settings = SettingsService(parent=self)
        self._controller = ScanController(parent=self)
        self._file_ops = FileOpsController(parent=self)
        self._export_ctrl = ExportController(parent=self)
        self._setup_ui()
        self._connect_signals()
        # Apply the persisted theme on startup.
        self._apply_theme(self._settings.resolve_theme())

    def _setup_ui(self) -> None:
        # Main toolbar
        self._toolbar = Toolbar(parent=self)
        self.addToolBar(self._toolbar)

        # Search toolbar (separate row, non-movable)
        self._search_bar = SearchBar(parent=self)
        self._search_toolbar = self.addToolBar("Search")
        self._search_toolbar.setMovable(False)
        self._search_toolbar.addWidget(self._search_bar)

        # Central: TreeView (75%) | BarChartPanel (25%)
        splitter = QSplitter(Qt.Orientation.Horizontal, parent=self)
        self._tree_view = TreeView(parent=splitter)
        self._bar_chart = BarChartPanel(parent=splitter)
        splitter.addWidget(self._tree_view)
        splitter.addWidget(self._bar_chart)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        self._status_bar = StatusBar(parent=self)
        self.setStatusBar(self._status_bar)
        self._status_bar.set_ready()

        # Ctrl+F — focus the name input in the search bar.
        search_action = QAction("Search", self)
        search_action.setShortcut("Ctrl+F")
        search_action.triggered.connect(self._search_bar.set_focus_on_name_input)
        self.addAction(search_action)

    def _connect_signals(self) -> None:
        # SearchBar → TreeModel
        self._search_bar.filterChanged.connect(self._on_filter_changed)

        # Toolbar → ScanController / Settings
        self._toolbar.scanRequested.connect(self._on_scan_requested)
        self._toolbar.pauseRequested.connect(self._controller.pause)
        self._toolbar.resumeRequested.connect(self._controller.resume)
        self._toolbar.stopRequested.connect(self._controller.cancel)
        self._toolbar.exportRequested.connect(self._on_export_requested)
        self._toolbar.settingsRequested.connect(self._on_settings_requested)

        # ScanController → StatusBar / TreeView
        self._controller.progressUpdated.connect(
            self._status_bar.on_progress,
            Qt.ConnectionType.QueuedConnection,
        )
        self._controller.nodeReady.connect(
            self._tree_view.tree_model.add_node,
            Qt.ConnectionType.QueuedConnection,
        )
        self._controller.scanFinished.connect(self._on_scan_finished)
        self._controller.scanError.connect(self._on_scan_error)

        # TreeView selection → BarChart
        self._tree_view.selectionModel().currentChanged.connect(
            self._on_tree_selection_changed
        )

        # TreeView context menu → FileOpsController
        self._tree_view.deleteRequested.connect(self._on_delete_requested)
        self._tree_view.openRequested.connect(self._file_ops.open_in_explorer)
        self._tree_view.copyPathRequested.connect(self._file_ops.copy_path_to_clipboard)

        # FileOpsController → TreeModel / StatusBar
        self._file_ops.deletionCompleted.connect(self._on_deletion_completed)
        self._file_ops.operationFailed.connect(self._on_operation_failed)

        # ExportController → StatusBar
        self._export_ctrl.exportCompleted.connect(self._on_export_completed)
        self._export_ctrl.exportFailed.connect(self._on_export_failed)

        # SettingsService → theme propagation (system theme change at OS level)
        self._settings.themeChanged.connect(self._apply_theme)

    # ── scan slots ───────────────────────────────────────────────────────────

    @Slot(object)
    def _on_scan_requested(self, path: object) -> None:
        if not isinstance(path, Path):
            return
        self._tree_view.start_scan()
        self._bar_chart.set_node(None)
        self._toolbar.enable_scan_controls(True)
        self._controller.start(path, ScanOptions())

    @Slot(object)
    def _on_scan_finished(self, result: object) -> None:
        self._tree_view.stop_scan()
        self._toolbar.enable_scan_controls(False)
        self._status_bar.on_finished(result)

    @Slot(str, object)
    def _on_scan_error(self, message: str, path: object) -> None:
        logger.error("Scan error: %s — %s", path, message)
        self._status_bar.showMessage(f"Error: {message}")

    # ── selection slot ───────────────────────────────────────────────────────

    @Slot(QModelIndex, QModelIndex)
    def _on_tree_selection_changed(
        self, current: QModelIndex, previous: QModelIndex
    ) -> None:
        """Refresh the BarChart when the tree selection changes."""
        if not current.isValid():
            self._bar_chart.set_node(None)
            return
        node = self._tree_view.tree_model._node_from_index(current)
        self._bar_chart.set_node(node)

    # ── settings slot ────────────────────────────────────────────────────────

    @Slot()
    def _on_settings_requested(self) -> None:
        """Open the SettingsDialog; apply theme immediately if changed."""
        dialog = SettingsDialog(self._settings, parent=self)
        dialog.themeChanged.connect(self._apply_theme)
        dialog.exec()

    # ── theme application ────────────────────────────────────────────────────

    @Slot(str)
    def _apply_theme(self, theme: str) -> None:
        """Apply *theme* ("light" or "dark") to QSS, icons, and chart colours."""
        theme_manager.apply_theme(theme)
        set_icon_theme(theme)
        self._toolbar.apply_theme(theme)
        self._bar_chart.apply_theme(theme)
        logger.info("Theme applied: %s", theme)

    # ── export slots ─────────────────────────────────────────────────────────

    @Slot()
    def _on_export_requested(self) -> None:
        """Open the export dialog and dispatch to ExportController."""
        root = self._tree_view.tree_model.root_node
        if root is None:
            QMessageBox.information(
                self, "Export", "Nothing to export — run a scan first."
            )
            return

        dialog = ExportDialog(parent=self)
        if dialog.exec() != ExportDialog.DialogCode.Accepted:
            return

        dest = dialog.dest_path
        if not dest:
            return

        self._export_ctrl.export(root, dest, dialog.format)

    @Slot(str, object)
    def _on_export_completed(self, message: str, path: object) -> None:
        self._status_bar.showMessage(message, 5000)
        logger.info("Export completed: %s", path)

    @Slot(str, object)
    def _on_export_failed(self, message: str, path: object) -> None:
        logger.error("Export failed (%s): %s", path, message)
        QMessageBox.critical(self, "Export Failed", message)

    # ── file-ops slots ───────────────────────────────────────────────────────

    @Slot(list)
    def _on_delete_requested(self, paths: list[Path]) -> None:
        """Show confirm dialog and dispatch to FileOpsController."""
        if not paths:
            return
        dialog = ConfirmDeleteDialog(paths, parent=self)
        result = dialog.exec()
        if result == 0:  # cancelled
            return
        if dialog.is_permanent:
            self._file_ops.delete_permanently(paths)
        else:
            self._file_ops.delete_to_recycle(paths)

    @Slot(list)
    def _on_deletion_completed(self, paths: list[Path]) -> None:
        """Remove deleted nodes from the tree model."""
        model = self._tree_view.tree_model
        root = model.root_node
        if root is None:
            return
        path_set = set(paths)
        for node in _collect_nodes(root):
            if node.path in path_set:
                model.remove_node(node)
        self._status_bar.showMessage(
            f"Deleted {len(paths)} item(s)", 5000
        )

    @Slot(str, object)
    def _on_operation_failed(self, message: str, path: object) -> None:
        logger.error("File operation failed: %s — %s", path, message)
        self._status_bar.showMessage(f"Error: {message}", 8000)

    # ── filter slot ──────────────────────────────────────────────────────────

    @Slot(object)
    def _on_filter_changed(self, spec: object) -> None:
        """Propagate SearchBar changes to the tree model."""
        if not isinstance(spec, FilterSpec):
            return
        self._tree_view.tree_model.set_filter(spec)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._controller.cancel()
        self._settings.sync()
        logger.info("MainWindow closing")
        super().closeEvent(event)


# ── helpers ───────────────────────────────────────────────────────────────────

def _collect_nodes(root: object) -> list[Node]:
    """Depth-first traversal that returns all Node objects in the tree."""
    from tree_size.core.node import Node as NodeType
    if not isinstance(root, NodeType):
        return []
    result: list[NodeType] = [root]
    stack = list(root.children)
    while stack:
        node = stack.pop()
        result.append(node)
        stack.extend(node.children)
    return result
