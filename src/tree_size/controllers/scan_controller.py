"""Application-layer controller: owns the ScanWorker lifecycle."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

from tree_size.core.node import ScanOptions
from tree_size.workers.scan_worker import ScanWorker

logger = logging.getLogger(__name__)


class ScanController(QObject):
    progressUpdated = Signal(object)    # ProgressEvent
    nodeReady = Signal(object)          # Node
    scanFinished = Signal(object)       # ScanResult
    scanError = Signal(str, object)     # message str, Path

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker: ScanWorker | None = None
        self._running = False

    def start(self, root: Path, options: ScanOptions | None = None) -> None:
        if self._running:
            logger.warning("Scan already running; ignoring start()")
            return
        opts = options or ScanOptions()
        worker = ScanWorker(root, opts)
        worker.signals.nodeReady.connect(self.nodeReady)
        worker.signals.progress.connect(self.progressUpdated)
        worker.signals.finished.connect(self._on_finished)
        worker.signals.error.connect(self.scanError)
        self._worker = worker
        self._running = True
        QThreadPool.globalInstance().start(worker)
        logger.info("Scan started: %s", root)

    def pause(self) -> None:
        if self._worker:
            self._worker.pause()

    def resume(self) -> None:
        if self._worker:
            self._worker.resume()

    def cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
            self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @Slot(object)
    def _on_finished(self, result: object) -> None:
        self._running = False
        self._worker = None
        self.scanFinished.emit(result)
        logger.info("Scan finished")
