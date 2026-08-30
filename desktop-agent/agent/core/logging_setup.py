"""
agent/core/logging_setup.py — Structured rotating log setup.
"""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from agent.core.config import config as _cfg

_LOGS_DIR = Path(__file__).resolve().parents[2] / "logs"
_LOG_FILE = _LOGS_DIR / "agent.log"
_MAX_BYTES = 5 * 1024 * 1024   # 5 MB per file
_BACKUP_COUNT = 5


def setup_logging() -> logging.Logger:
    """Configure root logger; return the 'agent' logger."""
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, _cfg.log_level, logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)-30s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Rotating file handler
    fh = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setFormatter(formatter)
    fh.setLevel(level)

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(level)

    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(fh)
        root.addHandler(ch)

    return logging.getLogger("agent")


logger = setup_logging()
