"""
agent/ui/dashboard.py — Terminal dashboard using Rich.

Shows live agent state: status, pending approvals, recent observations,
execution history, resource usage, and quick-action hints.

Run with:  python -m agent dashboard
"""
from __future__ import annotations

import time
from pathlib import Path

from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def _status_panel() -> Panel:
    from agent.core.emergency_stop import stop_status
    from agent.core.config import config
    import psutil

    proc = psutil.Process()
    cpu = proc.cpu_percent(interval=0.1)
    mem_mb = proc.memory_info().rss / (1024 * 1024)
    stop = stop_status()
    dry = "[yellow]DRY-RUN[/yellow]" if config.dry_run else "[green]LIVE[/green]"

    lines = [
        f"Status : {stop}",
        f"Mode   : {dry}",
        f"CPU    : {cpu:.1f}%",
        f"Memory : {mem_mb:.1f} MB",
        f"Dirs   : {len(config.approved_directories)} approved",
    ]
    return Panel("\n".join(lines), title="Agent Status", border_style="blue")


def _pending_panel() -> Panel:
    from agent.execution.approval_manager import ApprovalManager
    rows = ApprovalManager().pending()
    t = Table("ID", "Name", "Created", box=None)
    for r in rows:
        t.add_row(str(r["id"]), (r["name"] or "")[:50], r["created_at"][:16])
    if not rows:
        return Panel("[dim]No pending approvals[/dim]", title="Pending Approvals", border_style="yellow")
    return Panel(t, title=f"Pending Approvals ({len(rows)})", border_style="yellow")


def _observations_panel(limit: int = 10) -> Panel:
    from agent.core.database import get_connection
    with get_connection() as con:
        rows = con.execute(
            "SELECT event_type, source_path, observed_at "
            "FROM observations ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    t = Table("Time", "Event", "Path", box=None)
    for r in rows:
        t.add_row(r["observed_at"][:16], r["event_type"], Path(r["source_path"] or "").name)
    if not rows:
        return Panel("[dim]No observations yet[/dim]", title="Recent Observations", border_style="cyan")
    return Panel(t, title="Recent Observations", border_style="cyan")


def _executions_panel(limit: int = 8) -> Panel:
    from agent.core.database import get_connection
    with get_connection() as con:
        rows = con.execute(
            "SELECT id, automation_id, dry_run, status, started_at "
            "FROM executions ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    t = Table("ExecID", "AutoID", "DryRun", "Status", "Started", box=None)
    for r in rows:
        colour = "green" if r["status"] == "SUCCESS" else "red"
        t.add_row(
            str(r["id"]), str(r["automation_id"]),
            "✓" if r["dry_run"] else "",
            f"[{colour}]{r['status']}[/{colour}]",
            (r["started_at"] or "")[:16],
        )
    if not rows:
        return Panel("[dim]No executions yet[/dim]", title="Execution History", border_style="magenta")
    return Panel(t, title="Execution History", border_style="magenta")


def _hints_panel() -> Panel:
    hints = (
        "[b]Commands[/b]\n"
        "  python -m agent pending       — list proposals\n"
        "  python -m agent approve <id>  — approve\n"
        "  python -m agent run <id>      — execute\n"
        "  python -m agent stop          — emergency stop\n"
        "  python -m agent audit         — audit log\n"
        "  python -m agent rollback <id> — restore file\n"
        "\nPress [bold]Ctrl+C[/bold] to exit dashboard"
    )
    return Panel(hints, title="Quick Reference", border_style="white")


def run_dashboard(refresh_seconds: int = 5) -> None:
    """Render a live-updating terminal dashboard."""
    from agent.core.config import config
    refresh = int(config.ui.get("dashboard_refresh_seconds", refresh_seconds))

    with Live(console=console, refresh_per_second=1 / refresh, screen=True) as live:
        try:
            while True:
                layout = Layout()
                layout.split_column(
                    Layout(name="top", size=9),
                    Layout(name="middle"),
                    Layout(name="bottom", size=12),
                )
                layout["top"].split_row(
                    Layout(_status_panel()),
                    Layout(_pending_panel()),
                )
                layout["middle"].split_row(
                    Layout(_observations_panel()),
                    Layout(_executions_panel()),
                )
                layout["bottom"].update(_hints_panel())
                live.update(layout)
                time.sleep(refresh)
        except KeyboardInterrupt:
            pass
