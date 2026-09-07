"""``git-pulse badge`` — generate SVG badge files from a JSON report."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer()

EXIT_USAGE = 2

_BADGE_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20">
  <linearGradient id="g" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="c"><rect width="{width}" height="20" rx="3"/></clipPath>
  <g clip-path="url(#c)">
    <rect width="{label_width}" height="20" fill="#555"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{color}"/>
    <rect width="{width}" height="20" fill="url(#g)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,sans-serif" font-size="11">
    <text x="{label_x}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{label_x}" y="14">{label}</text>
    <text x="{value_x}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="{value_x}" y="14">{value}</text>
  </g>
</svg>"""


@app.callback(invoke_without_command=True)
def badge(
    report_file: str = typer.Option(..., "--report", help="Path to a JSON report file."),
    output_dir: str = typer.Option(".", "--output", "-o", help="Directory to write badge SVGs."),
) -> None:
    """Generate SVG badge files from a JSON report."""
    console = Console(stderr=True)
    report_path = Path(report_file).expanduser()
    out_dir = Path(output_dir).expanduser()

    if not report_path.exists():
        console.print(f"[red]error:[/red] report not found: {report_path}")
        raise typer.Exit(EXIT_USAGE)

    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(EXIT_USAGE) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    agent_share = data.get("attribution", {}).get("agent_commit_share", 0.0)
    _write_badge(
        out_dir / "agent-share.svg", "agent share", f"{agent_share:.0%}", _share_color(agent_share)
    )
    generated.append("agent-share.svg")

    ownership = data.get("ownership")
    if ownership:
        bus = ownership.get("repo_bus_factor", 0)
        _write_badge(out_dir / "bus-factor.svg", "bus factor", str(bus), _bus_color(bus))
        generated.append("bus-factor.svg")

    risk = data.get("risk")
    if risk:
        hot = risk.get("hot_risk", 0)
        _write_badge(out_dir / "hot-risk.svg", "hot risk", str(hot), _risk_color(hot))
        generated.append("hot-risk.svg")

    for name in generated:
        console.print(f"  [green]✓[/green] {out_dir / name}")


def _write_badge(path: Path, label: str, value: str, color: str) -> None:
    label_width = len(label) * 7 + 12
    value_width = len(value) * 7 + 12
    width = label_width + value_width
    svg = _BADGE_TEMPLATE.format(
        width=width,
        label_width=label_width,
        value_width=value_width,
        label_x=label_width / 2,
        value_x=label_width + value_width / 2,
        label=label,
        value=value,
        color=color,
    )
    path.write_text(svg, encoding="utf-8")


def _share_color(share: float) -> str:
    if share <= 0.25:
        return "#4c1"
    if share <= 0.50:
        return "#97ca00"
    if share <= 0.75:
        return "#dfb317"
    return "#e05d44"


def _bus_color(bus: int) -> str:
    if bus >= 3:
        return "#4c1"
    if bus >= 2:
        return "#97ca00"
    return "#e05d44"


def _risk_color(hot: int) -> str:
    if hot == 0:
        return "#4c1"
    if hot <= 3:
        return "#dfb317"
    return "#e05d44"
