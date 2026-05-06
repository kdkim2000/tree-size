"""Load and apply QSS themes."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

_THEMES_DIR = Path(__file__).parent


def apply_theme(name: str = "light") -> None:
    """Apply a named theme to the running QApplication."""
    qss_path = _THEMES_DIR / f"{name}.qss"
    if not qss_path.exists():
        logger.warning("Theme file not found: %s", qss_path)
        return
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return
    app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
    logger.info("Applied theme: %s", name)


def available_themes() -> list[str]:
    return [p.stem for p in _THEMES_DIR.glob("*.qss")]
