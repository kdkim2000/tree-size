"""QRunnable scan worker — runs Scanner in a thread pool."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QRunnable, Slot

from tree_size.core.node import CancelToken, ScanOptions
from tree_size.core.scanner import Scanner
from tree_size.workers.signals import WorkerSignals

logger = logging.getLogger(__name__)


class ScanWorker(QRunnable):
    def __init__(self, root: Path, options: ScanOptions) -> None:
        super().__init__()
        self.root = root
        self.options = options
        self.signals = WorkerSignals()
        self._cancel_token = CancelToken()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        scanner = Scanner()
        try:
            result = scanner.scan(
                self.root,
                self.options,
                self._cancel_token,
                on_node=self.signals.nodeReady.emit,
                on_progress=self.signals.progress.emit,
            )
            if not self._cancel_token.is_cancelled():
                self.signals.finished.emit(result)
        except Exception as exc:
            logger.exception("Scan failed for %s", self.root)
            self.signals.error.emit(str(exc), self.root)

    def pause(self) -> None:
        self._cancel_token.pause()

    def resume(self) -> None:
        self._cancel_token.resume()

    def cancel(self) -> None:
        self._cancel_token.cancel()
