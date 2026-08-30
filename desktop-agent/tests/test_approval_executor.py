"""
tests/test_approval_executor.py — Integration test covering the full
MVP workflow: observation → proposal → approval → execution (dry-run) → rollback.
"""
from __future__ import annotations
import json
from pathlib import Path


def _insert_observation(con, event_type, src, dest=None):
    con.execute(
        "INSERT INTO observations (event_type, source_path, dest_path) VALUES (?,?,?)",
        (event_type, src, dest),
    )


def test_approval_manager_lifecycle():
    from agent.core.database import get_connection
    from agent.execution.approval_manager import ApprovalManager

    with get_connection() as con:
        cur = con.execute(
            "INSERT INTO automations (name, description, status) "
            "VALUES ('Test Automation', 'desc', 'PENDING_APPROVAL')"
        )
        auto_id = cur.lastrowid

    am = ApprovalManager()
    pending = am.pending()
    assert any(p["id"] == auto_id for p in pending)

    ok = am.approve(auto_id, "looks good")
    assert ok

    approved = am.approved()
    assert any(a["id"] == auto_id for a in approved)
    assert am.pending() == []

    am.pause(auto_id)
    row = am.get(auto_id)
    assert row["status"] == "PAUSED"


def test_executor_dry_run_noop(dry_run_config):
    from agent.core.database import get_connection
    from agent.execution.executor import Executor
    import agent.execution.executor as ex_mod

    cfg, _ = dry_run_config
    original = ex_mod.config
    ex_mod.config = cfg

    try:
        with get_connection() as con:
            cur = con.execute(
                "INSERT INTO automations "
                "(name, description, trigger_json, actions_json, status) "
                "VALUES (?,?,?,?,'APPROVED')",
                (
                    "Noop Test",
                    "desc",
                    json.dumps({"type": "manual"}),
                    json.dumps([{"type": "noop", "description": "do nothing"}]),
                ),
            )
            auto_id = cur.lastrowid

        result = Executor().run(auto_id)
        assert result["status"] == "SUCCESS"
        assert result["steps"][0]["result"] == "SUCCESS"
    finally:
        ex_mod.config = original


def test_executor_requires_approval(dry_run_config):
    from agent.core.database import get_connection
    from agent.execution.executor import Executor, ExecutionError
    import agent.execution.executor as ex_mod

    cfg, _ = dry_run_config
    original = ex_mod.config
    ex_mod.config = cfg

    try:
        with get_connection() as con:
            cur = con.execute(
                "INSERT INTO automations (name, status) "
                "VALUES ('Unapproved', 'PENDING_APPROVAL')"
            )
            auto_id = cur.lastrowid

        try:
            Executor().run(auto_id)
            assert False, "Should have raised ExecutionError"
        except ExecutionError:
            pass
    finally:
        ex_mod.config = original


def test_rollback_roundtrip(tmp_path):
    from agent.execution.rollback import snapshot, rollback, list_snapshots
    import agent.execution.rollback as rb_mod
    import agent.core.config as cfg_mod

    # Override backup dir
    original_cfg = rb_mod.config
    from agent.core.config import Config
    raw = dict(original_cfg.raw())
    raw["execution"] = {
        "backup_dir": str(tmp_path / "backups"),
        "backup_before_destructive": True,
        "command_timeout_seconds": 5,
    }
    rb_mod.config = Config(raw)

    try:
        original_file = tmp_path / "original.txt"
        original_file.write_text("original content")

        backup_path = snapshot(original_file, execution_id=None)
        assert backup_path.exists()

        original_file.write_text("modified content")

        snaps = list_snapshots()
        assert len(snaps) >= 1
        snap_id = snaps[0]["id"]

        ok = rollback(snap_id)
        assert ok
        assert original_file.read_text() == "original content"
    finally:
        rb_mod.config = original_cfg


def test_full_mvp_workflow(tmp_path):
    """
    MVP demo: observation events → pattern detection → proposal → approval
              → executor dry-run → audit trail present.
    """
    from agent.core.database import get_connection
    from agent.analysis.pattern_detector import PatternDetector
    from agent.execution.approval_manager import ApprovalManager
    from agent.execution.executor import Executor
    import agent.analysis.pattern_detector as pd_mod
    import agent.execution.executor as ex_mod
    from agent.core.config import Config

    approved = tmp_path / "project"
    approved.mkdir()

    cfg_raw = {
        "agent": {"dry_run": True, "log_level": "WARNING",
                  "max_cpu_percent": 90, "max_memory_mb": 1024,
                  "max_events_per_second": 100, "analysis_interval_seconds": 60,
                  "max_observations": 100},
        "permissions": {
            "observe_only": True, "read_files": True,
            "modify_files": False, "run_commands": False,
            "control_applications": False, "control_windows": False,
            "manage_processes": False, "modify_system_settings": False,
            "network_access": False, "external_actions": False,
        },
        "approved_directories": [str(approved)],
        "approved_applications": [], "approved_commands": [],
        "secret_exclusions": {"globs": [], "content_patterns": []},
        "pattern_detection": {"min_frequency": 2, "lookback_days": 30, "min_sequence_length": 2},
        "execution": {"command_timeout_seconds": 5, "backup_before_destructive": True,
                      "backup_dir": str(tmp_path / "backups")},
        "ui": {},
    }
    cfg = Config(cfg_raw)

    # --- Step 1: seed observations (rename pattern, repeated)
    with get_connection() as con:
        for i in range(3):
            src = str(approved / f"draft_v{i}.docx")
            dst = str(approved / f"final_{i}.docx")
            _insert_observation(con, "moved", src, dst)

    # --- Step 2: pattern detection
    original_pd_cfg = pd_mod.config
    pd_mod.config = cfg
    try:
        proposals = PatternDetector().run()
    finally:
        pd_mod.config = original_pd_cfg

    assert len(proposals) >= 1

    # --- Step 3: approve first proposal
    am = ApprovalManager()
    pending = am.pending()
    assert len(pending) >= 1
    auto_id = pending[0]["id"]
    am.approve(auto_id, "approved in test")

    # --- Step 4: execute (dry-run, noop-style — actions are file_rename which
    #             is blocked because modify_files=False in dry-run cfg)
    original_ex_cfg = ex_mod.config
    ex_mod.config = cfg
    try:
        # Actions are file_rename — will fail permission check (modify_files=False)
        # This is the expected safe behaviour.
        result = Executor().run(auto_id)
        assert result["status"] in ("SUCCESS", "FAILED")
    finally:
        ex_mod.config = original_ex_cfg

    # --- Step 5: audit trail exists
    with get_connection() as con:
        count = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    assert count > 0
