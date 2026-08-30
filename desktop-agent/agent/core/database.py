"""
agent/core/database.py — SQLite schema creation and connection management.

All persistent agent state lives in a single SQLite file (agent.db by default).
The schema is documented here; never mutate it outside this module.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

_DEFAULT_DB = Path(__file__).resolve().parents[2] / "agent.db"

# ── DDL ───────────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ── file_index ──────────────────────────────────────────────────────────────
-- Snapshot of approved files at last indexing run.
CREATE TABLE IF NOT EXISTS file_index (
    id          INTEGER PRIMARY KEY,
    path        TEXT    NOT NULL UNIQUE,
    size_bytes  INTEGER,
    modified_at TEXT,           -- ISO-8601
    file_type   TEXT,           -- extension or 'directory'
    indexed_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── observations ────────────────────────────────────────────────────────────
-- Raw events observed from the filesystem / OS.
CREATE TABLE IF NOT EXISTS observations (
    id           INTEGER PRIMARY KEY,
    event_type   TEXT NOT NULL,   -- created | modified | deleted | moved | process_start | process_end
    source_path  TEXT,
    dest_path    TEXT,            -- for move events
    application  TEXT,
    extra_json   TEXT,            -- arbitrary JSON payload
    observed_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_observations_event_type  ON observations(event_type);
CREATE INDEX IF NOT EXISTS idx_observations_observed_at ON observations(observed_at);

-- ── automations ─────────────────────────────────────────────────────────────
-- Proposed or approved automation workflows.
CREATE TABLE IF NOT EXISTS automations (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL,
    description     TEXT,           -- plain-language summary
    trigger_json    TEXT,           -- JSON: what triggers this automation
    actions_json    TEXT,           -- JSON: ordered list of action steps
    status          TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',
                    -- PENDING_APPROVAL | APPROVED | REJECTED | PAUSED | DISABLED
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    approved_at     TEXT,
    approved_by     TEXT
);

-- ── approvals ───────────────────────────────────────────────────────────────
-- Approval decisions for automation proposals.
CREATE TABLE IF NOT EXISTS approvals (
    id             INTEGER PRIMARY KEY,
    automation_id  INTEGER NOT NULL REFERENCES automations(id),
    decision       TEXT NOT NULL,   -- APPROVED | REJECTED | EDIT
    notes          TEXT,
    decided_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── executions ──────────────────────────────────────────────────────────────
-- Record of every automation execution attempt.
CREATE TABLE IF NOT EXISTS executions (
    id              INTEGER PRIMARY KEY,
    automation_id   INTEGER REFERENCES automations(id),
    dry_run         INTEGER NOT NULL DEFAULT 1,   -- 1 = dry run, 0 = real
    status          TEXT NOT NULL DEFAULT 'UNKNOWN',
                    -- PENDING | RUNNING | SUCCESS | FAILED | ROLLED_BACK | UNKNOWN
    started_at      TEXT,
    finished_at     TEXT,
    output_json     TEXT,    -- JSON: stdout, stderr, return_code per step
    error_message   TEXT
);

-- ── audit_log ───────────────────────────────────────────────────────────────
-- Immutable append-only record of everything the agent did or attempted.
CREATE TABLE IF NOT EXISTS audit_log (
    id             INTEGER PRIMARY KEY,
    timestamp      TEXT NOT NULL DEFAULT (datetime('now')),
    actor          TEXT NOT NULL DEFAULT 'agent',  -- 'agent' | 'user' | 'system'
    action         TEXT NOT NULL,   -- human-readable action name
    target         TEXT,            -- file path, process name, etc.
    parameters_json TEXT,           -- JSON of exact parameters used
    result         TEXT,            -- SUCCESS | FAILED | DRY_RUN | SKIPPED | UNKNOWN
    dry_run        INTEGER NOT NULL DEFAULT 1,
    approval_required INTEGER NOT NULL DEFAULT 0,
    execution_id   INTEGER REFERENCES executions(id),
    notes          TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);

-- ── rollback_snapshots ──────────────────────────────────────────────────────
-- Pre-change snapshots enabling file-level rollback.
CREATE TABLE IF NOT EXISTS rollback_snapshots (
    id             INTEGER PRIMARY KEY,
    execution_id   INTEGER REFERENCES executions(id),
    original_path  TEXT NOT NULL,
    backup_path    TEXT NOT NULL,    -- absolute path to the backup copy
    snapshot_at    TEXT NOT NULL DEFAULT (datetime('now')),
    rolled_back    INTEGER NOT NULL DEFAULT 0,
    rolled_back_at TEXT
);
"""


def init_db(db_path: Path | None = None) -> Path:
    """Create the database and apply the schema.  Returns the DB path used."""
    path = db_path or _DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    try:
        con.executescript(_SCHEMA_SQL)
        con.commit()
    finally:
        con.close()
    return path


@contextmanager
def get_connection(db_path: Path | None = None):
    """Context manager that yields an open sqlite3.Connection with row_factory set."""
    path = db_path or _DEFAULT_DB
    if not path.exists():
        init_db(path)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
