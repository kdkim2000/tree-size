"""Export controller: selects the right Exporter and calls it."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)


class ExportController(QObject):
    """Coordinate export operations between the UI and the exporter layer.

    Signals are emitted on the calling thread, so connect with
    Qt.ConnectionType.AutoConnection (default) when used from the UI thread.
    """

    # (human-readable message, destination Path)
    exportCompleted: Signal = Signal(str, object)
    # (error message, destination Path)
    exportFailed: Signal = Signal(str, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    @Slot(object, str, str)
    def export(self, root: object, dest_path: str, format_: str) -> None:
        """Run the export synchronously.

        Importees live here (not at module level) to avoid circular imports and
        to keep the exporters free of Qt dependencies.

        Args:
            root:      The root Node to export.
            dest_path: Destination file path as a plain string.
            format_:   One of ``"csv"``, ``"json"``, or ``"html"`` (case-insensitive).
        """
        from tree_size.core.node import Node  # local import — core is Qt-free (R-A1)

        if not isinstance(root, Node):
            logger.warning("ExportController.export called with non-Node root: %r", root)
            return

        dest = Path(dest_path)
        fmt = format_.lower()

        try:
            if fmt == "csv":
                from tree_size.exporters.csv_exporter import CsvExporter
                CsvExporter().export([root], dest)
            elif fmt == "json":
                from tree_size.exporters.json_exporter import JsonExporter
                JsonExporter().export(root, dest)
            elif fmt == "html":
                from tree_size.exporters.html_exporter import HtmlExporter
                HtmlExporter().export(root, dest)
            else:
                msg = f"Unknown export format: {format_!r}"
                logger.error(msg)
                self.exportFailed.emit(msg, dest)
                return

            self.exportCompleted.emit(f"Exported to {dest.name}", dest)

        except OSError as exc:
            logger.exception("Export I/O error")
            self.exportFailed.emit(str(exc), dest)
        except Exception as exc:  # noqa: BLE001 — surface any unexpected error to UI
            logger.exception("Export failed unexpectedly")
            self.exportFailed.emit(str(exc), dest)
