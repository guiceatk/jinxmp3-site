"""
agent/execution/executor.py — Execute approved automations.

Supports action types:
  - file_copy    (requires modify_files)
  - file_move    (requires modify_files)
  - file_rename  (requires modify_files)
  - file_delete  (requires modify_files)
  - run_command  (requires run_commands)
  - noop         (always safe — used for dry-run demos)

Every execution records a row in `executions` and every step appends to
`audit_log`. Snapshots are taken before destructive file operations.

In dry_run mode: nothing is written to disk; the executor logs what
*would* happen and records DRY_RUN in the audit.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.core.config import config
from agent.core.database import get_connection
from agent.core.emergency_stop import check_stop
from agent.core.permissions import PermissionDenied, PermissionLevel, permission_guard
from agent.execution.rollback import snapshot

log = logging.getLogger("agent.execution.executor")


class ExecutionError(Exception):
    """Raised when an execution step fails."""


class Executor:
    """
    Executes a single approved automation.

    Usage:
        ex = Executor()
        result = ex.run(automation_id=3)
    """

    def __init__(self) -> None:
        self._cfg = config

    def run(self, automation_id: int) -> dict[str, Any]:
        """
        Load the automation, validate approval, and execute each step.

        Returns {execution_id, status, steps: [{action, result, …}]}.
        """
        check_stop()

        automation = self._load_automation(automation_id)
        if automation is None:
            raise ExecutionError(f"Automation {automation_id} not found.")

        if automation["status"] not in ("APPROVED",):
            raise ExecutionError(
                f"Automation {automation_id} has status '{automation['status']}'. "
                "Only APPROVED automations may be executed."
            )

        actions: list[dict] = automation.get("actions_json") or []
        if isinstance(actions, str):
            actions = json.loads(actions)

        exec_id = self._create_execution(automation_id)

        step_results: list[dict] = []
        overall_status = "SUCCESS"

        try:
            for step in actions:
                check_stop()
                step_result = self._dispatch(step, exec_id)
                step_results.append(step_result)
                if step_result["result"] == "FAILED":
                    overall_status = "FAILED"
                    break
        except PermissionDenied as exc:
            overall_status = "FAILED"
            step_results.append({"action": "permission_check", "result": "FAILED", "error": str(exc)})
        except Exception as exc:
            overall_status = "FAILED"
            step_results.append({"action": "unknown", "result": "FAILED", "error": str(exc)})
            log.exception("Unexpected error during execution %d", exec_id)

        self._finish_execution(exec_id, overall_status, step_results)
        log.info("Execution %d completed: %s", exec_id, overall_status)
        return {"execution_id": exec_id, "status": overall_status, "steps": step_results}

    # ── dispatch ──────────────────────────────────────────────────────────

    def _dispatch(self, step: dict, exec_id: int) -> dict:
        action_type = step.get("type", "noop")
        dispatch = {
            "noop": self._noop,
            "file_copy": self._file_copy,
            "file_move": self._file_move,
            "file_rename": self._file_rename,
            "file_delete": self._file_delete,
            "run_command": self._run_command,
        }
        handler = dispatch.get(action_type)
        if handler is None:
            return {
                "action": action_type,
                "result": "FAILED",
                "error": f"Unknown action type '{action_type}'",
            }
        return handler(step, exec_id)

    # ── action handlers ───────────────────────────────────────────────────

    def _noop(self, step: dict, exec_id: int) -> dict:
        desc = step.get("description", "noop")
        log.info("[NOOP] %s", desc)
        self._audit("noop", desc, None, {}, "SUCCESS" if not self._cfg.dry_run else "DRY_RUN", exec_id)
        return {"action": "noop", "description": desc, "result": "SUCCESS"}

    def _file_copy(self, step: dict, exec_id: int) -> dict:
        return self._file_op("file_copy", step, exec_id, destructive=False)

    def _file_move(self, step: dict, exec_id: int) -> dict:
        return self._file_op("file_move", step, exec_id, destructive=True)

    def _file_rename(self, step: dict, exec_id: int) -> dict:
        return self._file_op("file_rename", step, exec_id, destructive=True)

    def _file_delete(self, step: dict, exec_id: int) -> dict:
        return self._file_op("file_delete", step, exec_id, destructive=True)

    def _file_op(self, op: str, step: dict, exec_id: int, destructive: bool) -> dict:
        permission_guard.check(PermissionLevel.MODIFY_FILES, action=op)

        src = Path(step.get("source", ""))
        dst_raw = step.get("destination")
        dst = Path(dst_raw) if dst_raw else None

        permission_guard.require_approved_path(src, op)
        if dst:
            permission_guard.require_approved_path(dst, op)

        params = {"source": str(src), "destination": str(dst) if dst else None}

        if self._cfg.dry_run:
            log.info("[DRY-RUN] Would %s: %s → %s", op, src, dst)
            self._audit(op, str(src), str(dst) if dst else None, params, "DRY_RUN", exec_id)
            return {"action": op, "source": str(src), "result": "DRY_RUN"}

        if destructive and self._cfg.execution.get("backup_before_destructive", True):
            if src.exists():
                snapshot(src, exec_id)

        try:
            if op == "file_copy":
                shutil.copy2(src, dst)
            elif op in ("file_move", "file_rename"):
                shutil.move(str(src), str(dst))
            elif op == "file_delete":
                src.unlink()

            self._audit(op, str(src), str(dst) if dst else None, params, "SUCCESS", exec_id)
            return {"action": op, "source": str(src), "result": "SUCCESS"}

        except OSError as exc:
            msg = str(exc)
            self._audit(op, str(src), str(dst) if dst else None, params, "FAILED", exec_id, notes=msg)
            return {"action": op, "source": str(src), "result": "FAILED", "error": msg}

    def _run_command(self, step: dict, exec_id: int) -> dict:
        permission_guard.check(PermissionLevel.RUN_COMMANDS, action="run_command")

        cmd = step.get("command", "")
        args = step.get("args", [])
        timeout = int(
            step.get("timeout_seconds", self._cfg.execution.get("command_timeout_seconds", 30))
        )

        # Allowlist check
        allowed = self._cfg.approved_commands
        if allowed and cmd not in allowed:
            raise PermissionDenied(
                f"Command '{cmd}' is not in approved_commands list."
            )

        params = {"command": cmd, "args": args, "timeout_seconds": timeout}

        if self._cfg.dry_run:
            log.info("[DRY-RUN] Would run: %s %s", cmd, " ".join(str(a) for a in args))
            self._audit("run_command", cmd, None, params, "DRY_RUN", exec_id)
            return {"action": "run_command", "command": cmd, "result": "DRY_RUN"}

        try:
            proc = subprocess.run(
                [cmd, *[str(a) for a in args]],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            result_str = "SUCCESS" if proc.returncode == 0 else "FAILED"
            output = {
                "stdout": proc.stdout[:4096],
                "stderr": proc.stderr[:4096],
                "return_code": proc.returncode,
            }
            self._audit("run_command", cmd, None, params, result_str, exec_id)
            return {"action": "run_command", "command": cmd, "result": result_str, "output": output}

        except subprocess.TimeoutExpired:
            self._audit("run_command", cmd, None, params, "FAILED", exec_id, notes="Timeout")
            return {"action": "run_command", "command": cmd, "result": "FAILED", "error": "Timeout"}
        except OSError as exc:
            self._audit("run_command", cmd, None, params, "FAILED", exec_id, notes=str(exc))
            return {"action": "run_command", "command": cmd, "result": "FAILED", "error": str(exc)}

    # ── persistence helpers ───────────────────────────────────────────────

    def _load_automation(self, automation_id: int) -> dict | None:
        with get_connection() as con:
            row = con.execute(
                "SELECT * FROM automations WHERE id=?", (automation_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        for key in ("trigger_json", "actions_json"):
            if d.get(key):
                try:
                    d[key] = json.loads(d[key])
                except Exception:
                    pass
        return d

    def _create_execution(self, automation_id: int) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with get_connection() as con:
            cur = con.execute(
                """
                INSERT INTO executions (automation_id, dry_run, status, started_at)
                VALUES (?, ?, 'RUNNING', ?)
                """,
                (automation_id, int(self._cfg.dry_run), now),
            )
            return cur.lastrowid

    def _finish_execution(self, exec_id: int, status: str, steps: list[dict]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with get_connection() as con:
            con.execute(
                """
                UPDATE executions
                SET status=?, finished_at=?, output_json=?
                WHERE id=?
                """,
                (status, now, json.dumps(steps), exec_id),
            )

    def _audit(
        self,
        action: str,
        target: str | None,
        dest: str | None,
        params: dict,
        result: str,
        exec_id: int,
        notes: str | None = None,
    ) -> None:
        if dest:
            params = {**params, "destination": dest}
        with get_connection() as con:
            con.execute(
                """
                INSERT INTO audit_log
                    (actor, action, target, parameters_json, result,
                     dry_run, approval_required, execution_id, notes)
                VALUES ('agent', ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    action,
                    target,
                    json.dumps(params),
                    result,
                    int(self._cfg.dry_run),
                    exec_id,
                    notes,
                ),
            )
