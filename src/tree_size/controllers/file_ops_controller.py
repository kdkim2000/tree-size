"""Application-layer controller for file operations: delete, recycle, open in Explorer."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

import send2trash
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

# Paths whose subtrees must never be silently deleted (R-F2)
_PROTECTED_ROOTS: frozenset[Path] = frozenset(
    {
        Path("C:/Windows"),
        Path("C:/Program Files"),
        Path("C:/Program Files (x86)"),
    }
)


class FileOpsController(QObject):
    deletionCompleted = Signal(list)    # list[Path] — paths that were deleted
    operationFailed = Signal(str, object)  # human message, Path that failed

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    # ── public slots ────────────────────────────────────────────────────────

    @Slot(list)
    def delete_to_recycle(self, paths: list[Path]) -> None:
        """Move each path to the Windows Recycle Bin via send2trash."""
        deleted: list[Path] = []
        for path in paths:
            if self._is_protected(path):
                logger.warning("Protected path blocked from recycle: %s", path)
                self.operationFailed.emit(
                    f"Cannot delete protected path: {path.name}", path
                )
                continue
            try:
                send2trash.send2trash(str(path))
                logger.info("Recycled: %s", path)
                deleted.append(path)
            except Exception as exc:
                logger.exception("Recycle failed: %s", path)
                self.operationFailed.emit(str(exc), path)
        if deleted:
            self.deletionCompleted.emit(deleted)

    @Slot(list)
    def delete_permanently(self, paths: list[Path]) -> None:
        """Permanently remove each path from the filesystem."""
        deleted: list[Path] = []
        for path in paths:
            if self._is_protected(path):
                logger.warning("Protected path blocked from permanent delete: %s", path)
                self.operationFailed.emit(
                    f"Cannot delete protected path: {path.name}", path
                )
                continue
            try:
                if path.is_dir():
                    shutil.rmtree(str(path))
                else:
                    path.unlink()
                logger.info("Permanently deleted: %s", path)
                deleted.append(path)
            except OSError as exc:
                logger.exception("Permanent delete failed: %s", path)
                self.operationFailed.emit(str(exc), path)
        if deleted:
            self.deletionCompleted.emit(deleted)

    @Slot(object)
    def open_in_explorer(self, path: object) -> None:
        """Open Windows Explorer with the given path selected."""
        if not isinstance(path, Path):
            return
        try:
            # /select,<path> highlights the item in its parent folder
            subprocess.Popen(f'explorer /select,"{path}"')
        except OSError as exc:
            logger.exception("Open in Explorer failed: %s", path)
            self.operationFailed.emit(str(exc), path)

    @Slot(object)
    def copy_path_to_clipboard(self, path: object) -> None:
        """Copy the path string to the system clipboard."""
        if not isinstance(path, Path):
            return
        try:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(str(path))
                logger.debug("Copied to clipboard: %s", path)
        except Exception as exc:
            logger.exception("Copy path to clipboard failed: %s", path)
            self.operationFailed.emit(str(exc), path)

    # ── private helpers ─────────────────────────────────────────────────────

    def _is_protected(self, path: Path) -> bool:
        """Return True when *path* is inside a protected system root (R-F2)."""
        try:
            path_abs = path.resolve()
            for protected in _PROTECTED_ROOTS:
                if path_abs.is_relative_to(protected):
                    return True
        except (ValueError, OSError):
            pass
        return False
