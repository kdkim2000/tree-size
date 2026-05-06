"""Export format and destination dialog."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Maps display label to file extension used for the save dialog filter.
_FORMAT_EXT: dict[str, str] = {
    "CSV": "csv",
    "JSON": "json",
    "HTML": "html",
}

_SAVE_FILTERS = {
    "CSV":  "CSV files (*.csv);;All files (*.*)",
    "JSON": "JSON files (*.json);;All files (*.*)",
    "HTML": "HTML files (*.html);;All files (*.*)",
}


class ExportDialog(QDialog):
    """Let the user pick an export format and a destination path."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export")
        self.setModal(True)
        self.setMinimumWidth(420)
        self._build_ui()

    # ── public properties ────────────────────────────────────────────────────

    @property
    def format(self) -> str:
        """Lower-case format key: ``"csv"``, ``"json"``, or ``"html"``."""
        return _FORMAT_EXT[self._format_combo.currentText()]

    @property
    def dest_path(self) -> str:
        """Raw text from the path input field."""
        return self._path_input.text().strip()

    # ── internal helpers ─────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Format selector
        layout.addWidget(QLabel("Format:", parent=self))
        self._format_combo = QComboBox(parent=self)
        self._format_combo.addItems(list(_FORMAT_EXT.keys()))
        layout.addWidget(self._format_combo)

        # Destination path
        layout.addWidget(QLabel("Destination:", parent=self))
        path_row = QHBoxLayout()
        self._path_input = QLineEdit(parent=self)
        self._path_input.setPlaceholderText("C:\\export.csv")
        path_row.addWidget(self._path_input)

        self._browse_btn = QPushButton("Browse…", parent=self)
        self._browse_btn.clicked.connect(self._on_browse)
        path_row.addWidget(self._browse_btn)
        layout.addLayout(path_row)

        # Dialog buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._export_btn = QPushButton("Export", parent=self)
        self._export_btn.setDefault(True)
        self._export_btn.clicked.connect(self._on_accept)
        btn_row.addWidget(self._export_btn)

        cancel_btn = QPushButton("Cancel", parent=self)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    @Slot()
    def _on_browse(self) -> None:
        """Open a save-file dialog filtered to the selected format."""
        fmt_label = self._format_combo.currentText()
        file_filter = _SAVE_FILTERS.get(fmt_label, "All files (*.*)")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save export as", "", file_filter
        )
        if path:
            # Ensure the extension matches the chosen format when the user
            # omits it (common on Windows).
            p = Path(path)
            ext = _FORMAT_EXT[fmt_label]
            if p.suffix.lower() != f".{ext}":
                path = str(p.with_suffix(f".{ext}"))
            self._path_input.setText(path)
            logger.debug("Export destination set to: %s", path)

    @Slot()
    def _on_accept(self) -> None:
        """Validate input before accepting."""
        if not self.dest_path:
            # Re-trigger the browse dialog rather than silently accepting.
            self._on_browse()
            return
        self.accept()
