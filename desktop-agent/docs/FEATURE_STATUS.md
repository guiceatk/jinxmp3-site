# Feature Status

## ✅ Implemented and Tested

| Feature | Module | Tests |
|---|---|---|
| YAML config loading + local override | `core/config.py` | `test_config.py` |
| SQLite schema (all 7 tables) | `core/database.py` | `test_database.py` |
| Permission enforcement + audit write | `core/permissions.py` | `test_permissions.py` |
| Emergency stop (STOP file) | `core/emergency_stop.py` | `test_emergency_stop.py` |
| Secret path exclusion (globs) | `core/secret_scanner.py` | `test_secret_scanner.py` |
| Secret content scanner | `core/secret_scanner.py` | `test_secret_scanner.py` |
| Dry-run mode (global flag) | All execution modules | `test_approval_executor.py` |
| File indexer (walk + upsert) | `indexer/file_indexer.py` | `test_file_indexer.py` |
| Secret exclusion during indexing | `indexer/file_indexer.py` | `test_file_indexer.py` |
| Approval lifecycle (approve/reject/pause/disable) | `execution/approval_manager.py` | `test_approval_executor.py` |
| Execution engine (noop, file ops, run_command) | `execution/executor.py` | `test_approval_executor.py` |
| Pre-action file snapshots | `execution/rollback.py` | `test_approval_executor.py` |
| File rollback from snapshot | `execution/rollback.py` | `test_approval_executor.py` |
| Pattern detection (rename + batch) | `analysis/pattern_detector.py` | `test_approval_executor.py` |
| Script analyzer (secrets, TODO, long functions, JSON) | `analysis/script_analyzer.py` | — |
| Rotating structured log | `core/logging_setup.py` | — |
| Terminal dashboard (Rich) | `ui/dashboard.py` | — |
| Full CLI (click) | `__main__.py` | — |
| Full MVP workflow test | `tests/test_approval_executor.py` | ✅ |

## 🔶 Partially Implemented

| Feature | Status | Notes |
|---|---|---|
| Filesystem watcher | Implemented; requires `watchdog` installed | Not tested with mock (uses real watchdog) |
| Process observer | Implemented; requires `psutil` | Observe-only; no window control |
| Background daemon loop | Implemented; not covered by unit tests | Manual integration testing |
| Resource limits (CPU/mem) | Implemented in daemon loop | Not unit tested |

## ❌ Deferred (Planned, Not Yet Built)

| Feature | Phase | Notes |
|---|---|---|
| Windows Service wrapper (pywin32 serviceutil) | Phase 5 | Run as a real Windows service |
| System tray icon (pystray) | Phase 6 | Background tray with quick controls |
| Window/input control adapter | Phase 4+ | Requires `control_windows: true` |
| Clipboard observer | Phase 2 opt-in | Not built |
| Browser workflow automation | Post-MVP | Requires browser extension or CDP |
| Scheduled task creation (Task Scheduler XML) | Phase 5 | Windows-specific |
| Local LLM adapter (Ollama) | Phase 10 | After deterministic foundation is stable |
| PyQt6 GUI dashboard | Phase 6 | Terminal dashboard available now |
| Data transformation pipeline | Phase 4+ | Adapter not yet written |
| `plugins/` hot-reload system | Architecture ready | Not implemented |
