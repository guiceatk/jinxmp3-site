# Desktop Agent

A **local-first autonomous desktop agent** for Windows that observes, proposes, and executes automations — always with your explicit approval.

> **Important:** This project must live in its **own private repository**, never in a public website repo. No local state, databases, logs, or configs should ever be pushed to a public host.

---

## Quick Start

```powershell
# 1. Clone the repo to your Windows machine
git clone <your-private-repo> C:\DesktopAgent
cd C:\DesktopAgent\desktop-agent

# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Install
pip install -e ".[dev]"

# 4. Copy default config and edit for your machine
copy config\default.yaml config\local.yaml
notepad config\local.yaml

# 5. Run in dry-run mode (default — safe, no changes)
python -m agent status
python -m agent start
```

---

## Core Commands

| Command | Description |
|---|---|
| `python -m agent start` | Start daemon (blocking) |
| `python -m agent stop` | Activate emergency stop |
| `python -m agent resume` | Remove emergency stop |
| `python -m agent status` | Show status and mode |
| `python -m agent index` | Re-index approved directories |
| `python -m agent pending` | List proposals awaiting approval |
| `python -m agent approve <id>` | Approve a proposal |
| `python -m agent reject <id>` | Reject a proposal |
| `python -m agent pause <id>` | Pause an automation |
| `python -m agent disable <id>` | Permanently disable |
| `python -m agent run <id>` | Execute approved automation |
| `python -m agent audit` | View audit log |
| `python -m agent snapshots` | List rollback snapshots |
| `python -m agent rollback <id>` | Restore file from snapshot |
| `python -m agent analyze` | Analyse scripts in approved dirs |
| `python -m agent dashboard` | Open terminal dashboard |

---

## Run Tests

```powershell
pytest
```

---

## Configuration

Edit `config/local.yaml` (never committed). See `config/default.yaml` for all options.

**Minimum to get started:**

```yaml
agent:
  dry_run: false   # change from true only when ready

approved_directories:
  - "C:\\Projects\\MyWork"

permissions:
  observe_only: true
  read_files: true
  # enable others only when you need them:
  # modify_files: true
  # run_commands: true
```

---

## Safety

- Default mode is **dry-run** — nothing is ever modified
- All actions require a permission in config + your explicit approval
- Every action is written to `audit_log` in the database
- Files are snapshotted before any destructive operation
- Emergency stop: `python -m agent stop` (or create a file named `STOP` next to `agent.db`)
- Secrets are automatically excluded from indexing

---

## Architecture

See `docs/ARCHITECTURE.md`.

## Threat Model

See `docs/THREAT_MODEL.md`.

## Feature Status

See `docs/FEATURE_STATUS.md`.
