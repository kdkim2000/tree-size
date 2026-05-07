"""Load and apply QSS themes."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)


def _get_themes_dir() -> Path:
    # PyInstaller onefile: extracted files land under sys._MEIPASS
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "tree_size" / "ui" / "themes"  # type: ignore[attr-defined]
    return Path(__file__).parent


def apply_theme(name: str = "light") -> None:
    """Apply a named theme to the running QApplication."""
    themes_dir = _get_themes_dir()
    qss_path = themes_dir / f"{name}.qss"
    if not qss_path.exists():
        logger.warning("Theme file not found: %s", qss_path)
        return
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return
    app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
    logger.info("Applied theme: %s", name)


def available_themes() -> list[str]:
    return [p.stem for p in _get_themes_dir().glob("*.qss")]
