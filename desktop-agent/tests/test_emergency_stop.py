"""tests/test_emergency_stop.py"""
from __future__ import annotations


def test_not_stopped_by_default(_temp_stop_file):
    from agent.core.emergency_stop import is_stopped
    assert not is_stopped()


def test_activate_stop(_temp_stop_file):
    from agent.core.emergency_stop import activate_stop, is_stopped
    activate_stop("test reason")
    assert is_stopped()


def test_deactivate_stop(_temp_stop_file):
    from agent.core.emergency_stop import activate_stop, deactivate_stop, is_stopped
    activate_stop("test")
    deactivate_stop()
    assert not is_stopped()


def test_check_stop_raises(_temp_stop_file):
    from agent.core.emergency_stop import activate_stop, check_stop, EmergencyStop
    activate_stop("halt")
    try:
        check_stop()
        assert False, "Should have raised"
    except EmergencyStop:
        pass


def test_stop_status(_temp_stop_file):
    from agent.core.emergency_stop import activate_stop, stop_status
    activate_stop("reason x")
    s = stop_status()
    assert "STOPPED" in s
    assert "reason x" in s
