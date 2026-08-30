"""
agent/indexer/file_indexer.py — Walk approved directories and build/refresh
the file_index table in the local database.

Only runs when permissions.read_files is True.
Respects secret_exclusions from config.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from agent.core.config import Config, config
from agent.core.database import get_connection
from agent.core.emergency_stop import check_stop
from agent.core.permissions import PermissionDenied, PermissionGuard, PermissionLevel
from agent.core.secret_scanner import SecretScanner, secret_scanner

log = logging.getLogger("agent.indexer")


class FileIndexer:
    """
    Walks each approved directory and upserts rows into file_index.

    In dry_run mode it only logs what *would* be indexed.
    """

    def __init__(self) -> None:
        self._cfg = config
        self._guard = PermissionGuard(self._cfg)
        self._scanner = SecretScanner(self._cfg)

    def run(self) -> dict:
        """
        Perform a full indexing pass.

        Returns a summary dict:
            {"indexed": int, "skipped_secrets": int, "errors": int}
        """
        check_stop()

        try:
            self._guard.check(
                PermissionLevel.READ_FILES,
                action="file_index.run",
                target="approved_directories",
            )
        except PermissionDenied as exc:
            log.warning("FileIndexer skipped — %s", exc)
            return {"indexed": 0, "skipped_secrets": 0, "errors": 0}

        approved = self._cfg.approved_directories
        if not approved:
            log.info("No approved_directories configured — nothing to index.")
            return {"indexed": 0, "skipped_secrets": 0, "errors": 0}

        total_indexed = 0
        total_skipped = 0
        total_errors = 0

        for root_dir in approved:
            i, s, e = self._index_directory(root_dir)
            total_indexed += i
            total_skipped += s
            total_errors += e

        log.info(
            "Indexing complete: %d files indexed, %d secrets skipped, %d errors",
            total_indexed, total_skipped, total_errors,
        )
        return {
            "indexed": total_indexed,
            "skipped_secrets": total_skipped,
            "errors": total_errors,
        }

    # ── internals ─────────────────────────────────────────────────────────

    def _index_directory(self, root: Path) -> tuple[int, int, int]:
        indexed = skipped = errors = 0

        if not root.exists():
            log.warning("Approved directory does not exist: %s", root)
            return 0, 0, 0

        log.info("Indexing directory: %s", root)

        for dirpath, dirnames, filenames in os.walk(root):
            check_stop()

            current_dir = Path(dirpath)

            # Filter excluded subdirs in-place (prevents descent)
            dirnames[:] = [
                d for d in dirnames
                if not self._scanner.is_excluded_path(current_dir / d)
            ]

            for filename in filenames:
                filepath = current_dir / filename

                if self._scanner.is_excluded_path(filepath):
                    log.debug("Secret exclusion — skipping: %s", filepath)
                    skipped += 1
                    continue

                try:
                    stat = filepath.stat()
                    mtime = datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat()
                    size = stat.st_size
                    ftype = filepath.suffix.lower() or "no_ext"

                    if self._cfg.dry_run:
                        log.debug("[DRY-RUN] Would index: %s  (%d bytes)", filepath, size)
                    else:
                        self._upsert(str(filepath), size, mtime, ftype)

                    indexed += 1

                except OSError as exc:
                    log.warning("Could not stat %s: %s", filepath, exc)
                    errors += 1

        return indexed, skipped, errors

    def _upsert(
        self, path: str, size: int, modified_at: str, file_type: str
    ) -> None:
        with get_connection() as con:
            con.execute(
                """
                INSERT INTO file_index (path, size_bytes, modified_at, file_type, indexed_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(path) DO UPDATE SET
                    size_bytes  = excluded.size_bytes,
                    modified_at = excluded.modified_at,
                    file_type   = excluded.file_type,
                    indexed_at  = excluded.indexed_at
                """,
                (path, size, modified_at, file_type),
            )

    def get_index(self) -> list[dict]:
        """Return all rows from file_index as a list of dicts."""
        with get_connection() as con:
            rows = con.execute(
                "SELECT path, size_bytes, modified_at, file_type, indexed_at "
                "FROM file_index ORDER BY indexed_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]
