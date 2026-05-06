"""Status bar: scan progress, ETA, file count, and completion summary."""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QLabel, QProgressBar, QStatusBar, QWidget

from tree_size.core.formatter import fmt_count, fmt_size
from tree_size.workers.progress import ProgressTracker, format_eta

logger = logging.getLogger(__name__)


class StatusBar(QStatusBar):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._progress_tracker: ProgressTracker | None = None

        # Left: path, file count, total size
        self._left_label = QLabel("Ready", parent=self)
        self.addWidget(self._left_label, 1)

        # Centre: indeterminate progress bar while scanning
        self._progress_bar = QProgressBar(parent=self)
        self._progress_bar.setMinimum(0)
        # Maximum=0 renders as indeterminate (busy indicator)
        self._progress_bar.setMaximum(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setMaximumWidth(300)
        self.addPermanentWidget(self._progress_bar)

        # Right: ETA + throughput
        self._right_label = QLabel("", parent=self)
        self._right_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.addPermanentWidget(self._right_label)

        self.set_ready()

    # ── public API ─────────────────────────────────────────────────────────

    def set_ready(self) -> None:
        self._left_label.setText("Ready")
        self._right_label.setText("")
        self._progress_bar.setMaximum(0)
        self._progress_tracker = None

    @Slot(object)
    def on_progress(self, event: Any) -> None:
        """Receive ProgressEvent from ScanController and refresh UI."""
        from tree_size.core.node import ProgressEvent

        if not isinstance(event, ProgressEvent):
            return

        if self._progress_tracker is None:
            self._progress_tracker = ProgressTracker()

        stats = self._progress_tracker.update(
            event.elapsed_sec,
            event.total_files,
            event.total_bytes,
        )

        self._left_label.setText(
            f"Files: {fmt_count(event.total_files)} | "
            f"Total: {fmt_size(event.total_bytes)} | "
            f"Path: {event.current_path.name}"
        )

        eta_str = format_eta(stats.estimated_remaining_sec)
        speed_str = f"{stats.files_per_sec:.0f} files/s"
        self._right_label.setText(f"ETA: {eta_str} | {speed_str}")

    @Slot(object)
    def on_finished(self, result: Any) -> None:
        """Display final statistics once the scan completes."""
        from tree_size.core.node import ScanResult

        if not isinstance(result, ScanResult):
            return

        self._left_label.setText(
            f"Done: {fmt_count(result.total_files)} files, "
            f"{fmt_size(result.total_bytes)} in {result.elapsed_sec:.1f}s"
        )
        self._right_label.setText("")
        # Switch to determinate mode and show 100 %
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(100)
        self._progress_tracker = None
