"""QApplication bootstrap."""
from __future__ import annotations

import logging
import os
import sys

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from tree_size.controllers.settings_service import SettingsService
from tree_size.ui.main_window import MainWindow
from tree_size.ui.themes import theme_manager
from tree_size.utils.logging_setup import setup_logging
from tree_size.utils.paths import log_dir
from tree_size.utils.paths import resource_path

logger = logging.getLogger(__name__)


def run() -> int:
    _bootstrap_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Tree-Size")
    app.setOrganizationName("TreeSize")
    app.setApplicationVersion("0.1.0")

    # Show splash screen before any heavy work
    splash_path = resource_path("resources/splash.png")
    splash_pixmap = QPixmap(str(splash_path))
    splash: QSplashScreen | None = None
    if not splash_pixmap.isNull():
        splash = QSplashScreen(splash_pixmap)
        splash.show()
        app.processEvents()

    # Resolve the initial theme before any widgets are created so the first
    # paint already uses the correct palette.  A temporary SettingsService
    # instance is used here; MainWindow creates its own persistent instance.
    _svc = SettingsService()
    theme_manager.apply_theme(_svc.resolve_theme())

    window = MainWindow(parent=None)
    window.show()

    if splash is not None:
        splash.finish(window)

    logger.info("Tree-Size started")
    return app.exec()


def _bootstrap_logging() -> None:
    level_name = os.environ.get("TREESIZE_LOG_LEVEL", "INFO")
    level = getattr(logging, level_name.upper(), logging.INFO)
    setup_logging(log_dir(), level=level)
