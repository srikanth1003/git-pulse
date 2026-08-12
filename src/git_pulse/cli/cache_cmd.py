from __future__ import annotations

import typer
from rich.console import Console

from git_pulse.gitlayer.cache import CACHE_SCHEMA_VERSION, clear_all, global_info

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command("info")
def info() -> None:
    """Show cache location, entry count, and size."""
    # Aggregated across repositories: this command is run from anywhere, so a
    # single repository's cache directory would be the wrong answer.
    details = global_info()

    console.print(f"location : {details.directory}")
    console.print(f"entries  : {details.entries}")
    console.print(f"size     : {details.bytes / 1024:.1f} KiB")
    console.print(f"schema   : v{CACHE_SCHEMA_VERSION}")


@app.command("clear")
def clear() -> None:
    """Delete every cached history entry."""
    removed = clear_all()

    console.print(f"Removed {removed} cache entr{'y' if removed == 1 else 'ies'}.")
