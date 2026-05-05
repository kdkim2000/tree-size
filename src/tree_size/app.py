"""QApplication bootstrap."""
from __future__ import annotations

import logging
import os
import sys

from PySide6.QtWidgets import QApplication

from tree_size.ui.main_window import MainWindow
from tree_size.utils.logging_setup import setup_logging
from tree_size.utils.paths import log_dir

logger = logging.getLogger(__name__)


def run() -> int:
    _bootstrap_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Tree-Size")
    app.setOrganizationName("TreeSize")
    app.setApplicationVersion("0.1.0")

    _apply_theme(app)

    window = MainWindow(parent=None)
    window.show()

    logger.info("Tree-Size started")
    return app.exec()


def _bootstrap_logging() -> None:
    level_name = os.environ.get("TREESIZE_LOG_LEVEL", "INFO")
    level = getattr(logging, level_name.upper(), logging.INFO)
    setup_logging(log_dir(), level=level)


def _apply_theme(app: QApplication) -> None:
    from pathlib import Path
    qss_path = Path(__file__).parent / "ui" / "themes" / "light.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
