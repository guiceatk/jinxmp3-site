# Architecture

## Component Map

```
desktop-agent/
├── agent/
│   ├── core/
│   │   ├── config.py           Load & merge YAML config
│   │   ├── database.py         SQLite schema + connection context manager
│   │   ├── permissions.py      Permission enforcement + audit writes
│   │   ├── emergency_stop.py   STOP file read/write
│   │   ├── secret_scanner.py   Path/content exclusion rules
│   │   ├── logging_setup.py    Rotating file + console logger
│   │   └── daemon.py           Main orchestration loop
│   ├── indexer/
│   │   └── file_indexer.py     Walk approved dirs → file_index table
│   ├── observer/
│   │   ├── fs_watcher.py       watchdog → observations table
│   │   └── process_observer.py psutil → observations table
│   ├── analysis/
│   │   ├── pattern_detector.py Queries observations → automations proposals
│   │   └── script_analyzer.py  Static analysis of scripts
│   ├── execution/
│   │   ├── approval_manager.py Approve/reject/pause/disable automations
│   │   ├── executor.py         Execute approved automations (file ops, commands)
│   │   └── rollback.py         Snapshot + restore files
│   ├── ui/
│   │   └── dashboard.py        Rich terminal live dashboard
│   └── __main__.py             Click CLI entrypoint
├── config/
│   ├── default.yaml            Shipped defaults (committed)
│   └── local.yaml              Per-machine overrides (git-ignored)
├── tests/
├── docs/
├── logs/                       Rotating log files (git-ignored)
└── backups/                    Pre-action file snapshots (git-ignored)
```

## Data Flow

```
Filesystem events
    └─► fs_watcher ──────────────────────► observations table
Process events
    └─► process_observer ────────────────► observations table
                                                │
                                         pattern_detector
                                                │
                                         automations table (PENDING_APPROVAL)
                                                │
                                    ◄── User: approve/reject ───►
                                                │
                                         executor.run()
                                                │
                              ┌─────────────────┼─────────────────┐
                          snapshot           execute           audit_log
                        (rollback)        (file/cmd)
```

## Database Schema

| Table | Purpose |
|---|---|
| `file_index` | Snapshot of indexed files |
| `observations` | Raw filesystem/process events |
| `automations` | Proposed and approved workflows |
| `approvals` | Decision history per automation |
| `executions` | Every run attempt with result |
| `audit_log` | Immutable append-only action log |
| `rollback_snapshots` | Pre-action file backups |

## Permission Levels (in escalating order)

1. `observe_only` — watch filesystem events (default ON)
2. `read_files` — read file contents for indexing/analysis
3. `modify_files` — copy/move/rename/delete files
4. `run_commands` — run PowerShell/CMD
5. `control_applications` — launch/close apps
6. `control_windows` — window focus/input (Windows only)
7. `manage_processes` — kill/suspend processes
8. `modify_system_settings` — registry, scheduled tasks
9. `network_access` — any outbound network calls
10. `external_actions` — off-machine effects

All are `false` by default except `observe_only`.

## Plugin / Adapter Architecture

New action types are added by:
1. Adding a handler method to `Executor._dispatch`
2. Adding a corresponding permission level check
3. Registering the new action type in `config/default.yaml` docs

New observers are added under `agent/observer/` and wired into `AgentDaemon`.
