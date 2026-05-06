"""Application toolbar — Open, Refresh, Pause, Resume, Stop."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMessageBox, QToolBar, QWidget

logger = logging.getLogger(__name__)


class Toolbar(QToolBar):
    scanRequested = Signal(object)   # Path
    pauseRequested = Signal()
    resumeRequested = Signal()
    stopRequested = Signal()
    exportRequested = Signal()       # triggered by Export button / Ctrl+E

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Main Toolbar", parent)
        self.setMovable(False)
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

        self.addSeparator()

        self._act_pause = QAction("Pause", parent=self)
        self._act_pause.setToolTip("Pause the running scan")
        self._act_pause.triggered.connect(self._on_pause)
        self._act_pause.setEnabled(False)
        self.addAction(self._act_pause)

        self._act_resume = QAction("Resume", parent=self)
        self._act_resume.setToolTip("Resume a paused scan")
        self._act_resume.triggered.connect(self._on_resume)
        self._act_resume.setEnabled(False)
        self.addAction(self._act_resume)

        self._act_stop = QAction("Stop", parent=self)
        self._act_stop.setToolTip("Cancel the running scan")
        self._act_stop.triggered.connect(self._on_stop)
        self._act_stop.setEnabled(False)
        self.addAction(self._act_stop)

        self.addSeparator()

        self._act_export = QAction("Export", parent=self)
        self._act_export.setShortcut(QKeySequence("Ctrl+E"))
        self._act_export.setToolTip("Export results (Ctrl+E)")
        self._act_export.triggered.connect(self._on_export)
        # Enabled only after a scan has produced results (see enable_export).
        self._act_export.setEnabled(False)
        self.addAction(self._act_export)

    # ── public helpers ──────────────────────────────────────────────────────

    def enable_scan_controls(self, enabled: bool) -> None:
        """Called when a scan starts (enabled=True) or stops (enabled=False)."""
        self._act_pause.setEnabled(enabled)
        self._act_resume.setEnabled(False)
        self._act_stop.setEnabled(enabled)
        # Export becomes available once a scan completes (enabled=False means done).
        if not enabled:
            self._act_export.setEnabled(True)

    def enable_export(self, enabled: bool) -> None:
        """Explicitly toggle the Export action (e.g. after model cleared)."""
        self._act_export.setEnabled(enabled)

    def enable_resume(self, paused: bool) -> None:
        """Called when the scan is paused (paused=True) or resumed (paused=False)."""
        self._act_pause.setEnabled(not paused)
        self._act_resume.setEnabled(paused)

    # ── slots ───────────────────────────────────────────────────────────────

    @Slot()
    def _on_open(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self.parentWidget(), "Select Folder to Scan"
        )
        if folder:
            path = Path(folder)
            self._last_path = path
            self.scanRequested.emit(path)

    @Slot()
    def _on_refresh(self) -> None:
        if self._last_path:
            self.scanRequested.emit(self._last_path)

    @Slot()
    def _on_pause(self) -> None:
        logger.info("Pause requested")
        self.pauseRequested.emit()
        self.enable_resume(True)

    @Slot()
    def _on_resume(self) -> None:
        logger.info("Resume requested")
        self.resumeRequested.emit()
        self.enable_resume(False)

    @Slot()
    def _on_export(self) -> None:
        logger.info("Export requested")
        self.exportRequested.emit()

    @Slot()
    def _on_stop(self) -> None:
        logger.info("Stop requested")
        answer = QMessageBox.question(
            self.parentWidget(),
            "Stop Scan",
            "Stop the current scan?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.stopRequested.emit()
            self.enable_scan_controls(False)
