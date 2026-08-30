"""
agent/analysis/pattern_detector.py — Detect repeated sequences of file events
and propose automation candidates.

Reads from the observations table; writes proposed automations to the
automations table with status PENDING_APPROVAL.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent.core.config import config
from agent.core.database import get_connection

log = logging.getLogger("agent.analysis.pattern")


class PatternDetector:
    """
    Looks for repeated sequences in observations and generates proposals.

    Currently detects:
    - Files repeatedly modified then moved/renamed (e.g. draft → final)
    - File-type batches (same extension repeatedly created in same dir)
    """

    def __init__(self) -> None:
        self._cfg = config
        self._pd = self._cfg.pattern_detection

    def run(self) -> list[dict]:
        """
        Analyse recent observations and create PENDING_APPROVAL automation rows.

        Returns a list of created proposal dicts.
        """
        lookback_days = int(self._pd.get("lookback_days", 30))
        min_freq = int(self._pd.get("min_frequency", 3))

        since = (
            datetime.now(timezone.utc) - timedelta(days=lookback_days)
        ).isoformat()

        proposals: list[dict] = []
        proposals += self._detect_rename_patterns(since, min_freq)
        proposals += self._detect_batch_create_patterns(since, min_freq)

        if proposals:
            log.info("Pattern detector: %d new proposal(s) generated.", len(proposals))
        return proposals

    # ── rename / move pattern ─────────────────────────────────────────────

    def _detect_rename_patterns(self, since: str, min_freq: int) -> list[dict]:
        with get_connection() as con:
            rows = con.execute(
                """
                SELECT source_path, dest_path
                FROM   observations
                WHERE  event_type = 'moved'
                  AND  observed_at >= ?
                  AND  dest_path IS NOT NULL
                """,
                (since,),
            ).fetchall()

        if not rows:
            return []

        # Bucket by (source_extension, dest_extension, parent_dir)
        counter: Counter = Counter()
        for row in rows:
            src = Path(row["source_path"])
            dst = Path(row["dest_path"])
            if src.parent == dst.parent:
                key = (src.suffix.lower(), dst.suffix.lower(), str(src.parent))
                counter[key] += 1

        proposals = []
        for (src_ext, dst_ext, parent), count in counter.items():
            if count >= min_freq:
                name = f"Auto-rename {src_ext or 'files'} → {dst_ext or 'files'} in {Path(parent).name}"
                description = (
                    f"Detected {count} times: files with extension '{src_ext}' "
                    f"were renamed/moved to '{dst_ext}' inside '{parent}'. "
                    f"Would you like to automate this rename pattern?"
                )
                actions = [
                    {
                        "type": "file_rename",
                        "source_pattern": f"*{src_ext}",
                        "dest_pattern": f"*{dst_ext}",
                        "directory": parent,
                    }
                ]
                trigger = {
                    "type": "file_created",
                    "directory": parent,
                    "extension": src_ext,
                }
                proposals.append(
                    self._upsert_proposal(name, description, trigger, actions)
                )

        return [p for p in proposals if p]

    # ── batch-create pattern ──────────────────────────────────────────────

    def _detect_batch_create_patterns(self, since: str, min_freq: int) -> list[dict]:
        with get_connection() as con:
            rows = con.execute(
                """
                SELECT source_path
                FROM   observations
                WHERE  event_type = 'created'
                  AND  observed_at >= ?
                """,
                (since,),
            ).fetchall()

        if not rows:
            return []

        counter: Counter = Counter()
        for row in rows:
            p = Path(row["source_path"])
            key = (p.suffix.lower(), str(p.parent))
            counter[key] += 1

        proposals = []
        for (ext, parent), count in counter.items():
            if count >= min_freq * 3:   # higher bar for batch proposals
                name = f"Batch process {ext or 'files'} in {Path(parent).name}"
                description = (
                    f"Detected {count} new '{ext}' files created in '{parent}'. "
                    f"Would you like to create an automation to process new {ext} files automatically?"
                )
                actions = [{"type": "noop", "description": "Define processing steps"}]
                trigger = {
                    "type": "file_created",
                    "directory": parent,
                    "extension": ext,
                }
                proposals.append(
                    self._upsert_proposal(name, description, trigger, actions)
                )

        return [p for p in proposals if p]

    # ── shared ────────────────────────────────────────────────────────────

    def _upsert_proposal(
        self,
        name: str,
        description: str,
        trigger: dict,
        actions: list[dict],
    ) -> dict | None:
        """
        Insert a PENDING_APPROVAL automation row if one with the same name
        and PENDING_APPROVAL status does not already exist.
        """
        try:
            with get_connection() as con:
                existing = con.execute(
                    "SELECT id FROM automations WHERE name = ? AND status = 'PENDING_APPROVAL'",
                    (name,),
                ).fetchone()
                if existing:
                    return None   # Already proposed; don't duplicate

                cur = con.execute(
                    """
                    INSERT INTO automations
                        (name, description, trigger_json, actions_json, status)
                    VALUES (?, ?, ?, ?, 'PENDING_APPROVAL')
                    """,
                    (name, description, json.dumps(trigger), json.dumps(actions)),
                )
                row_id = cur.lastrowid
                log.info("New automation proposal: [%d] %s", row_id, name)
                return {
                    "id": row_id,
                    "name": name,
                    "description": description,
                    "status": "PENDING_APPROVAL",
                }
        except Exception as exc:
            log.error("Failed to upsert proposal '%s': %s", name, exc)
            return None
