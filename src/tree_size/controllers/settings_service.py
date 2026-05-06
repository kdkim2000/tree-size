"""Application settings — thin QSettings wrapper stored as INI.

Path: %LOCALAPPDATA%\\TreeSize\\settings.ini

Key design decisions
--------------------
* QSettings in IniFormat so it is human-editable on disk.
* SettingsService owns the single QSettings instance; all reads/writes
  go through typed accessor methods.  Callers never import QSettings.
* themeChanged is emitted only when the value actually changes, so
  MainWindow can re-apply the QSS without redundant work.
* "system" theme reads the Windows AppsUseLightTheme registry value at
  call-time; no polling — MainWindow re-queries on QStyleHints signal.
"""
from __future__ import annotations

import logging
import winreg

from PySide6.QtCore import QObject, QSettings, Signal, Slot

from tree_size.utils.paths import settings_ini_path

logger = logging.getLogger(__name__)

_VALID_THEMES = frozenset({"light", "dark", "system"})

_REG_THEME_PATH = (
    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
)
_REG_THEME_KEY = "AppsUseLightTheme"


def _resolve_system_theme() -> str:
    """Read the Windows personalization registry key.

    Returns "light" or "dark"; defaults to "light" on any error.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_THEME_PATH) as key:
            value, _ = winreg.QueryValueEx(key, _REG_THEME_KEY)
            return "light" if int(value) else "dark"
    except OSError:
        logger.debug("Could not read Windows theme registry key; defaulting to light")
        return "light"


class SettingsService(QObject):
    """Persist and expose user preferences via QSettings (INI format)."""

    # Emitted with the *resolved* theme name ("light" or "dark") — never "system".
    themeChanged = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        ini_path = settings_ini_path()
        ini_path.parent.mkdir(parents=True, exist_ok=True)
        self._qs = QSettings(str(ini_path), QSettings.Format.IniFormat)
        logger.debug("SettingsService: using %s", ini_path)

    # ── theme ────────────────────────────────────────────────────────────────

    def get_theme(self) -> str:
        """Return stored preference: "light", "dark", or "system" (default "light")."""
        raw = self._qs.value("theme", "light")
        return str(raw) if raw in _VALID_THEMES else "light"

    @Slot(str)
    def set_theme(self, theme: str) -> None:
        """Store preference and emit themeChanged with the resolved name."""
        if theme not in _VALID_THEMES:
            logger.warning("set_theme: unknown theme %r; ignored", theme)
            return
        old = self.get_theme()
        self._qs.setValue("theme", theme)
        new_resolved = self.resolve_theme()
        old_resolved = (
            _resolve_system_theme() if old == "system" else old
        )
        if new_resolved != old_resolved:
            self.themeChanged.emit(new_resolved)

    def resolve_theme(self) -> str:
        """Return the concrete theme name ("light" or "dark") accounting for system."""
        pref = self.get_theme()
        if pref == "system":
            return _resolve_system_theme()
        return pref

    # ── scan options ─────────────────────────────────────────────────────────

    def get_follow_symlinks(self) -> bool:
        return self._qs.value("scan/follow_symlinks", False, type=bool)  # type: ignore[call-overload]

    @Slot(bool)
    def set_follow_symlinks(self, val: bool) -> None:
        self._qs.setValue("scan/follow_symlinks", val)

    def get_measure_alloc_size(self) -> bool:
        return self._qs.value("scan/measure_allocation_size", True, type=bool)  # type: ignore[call-overload]

    @Slot(bool)
    def set_measure_alloc_size(self, val: bool) -> None:
        self._qs.setValue("scan/measure_allocation_size", val)

    # ── cache ────────────────────────────────────────────────────────────────

    def get_use_cache(self) -> bool:
        return self._qs.value("cache/enabled", True, type=bool)  # type: ignore[call-overload]

    @Slot(bool)
    def set_use_cache(self, val: bool) -> None:
        self._qs.setValue("cache/enabled", val)

    # ── sync ─────────────────────────────────────────────────────────────────

    def sync(self) -> None:
        """Flush pending writes to disk."""
        self._qs.sync()
