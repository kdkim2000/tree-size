"""Settings dialog — General | Scan Options | Cache tabs.

Responsibilities
----------------
* Display current preferences from SettingsService.
* On Accept: write changed values back; let SettingsService.themeChanged
  propagate to MainWindow which calls theme_manager.apply_theme().
* On Reject / Cancel: no writes — QSettings never modified.

Layout
------
  [General]      Theme: [Light / Dark / System ▼]
  [Scan Options] [x] Follow Symlinks
                 [x] Measure Allocated Size
  [Cache]        [x] Enable Cache

Rule compliance
---------------
* R-U2: No inline setStyleSheet.
* R-U3: parent= always passed.
* R-U1: Signals are class variables; slots use @Slot.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tree_size.controllers.settings_service import SettingsService

logger = logging.getLogger(__name__)

_THEME_LABELS = ["Light", "Dark", "System"]
_THEME_VALUES = ["light", "dark", "system"]


class SettingsDialog(QDialog):
    """Modal settings editor.  Call exec(); on Accepted the service is updated."""

    # Emitted (with resolved theme name) when the user changes the theme
    # selection and clicks OK.  MainWindow connects this to apply_theme().
    themeChanged = Signal(str)

    def __init__(
        self,
        service: SettingsService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self.setWindowTitle("Settings")
        self.setMinimumWidth(380)
        self._build_ui()
        self._load_values()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)

        tabs = QTabWidget(parent=self)
        tabs.addTab(self._make_general_tab(), "General")
        tabs.addTab(self._make_scan_tab(), "Scan Options")
        tabs.addTab(self._make_cache_tab(), "Cache")
        root_layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root_layout.addWidget(buttons)

    def _make_general_tab(self) -> QWidget:
        tab = QWidget(parent=self)
        form = QFormLayout(tab)
        form.setContentsMargins(12, 12, 12, 12)

        self._theme_combo = QComboBox(parent=tab)
        for label in _THEME_LABELS:
            self._theme_combo.addItem(label)
        form.addRow(QLabel("Theme:", parent=tab), self._theme_combo)
        return tab

    def _make_scan_tab(self) -> QWidget:
        tab = QWidget(parent=self)
        form = QFormLayout(tab)
        form.setContentsMargins(12, 12, 12, 12)

        self._follow_sym = QCheckBox("Follow Symlinks", parent=tab)
        self._measure_alloc = QCheckBox("Measure Allocated Size", parent=tab)
        form.addRow(self._follow_sym)
        form.addRow(self._measure_alloc)
        return tab

    def _make_cache_tab(self) -> QWidget:
        tab = QWidget(parent=self)
        form = QFormLayout(tab)
        form.setContentsMargins(12, 12, 12, 12)

        self._use_cache = QCheckBox("Enable scan cache (SQLite)", parent=tab)
        form.addRow(self._use_cache)
        return tab

    # ── value sync ───────────────────────────────────────────────────────────

    def _load_values(self) -> None:
        """Populate widgets from the current SettingsService state."""
        theme = self._service.get_theme()
        idx = _THEME_VALUES.index(theme) if theme in _THEME_VALUES else 0
        self._theme_combo.setCurrentIndex(idx)

        self._follow_sym.setChecked(self._service.get_follow_symlinks())
        self._measure_alloc.setChecked(self._service.get_measure_alloc_size())
        self._use_cache.setChecked(self._service.get_use_cache())

    # ── slots ─────────────────────────────────────────────────────────────────

    @Slot()
    def _on_accept(self) -> None:
        """Write changed values and emit themeChanged if needed."""
        old_resolved = self._service.resolve_theme()

        theme_idx = self._theme_combo.currentIndex()
        theme_value = _THEME_VALUES[theme_idx] if 0 <= theme_idx < len(_THEME_VALUES) else "light"
        self._service.set_theme(theme_value)
        self._service.set_follow_symlinks(self._follow_sym.isChecked())
        self._service.set_measure_alloc_size(self._measure_alloc.isChecked())
        self._service.set_use_cache(self._use_cache.isChecked())
        self._service.sync()

        new_resolved = self._service.resolve_theme()
        if new_resolved != old_resolved:
            self.themeChanged.emit(new_resolved)
            logger.info("Theme changed to %s (resolved: %s)", theme_value, new_resolved)

        self.accept()
