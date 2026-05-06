"""Application path helpers — all paths via pathlib.Path."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_APP_NAME = "TreeSize"


def resource_path(relative: str) -> Path:
    """Return absolute path to a bundled resource, works both in-source and PyInstaller onefile."""
    # PyInstaller extracts to sys._MEIPASS at runtime
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent.parent.parent))
    return base / relative


def app_data_dir() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    base = Path(local_appdata) if local_appdata else Path.home() / "AppData" / "Local"
    return base / _APP_NAME


def log_dir() -> Path:
    return app_data_dir() / "logs"


def cache_db_path() -> Path:
    return app_data_dir() / "cache.db"


def settings_ini_path() -> Path:
    return app_data_dir() / "settings.ini"
