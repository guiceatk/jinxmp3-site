"""
agent/core/daemon.py — Main agent daemon loop.

Coordinates all subsystems:
  - FilesystemWatcher (always running)
  - ProcessObserver   (always running)
  - FileIndexer       (periodic)
  - PatternDetector   (periodic)

Respects emergency stop and resource limits.
"""
from __future__ import annotations

import logging
import threading
import time

import psutil

from agent.core.config import config
from agent.core.emergency_stop import check_stop, is_stopped
from agent.core.logging_setup import logger
from agent.indexer.file_indexer import FileIndexer
from agent.observer.fs_watcher import FilesystemWatcher
from agent.observer.process_observer import ProcessObserver
from agent.analysis.pattern_detector import PatternDetector

log = logging.getLogger("agent.daemon")

_RESOURCE_CHECK_INTERVAL = 10   # seconds


class AgentDaemon:
    """
    Orchestrates the agent subsystems.

    Usage:
        daemon = AgentDaemon()
        daemon.start()          # non-blocking; returns immediately
        daemon.stop()
    """

    def __init__(self) -> None:
        self._cfg = config
        self._fs_watcher = FilesystemWatcher()
        self._proc_observer = ProcessObserver()
        self._indexer = FileIndexer()
        self._pattern_detector = PatternDetector()

        self._running = False
        self._main_thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        check_stop()
        log.info("Agent daemon starting…")

        self._fs_watcher.start()
        self._proc_observer.start()

        # Initial index pass
        self._indexer.run()

        self._running = True
        self._main_thread = threading.Thread(
            target=self._loop, name="agent-daemon", daemon=True
        )
        self._main_thread.start()
        log.info("Agent daemon started. dry_run=%s", self._cfg.dry_run)

    def stop(self) -> None:
        log.info("Agent daemon stopping…")
        self._running = False
        self._fs_watcher.stop()
        self._proc_observer.stop()
        if self._main_thread:
            self._main_thread.join(timeout=15)
        log.info("Agent daemon stopped.")

    # ── main loop ─────────────────────────────────────────────────────────

    def _loop(self) -> None:
        analysis_interval = int(
            self._cfg.agent.get("analysis_interval_seconds", 300)
        )
        last_analysis = 0.0
        last_resource_check = 0.0

        while self._running:
            now = time.monotonic()

            if is_stopped():
                log.warning("Emergency stop detected — shutting down daemon.")
                self._running = False
                break

            # Resource limit check
            if now - last_resource_check >= _RESOURCE_CHECK_INTERVAL:
                self._check_resources()
                last_resource_check = now

            # Periodic analysis + indexing
            if now - last_analysis >= analysis_interval:
                try:
                    self._indexer.run()
                    self._pattern_detector.run()
                except Exception as exc:
                    log.error("Periodic analysis error: %s", exc)
                last_analysis = now

            time.sleep(1)

    def _check_resources(self) -> None:
        max_cpu = float(self._cfg.agent.get("max_cpu_percent", 10))
        max_mem_mb = float(self._cfg.agent.get("max_memory_mb", 256))

        proc = psutil.Process()
        cpu = proc.cpu_percent(interval=0.1)
        mem_mb = proc.memory_info().rss / (1024 * 1024)

        if cpu > max_cpu:
            log.warning(
                "CPU usage %.1f%% exceeds limit %.1f%% — analysis paused for 30s",
                cpu, max_cpu,
            )
            time.sleep(30)

        if mem_mb > max_mem_mb:
            log.warning(
                "Memory %.1fMB exceeds limit %.1fMB",
                mem_mb, max_mem_mb,
            )
