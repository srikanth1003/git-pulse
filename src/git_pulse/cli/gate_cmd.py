"""``git-pulse gate`` — exit non-zero if metrics exceed thresholds.

Designed for CI: run after ``analyze --json`` or inline. Each threshold
is optional; only enabled checks can fail the gate.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console

from git_pulse.config import ConfigError, load_config
from git_pulse.gitlayer.cache import HistoryCache
from git_pulse.gitlayer.collect import CollectOptions
from git_pulse.gitlayer.repo import GitError, NotARepositoryError
from git_pulse.render.json_output import render_json
from git_pulse.report.builder import build_report

app = typer.Typer()

EXIT_GATE_FAIL = 1
EXIT_USAGE = 2


@app.callback(invoke_without_command=True)
def gate(
    path: str = typer.Option(".", help="Path to a git repository."),
    report_file: str | None = typer.Option(
        None, "--report", help="Read from a JSON report file instead of analyzing."
    ),
    max_agent_share: float | None = typer.Option(
        None, help="Fail if agent commit share exceeds this (0.0-1.0)."
    ),
    max_rework: float | None = typer.Option(
        None, help="Fail if file rework rate exceeds this (0.0-1.0)."
    ),
    min_bus_factor: int | None = typer.Option(None, help="Fail if repo bus factor is below this."),
    max_hot_risk: int | None = typer.Option(None, help="Fail if hot-risk file count exceeds this."),
    max_line_rework: float | None = typer.Option(
        None, help="Fail if per-line rework rate exceeds this (0.0-1.0)."
    ),
    days: int | None = typer.Option(None, help="Analyze the last N days (ignored with --report)."),
    config_path: str | None = typer.Option(None, "--config", help="Path to a config file."),
) -> None:
    """Check metrics against thresholds. Exits 0 if all pass, 1 if any fail."""
    console = Console(stderr=True)

    if not any([max_agent_share, max_rework, min_bus_factor, max_hot_risk, max_line_rework]):
        console.print("[yellow]warning:[/yellow] no thresholds set; gate always passes")

    data = _load_report(report_file, path, days, config_path, console)

    failures: list[str] = []

    if max_agent_share is not None:
        actual = data.get("attribution", {}).get("agent_commit_share", 0.0)
        if actual > max_agent_share:
            failures.append(f"agent_commit_share {actual:.1%} > {max_agent_share:.1%}")

    if max_rework is not None:
        actual = data.get("rework", {}).get("file_rework_rate", 0.0)
        if actual > max_rework:
            failures.append(f"file_rework_rate {actual:.1%} > {max_rework:.1%}")

    if max_line_rework is not None:
        lr = data.get("line_rework")
        if lr:
            actual = lr.get("line_rework_rate", 0.0)
            if actual > max_line_rework:
                failures.append(f"line_rework_rate {actual:.1%} > {max_line_rework:.1%}")

    if min_bus_factor is not None:
        ownership = data.get("ownership")
        if ownership:
            actual = ownership.get("repo_bus_factor", 0)
            if actual < min_bus_factor:
                failures.append(f"bus_factor {actual} < {min_bus_factor}")

    if max_hot_risk is not None:
        risk = data.get("risk")
        if risk:
            actual = risk.get("hot_risk", 0)
            if actual > max_hot_risk:
                failures.append(f"hot_risk {actual} > {max_hot_risk}")

    if failures:
        console.print(
            f"[red]GATE FAILED[/red] ({len(failures)} threshold{'s' if len(failures) > 1 else ''} exceeded)"
        )
        for f in failures:
            console.print(f"  [red]✗[/red] {f}")
        raise typer.Exit(EXIT_GATE_FAIL)

    console.print("[green]GATE PASSED[/green] — all thresholds met")


def _load_report(
    report_file: str | None,
    path: str,
    days: int | None,
    config_path: str | None,
    console: Console,
) -> dict:
    if report_file:
        p = Path(report_file).expanduser()
        if not p.exists():
            console.print(f"[red]error:[/red] report file not found: {p}")
            raise typer.Exit(EXIT_USAGE)
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            console.print(f"[red]error:[/red] {exc}")
            raise typer.Exit(EXIT_USAGE) from exc

    repo_path = Path(path).expanduser()
    try:
        config = load_config(config_path=config_path, repo_path=str(repo_path))
    except ConfigError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(EXIT_USAGE) from exc

    options = CollectOptions(
        days=days if days else config.default_days,
        exclude=tuple(config.exclude),
    )

    console.print("[dim]Reading history…[/dim]")
    try:
        report = build_report(
            repo_path, config, options=options, cache=HistoryCache(repo_path), now=datetime.now(UTC)
        )
    except (NotARepositoryError, GitError) as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(EXIT_USAGE) from exc

    return json.loads(render_json(report, indent=None))
