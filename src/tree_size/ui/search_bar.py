"""Search input widget with filter options.

Emits filterChanged(FilterSpec) whenever the user changes any control.
The widget is intentionally stateless beyond the Qt widget state — callers
read the current spec via the ``filter_spec`` property.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from tree_size.core.filter import FilterSpec

logger = logging.getLogger(__name__)

# Extension presets keyed by combo-box index (index 0 = "All" → empty list).
_EXT_PRESETS: list[list[str]] = [
    [],  # All
    [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],   # Images
    [".mp4", ".mkv", ".avi", ".mov", ".wmv"],              # Videos
    [".zip", ".7z", ".rar", ".tar", ".gz", ".bz2"],        # Archives
]


class SearchBar(QWidget):
    """Horizontal bar: name search, regex toggle, type combo, min-size spinner.

    All controls are wired together so that any change immediately emits
    ``filterChanged`` with the fully updated :class:`FilterSpec`.
    """

    filterChanged = Signal(object)  # FilterSpec

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    # ── public API ───────────────────────────────────────────────────────────

    @property
    def filter_spec(self) -> FilterSpec:
        """Return the FilterSpec that reflects the current widget state."""
        return FilterSpec(
            name_pattern=self._name_input.text(),
            use_regex=self._regex_check.isChecked(),
            extensions=_EXT_PRESETS[self._ext_combo.currentIndex()],
            min_size=self._min_size.value() * 1024 * 1024,
        )

    def set_focus_on_name_input(self) -> None:
        """Focus and select-all the name field (bound to Ctrl+F)."""
        self._name_input.setFocus()
        self._name_input.selectAll()

    # ── private setup ────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # Name search
        layout.addWidget(QLabel("Name:", parent=self))
        self._name_input = QLineEdit(parent=self)
        self._name_input.setPlaceholderText("Search (Ctrl+F)")
        self._name_input.setMinimumWidth(160)
        self._name_input.textChanged.connect(self._on_filter_changed)
        layout.addWidget(self._name_input)

        # Regex toggle
        self._regex_check = QCheckBox("Regex", parent=self)
        self._regex_check.toggled.connect(self._on_filter_changed)
        layout.addWidget(self._regex_check)

        layout.addSpacing(12)

        # File-type preset
        layout.addWidget(QLabel("Type:", parent=self))
        self._ext_combo = QComboBox(parent=self)
        self._ext_combo.addItems(
            ["All", "Images (.jpg, .png)", "Videos (.mp4, .mkv)", "Archives (.zip, .7z)"]
        )
        self._ext_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._ext_combo)

        layout.addSpacing(12)

        # Minimum size
        layout.addWidget(QLabel("Min size (MB):", parent=self))
        self._min_size = QSpinBox(parent=self)
        self._min_size.setMaximum(100_000)
        self._min_size.setSuffix(" MB")
        self._min_size.valueChanged.connect(self._on_filter_changed)
        layout.addWidget(self._min_size)

        layout.addStretch()

    # ── slots ────────────────────────────────────────────────────────────────

    @Slot()
    def _on_filter_changed(self) -> None:
        """Emit filterChanged with the current spec whenever any control changes."""
        spec = self.filter_spec
        logger.debug(
            "Filter changed: pattern=%r regex=%s exts=%s min_size=%d",
            spec.name_pattern,
            spec.use_regex,
            spec.extensions,
            spec.min_size,
        )
        self.filterChanged.emit(spec)
