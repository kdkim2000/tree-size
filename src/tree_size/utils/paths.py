"""Application path helpers — all paths via pathlib.Path."""
from __future__ import annotations

import os
from pathlib import Path

_APP_NAME = "TreeSize"


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
