"""Confirm-delete dialog: lets the user choose recycle or permanent deletion."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# done() codes used by callers
_RECYCLE = 1   # QDialog.Accepted
_PERMANENT = 2
_CANCEL = 0    # QDialog.Rejected


class ConfirmDeleteDialog(QDialog):
    """Two-option delete confirmation dialog.

    After exec() returns, check :attr:`is_permanent` to decide which
    deletion mode the user selected.  A return code of 0 (Rejected) means
    the user cancelled.

    Result codes
    ------------
    1 (Accepted)  — Move to Recycle Bin
    2             — Delete Permanently
    0 (Rejected)  — Cancel
    """

    def __init__(
        self,
        paths: list[Path],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Delete Files")
        self.setModal(True)
        self._result_code: int = _CANCEL

        if len(paths) > 1:
            description = f"Delete {len(paths)} selected items?"
        else:
            description = f"Delete '{paths[0].name}'?"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(description, parent=self))

        btn_recycle = QPushButton("Move to Recycle Bin", parent=self)
        btn_permanent = QPushButton("Delete Permanently", parent=self)
        btn_cancel = QPushButton("Cancel", parent=self)

        btn_recycle.clicked.connect(self._on_recycle)
        btn_permanent.clicked.connect(self._on_permanent)
        btn_cancel.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_recycle)
        btn_row.addWidget(btn_permanent)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    # ── slots ───────────────────────────────────────────────────────────────

    def _on_recycle(self) -> None:
        self._result_code = _RECYCLE
        super().done(_RECYCLE)

    def _on_permanent(self) -> None:
        self._result_code = _PERMANENT
        super().done(_PERMANENT)

    # ── public API ──────────────────────────────────────────────────────────

    @property
    def is_permanent(self) -> bool:
        """True when the user selected 'Delete Permanently'."""
        return self._result_code == _PERMANENT
