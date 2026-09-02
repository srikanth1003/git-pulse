"""Rich terminal output.

Accepts an injected ``Console`` so tests can capture output at a fixed width.
Every section guards against an empty report rather than assuming data exists.
"""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from git_pulse.models.history import AuthorClass
from git_pulse.models.report import Report

_CLASS_STYLE = {
    AuthorClass.AGENT: "cyan",
    AuthorClass.MIXED: "yellow",
    AuthorClass.HUMAN: "green",
}

_SEVERITY_STYLE = {"high": "red", "medium": "yellow", "low": "cyan", "info": "dim"}


def render_terminal(report: Report, *, console: Console | None = None) -> None:
    console = console or Console()

    _header(report, console)
    if report.is_empty:
        console.print("[yellow]No commits matched the selected range and filters.[/yellow]")
        return

    _attribution(report, console)
    _churn(report, console)
    _velocity(report, console)
    _sessions(report, console)
    _hotspots(report, console)
    _coupling(report, console)
    _narrative(report, console)
    _warnings(report, console)


def _header(report: Report, console: Console) -> None:
    span = ""
    if report.time_range:
        first, last = report.time_range
        span = f"\n{first:%Y-%m-%d} → {last:%Y-%m-%d}  ·  {report.total_commits} commits"

    console.print(
        Panel(
            Text.from_markup(
                f"[bold]{escape(report.repo_name)}[/bold]  ·  "
                f"branch [cyan]{escape(report.branch)}[/cyan]"
                f"  ·  {report.head_sha[:8]}{span}"
            ),
            title="git-pulse",
            subtitle=f"v{report.git_pulse_version}",
            expand=False,
        )
    )


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _attribution(report: Report, console: Console) -> None:
    a = report.attribution
    table = Table(title="Attribution", title_justify="left", expand=False)
    table.add_column("Metric")
    table.add_column("Value", justify="right")

    table.add_row("Agent commits", f"{a.agent_commits} ({_pct(a.agent_commit_share)})")
    table.add_row("Mixed commits", str(a.mixed_commits))
    table.add_row("Human commits", str(a.human_commits))
    table.add_row("Agent lines added", f"{a.agent_lines_added} ({_pct(a.agent_line_share)})")
    if a.providers_seen:
        table.add_row(
            "Providers",
            ", ".join(f"{escape(k)} ({v})" for k, v in sorted(a.providers_seen.items())),
        )
    console.print(table)

    if a.authors:
        authors = Table(title="Authors", title_justify="left", expand=False)
        authors.add_column("Author")
        authors.add_column("Class")
        authors.add_column("Commits", justify="right")
        authors.add_column("+/-", justify="right")
        for author in a.authors[:10]:
            authors.add_row(
                escape(author.name),
                # ``.get`` because an unclassified author must not crash the render.
                Text(
                    author.author_class.value, style=_CLASS_STYLE.get(author.author_class, "white")
                ),
                str(author.commits),
                f"+{author.lines_added}/-{author.lines_removed}",
            )
        console.print(authors)


def _churn(report: Report, console: Console) -> None:
    if not report.churn.files:
        return
    table = Table(title="Most-changed files", title_justify="left", expand=False)
    table.add_column("File", overflow="fold")
    table.add_column("Commits", justify="right")
    table.add_column("Churn", justify="right")
    table.add_column("Agent", justify="right")
    for f in report.churn.files:
        table.add_row(escape(f.path), str(f.commits), str(f.churn), _pct(f.agent_share))
    console.print(table)
    console.print(
        f"  Rework (file-level): {report.rework.file_rework_rate * 100:.0f}% of churn "
        f"in {report.rework.reworked_files} of {report.rework.total_files} files"
    )


def _velocity(report: Report, console: Console) -> None:
    v = report.velocity
    table = Table(title="Velocity", title_justify="left", expand=False)
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Commits / day", f"{v.commits_per_day:.2f}")
    table.add_row("Active days", f"{v.active_days} of {v.span_days}")
    table.add_row("Files / commit", f"{v.avg_files_per_commit:.1f}")
    if v.peak_day:
        table.add_row("Busiest day", f"{v.peak_day} ({v.peak_commits})")
    console.print(table)


def _sessions(report: Report, console: Console) -> None:
    s = report.sessions
    table = Table(title="Sessions", title_justify="left", expand=False)
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Work sessions", str(s.total_sessions))
    table.add_row("Commits / session", f"{s.avg_commits_per_session:.1f}")
    table.add_row("Avg duration", f"{s.avg_duration_minutes:.0f} min")
    if s.longest:
        table.add_row(
            "Longest",
            f"{s.longest.duration_minutes:.0f} min, {s.longest.commit_count} commits",
        )
    console.print(table)


def _hotspots(report: Report, console: Console) -> None:
    if not report.hotspots.hotspots:
        return
    table = Table(
        title=f"Hotspots ({report.hotspots.total_detected} detected)",
        title_justify="left",
        expand=False,
    )
    table.add_column("Location", overflow="fold")
    table.add_column("Edits", justify="right")
    table.add_column("Span", justify="right")
    table.add_column("Pattern")
    for h in report.hotspots.hotspots:
        table.add_row(
            f"{escape(h.file_path)}:{h.line_start}-{h.line_end}",
            str(h.modification_count),
            f"{h.time_span_hours:.1f}h",
            h.classification,
        )
    console.print(table)


def _coupling(report: Report, console: Console) -> None:
    if not report.coupling.pairs:
        return
    table = Table(
        title=f"Temporal coupling ({report.coupling.total_detected} pairs)",
        title_justify="left",
        expand=False,
    )
    table.add_column("File A", overflow="fold")
    table.add_column("File B", overflow="fold")
    table.add_column("Shared", justify="right")
    table.add_column("Ratio", justify="right")
    for p in report.coupling.pairs:
        table.add_row(
            escape(p.file_a), escape(p.file_b), str(p.shared_commits), _pct(p.coupling_ratio)
        )
    console.print(table)


def _narrative(report: Report, console: Console) -> None:
    if not report.narrative:
        return
    console.print(Panel(Text(report.narrative), title="Narrative", title_align="left"))

    for insight in report.insights:
        style = _SEVERITY_STYLE.get(insight.severity, "dim")
        console.print(
            f"  [{style}]● {insight.severity}[/{style}]  "
            f"[bold]{escape(insight.title)}[/bold] [dim]({escape(insight.category)})[/dim]"
        )
        for line in insight.evidence:
            console.print(f"      [dim]evidence:[/dim] {escape(line)}")
        if insight.recommendation:
            console.print(f"      [dim]→[/dim] {escape(insight.recommendation)}")

    if report.actions:
        console.print("\n[bold]Next steps[/bold]")
        for n, action in enumerate(report.actions, 1):
            console.print(f"  {n}. {escape(action)}")


def _warnings(report: Report, console: Console) -> None:
    for warning in report.warnings:
        console.print(f"[yellow]warning:[/yellow] {escape(warning)}")
