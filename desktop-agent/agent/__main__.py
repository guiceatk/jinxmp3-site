"""
agent/__main__.py — CLI entrypoint.

Commands:
  start          Start the agent daemon (blocking)
  stop           Activate emergency stop
  resume         Remove emergency stop
  status         Show daemon / stop status
  index          Run a one-shot file indexing pass
  pending        List pending approval requests
  approve <id>   Approve an automation
  reject  <id>   Reject an automation
  pause   <id>   Pause an approved automation
  disable <id>   Permanently disable an automation
  run     <id>   Execute an approved automation (respects dry_run)
  audit          Show recent audit log entries
  snapshots      List rollback snapshots
  rollback <id>  Restore file from snapshot
  analyze        Run script analysis pass
  dashboard      Open terminal dashboard (rich)
"""
from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def main():
    """Desktop Agent — local autonomous automation daemon."""
    pass


# ── daemon control ─────────────────────────────────────────────────────────

@main.command()
def start():
    """Start the agent daemon (blocking until Ctrl+C or emergency stop)."""
    from agent.core.daemon import AgentDaemon
    from agent.core.emergency_stop import check_stop
    import signal, time

    check_stop()
    daemon = AgentDaemon()
    daemon.start()

    console.print("[green]Agent daemon running.[/green] Press Ctrl+C to stop.")

    def _shutdown(sig, frame):
        console.print("\n[yellow]Shutting down…[/yellow]")
        daemon.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while daemon.is_running:
            time.sleep(1)
    except SystemExit:
        pass


@main.command()
def stop():
    """Activate global emergency stop."""
    from agent.core.emergency_stop import activate_stop
    activate_stop("CLI stop command")
    console.print("[red]Emergency stop activated.[/red] Remove STOP file to resume.")


@main.command()
def resume():
    """Remove emergency stop so the daemon can run."""
    from agent.core.emergency_stop import deactivate_stop
    deactivate_stop()
    console.print("[green]Emergency stop removed.[/green]")


@main.command()
def status():
    """Show current agent status."""
    from agent.core.emergency_stop import stop_status
    from agent.core.config import config
    s = stop_status()
    dry = "[yellow]DRY-RUN[/yellow]" if config.dry_run else "[green]LIVE[/green]"
    console.print(f"Status : {s}")
    console.print(f"Mode   : {dry}")
    console.print(f"Approved dirs: {config.approved_directories or '(none)'}")


# ── indexer ────────────────────────────────────────────────────────────────

@main.command()
def index():
    """Run a one-shot file indexing pass."""
    from agent.indexer.file_indexer import FileIndexer
    result = FileIndexer().run()
    console.print(result)


# ── approvals ──────────────────────────────────────────────────────────────

@main.command()
def pending():
    """List pending automation proposals."""
    from agent.execution.approval_manager import ApprovalManager
    rows = ApprovalManager().pending()
    if not rows:
        console.print("[dim]No pending proposals.[/dim]")
        return
    t = Table("ID", "Name", "Description", "Created")
    for r in rows:
        t.add_row(str(r["id"]), r["name"], (r["description"] or "")[:60], r["created_at"])
    console.print(t)


@main.command()
@click.argument("automation_id", type=int)
@click.option("--notes", default="", help="Optional notes")
def approve(automation_id, notes):
    """Approve an automation proposal."""
    from agent.execution.approval_manager import ApprovalManager
    ok = ApprovalManager().approve(automation_id, notes)
    console.print("[green]Approved[/green]" if ok else "[red]Not found[/red]")


@main.command()
@click.argument("automation_id", type=int)
@click.option("--notes", default="")
def reject(automation_id, notes):
    """Reject an automation proposal."""
    from agent.execution.approval_manager import ApprovalManager
    ok = ApprovalManager().reject(automation_id, notes)
    console.print("[red]Rejected[/red]" if ok else "[red]Not found[/red]")


@main.command()
@click.argument("automation_id", type=int)
def pause(automation_id):
    """Pause an approved automation."""
    from agent.execution.approval_manager import ApprovalManager
    ok = ApprovalManager().pause(automation_id)
    console.print("[yellow]Paused[/yellow]" if ok else "[red]Not found[/red]")


@main.command()
@click.argument("automation_id", type=int)
def disable(automation_id):
    """Permanently disable an automation."""
    from agent.execution.approval_manager import ApprovalManager
    ok = ApprovalManager().disable(automation_id)
    console.print("[red]Disabled[/red]" if ok else "[red]Not found[/red]")


# ── execution ──────────────────────────────────────────────────────────────

@main.command("run")
@click.argument("automation_id", type=int)
def run_automation(automation_id):
    """Execute an approved automation (respects dry_run mode)."""
    from agent.execution.executor import Executor, ExecutionError
    try:
        result = Executor().run(automation_id)
        console.print(result)
    except ExecutionError as exc:
        console.print(f"[red]Error:[/red] {exc}")


# ── audit & rollback ───────────────────────────────────────────────────────

@main.command()
@click.option("--limit", default=20, help="Number of rows to show")
def audit(limit):
    """Show recent audit log entries."""
    from agent.core.database import get_connection
    with get_connection() as con:
        rows = con.execute(
            "SELECT timestamp, actor, action, target, result, dry_run "
            "FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    if not rows:
        console.print("[dim]Audit log is empty.[/dim]")
        return
    t = Table("Time", "Actor", "Action", "Target", "Result", "DryRun")
    for r in rows:
        t.add_row(
            r["timestamp"][:19], r["actor"], r["action"],
            (r["target"] or "")[:40], r["result"], "✓" if r["dry_run"] else ""
        )
    console.print(t)


@main.command()
def snapshots():
    """List rollback snapshots."""
    from agent.execution.rollback import list_snapshots
    rows = list_snapshots()
    if not rows:
        console.print("[dim]No snapshots.[/dim]")
        return
    t = Table("ID", "Original", "Backup", "SnapshotAt", "Rolled Back")
    for r in rows:
        t.add_row(
            str(r["id"]), Path(r["original_path"]).name,
            Path(r["backup_path"]).name, r["snapshot_at"][:19],
            "✓" if r["rolled_back"] else ""
        )
    console.print(t)


@main.command()
@click.argument("snapshot_id", type=int)
def rollback(snapshot_id):
    """Restore a file from a rollback snapshot."""
    from agent.execution.rollback import rollback as do_rollback
    from pathlib import Path
    ok = do_rollback(snapshot_id)
    console.print("[green]Rollback succeeded[/green]" if ok else "[red]Rollback failed[/red]")


# ── analysis ───────────────────────────────────────────────────────────────

@main.command()
def analyze():
    """Run script analysis on approved directories."""
    from agent.analysis.script_analyzer import ScriptAnalyzer
    findings = ScriptAnalyzer().run()
    if not findings:
        console.print("[green]No findings.[/green]")
        return
    t = Table("Path", "Type", "Line", "Message")
    for f in findings:
        t.add_row(
            Path(f["path"]).name, f["finding_type"],
            str(f["line"]), (f["message"] or "")[:80]
        )
    console.print(t)


# ── dashboard ──────────────────────────────────────────────────────────────

@main.command()
def dashboard():
    """Open the terminal dashboard."""
    from agent.ui.dashboard import run_dashboard
    run_dashboard()


if __name__ == "__main__":
    from pathlib import Path  # needed in rollback command
    main()
