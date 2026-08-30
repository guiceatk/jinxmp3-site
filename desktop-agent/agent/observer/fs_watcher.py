"""
agent/observer/fs_watcher.py — Filesystem event observer.

Uses the watchdog library to monitor approved directories and persist
events to the observations table.

Requires at least permissions.observe_only = true (no file reads).
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from watchdog.events import (
        FileCreatedEvent,
        FileDeletedEvent,
        FileModifiedEvent,
        FileMovedEvent,
        FileSystemEventHandler,
    )
    from watchdog.observers import Observer

    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False

from agent.core.config import config
from agent.core.database import get_connection
from agent.core.emergency_stop import check_stop
from agent.core.secret_scanner import secret_scanner

log = logging.getLogger("agent.observer.fs")

_MAX_EVENTS_DEFAULT = 50


class _AgentEventHandler(FileSystemEventHandler if _WATCHDOG_AVAILABLE else object):  # type: ignore[misc]
    """Watchdog handler that writes events to the observations table."""

    def __init__(self, rate_limit: int = _MAX_EVENTS_DEFAULT) -> None:
        if _WATCHDOG_AVAILABLE:
            super().__init__()
        self._rate_limit = rate_limit
        self._window_start = time.monotonic()
        self._window_count = 0
        self._lock = threading.Lock()

    def _record(self, event_type: str, src: str, dest: str | None = None) -> None:
        check_stop()

        src_path = Path(src)
        if secret_scanner.is_excluded_path(src_path):
            return
        if dest and secret_scanner.is_excluded_path(Path(dest)):
            return

        # Rate limiting
        with self._lock:
            now = time.monotonic()
            if now - self._window_start >= 1.0:
                self._window_start = now
                self._window_count = 0
            if self._window_count >= self._rate_limit:
                log.debug("Rate limit reached — dropping event %s %s", event_type, src)
                return
            self._window_count += 1

        ts = datetime.now(timezone.utc).isoformat()
        log.debug("FS event: %s  %s", event_type, src)

        try:
            with get_connection() as con:
                con.execute(
                    """
                    INSERT INTO observations
                        (event_type, source_path, dest_path, observed_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (event_type, str(src_path), dest, ts),
                )
        except Exception as exc:
            log.error("Failed to record observation: %s", exc)

    # ── watchdog callbacks ────────────────────────────────────────────────

    def on_created(self, event):
        if not event.is_directory:
            self._record("created", event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._record("modified", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self._record("deleted", event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._record("moved", event.src_path, event.dest_path)


class FilesystemWatcher:
    """
    Starts and stops watchdog observers for all approved directories.

    Usage:
        watcher = FilesystemWatcher()
        watcher.start()
        ...
        watcher.stop()
    """

    def __init__(self) -> None:
        self._cfg = config
        self._observer: "Observer | None" = None
        self._running = False

    def start(self) -> None:
        if not _WATCHDOG_AVAILABLE:
            log.warning(
                "watchdog library not installed — filesystem watching disabled. "
                "Install it with: pip install watchdog"
            )
            return

        approved = self._cfg.approved_directories
        if not approved:
            log.info("No approved_directories — filesystem watcher not started.")
            return

        rate_limit = self._cfg.agent.get("max_events_per_second", _MAX_EVENTS_DEFAULT)
        handler = _AgentEventHandler(rate_limit=int(rate_limit))

        self._observer = Observer()
        for d in approved:
            if d.exists():
                self._observer.schedule(handler, str(d), recursive=True)
                log.info("Watching: %s", d)
            else:
                log.warning("Approved directory not found, skipping watch: %s", d)

        self._observer.start()
        self._running = True
        log.info("Filesystem watcher started.")

    def stop(self) -> None:
        if self._observer and self._running:
            self._observer.stop()
            self._observer.join()
            self._running = False
            log.info("Filesystem watcher stopped.")

    @property
    def is_running(self) -> bool:
        return self._running
