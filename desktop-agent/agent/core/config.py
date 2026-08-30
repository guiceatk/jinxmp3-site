"""
agent/core/config.py — Load, validate and expose the agent configuration.

Merges config/default.yaml with config/local.yaml (if present).
config/local.yaml is git-ignored and is the right place for per-machine settings.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

# Resolve paths relative to the desktop-agent project root
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG = _PROJECT_ROOT / "config" / "default.yaml"
_LOCAL_CONFIG = _PROJECT_ROOT / "config" / "local.yaml"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*, returning a new dict."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config() -> dict[str, Any]:
    """Return the merged configuration dictionary."""
    if not _DEFAULT_CONFIG.exists():
        raise FileNotFoundError(f"Default config not found: {_DEFAULT_CONFIG}")

    with _DEFAULT_CONFIG.open("r", encoding="utf-8") as fh:
        cfg: dict = yaml.safe_load(fh) or {}

    if _LOCAL_CONFIG.exists():
        with _LOCAL_CONFIG.open("r", encoding="utf-8") as fh:
            local: dict = yaml.safe_load(fh) or {}
        cfg = _deep_merge(cfg, local)

    return cfg


class Config:
    """Thin wrapper around the raw config dict with typed accessors."""

    def __init__(self, raw: dict[str, Any] | None = None) -> None:
        self._raw = raw if raw is not None else load_config()

    # ── top-level sections ─────────────────────────────────────────────────

    @property
    def agent(self) -> dict:
        return self._raw.get("agent", {})

    @property
    def permissions(self) -> dict:
        return self._raw.get("permissions", {})

    @property
    def approved_directories(self) -> list[Path]:
        return [Path(p) for p in self._raw.get("approved_directories", [])]

    @property
    def approved_applications(self) -> list[str]:
        return self._raw.get("approved_applications", [])

    @property
    def approved_commands(self) -> list[str]:
        return self._raw.get("approved_commands", [])

    @property
    def secret_exclusions(self) -> dict:
        return self._raw.get("secret_exclusions", {})

    @property
    def pattern_detection(self) -> dict:
        return self._raw.get("pattern_detection", {})

    @property
    def execution(self) -> dict:
        return self._raw.get("execution", {})

    @property
    def ui(self) -> dict:
        return self._raw.get("ui", {})

    # ── convenience helpers ────────────────────────────────────────────────

    @property
    def dry_run(self) -> bool:
        return bool(self.agent.get("dry_run", True))

    @property
    def log_level(self) -> str:
        return str(self.agent.get("log_level", "INFO")).upper()

    def permission(self, level: str) -> bool:
        """Return whether a named permission level is enabled."""
        return bool(self.permissions.get(level, False))

    def raw(self) -> dict:
        return copy.deepcopy(self._raw)


# Module-level singleton — callers do `from agent.core.config import config`
config = Config()
