"""Worker ↔ UI signal definitions."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class WorkerSignals(QObject):
    nodeReady = Signal(object)       # Node
    progress = Signal(object)        # ProgressEvent
    finished = Signal(object)        # ScanResult
    error = Signal(str, object)      # message str, path Path
