"""
agent/analysis/script_analyzer.py — Static analysis of scripts in approved dirs.

Scans .py, .ps1, .bat, .sh, .json files for:
  - Hardcoded secrets (via SecretScanner)
  - TODO/FIXME/HACK markers
  - Very long functions (complexity proxy)
  - Duplicate shebang / import blocks (heuristic)

Reports findings without modifying any file.
Requires permissions.read_files.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from agent.core.config import config
from agent.core.emergency_stop import check_stop
from agent.core.permissions import PermissionDenied, PermissionLevel, permission_guard
from agent.core.secret_scanner import secret_scanner

log = logging.getLogger("agent.analysis.script")

_ANALYSABLE_EXTENSIONS = {".py", ".ps1", ".bat", ".sh", ".json", ".yaml", ".yml"}
_TODO_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
_MAX_FUNCTION_LINES = 80


class ScriptAnalyzer:
    """
    Reads and analyses scripts in approved directories.

    Returns a list of findings (never writes to disk).
    """

    def run(self) -> list[dict[str, Any]]:
        """
        Analyse all approved scripts.

        Returns a list of finding dicts:
            {path, finding_type, line, message}
        """
        check_stop()

        try:
            permission_guard.check(
                PermissionLevel.READ_FILES,
                action="script_analyzer.run",
                target="approved_directories",
            )
        except PermissionDenied as exc:
            log.warning("ScriptAnalyzer skipped — %s", exc)
            return []

        all_findings: list[dict] = []

        for root_dir in config.approved_directories:
            if not root_dir.exists():
                continue
            for dirpath, _dirs, filenames in os.walk(root_dir):
                check_stop()
                for fname in filenames:
                    fpath = Path(dirpath) / fname
                    if fpath.suffix.lower() not in _ANALYSABLE_EXTENSIONS:
                        continue
                    if secret_scanner.is_excluded_path(fpath):
                        continue
                    findings = self._analyse_file(fpath)
                    all_findings.extend(findings)

        log.info("Script analysis complete: %d findings.", len(all_findings))
        return all_findings

    # ── per-file analysis ─────────────────────────────────────────────────

    def _analyse_file(self, path: Path) -> list[dict]:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            log.warning("Could not read %s: %s", path, exc)
            return []

        findings: list[dict] = []
        lines = text.splitlines()

        # 1. Secret patterns
        for hit in secret_scanner.scan_content(text):
            findings.append({
                "path": str(path),
                "finding_type": "hardcoded_secret",
                "line": hit["line"],
                "message": f"Possible secret matched pattern: {hit['pattern']}",
            })

        # 2. TODO/FIXME markers
        for lineno, line in enumerate(lines, start=1):
            m = _TODO_PATTERN.search(line)
            if m:
                findings.append({
                    "path": str(path),
                    "finding_type": "todo_marker",
                    "line": lineno,
                    "message": f"Unresolved marker: {m.group(0)} — {line.strip()[:80]}",
                })

        # 3. Long functions (Python only)
        if path.suffix == ".py":
            findings += self._detect_long_functions(path, lines)

        # 4. JSON validity
        if path.suffix == ".json":
            findings += self._check_json(path, text)

        return findings

    def _detect_long_functions(self, path: Path, lines: list[str]) -> list[dict]:
        findings = []
        func_start: int | None = None
        func_name: str = ""
        _def = re.compile(r"^\s*(def|async def)\s+(\w+)")
        for lineno, line in enumerate(lines, start=1):
            m = _def.match(line)
            if m:
                if func_start is not None:
                    length = lineno - func_start
                    if length > _MAX_FUNCTION_LINES:
                        findings.append({
                            "path": str(path),
                            "finding_type": "long_function",
                            "line": func_start,
                            "message": (
                                f"Function '{func_name}' is {length} lines long "
                                f"(threshold: {_MAX_FUNCTION_LINES}). "
                                "Consider refactoring."
                            ),
                        })
                func_start = lineno
                func_name = m.group(2)
        return findings

    def _check_json(self, path: Path, text: str) -> list[dict]:
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            return [{
                "path": str(path),
                "finding_type": "invalid_json",
                "line": exc.lineno,
                "message": f"JSON parse error: {exc.msg}",
            }]
        return []
