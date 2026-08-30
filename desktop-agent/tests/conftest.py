"""
tests/conftest.py — Shared pytest fixtures.

All fixtures use temporary directories and in-memory / temp databases
so tests never touch the real project state.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

# ── isolate the database ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    """Redirect every get_connection call to a fresh temp database."""
    from agent.core import database as db_module

    temp_db = tmp_path / "test_agent.db"
    db_module.init_db(temp_db)

    # Monkeypatch the default path used by get_connection
    monkeypatch.setattr(db_module, "_DEFAULT_DB", temp_db)
    yield temp_db


# ── isolate the STOP file ─────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _temp_stop_file(tmp_path, monkeypatch):
    """Use a temp STOP file so tests don't interfere with real state."""
    from agent.core import emergency_stop as es_module
    stop_path = tmp_path / "STOP"
    monkeypatch.setattr(es_module, "_STOP_FILE", stop_path)
    yield stop_path


# ── provide a minimal config ──────────────────────────────────────────────

@pytest.fixture()
def dry_run_config(tmp_path):
    """Return a Config object in dry-run mode with one approved temp dir."""
    from agent.core.config import Config

    approved = tmp_path / "approved"
    approved.mkdir()

    raw = {
        "agent": {
            "name": "test-agent",
            "dry_run": True,
            "log_level": "WARNING",
            "max_observations": 100,
            "analysis_interval_seconds": 60,
            "max_cpu_percent": 90,
            "max_memory_mb": 1024,
            "max_events_per_second": 100,
        },
        "permissions": {
            "observe_only": True,
            "read_files": True,
            "modify_files": False,
            "run_commands": False,
            "control_applications": False,
            "control_windows": False,
            "manage_processes": False,
            "modify_system_settings": False,
            "network_access": False,
            "external_actions": False,
        },
        "approved_directories": [str(approved)],
        "approved_applications": [],
        "approved_commands": [],
        "secret_exclusions": {
            "globs": ["**/.env", "**/*secret*"],
            "content_patterns": [
                r'(?i)(password|passwd)\s*[=:]\s*\S+',
                r'-----BEGIN .* PRIVATE KEY-----',
            ],
        },
        "pattern_detection": {
            "min_frequency": 2,
            "lookback_days": 30,
            "min_sequence_length": 2,
        },
        "execution": {
            "command_timeout_seconds": 5,
            "backup_before_destructive": True,
            "backup_dir": str(tmp_path / "backups"),
        },
        "ui": {"tray_icon": False, "dashboard_refresh_seconds": 1},
    }
    return Config(raw), approved
