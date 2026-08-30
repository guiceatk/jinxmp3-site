"""
agent/execution/rollback.py — Pre-action snapshot and rollback support.

Before any destructive file operation, take a versioned backup.
Rollback restores from that backup.
"""
from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from agent.core.config import config
from agent.core.database import get_connection

log = logging.getLogger("agent.execution.rollback")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _backup_dir() -> Path:
    bdir = _PROJECT_ROOT / config.execution.get("backup_dir", "backups")
    bdir.mkdir(parents=True, exist_ok=True)
    return bdir


def snapshot(original_path: Path, execution_id: int | None = None) -> Path:
    """
    Copy *original_path* into the backup directory.

    Returns the backup path.
    Raises if the file cannot be read.
    """
    if not original_path.exists():
        raise FileNotFoundError(f"Cannot snapshot non-existent file: {original_path}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    safe_name = original_path.name.replace(" ", "_")
    backup_path = _backup_dir() / f"{safe_name}.{ts}.bak"

    shutil.copy2(original_path, backup_path)
    log.info("Snapshot: %s → %s", original_path, backup_path)

    _record_snapshot(str(original_path), str(backup_path), execution_id)
    return backup_path


def rollback(snapshot_id: int) -> bool:
    """
    Restore the original file from the snapshot identified by *snapshot_id*.

    Returns True on success.
    """
    with get_connection() as con:
        row = con.execute(
            "SELECT * FROM rollback_snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()

    if not row:
        log.error("Snapshot id %d not found.", snapshot_id)
        return False

    backup_path = Path(row["backup_path"])
    original_path = Path(row["original_path"])

    if not backup_path.exists():
        log.error("Backup file missing: %s", backup_path)
        return False

    original_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, original_path)
    log.info("Rollback: %s → %s", backup_path, original_path)

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as con:
        con.execute(
            "UPDATE rollback_snapshots SET rolled_back=1, rolled_back_at=? WHERE id=?",
            (now, snapshot_id),
        )

    return True


def list_snapshots(execution_id: int | None = None) -> list[dict]:
    """Return rollback snapshots, optionally filtered by execution_id."""
    with get_connection() as con:
        if execution_id is not None:
            rows = con.execute(
                "SELECT * FROM rollback_snapshots WHERE execution_id=? ORDER BY snapshot_at DESC",
                (execution_id,),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM rollback_snapshots ORDER BY snapshot_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def _record_snapshot(
    original_path: str, backup_path: str, execution_id: int | None
) -> None:
    with get_connection() as con:
        con.execute(
            """
            INSERT INTO rollback_snapshots (execution_id, original_path, backup_path)
            VALUES (?, ?, ?)
            """,
            (execution_id, original_path, backup_path),
        )
