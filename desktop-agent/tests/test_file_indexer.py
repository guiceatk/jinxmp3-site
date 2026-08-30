"""tests/test_file_indexer.py"""
from __future__ import annotations
from pathlib import Path


def _make_live_config(tmp_path, approved_dir: Path):
    """Return a live (non-dry-run) Config with read_files enabled."""
    from agent.core.config import Config
    raw = {
        "agent": {
            "dry_run": False,
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
        "approved_directories": [str(approved_dir)],
        "approved_applications": [],
        "approved_commands": [],
        "secret_exclusions": {"globs": ["**/.env"], "content_patterns": []},
        "pattern_detection": {"min_frequency": 2, "lookback_days": 30, "min_sequence_length": 2},
        "execution": {"command_timeout_seconds": 5, "backup_before_destructive": True, "backup_dir": str(tmp_path / "backups")},
        "ui": {},
    }
    return Config(raw)


def test_indexer_dry_run_skips_db(dry_run_config):
    from agent.core.database import get_connection
    from agent.indexer import file_indexer as fi_mod

    cfg, approved = dry_run_config
    (approved / "hello.txt").write_text("hello")

    original = fi_mod.config
    fi_mod.config = cfg
    try:
        from agent.indexer.file_indexer import FileIndexer
        result = FileIndexer().run()
    finally:
        fi_mod.config = original

    assert result["indexed"] >= 1
    # In dry_run mode, nothing should be in the DB
    with get_connection() as con:
        count = con.execute("SELECT COUNT(*) FROM file_index").fetchone()[0]
    assert count == 0


def test_indexer_live_inserts_db(tmp_path):
    from agent.core.database import get_connection
    from agent.indexer import file_indexer as fi_mod

    approved = tmp_path / "approved"
    approved.mkdir()
    (approved / "readme.txt").write_text("data")

    cfg = _make_live_config(tmp_path, approved)
    original = fi_mod.config
    fi_mod.config = cfg
    try:
        from agent.indexer.file_indexer import FileIndexer
        FileIndexer().run()
    finally:
        fi_mod.config = original

    with get_connection() as con:
        count = con.execute("SELECT COUNT(*) FROM file_index").fetchone()[0]
    assert count >= 1


def test_indexer_excludes_secrets(tmp_path):
    from agent.core.database import get_connection
    from agent.indexer import file_indexer as fi_mod

    approved = tmp_path / "approved"
    approved.mkdir()
    (approved / "normal.txt").write_text("data")
    (approved / ".env").write_text("SECRET=1")

    cfg = _make_live_config(tmp_path, approved)
    original = fi_mod.config
    fi_mod.config = cfg
    try:
        from agent.indexer.file_indexer import FileIndexer
        result = FileIndexer().run()
    finally:
        fi_mod.config = original

    assert result["skipped_secrets"] >= 1
    with get_connection() as con:
        rows = con.execute("SELECT path FROM file_index").fetchall()
    indexed_paths = [r["path"] for r in rows]
    assert not any(".env" in p for p in indexed_paths)
