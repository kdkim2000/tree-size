"""Shared fixtures for all test layers."""
from __future__ import annotations

from pathlib import Path

import pytest

from tree_size.core.node import CancelToken, ScanOptions
from tree_size.core.scanner import Scanner


@pytest.fixture()
def synthetic_tree(tmp_path: Path) -> Path:
    """Build a known directory tree: 100 files across 10 folders, sizes 1 KB .. ~100 KB."""
    for folder_idx in range(10):
        folder = tmp_path / f"folder_{folder_idx:02d}"
        folder.mkdir()
        for file_idx in range(10):
            size = 1024 * (folder_idx * 10 + file_idx + 1)  # 1 KB .. 1000 KB
            (folder / f"file_{file_idx:02d}.bin").write_bytes(b"\x00" * size)
    return tmp_path
