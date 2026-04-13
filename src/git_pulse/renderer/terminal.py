from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from git_pulse.analyst.models import AnalystReport
from git_pulse.collector.models import CollectorReport

SEVERITY_COLORS = {"high": "red", "medium": "yellow", "low": "blue"}

CATEGORY_LABELS = {
    "REWORK_REDUCTION": "Rework Reduction",
    "AGENT_EFFECTIVENESS": "Agent Effectiveness",
    "CODEBASE_HEALTH": "Codebase Health",
    "PROMPT_GUIDANCE": "Prompt Guidance",
    "WORKFLOW_OPTIMIZATION": "Workflow Optimization",
}


def render_terminal(
    analyst_report: AnalystReport,
    collector_report: CollectorReport,
    console: Console | None = None,
    verbose: bool = False,
) -> None:
    """Render the full report to the terminal using Rich."""
    if console is None:
        console = Console()

    repo_name = collector_report.repo_path.rstrip("/").split("/")[-1]
    days = (collector_report.time_range[1] - collector_report.time_range[0]).days

    # Header
    console.print()
    console.rule(style="bold")
    console.print(
        f" [bold]Git-Pulse Report[/bold] — {repo_name} ({collector_report.branch})",
        highlight=False,
    )
    console.print(
        f" {days} days · {collector_report.total_commits} commits · {collector_report.total_files_changed} files changed",
        style="dim",
    )
    console.rule(style="bold")
    console.print()

    # Verbose: raw metrics
    if verbose:
        _render_verbose(console, collector_report)

    # Summary
    console.print(Panel(analyst_report.summary, title="Summary", border_style="cyan"))
    console.print()

    # Top actions
    if analyst_report.top_actions:
        console.print("[bold]Top Actions[/bold]")
        for i, action in enumerate(analyst_report.top_actions, 1):
            console.print(f"  {i}. {action}")
        console.print()

    # Insights by category
    categories_seen: dict[str, list] = {}
    for insight in analyst_report.insights:
        categories_seen.setdefault(insight.category, []).append(insight)

    for category, insights in categories_seen.items():
        label = CATEGORY_LABELS.get(category, category)
        console.rule(f" {label} ({len(insights)} insights) ", style="dim")
        console.print()

        for insight in insights:
            color = SEVERITY_COLORS.get(insight.severity, "white")
            console.print(f"  [{color}][{insight.severity.upper()}][/{color}] [bold]{insight.title}[/bold]")
            for ev in insight.evidence:
                console.print(f"    {ev}", style="dim")

            if insight.category == "PROMPT_GUIDANCE" and "```" in insight.recommendation:
                _render_prompt_guidance(console, insight.recommendation)
            else:
                console.print(f"  → {insight.recommendation}")
            console.print()


def _render_prompt_guidance(console: Console, recommendation: str) -> None:
    """Render PROMPT_GUIDANCE recommendations with formatted code blocks."""
    import re

    parts = re.split(r"```\n?", recommendation)
    for i, part in enumerate(parts):
        if i % 2 == 0:
            # Text section
            lines = part.strip().splitlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("PROBLEM:"):
                    console.print(f"  [bold red]  {line}[/bold red]")
                elif line.startswith("BAD PROMPT EXAMPLE:"):
                    console.print(f"  [bold red]  {line}[/bold red]")
                elif line.startswith("BETTER PROMPT EXAMPLE:"):
                    console.print(f"  [bold green]  {line}[/bold green]")
                elif line.startswith("WHY THIS WORKS:"):
                    console.print(f"  [bold cyan]  {line}[/bold cyan]")
                else:
                    console.print(f"    {line}")
        else:
            # Code block
            console.print()
            console.print(Panel(
                part.strip(),
                border_style="dim",
                padding=(0, 2),
            ))
            console.print()


def _render_verbose(console: Console, report: CollectorReport) -> None:
    """Print raw collector metrics."""
    console.print("[bold]Collector Metrics[/bold]", style="cyan")
    console.print(f"  Commits: {report.total_commits}")
    console.print(f"  Files changed: {report.total_files_changed}")
    console.print(f"  Rework rate: {report.rework_rate:.1%}")
    console.print(f"  Velocity: {report.change_velocity.commits_per_day} commits/day")
    console.print(f"  Peak day: {report.change_velocity.peak_day} ({report.change_velocity.peak_commits} commits)")

    if report.agent_human_ratio:
        r = report.agent_human_ratio
        console.print(f"  Agent/Human: {r.agent_commits}/{r.human_commits} ({r.ratio:.0%} agent)")
    else:
        console.print("  Attribution: not detected")

    console.print(f"  Sessions: {len(report.sessions)}")
    console.print(f"  Hotspots: {len(report.hotspots)}")

    if report.file_churn:
        console.print()
        table = Table(title="Top Files by Churn")
        table.add_column("File", style="cyan")
        table.add_column("Modifications", justify="right")
        table.add_column("+/-", justify="right")
        for entry in report.file_churn[:15]:
            table.add_row(entry.file_path, str(entry.modification_count), f"+{entry.insertions}/-{entry.deletions}")
        console.print(table)

    console.print()
