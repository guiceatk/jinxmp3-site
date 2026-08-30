"""
agent/core/secret_scanner.py — Detect and exclude secrets from indexing.

Rules are loaded from config.secret_exclusions.
"""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Iterable

from agent.core.config import Config, config as _global_config


class SecretScanner:
    """
    Tests paths and file content against secret-exclusion rules.

    Usage:
        scanner = SecretScanner()
        if scanner.is_excluded_path(Path("config/.env")):
            ...
        matches = scanner.scan_content(text)
    """

    def __init__(self, cfg: Config | None = None) -> None:
        self._cfg = cfg or _global_config
        excl = self._cfg.secret_exclusions
        self._glob_patterns: list[str] = excl.get("globs", [])
        self._content_patterns: list[re.Pattern] = [
            re.compile(p) for p in excl.get("content_patterns", [])
        ]

    # ── path-level exclusion ──────────────────────────────────────────────

    def is_excluded_path(self, path: Path) -> bool:
        """Return True if the path matches any secret-exclusion glob pattern."""
        path_str = path.as_posix()
        name = path.name
        for pattern in self._glob_patterns:
            # Test against full posix path and against filename alone
            if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(name, pattern.lstrip("*/")):
                return True
        return False

    def filter_paths(self, paths: Iterable[Path]) -> list[Path]:
        """Return only paths that are NOT excluded."""
        return [p for p in paths if not self.is_excluded_path(p)]

    # ── content-level scanning ────────────────────────────────────────────

    def scan_content(self, text: str) -> list[dict]:
        """
        Scan *text* for secret patterns.

        Returns a list of findings:
            [{"pattern": <pattern_string>, "line": <line_number>, "match": <redacted>}]
        """
        findings: list[dict] = []
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pat in self._content_patterns:
                m = pat.search(line)
                if m:
                    findings.append({
                        "pattern": pat.pattern,
                        "line": lineno,
                        "match": "[REDACTED]",   # Never log the actual secret
                    })
        return findings

    def is_clean_content(self, text: str) -> bool:
        """Return True if no secret patterns are found in *text*."""
        return len(self.scan_content(text)) == 0


# Module-level singleton
secret_scanner = SecretScanner()
