"""
agent/core/permissions.py — Permission enforcement layer.

Every action that touches the OS must call `check()` before executing.
The check logs the attempt whether or not it is permitted.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from agent.core.config import Config, config as _global_config
from agent.core.database import get_connection


class PermissionLevel(str, Enum):
    OBSERVE_ONLY = "observe_only"
    READ_FILES = "read_files"
    MODIFY_FILES = "modify_files"
    RUN_COMMANDS = "run_commands"
    CONTROL_APPLICATIONS = "control_applications"
    CONTROL_WINDOWS = "control_windows"
    MANAGE_PROCESSES = "manage_processes"
    MODIFY_SYSTEM_SETTINGS = "modify_system_settings"
    NETWORK_ACCESS = "network_access"
    EXTERNAL_ACTIONS = "external_actions"


class PermissionDenied(Exception):
    """Raised when a required permission is not enabled in config."""


@dataclass
class PermissionCheck:
    """Result of a permission check."""
    level: PermissionLevel
    action: str
    target: str | None
    parameters: dict[str, Any] = field(default_factory=dict)
    permitted: bool = False
    dry_run: bool = True
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PermissionGuard:
    """Enforces permission checks and writes every attempt to the audit log."""

    def __init__(self, cfg: Config | None = None) -> None:
        self._cfg = cfg or _global_config

    # ── public API ────────────────────────────────────────────────────────

    def check(
        self,
        level: PermissionLevel,
        action: str,
        target: str | None = None,
        parameters: dict[str, Any] | None = None,
        approval_required: bool = False,
    ) -> PermissionCheck:
        """
        Verify that *level* is enabled in config.

        Raises PermissionDenied if not permitted.
        Always writes a row to audit_log.
        Returns the PermissionCheck result.
        """
        params = parameters or {}
        permitted = self._cfg.permission(level.value)
        dry = self._cfg.dry_run

        result_str = "DRY_RUN" if dry and permitted else ("SUCCESS" if permitted else "FAILED")

        pc = PermissionCheck(
            level=level,
            action=action,
            target=target,
            parameters=params,
            permitted=permitted,
            dry_run=dry,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        self._write_audit(pc, result_str, approval_required)

        if not permitted:
            raise PermissionDenied(
                f"Permission '{level.value}' is not enabled. "
                f"Enable it in config/local.yaml to use '{action}'."
            )
        return pc

    def is_path_approved(self, path: Path) -> bool:
        """Return True if *path* is under an approved directory."""
        approved = self._cfg.approved_directories
        if not approved:
            return False
        resolved = path.resolve()
        for approved_dir in approved:
            try:
                resolved.relative_to(approved_dir.resolve())
                return True
            except ValueError:
                continue
        return False

    def require_approved_path(self, path: Path, action: str) -> None:
        """Raise PermissionDenied if *path* is not under an approved directory."""
        if not self.is_path_approved(path):
            msg = (
                f"Path '{path}' is not under any approved directory. "
                f"Add it to approved_directories in config/local.yaml."
            )
            self._write_audit_simple(action, str(path), "FAILED", msg)
            raise PermissionDenied(msg)

    # ── internal ──────────────────────────────────────────────────────────

    def _write_audit(
        self,
        pc: PermissionCheck,
        result: str,
        approval_required: bool,
    ) -> None:
        try:
            with get_connection() as con:
                con.execute(
                    """
                    INSERT INTO audit_log
                        (timestamp, actor, action, target, parameters_json,
                         result, dry_run, approval_required)
                    VALUES (?, 'agent', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pc.timestamp,
                        pc.action,
                        pc.target,
                        json.dumps(pc.parameters),
                        result,
                        int(pc.dry_run),
                        int(approval_required),
                    ),
                )
        except Exception:
            # Audit failures must never crash the caller — but surface the error
            import traceback
            traceback.print_exc()

    def _write_audit_simple(
        self, action: str, target: str, result: str, notes: str | None = None
    ) -> None:
        try:
            with get_connection() as con:
                con.execute(
                    """
                    INSERT INTO audit_log (actor, action, target, result, dry_run, notes)
                    VALUES ('agent', ?, ?, ?, ?, ?)
                    """,
                    (action, target, result, int(self._cfg.dry_run), notes),
                )
        except Exception:
            import traceback
            traceback.print_exc()


# Module-level singleton
permission_guard = PermissionGuard()
