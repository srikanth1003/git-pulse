"""``git-pulse compare`` — diff two JSON reports."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer()

EXIT_USAGE = 2


@app.callback(invoke_without_command=True)
def compare(
    before: str = typer.Argument(..., help="Path to the baseline JSON report."),
    after: str = typer.Argument(..., help="Path to the newer JSON report."),
) -> None:
    """Compare two git-pulse JSON reports and show key metric deltas."""
    console = Console()

    before_path = Path(before).expanduser()
    after_path = Path(after).expanduser()

    for p in (before_path, after_path):
        if not p.exists():
            console.print(f"[red]error:[/red] file not found: {p}")
            raise typer.Exit(EXIT_USAGE)

    try:
        b = json.loads(before_path.read_text(encoding="utf-8"))
        a = json.loads(after_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(EXIT_USAGE) from exc

    for report, label in ((b, "before"), (a, "after")):
        if "schema_version" not in report:
            console.print(f"[red]error:[/red] {label} file is not a git-pulse JSON report")
            raise typer.Exit(EXIT_USAGE)

    table = Table(title="Comparison", title_justify="left", expand=False)
    table.add_column("Metric")
    table.add_column("Before", justify="right")
    table.add_column("After", justify="right")
    table.add_column("Delta", justify="right")

    _compare_scalar(table, "Total commits", b["scope"], a["scope"], "total_commits")
    _compare_scalar(table, "Agent commits", b["attribution"], a["attribution"], "agent_commits")
    _compare_scalar(table, "Human commits", b["attribution"], a["attribution"], "human_commits")
    _compare_pct(
        table, "Agent commit share", b["attribution"], a["attribution"], "agent_commit_share"
    )
    _compare_pct(table, "Agent line share", b["attribution"], a["attribution"], "agent_line_share")
    _compare_scalar(table, "Total files", b["churn"], a["churn"], "total_files")
    _compare_scalar(table, "Total insertions", b["churn"], a["churn"], "total_insertions")
    _compare_scalar(table, "Total deletions", b["churn"], a["churn"], "total_deletions")
    _compare_pct(table, "File rework rate", b["rework"], a["rework"], "file_rework_rate")
    _compare_scalar(table, "Active days", b["velocity"], a["velocity"], "active_days")
    _compare_scalar(table, "Total sessions", b["sessions"], a["sessions"], "total_sessions")
    _compare_scalar(table, "Hotspots", b["hotspots"], a["hotspots"], "total_detected")

    if b.get("coupling") and a.get("coupling"):
        _compare_scalar(table, "Coupled pairs", b["coupling"], a["coupling"], "total_detected")

    if b.get("line_rework") and a.get("line_rework"):
        _compare_pct(
            table, "Line rework rate", b["line_rework"], a["line_rework"], "line_rework_rate"
        )

    if b.get("ownership") and a.get("ownership"):
        _compare_scalar(
            table, "Bus factor (repo)", b["ownership"], a["ownership"], "repo_bus_factor"
        )

    if b.get("risk") and a.get("risk"):
        _compare_scalar(table, "Hot-risk files", b["risk"], a["risk"], "hot_risk")

    console.print(table)


def _compare_scalar(table: Table, label: str, b: dict, a: dict, key: str) -> None:
    bv = b.get(key, 0)
    av = a.get(key, 0)
    delta = av - bv
    sign = "+" if delta > 0 else ""
    style = (
        "red"
        if delta > 0 and "rework" in label.lower()
        else ("green" if delta < 0 and "rework" in label.lower() else "")
    )
    table.add_row(
        label, str(bv), str(av), f"[{style}]{sign}{delta}[/{style}]" if style else f"{sign}{delta}"
    )


def _compare_pct(table: Table, label: str, b: dict, a: dict, key: str) -> None:
    bv = b.get(key, 0.0)
    av = a.get(key, 0.0)
    delta = av - bv
    sign = "+" if delta > 0 else ""
    table.add_row(label, f"{bv:.1%}", f"{av:.1%}", f"{sign}{delta:.1%}")
