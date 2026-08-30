"""
agent/execution/approval_manager.py — Manage automation approval lifecycle.

Provides both programmatic and CLI interfaces for:
  - Listing pending proposals
  - Approving / rejecting / editing / pausing / disabling automations
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Literal

from agent.core.database import get_connection

log = logging.getLogger("agent.execution.approval")

Decision = Literal["APPROVED", "REJECTED", "PAUSED", "DISABLED"]


class ApprovalManager:
    """
    Manages transitions between automation statuses.

    Status transitions:
        PENDING_APPROVAL → APPROVED | REJECTED
        APPROVED         → PAUSED | DISABLED
        PAUSED           → APPROVED | DISABLED
        REJECTED         → (terminal unless re-proposed)
        DISABLED         → (terminal)
    """

    # ── queries ───────────────────────────────────────────────────────────

    def pending(self) -> list[dict]:
        """Return all PENDING_APPROVAL automations."""
        return self._query_by_status("PENDING_APPROVAL")

    def approved(self) -> list[dict]:
        return self._query_by_status("APPROVED")

    def all_automations(self) -> list[dict]:
        with get_connection() as con:
            rows = con.execute(
                "SELECT id, name, description, status, created_at, updated_at "
                "FROM automations ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get(self, automation_id: int) -> dict | None:
        with get_connection() as con:
            row = con.execute(
                "SELECT * FROM automations WHERE id = ?", (automation_id,)
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

    # ── decisions ─────────────────────────────────────────────────────────

    def approve(self, automation_id: int, notes: str = "") -> bool:
        return self._transition(automation_id, "APPROVED", notes)

    def reject(self, automation_id: int, notes: str = "") -> bool:
        return self._transition(automation_id, "REJECTED", notes)

    def pause(self, automation_id: int, notes: str = "") -> bool:
        return self._transition(automation_id, "PAUSED", notes)

    def disable(self, automation_id: int, notes: str = "") -> bool:
        return self._transition(automation_id, "DISABLED", notes)

    # ── edit ──────────────────────────────────────────────────────────────

    def update_description(self, automation_id: int, description: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with get_connection() as con:
            cur = con.execute(
                "UPDATE automations SET description=?, updated_at=? WHERE id=?",
                (description, now, automation_id),
            )
        changed = cur.rowcount > 0
        if changed:
            log.info("Automation %d description updated.", automation_id)
        return changed

    def update_actions(self, automation_id: int, actions: list[dict]) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with get_connection() as con:
            cur = con.execute(
                "UPDATE automations SET actions_json=?, updated_at=? WHERE id=?",
                (json.dumps(actions), now, automation_id),
            )
        changed = cur.rowcount > 0
        if changed:
            log.info("Automation %d actions updated.", automation_id)
        return changed

    # ── internals ─────────────────────────────────────────────────────────

    def _query_by_status(self, status: str) -> list[dict]:
        with get_connection() as con:
            rows = con.execute(
                "SELECT id, name, description, status, created_at "
                "FROM automations WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _transition(self, automation_id: int, new_status: str, notes: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        approved_at = now if new_status == "APPROVED" else None

        with get_connection() as con:
            # Update automation status
            cur = con.execute(
                """
                UPDATE automations
                SET status=?, updated_at=?, approved_at=COALESCE(?, approved_at)
                WHERE id=?
                """,
                (new_status, now, approved_at, automation_id),
            )
            if cur.rowcount == 0:
                log.warning("Automation %d not found.", automation_id)
                return False

            # Record the approval decision
            con.execute(
                """
                INSERT INTO approvals (automation_id, decision, notes, decided_at)
                VALUES (?, ?, ?, ?)
                """,
                (automation_id, new_status, notes, now),
            )

        log.info("Automation %d → %s", automation_id, new_status)
        return True
