"""
agent/core/emergency_stop.py — Global emergency stop mechanism.

Any module can call `check_stop()` before a sensitive operation.
The stop state is persisted as a file on disk so it survives crashes.
"""
from __future__ import annotations

from pathlib import Path

_STOP_FILE = Path(__file__).resolve().parents[2] / "STOP"


def is_stopped() -> bool:
    """Return True if the emergency stop file exists."""
    return _STOP_FILE.exists()


def check_stop() -> None:
    """Raise EmergencyStop if the stop file is present."""
    if is_stopped():
        raise EmergencyStop(
            "Emergency stop is active. "
            "Remove the STOP file to resume: "
            f"{_STOP_FILE}"
        )


def activate_stop(reason: str = "User requested emergency stop") -> None:
    """Write the stop file, halting all agent execution."""
    _STOP_FILE.write_text(reason, encoding="utf-8")


def deactivate_stop() -> None:
    """Remove the stop file, allowing the agent to resume."""
    if _STOP_FILE.exists():
        _STOP_FILE.unlink()


def stop_status() -> str:
    """Return a human-readable status string."""
    if is_stopped():
        return f"STOPPED — {_STOP_FILE.read_text(encoding='utf-8').strip()}"
    return "RUNNING"


class EmergencyStop(Exception):
    """Raised when the emergency stop file is detected."""
