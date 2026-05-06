"""Application toolbar — Open, Refresh, Pause, Resume, Stop, Settings."""
from __future__ import annotations

import logging
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMessageBox, QToolBar, QWidget

logger = logging.getLogger(__name__)

# Icon color tokens — updated by apply_theme() when the palette changes.
_COLOR_NORMAL = "#444444"
_COLOR_DARK = "#dddddd"


def _icon(name: str, color: str) -> "qta.icon":  # type: ignore[name-defined]
    return qta.icon(name, color=color)


class Toolbar(QToolBar):
    scanRequested = Signal(object)    # Path
    pauseRequested = Signal()
    resumeRequested = Signal()
    stopRequested = Signal()
    exportRequested = Signal()        # triggered by Export button / Ctrl+E
    settingsRequested = Signal()      # triggered by Settings button

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Main Toolbar", parent)
        self.setMovable(False)
        self._last_path: Path | None = None
        self._icon_color: str = _COLOR_NORMAL
        self._build_actions()

    # ── theme support ────────────────────────────────────────────────────────

    def apply_theme(self, theme: str) -> None:
        """Update icon colours when the active theme changes."""
        self._icon_color = _COLOR_DARK if theme == "dark" else _COLOR_NORMAL
        self._refresh_icons()

    def _refresh_icons(self) -> None:
        c = self._icon_color
        self._act_open.setIcon(_icon("fa.folder-open", c))
        self._act_refresh.setIcon(_icon("fa5s.sync-alt", c))
        self._act_pause.setIcon(_icon("fa.pause", c))
        self._act_resume.setIcon(_icon("fa.play", c))
        self._act_stop.setIcon(_icon("fa.stop", c))
        self._act_export.setIcon(_icon("fa.download", c))
        self._act_settings.setIcon(_icon("fa.cog", c))

    # ── construction ─────────────────────────────────────────────────────────

    def _build_actions(self) -> None:
        c = self._icon_color

        self._act_open = QAction(_icon("fa.folder-open", c), "Open Folder", parent=self)
        self._act_open.setShortcut(QKeySequence("Ctrl+O"))
        self._act_open.setToolTip("Choose a folder to scan (Ctrl+O)")
        self._act_open.triggered.connect(self._on_open)
        self.addAction(self._act_open)

        self._act_refresh = QAction(_icon("fa5s.sync-alt", c), "Refresh", parent=self)
        self._act_refresh.setShortcut(QKeySequence("F5"))
        self._act_refresh.setToolTip("Re-scan current folder (F5)")
        self._act_refresh.triggered.connect(self._on_refresh)
        self.addAction(self._act_refresh)

        self.addSeparator()

        self._act_pause = QAction(_icon("fa.pause", c), "Pause", parent=self)
        self._act_pause.setToolTip("Pause the running scan")
        self._act_pause.triggered.connect(self._on_pause)
        self._act_pause.setEnabled(False)
        self.addAction(self._act_pause)

        self._act_resume = QAction(_icon("fa.play", c), "Resume", parent=self)
        self._act_resume.setToolTip("Resume a paused scan")
        self._act_resume.triggered.connect(self._on_resume)
        self._act_resume.setEnabled(False)
        self.addAction(self._act_resume)

        self._act_stop = QAction(_icon("fa.stop", c), "Stop", parent=self)
        self._act_stop.setToolTip("Cancel the running scan")
        self._act_stop.triggered.connect(self._on_stop)
        self._act_stop.setEnabled(False)
        self.addAction(self._act_stop)

        self.addSeparator()

        self._act_export = QAction(_icon("fa.download", c), "Export", parent=self)
        self._act_export.setShortcut(QKeySequence("Ctrl+E"))
        self._act_export.setToolTip("Export results (Ctrl+E)")
        self._act_export.triggered.connect(self._on_export)
        self._act_export.setEnabled(False)
        self.addAction(self._act_export)

        self.addSeparator()

        self._act_settings = QAction(_icon("fa.cog", c), "Settings", parent=self)
        self._act_settings.setShortcut(QKeySequence("Ctrl+,"))
        self._act_settings.setToolTip("Open settings (Ctrl+,)")
        self._act_settings.triggered.connect(self._on_settings)
        self.addAction(self._act_settings)

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

    @Slot()
    def _on_settings(self) -> None:
        logger.info("Settings requested")
        self.settingsRequested.emit()
