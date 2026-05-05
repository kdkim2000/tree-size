"""Application toolbar — Open folder, Refresh, scan controls."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QFileDialog, QToolBar, QWidget

logger = logging.getLogger(__name__)


class Toolbar(QToolBar):
    scanRequested = Signal(object)   # Path

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Main Toolbar", parent)
        self._last_path: Path | None = None
        self._build_actions()

    def _build_actions(self) -> None:
        self._act_open = QAction("Open Folder", parent=self)
        self._act_open.setShortcut(QKeySequence("Ctrl+O"))
        self._act_open.setToolTip("Choose a folder to scan (Ctrl+O)")
        self._act_open.triggered.connect(self._on_open)
        self.addAction(self._act_open)

        self._act_refresh = QAction("Refresh", parent=self)
        self._act_refresh.setShortcut(QKeySequence("F5"))
        self._act_refresh.setToolTip("Re-scan current folder (F5)")
        self._act_refresh.triggered.connect(self._on_refresh)
        self.addAction(self._act_refresh)

    def _on_open(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self.parentWidget(), "Select Folder to Scan"
        )
        if folder:
            path = Path(folder)
            self._last_path = path
            self.scanRequested.emit(path)

    def _on_refresh(self) -> None:
        if self._last_path:
            self.scanRequested.emit(self._last_path)
