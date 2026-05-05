"""Status bar showing scan progress and results."""
from __future__ import annotations

import logging

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QLabel, QStatusBar, QWidget

from tree_size.core.formatter import fmt_count, fmt_size

logger = logging.getLogger(__name__)


class StatusBar(QStatusBar):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lbl_files = QLabel("Files: —", parent=self)
        self._lbl_size = QLabel("Size: —", parent=self)
        self._lbl_path = QLabel("", parent=self)
        self.addPermanentWidget(self._lbl_path, stretch=1)
        self.addPermanentWidget(self._lbl_files)
        self.addPermanentWidget(self._lbl_size)

    @Slot(object)
    def on_progress(self, event: object) -> None:
        from tree_size.core.node import ProgressEvent

        if isinstance(event, ProgressEvent):
            self._lbl_files.setText(f"Files: {fmt_count(event.total_files)}")
            self._lbl_size.setText(f"Size: {fmt_size(event.total_bytes)}")
            self._lbl_path.setText(str(event.current_path))

    @Slot(object)
    def on_finished(self, result: object) -> None:
        from tree_size.core.node import ScanResult

        if isinstance(result, ScanResult):
            self._lbl_files.setText(f"Files: {fmt_count(result.total_files)}")
            self._lbl_size.setText(f"Size: {fmt_size(result.total_bytes)}")
            elapsed = f"{result.elapsed_sec:.1f}s"
            self.showMessage(f"Scan complete in {elapsed} — {result.error_count} errors")

    def set_ready(self) -> None:
        self._lbl_files.setText("Files: —")
        self._lbl_size.setText("Size: —")
        self._lbl_path.setText("")
        self.showMessage("Ready")
