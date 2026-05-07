# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Tree-Size — single onefile windowed EXE."""
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent  # repo root (one level above build/)
SRC = ROOT / "src" / "tree_size"

# Locate qtawesome fonts for explicit bundling
import qtawesome as _qta
QTA_FONTS = Path(_qta.__file__).parent / "fonts"

block_cipher = None

a = Analysis(
    [str(SRC / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[
        (str(SRC / "ui" / "themes" / "light.qss"), "tree_size/ui/themes"),
        (str(SRC / "ui" / "themes" / "dark.qss"), "tree_size/ui/themes"),
        (str(ROOT / "resources"), "resources"),
        # qtawesome font files (TTF + JSON charmaps)
        (str(QTA_FONTS / "*.ttf"), "qtawesome/fonts"),
        (str(QTA_FONTS / "*.json"), "qtawesome/fonts"),
    ],
    hiddenimports=[
        "tree_size",
        "tree_size.app",
        "tree_size.ui.main_window",
        "tree_size.ui.themes.theme_manager",
        "tree_size.utils.logging_setup",
        "tree_size.utils.paths",
        "tree_size.utils.win32",
        "tree_size.core.scanner",
        "tree_size.core.node",
        "tree_size.core.aggregator",
        "tree_size.core.formatter",
        "tree_size.core.fs_probe",
        "tree_size.core.filter",
        "tree_size.persistence.cache_db",
        "tree_size.workers.scan_worker",
        "tree_size.workers.signals",
        "tree_size.workers.progress",
        "tree_size.controllers.scan_controller",
        "tree_size.controllers.file_ops_controller",
        "tree_size.controllers.export_controller",
        "tree_size.controllers.settings_service",
        "tree_size.exporters.csv_exporter",
        "tree_size.exporters.json_exporter",
        "tree_size.exporters.html_exporter",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtCharts",
        "pyqtgraph",
        "qtawesome",
        "send2trash",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "doctest", "pdb"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

_manifest = str(ROOT / "build" / "tree-size.manifest")
_version  = str(ROOT / "build" / "version_info.txt")
_icon     = str(ROOT / "resources" / "tree-size.ico")

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="tree-size",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX disabled — Defender false-positive risk
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,      # windowed — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    manifest=_manifest,
    version=_version,
    icon=_icon if Path(_icon).exists() else None,
)
