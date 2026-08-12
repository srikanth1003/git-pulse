from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from git_pulse.config import DEFAULT_CONFIG, load_config

app = typer.Typer(no_args_is_help=True)
console = Console()

_TEMPLATE = """\
# git-pulse configuration.
# Place at .gitpulse.toml in a repository, or ~/.config/gitpulse/config.toml.

[analysis]
default_days = {default_days}
max_hotspots = {max_hotspots}
hotspot_window_hours = {hotspot_window_hours}
hotspot_region_lines = {hotspot_region_lines}
exclude = {exclude}

[attribution]
# Weight below which a commit counts as human, and at or above which as agent.
human_threshold = {human_threshold}
agent_threshold = {agent_threshold}

[sessions]
gap_minutes = {gap_minutes}

[llm]
# Off by default: every metric above is computed without a network call.
# Enable here or pass --llm. Supply the key via ANTHROPIC_API_KEY (or your
# provider's variable) — do not put secrets in this file.
enabled = false
model = "{model}"
timeout_seconds = {timeout_seconds}
max_tokens = {max_tokens}
"""


@app.command("show")
def show(config_path: str | None = typer.Option(None, "--config")) -> None:
    """Print the effective configuration and where each section came from."""
    config = load_config(config_path=config_path, repo_path=".")

    table = Table("Setting", "Value")
    table.add_row("default_days", str(config.default_days))
    table.add_row("max_hotspots", str(config.analysis.max_hotspots))
    table.add_row("exclude", ", ".join(config.exclude) or "—")
    table.add_row("sessions.gap_minutes", str(config.sessions.gap_minutes))
    table.add_row("llm.enabled", str(config.llm.enabled))
    table.add_row("llm.model", config.llm.model)
    console.print(table)


@app.command("init")
def init(
    output: str = typer.Option(".gitpulse.toml", "--output", help="Where to write the file."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing file."),
) -> None:
    """Write a commented configuration file."""
    target = Path(output).expanduser()
    if target.exists() and not force:
        console.print(f"[red]error:[/red] {target} already exists; pass --force to overwrite")
        raise typer.Exit(1)

    analysis = DEFAULT_CONFIG["analysis"]
    target.write_text(
        _TEMPLATE.format(
            default_days=analysis["default_days"],
            max_hotspots=analysis["max_hotspots"],
            hotspot_window_hours=analysis["hotspot_window_hours"],
            hotspot_region_lines=analysis["hotspot_region_lines"],
            exclude=list(analysis["exclude"]),
            human_threshold=DEFAULT_CONFIG["attribution"]["human_threshold"],
            agent_threshold=DEFAULT_CONFIG["attribution"]["agent_threshold"],
            gap_minutes=DEFAULT_CONFIG["sessions"]["gap_minutes"],
            model=DEFAULT_CONFIG["llm"]["model"],
            timeout_seconds=DEFAULT_CONFIG["llm"]["timeout_seconds"],
            max_tokens=DEFAULT_CONFIG["llm"]["max_tokens"],
        ),
        encoding="utf-8",
    )
    console.print(f"[green]Wrote {target}[/green]")
