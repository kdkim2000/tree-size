"""Main application window."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QWidget

from tree_size.controllers.scan_controller import ScanController
from tree_size.core.node import ScanOptions
from tree_size.ui.status_bar import StatusBar
from tree_size.ui.toolbar import Toolbar
from tree_size.ui.tree_view import TreeView

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tree-Size")
        self.resize(1200, 750)
        self._controller = ScanController(parent=self)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        self._tree_view = TreeView(parent=self)
        self.setCentralWidget(self._tree_view)

        self._toolbar = Toolbar(parent=self)
        self.addToolBar(self._toolbar)

        self._status_bar = StatusBar(parent=self)
        self.setStatusBar(self._status_bar)
        self._status_bar.set_ready()

    def _connect_signals(self) -> None:
        self._toolbar.scanRequested.connect(self._on_scan_requested)
        self._controller.progressUpdated.connect(self._status_bar.on_progress)
        self._controller.nodeReady.connect(self._tree_view.tree_model.add_node)
        self._controller.scanFinished.connect(self._on_scan_finished)
        self._controller.scanError.connect(self._on_scan_error)

    @Slot(object)
    def _on_scan_requested(self, path: object) -> None:
        if not isinstance(path, Path):
            return
        self._tree_view.start_scan()
        self._controller.start(path, ScanOptions())

    @Slot(object)
    def _on_scan_finished(self, result: object) -> None:
        self._tree_view.stop_scan()
        self._status_bar.on_finished(result)

    @Slot(str, object)
    def _on_scan_error(self, message: str, path: object) -> None:
        logger.error("Scan error: %s — %s", path, message)
        self._status_bar.showMessage(f"Error: {message}")

    def closeEvent(self, event: QCloseEvent) -> None:
        self._controller.cancel()
        logger.info("MainWindow closing")
        super().closeEvent(event)
