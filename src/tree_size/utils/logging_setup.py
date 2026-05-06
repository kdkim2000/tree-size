"""Centralized logging configuration for Tree-Size."""
from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(log_dir: Path, level: int = logging.INFO) -> None:
    """Configure root logger: file handler (rotating) + console handler."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "tree-size.log"

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    fh = _rotating_file_handler(log_file, fmt)
    root.addHandler(fh)

    ch = logging.StreamHandler(sys.stderr)
    ch.setFormatter(fmt)
    ch.setLevel(logging.WARNING)
    root.addHandler(ch)


def _rotating_file_handler(
    log_file: Path, fmt: logging.Formatter
) -> logging.Handler:
    from logging.handlers import RotatingFileHandler

    handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB per shard before rotation
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(fmt)
    return handler
