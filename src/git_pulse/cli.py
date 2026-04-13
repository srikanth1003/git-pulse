from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from git_pulse.config import load_config

app = typer.Typer(
    name="git-pulse",
    help="Analyze git repo history for development hotspots with LLM-powered insights.",
    no_args_is_help=True,
)

console = Console()


@app.command()
def version():
    """Show version information."""
    console.print("git-pulse version 0.1.0")


@app.command()
def analyze(
    path: str = typer.Argument(".", help="Path to a git repository"),
    days: Optional[int] = typer.Option(None, help="Analyze last N days of history"),
    commits: Optional[int] = typer.Option(None, help="Analyze last N commits"),
    branch: Optional[str] = typer.Option(None, help="Branch to analyze (default: current)"),
    include: Optional[list[str]] = typer.Option(None, help="Only analyze files matching glob"),
    exclude: Optional[list[str]] = typer.Option(None, help="Skip files matching glob"),
    max_hotspots: Optional[int] = typer.Option(None, help="Max hotspots to send to LLM"),
    model: Optional[str] = typer.Option(None, help="LiteLLM model string"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON instead of terminal"),
    output: Optional[str] = typer.Option(None, help="Write report to file"),
    verbose: bool = typer.Option(False, help="Show collector metrics before LLM analysis"),
    config: Optional[str] = typer.Option(None, help="Path to config file"),
) -> None:
    """Analyze a git repository for development hotspots and get LLM-powered insights."""
    repo_path = Path(path).resolve()

    # Validate repo
    if not repo_path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {repo_path}")
        raise typer.Exit(1)
    if not (repo_path / ".git").exists():
        console.print(f"[red]Error:[/red] Not a git repository: {repo_path}")
        raise typer.Exit(1)

    # Load config
    cfg = load_config(config_path=config, repo_path=str(repo_path))
    effective_days = days or (None if commits else cfg.default_days)
    effective_max_hotspots = max_hotspots or cfg.max_hotspots
    effective_model = model or cfg.model
    effective_exclude = (exclude or []) + cfg.exclude

    # Collect
    from git_pulse.collector.git_history import GitHistoryCollector
    from git_pulse.collector.hotspot_detector import HotspotDetector
    from git_pulse.collector.metrics import MetricsCalculator
    from git_pulse.collector.models import CollectorReport

    if not json_output:
        console.print("[dim]Collecting git history...[/dim]")

    collector = GitHistoryCollector(str(repo_path), branch=branch)
    commit_data = collector.collect(
        days=effective_days,
        commits=commits,
        include=include,
        exclude=effective_exclude,
    )

    if not commit_data:
        console.print("[yellow]No commits found in the specified range.[/yellow]")
        raise typer.Exit(0)

    # Detect hotspots
    detector = HotspotDetector(commit_data, max_hotspots=effective_max_hotspots)
    hotspots = detector.detect()

    # Calculate metrics
    calc = MetricsCalculator(commit_data)
    file_churn = calc.file_churn()
    change_velocity = calc.change_velocity()
    agent_human_ratio = calc.agent_human_ratio()
    rework_rate = calc.rework_rate()
    sessions = calc.sessions()

    from datetime import datetime

    timestamps = [datetime.fromisoformat(c["timestamp"]) for c in commit_data]

    collector_report = CollectorReport(
        repo_path=str(repo_path),
        branch=branch or collector.branch,
        commit_range=(commit_data[-1]["hash"][:8], commit_data[0]["hash"][:8]),
        time_range=(min(timestamps), max(timestamps)),
        total_commits=len(commit_data),
        total_files_changed=len(file_churn),
        hotspots=hotspots,
        file_churn=file_churn,
        change_velocity=change_velocity,
        agent_human_ratio=agent_human_ratio,
        rework_rate=rework_rate,
        sessions=sessions,
        has_attribution_data=any(c["is_agent_attributed"] for c in commit_data),
        attribution_source=next(
            (c["attribution_source"] for c in commit_data if c["attribution_source"]),
            None,
        ),
    )

    # Analyze with LLM
    if not json_output:
        console.print("[dim]Analyzing with LLM...[/dim]")

    from git_pulse.analyst.engine import AnalystEngine

    engine = AnalystEngine(model=effective_model)

    try:
        analyst_report = engine.analyze(collector_report.to_dict())
    except Exception as e:
        console.print(f"[red]LLM analysis failed:[/red] {e}")
        if verbose:
            from git_pulse.renderer.terminal import _render_verbose
            _render_verbose(console, collector_report)
        raise typer.Exit(1)

    # Render
    if json_output:
        from git_pulse.renderer.json_output import render_json

        json_str = render_json(analyst_report)
        if output:
            Path(output).write_text(json_str)
            console.print(f"[green]Report written to {output}[/green]")
        else:
            print(json_str)
    else:
        from git_pulse.renderer.terminal import render_terminal

        render_terminal(
            analyst_report=analyst_report,
            collector_report=collector_report,
            console=console,
            verbose=verbose,
        )
        if output:
            from git_pulse.renderer.json_output import render_json

            Path(output).write_text(render_json(analyst_report))
            console.print(f"\n[green]JSON report also written to {output}[/green]")
