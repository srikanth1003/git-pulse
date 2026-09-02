from __future__ import annotations

import typer
from rich.console import Console

from git_pulse.cli import cache_cmd, compare_cmd, config_cmd, report_cmd
from git_pulse.cli.analyze import analyze

app = typer.Typer(
    name="git-pulse",
    help="Measure how much of your git history was written by AI agents, and what it cost.",
    no_args_is_help=True,
    add_completion=True,
)

app.command()(analyze)
app.add_typer(cache_cmd.app, name="cache", help="Inspect or clear the history cache.")
app.add_typer(config_cmd.app, name="config", help="Show or scaffold configuration.")
app.add_typer(report_cmd.app, name="report", help="Save analysis to a file.")
app.add_typer(compare_cmd.app, name="compare", help="Compare two JSON reports.")


@app.command()
def version() -> None:
    """Show the installed version."""
    from git_pulse import __version__

    Console().print(f"git-pulse {__version__}")
