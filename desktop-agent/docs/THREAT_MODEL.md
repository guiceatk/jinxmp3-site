# Threat Model

## What this agent accesses

| Data | Accessed? | How controlled |
|---|---|---|
| Files in approved directories | Yes (read, optionally write) | `approved_directories` allowlist; `secret_exclusions` |
| Files outside approved directories | Never | `require_approved_path` enforced in every file op |
| Credentials, keys, tokens | Never | Secret exclusion globs + content regex applied before indexing |
| Browser profiles, cookies | Never | Excluded by default globs |
| Clipboard | Only with explicit opt-in | Clipboard observer not enabled by default |
| Running process list | Yes (names/PIDs only for approved apps) | `approved_applications` allowlist |
| Network | Never (default) | `network_access: false` by default |
| External services | Never | `external_actions: false` by default |

## What leaves the machine

**Nothing by default.** The agent is entirely local:
- No telemetry
- No cloud APIs called
- No automatic pushes to GitHub or any service
- The SQLite database stays on-disk only

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Automation executes destructive action | `backup_before_destructive: true`; rollback available; dry-run default |
| Agent indexes a secrets file | Secret exclusion globs + content scanner |
| Runaway automation consumes resources | CPU% and memory caps enforced per cycle |
| Emergency stop not respected | All execution paths check STOP file before acting |
| Config file modified to grant excessive permissions | Config is plain YAML — user must consciously change it; audit log records all permission checks |
| Command injection via automation actions | Commands must be in `approved_commands` allowlist; args passed as list to subprocess (no shell=True) |
| Long-running command hangs | `command_timeout_seconds` enforced |
| Automation silently overwrites important file | Snapshot taken before every destructive op; rollback available via CLI |
| Agent crashes mid-execution | Execution status left as RUNNING/UNKNOWN in DB, not SUCCESS |

## Unknown / unresolved risks

- Window control (`pywin32`) could theoretically interact with password prompts — disabled by default and opt-in
- `psutil` process listing exposes process names system-wide (names only, not contents)
- Long-term pattern storage could accumulate sensitive filenames — addressed by secret_exclusions but not 100% guaranteed for all naming conventions

## Not in scope (MVP)

- Browser automation (requires separate explicit opt-in and browser extension)
- Scheduled task creation (deferred to Phase 5+)
- Local LLM integration (deferred)
- Multi-user or networked deployments
