"""``git-pulse report`` — save analysis to a file in any format."""

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
from git_pulse.report.builder import add_narrative, build_report

app = typer.Typer()

_FORMATS = {"json", "md", "markdown", "csv", "html"}

EXIT_USAGE = 2
EXIT_ERROR = 1


@app.callback(invoke_without_command=True)
def report(
    output: str = typer.Argument(
        ..., help="Output file path. Format detected from extension (.json, .md, .csv)."
    ),
    path: str = typer.Option(".", help="Path to a git repository."),
    days: int | None = typer.Option(None, help="Analyze the last N days."),
    since: str | None = typer.Option(None, help="Analyze commits after this date."),
    until: str | None = typer.Option(None, help="Analyze commits before this date."),
    branch: str | None = typer.Option(None, help="Branch to analyze."),
    fmt: str | None = typer.Option(None, "--format", help="Force format: json, md, csv."),
    llm: bool = typer.Option(False, "--llm", help="Add an LLM narrative."),
    config_path: str | None = typer.Option(None, "--config", help="Path to a config file."),
) -> None:
    """Save an analysis report to a file.

    Format is auto-detected from the file extension, or forced with --format.
    """
    console = Console(stderr=True)
    repo_path = Path(path).expanduser()
    out_path = Path(output).expanduser()

    detected = fmt or _detect_format(out_path)
    if detected not in _FORMATS:
        console.print(f"[red]error:[/red] unknown format {detected!r}; use json, md, or csv")
        raise typer.Exit(EXIT_USAGE)

    try:
        config = load_config(config_path=config_path, repo_path=str(repo_path))
    except ConfigError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(EXIT_USAGE) from exc

    if llm:
        config.llm.enabled = True

    options = CollectOptions(
        days=days if (days or since) else config.default_days,
        since=since,
        until=until,
        branch=branch,
        exclude=tuple(config.exclude),
    )

    console.print("[dim]Reading history…[/dim]")
    try:
        r = build_report(
            repo_path, config, options=options, cache=HistoryCache(repo_path), now=datetime.now(UTC)
        )
    except (NotARepositoryError, GitError) as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(EXIT_ERROR) from exc

    r = add_narrative(r, config)

    if detected == "json":
        content = render_json(r)
    elif detected in ("md", "markdown"):
        content = render_markdown(r)
    elif detected == "html":
        content = render_html(r)
    else:
        content = render_csv(r)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    console.print(f"[green]Report written to {out_path}[/green]")


def _detect_format(path: Path) -> str:
    ext = path.suffix.lstrip(".")
    if ext in ("md", "markdown"):
        return "md"
    if ext == "csv":
        return "csv"
    if ext in ("html", "htm"):
        return "html"
    return "json"
