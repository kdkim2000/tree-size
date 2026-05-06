"""QRunnable scan worker — runs Scanner in a thread pool."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from PySide6.QtCore import QRunnable, Slot

from tree_size.core.node import CancelToken, Node, ScanOptions
from tree_size.core.scanner import Scanner
from tree_size.workers.signals import WorkerSignals

logger = logging.getLogger(__name__)


class ScanWorker(QRunnable):
    def __init__(
        self,
        root: Path,
        options: ScanOptions,
        cache_db: object | None = None,
    ) -> None:
        super().__init__()
        self.root = root
        self.options = options
        self.signals = WorkerSignals()
        self._cancel_token = CancelToken()
        self._cache_db = cache_db  # CacheDb | None (type kept as object to avoid circular import)
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        scanner = Scanner()
        scan_id: int | None = None

        # --- M4-4: open a scan session in the cache before traversal ---
        if self._cache_db is not None:
            try:
                options_json = json.dumps(
                    {
                        "follow_symlinks": self.options.follow_symlinks,
                        "measure_alloc_size": self.options.measure_alloc_size,
                        "max_workers": self.options.max_workers,
                    }
                )
                scan_id = self._cache_db.begin_scan(self.root, options_json)  # type: ignore[attr-defined]
                logger.debug("Cache scan session started: scan_id=%d", scan_id)
            except Exception:
                logger.exception("begin_scan failed — continuing without cache")
                scan_id = None

        # --- Build the on_node callback that also writes to cache ---
        def _on_node(node: Node) -> None:
            # Always emit to UI first so the tree updates immediately.
            self.signals.nodeReady.emit(node)

            if scan_id is not None and self._cache_db is not None:
                try:
                    # parent_id resolution: we rely on ON CONFLICT REPLACE in
                    # the DB; pass None — cache_db.insert_nodes handles bulk.
                    self._cache_db.insert_nodes(scan_id, [node])  # type: ignore[attr-defined]
                except Exception:
                    logger.exception("insert_nodes failed for %s", node.path)

        try:
            result = scanner.scan(
                self.root,
                self.options,
                self._cancel_token,
                on_node=_on_node,
                on_progress=self.signals.progress.emit,
            )

            # --- M4-4: mark scan complete ---
            is_complete = (
                scan_id is not None
                and self._cache_db is not None
                and not self._cancel_token.is_cancelled()
            )
            if is_complete:
                try:
                    self._cache_db.finish_scan(scan_id, result.total_files, result.total_bytes)  # type: ignore[union-attr]
                    self.signals.cacheWritten.emit(scan_id)
                    logger.debug(
                        "Cache scan finished: scan_id=%d files=%d bytes=%d",
                        scan_id,
                        result.total_files,
                        result.total_bytes,
                    )
                except Exception:
                    logger.exception("finish_scan failed for scan_id=%d", scan_id)

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
