from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console

from git_pulse.config import ConfigError, load_config
from git_pulse.gitlayer.cache import HistoryCache
from git_pulse.gitlayer.collect import CollectOptions
from git_pulse.gitlayer.repo import GitError, NotARepositoryError
from git_pulse.render.csv_output import render_csv
from git_pulse.render.html_report import render_html
from git_pulse.render.json_output import render_json
from git_pulse.render.markdown import render_markdown
from git_pulse.render.terminal import render_terminal
from git_pulse.report.builder import add_narrative, build_report

# Exit codes: 0 success, 1 runtime failure, 2 usage error.
EXIT_USAGE = 2
EXIT_ERROR = 1


def analyze(
    path: str = typer.Argument(".", help="Path to a git repository."),
    days: int | None = typer.Option(None, help="Analyze the last N days."),
    commits: int | None = typer.Option(None, help="Analyze the last N commits."),
    since: str | None = typer.Option(None, help="Analyze commits after this date (ISO 8601)."),
    until: str | None = typer.Option(None, help="Analyze commits before this date."),
    branch: str | None = typer.Option(None, help="Branch to analyze (default: current)."),
    include: list[str] | None = typer.Option(None, help="Only files matching this glob."),
    exclude: list[str] | None = typer.Option(None, help="Skip files matching this glob."),
    include_merges: bool = typer.Option(False, help="Include merge commits."),
    max_hotspots: int | None = typer.Option(None, help="Maximum hotspots to report."),
    llm: bool = typer.Option(False, "--llm", help="Add an LLM narrative (needs an API key)."),
    model: str | None = typer.Option(None, help="LiteLLM model string, e.g. gpt-4o-mini."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON on stdout."),
    markdown_output: bool = typer.Option(False, "--markdown", help="Emit Markdown on stdout."),
    csv_output: bool = typer.Option(False, "--csv", help="Emit per-file CSV on stdout."),
    html_output: bool = typer.Option(False, "--html", help="Emit self-contained HTML on stdout."),
    output: str | None = typer.Option(None, help="Also write the JSON report to this file."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass the history cache."),
    refresh: bool = typer.Option(False, "--refresh", help="Recompute and overwrite the cache."),
    config_path: str | None = typer.Option(None, "--config", help="Path to a config file."),
) -> None:
    """Analyze a repository's history and report agent vs. human contribution.

    Runs entirely offline by default; ``--llm`` adds an interpretive narrative.
    """
    # Progress messages must never contaminate --json/--markdown stdout.
    console = Console(stderr=json_output or markdown_output or csv_output or html_output)
    out = Console()

    repo_path = Path(path).expanduser()
    if not repo_path.exists():
        console.print(f"[red]error:[/red] path does not exist: {repo_path}")
        raise typer.Exit(EXIT_USAGE)
    if days is not None and commits is not None:
        console.print("[red]error:[/red] --days and --commits are mutually exclusive")
        raise typer.Exit(EXIT_USAGE)

    try:
        config = load_config(config_path=config_path, repo_path=str(repo_path))
    except ConfigError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(EXIT_USAGE) from exc

    if max_hotspots is not None:
        config.analysis.max_hotspots = max_hotspots
    if model is not None:
        config.llm.model = model
    if llm:
        config.llm.enabled = True

    options = CollectOptions(
        days=days if (days or commits or since) else config.default_days,
        commits=commits,
        since=_parse_date(since, "--since", console),
        until=_parse_date(until, "--until", console),
        branch=branch,
        include=tuple(include or ()),
        exclude=tuple(exclude or ()) + tuple(config.exclude),
        include_merges=include_merges,
    )

    cache = None if no_cache else HistoryCache(repo_path, write_only=refresh)

    if not json_output:
        console.print("[dim]Reading history…[/dim]")

    try:
        report = build_report(
            repo_path, config, options=options, cache=cache, now=datetime.now(UTC)
        )
    except NotARepositoryError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(EXIT_USAGE) from exc
    except GitError as exc:
        console.print(f"[red]error:[/red] git failed: {exc}")
        raise typer.Exit(EXIT_ERROR) from exc

    if config.llm.enabled and not report.is_empty and not json_output:
        console.print("[dim]Generating narrative…[/dim]")
    report = add_narrative(report, config)

    if json_output:
        out.file.write(render_json(report) + "\n")
    elif markdown_output:
        out.file.write(render_markdown(report) + "\n")
    elif csv_output:
        out.file.write(render_csv(report))
    elif html_output:
        out.file.write(render_html(report) + "\n")
    else:
        render_terminal(report, console=out)

    if output:
        Path(output).expanduser().write_text(render_json(report), encoding="utf-8")
        if not json_output:
            console.print(f"[green]JSON report written to {output}[/green]")


def _parse_date(value: str | None, flag: str, console: Console) -> str | None:
    """Validate a date and normalise it to ISO 8601.

    ``CollectOptions.since``/``until`` are strings passed straight to ``git log``,
    so this returns a string. Validating here means a typo fails with a usage
    error instead of git silently interpreting it as something else.
    """
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        console.print(f"[red]error:[/red] {flag} is not a valid ISO 8601 date: {value!r}")
        raise typer.Exit(EXIT_USAGE) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.isoformat()
