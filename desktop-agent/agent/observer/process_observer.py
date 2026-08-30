"""
agent/observer/process_observer.py — Observe running processes / applications.

Uses psutil to snapshot running processes at intervals and record
process_start / process_end events for approved applications.

Requires only permissions.observe_only (default).
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

from agent.core.config import config
from agent.core.database import get_connection
from agent.core.emergency_stop import check_stop

log = logging.getLogger("agent.observer.process")

_POLL_INTERVAL = 5  # seconds


class ProcessObserver:
    """
    Polls running processes and records start/end events for approved apps.

    Runs in a background thread started by start() / stopped by stop().
    """

    def __init__(self) -> None:
        self._cfg = config
        self._thread: threading.Thread | None = None
        self._running = False
        self._seen_pids: dict[int, str] = {}   # pid -> process name

    def start(self) -> None:
        if not _PSUTIL_AVAILABLE:
            log.warning(
                "psutil not installed — process observer disabled. "
                "Install with: pip install psutil"
            )
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._loop, name="process-observer", daemon=True
        )
        self._thread.start()
        log.info("Process observer started.")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        log.info("Process observer stopped.")

    @property
    def is_running(self) -> bool:
        return self._running

    # ── internal ──────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while self._running:
            try:
                check_stop()
                self._poll()
            except Exception as exc:
                log.error("Process observer error: %s", exc)
            time.sleep(_POLL_INTERVAL)

    def _poll(self) -> None:
        approved = {a.lower() for a in self._cfg.approved_applications}
        if not approved:
            return   # Nothing to watch

        current: dict[int, str] = {}
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info["name"] or "").lower()
                pid = proc.info["pid"]
                current[pid] = name
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Detect new processes
        for pid, name in current.items():
            if name in approved and pid not in self._seen_pids:
                log.info("Process started: %s (pid=%d)", name, pid)
                self._record_event("process_start", name, pid)

        # Detect ended processes
        for pid, name in list(self._seen_pids.items()):
            if pid not in current:
                log.info("Process ended: %s (pid=%d)", name, pid)
                self._record_event("process_end", name, pid)

        self._seen_pids = current

    def _record_event(self, event_type: str, name: str, pid: int) -> None:
        import json
        ts = datetime.now(timezone.utc).isoformat()
        try:
            with get_connection() as con:
                con.execute(
                    """
                    INSERT INTO observations
                        (event_type, application, extra_json, observed_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (event_type, name, json.dumps({"pid": pid}), ts),
                )
        except Exception as exc:
            log.error("Failed to record process event: %s", exc)
