"""tests/test_config.py"""
from __future__ import annotations
from pathlib import Path


def test_config_loads_defaults():
    from agent.core.config import Config
    cfg = Config()
    assert cfg.dry_run is True
    assert isinstance(cfg.approved_directories, list)


def test_deep_merge():
    from agent.core.config import _deep_merge
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    override = {"a": {"y": 99, "z": 0}}
    result = _deep_merge(base, override)
    assert result == {"a": {"x": 1, "y": 99, "z": 0}, "b": 3}


def test_permission_accessor(dry_run_config):
    cfg, _ = dry_run_config
    assert cfg.permission("observe_only") is True
    assert cfg.permission("modify_files") is False
    assert cfg.permission("nonexistent") is False
