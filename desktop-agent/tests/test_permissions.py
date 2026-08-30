"""tests/test_permissions.py"""
from __future__ import annotations
from pathlib import Path


def test_permission_denied_raises(dry_run_config):
    from agent.core.permissions import PermissionGuard, PermissionLevel, PermissionDenied
    cfg, _ = dry_run_config
    guard = PermissionGuard(cfg)
    try:
        guard.check(PermissionLevel.MODIFY_FILES, action="test", target="x")
        assert False, "Should have raised PermissionDenied"
    except PermissionDenied:
        pass


def test_permission_allowed_returns_check(dry_run_config):
    from agent.core.permissions import PermissionGuard, PermissionLevel
    cfg, _ = dry_run_config
    guard = PermissionGuard(cfg)
    pc = guard.check(PermissionLevel.READ_FILES, action="test.read", target="/tmp/x")
    assert pc.permitted is True
    assert pc.dry_run is True


def test_approved_path(dry_run_config):
    from agent.core.permissions import PermissionGuard
    cfg, approved = dry_run_config
    guard = PermissionGuard(cfg)
    assert guard.is_path_approved(approved / "file.txt")
    assert not guard.is_path_approved(Path("/some/other/place/file.txt"))


def test_require_approved_path_raises(dry_run_config):
    from agent.core.permissions import PermissionGuard, PermissionDenied
    cfg, _ = dry_run_config
    guard = PermissionGuard(cfg)
    try:
        guard.require_approved_path(Path("/not/approved"), "test")
        assert False
    except PermissionDenied:
        pass


def test_denied_permission_written_to_audit(dry_run_config):
    from agent.core.permissions import PermissionGuard, PermissionLevel, PermissionDenied
    from agent.core.database import get_connection
    cfg, _ = dry_run_config
    guard = PermissionGuard(cfg)
    try:
        guard.check(PermissionLevel.RUN_COMMANDS, action="cmd.test")
    except PermissionDenied:
        pass

    with get_connection() as con:
        row = con.execute(
            "SELECT result FROM audit_log WHERE action='cmd.test'"
        ).fetchone()
    assert row is not None
    assert row["result"] == "FAILED"
