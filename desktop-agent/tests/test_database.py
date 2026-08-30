"""tests/test_database.py"""
from __future__ import annotations


def test_init_db_creates_tables(tmp_path):
    from agent.core.database import init_db, get_connection

    db_path = tmp_path / "test.db"
    init_db(db_path)

    import sqlite3
    con = sqlite3.connect(str(db_path))
    tables = {
        r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    con.close()

    expected = {
        "file_index", "observations", "automations",
        "approvals", "executions", "audit_log", "rollback_snapshots",
    }
    assert expected.issubset(tables)


def test_get_connection_insert_and_read(tmp_path):
    from agent.core import database as db_module
    from agent.core.database import get_connection

    with get_connection() as con:
        con.execute(
            "INSERT INTO audit_log (actor, action, result, dry_run) "
            "VALUES ('test', 'test_action', 'SUCCESS', 1)"
        )

    with get_connection() as con:
        row = con.execute(
            "SELECT actor, action, result FROM audit_log WHERE action='test_action'"
        ).fetchone()

    assert row is not None
    assert row["result"] == "SUCCESS"
