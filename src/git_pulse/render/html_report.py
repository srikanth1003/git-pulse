"""Self-contained HTML report with inline SVG charts."""

from __future__ import annotations

import html

from git_pulse.models.report import Report

_AGENT_COLOR = "#2a78d6"
_HUMAN_COLOR = "#008300"
_MIXED_COLOR = "#eda100"
_SURFACE = "#fcfcfb"
_TEXT = "#0b0b0b"
_TEXT_SEC = "#52514e"
_GRID = "#e5e5e0"

_DARK_AGENT = "#3987e5"
_DARK_HUMAN = "#008300"
_DARK_MIXED = "#c98500"
_DARK_SURFACE = "#1a1a19"
_DARK_TEXT = "#ffffff"
_DARK_TEXT_SEC = "#c3c2b7"
_DARK_GRID = "#333330"


def render_html(report: Report) -> str:
    """Render a self-contained HTML report."""
    parts: list[str] = []
    parts.append(_html_head(report))
    parts.append('<body><div class="report">')
    parts.append(_header_html(report))

    if report.is_empty:
        parts.append('<p class="empty">No commits matched the selected range and filters.</p>')
    else:
        parts.append(_attribution_section(report))
        parts.append(_velocity_section(report))
        parts.append(_churn_section(report))
        parts.append(_summary_metrics(report))

    parts.append("</div></body></html>")
    return "\n".join(parts)


def _html_head(report: Report) -> str:
    title = html.escape(f"git-pulse: {report.repo_name}")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{
  --surface: {_SURFACE};
  --text: {_TEXT};
  --text-sec: {_TEXT_SEC};
  --grid: {_GRID};
  --agent: {_AGENT_COLOR};
  --human: {_HUMAN_COLOR};
  --mixed: {_MIXED_COLOR};
  color-scheme: light;
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) {{
    --surface: {_DARK_SURFACE};
    --text: {_DARK_TEXT};
    --text-sec: {_DARK_TEXT_SEC};
    --grid: {_DARK_GRID};
    --agent: {_DARK_AGENT};
    --human: {_DARK_HUMAN};
    --mixed: {_DARK_MIXED};
    color-scheme: dark;
  }}
}}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--surface);
  color: var(--text);
  margin: 0;
  padding: 24px;
  line-height: 1.5;
}}
.report {{ max-width: 900px; margin: 0 auto; }}
h1 {{ font-size: 24px; margin: 0 0 4px; }}
.meta {{ color: var(--text-sec); font-size: 14px; margin-bottom: 24px; }}
h2 {{ font-size: 18px; margin: 32px 0 12px; border-bottom: 1px solid var(--grid); padding-bottom: 4px; }}
.stats {{ display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 24px; }}
.stat {{ text-align: center; }}
.stat-value {{ font-size: 32px; font-weight: 700; }}
.stat-label {{ font-size: 12px; color: var(--text-sec); text-transform: uppercase; letter-spacing: 0.5px; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 16px; font-size: 14px; }}
th, td {{ padding: 6px 12px; text-align: left; border-bottom: 1px solid var(--grid); }}
th {{ color: var(--text-sec); font-weight: 600; font-size: 12px; text-transform: uppercase; }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.chart-row {{ display: flex; gap: 24px; flex-wrap: wrap; align-items: flex-start; }}
.chart-box {{ flex: 1; min-width: 300px; }}
svg text {{ font-family: inherit; }}
.empty {{ color: var(--text-sec); font-style: italic; }}
.legend {{ display: flex; gap: 16px; font-size: 13px; margin-top: 8px; }}
.legend-item {{ display: flex; align-items: center; gap: 4px; }}
.legend-dot {{ width: 10px; height: 10px; border-radius: 2px; }}
</style>
</head>"""


def _header_html(report: Report) -> str:
    h = html.escape(report.repo_name)
    branch = html.escape(report.branch)
    sha = report.head_sha[:8]
    meta_parts = [f"branch <b>{branch}</b>", f"<code>{sha}</code>"]
    if report.time_range:
        first, last = report.time_range
        meta_parts.append(f"{first:%Y-%m-%d} &rarr; {last:%Y-%m-%d}")
        meta_parts.append(f"{report.total_commits} commits")
    meta_parts.append(f"v{html.escape(report.git_pulse_version)}")
    return f'<h1>{h}</h1>\n<div class="meta">{" &middot; ".join(meta_parts)}</div>'


def _attribution_section(report: Report) -> str:
    a = report.attribution
    total = a.agent_commits + a.human_commits + a.mixed_commits
    if total == 0:
        return ""

    parts = [
        (a.agent_commits, "Agent", "var(--agent)"),
        (a.human_commits, "Human", "var(--human)"),
    ]
    if a.mixed_commits > 0:
        parts.append((a.mixed_commits, "Mixed", "var(--mixed)"))

    pie = _pie_svg([(count, label, color) for count, label, color in parts], 120)
    stats = f"""<div class="stats">
<div class="stat"><div class="stat-value" style="color:var(--agent)">{a.agent_commits}</div><div class="stat-label">Agent commits ({a.agent_commit_share:.0%})</div></div>
<div class="stat"><div class="stat-value" style="color:var(--human)">{a.human_commits}</div><div class="stat-label">Human commits</div></div>
<div class="stat"><div class="stat-value">{a.agent_line_share:.0%}</div><div class="stat-label">Agent line share</div></div>
</div>"""

    legend = (
        '<div class="legend">'
        + "".join(
            f'<div class="legend-item"><div class="legend-dot" style="background:{color}"></div>{label}</div>'
            for _, label, color in parts
        )
        + "</div>"
    )

    return f'<h2>Attribution</h2>\n<div class="chart-row"><div class="chart-box">{pie}{legend}</div><div class="chart-box">{stats}</div></div>'


def _pie_svg(slices: list[tuple[int, str, str]], radius: int) -> str:
    """Render a simple SVG donut chart."""
    total = sum(s[0] for s in slices)
    if total == 0:
        return ""

    cx, cy = radius + 10, radius + 10
    size = (radius + 10) * 2
    inner_r = radius * 0.55
    paths: list[str] = []
    start_angle = -90.0

    import math

    for count, _label, color in slices:
        if count == 0:
            continue
        sweep = (count / total) * 360
        end_angle = start_angle + sweep

        sr, er = math.radians(start_angle), math.radians(end_angle)
        x1_o, y1_o = cx + radius * math.cos(sr), cy + radius * math.sin(sr)
        x2_o, y2_o = cx + radius * math.cos(er), cy + radius * math.sin(er)
        x1_i, y1_i = cx + inner_r * math.cos(er), cy + inner_r * math.sin(er)
        x2_i, y2_i = cx + inner_r * math.cos(sr), cy + inner_r * math.sin(sr)

        large = 1 if sweep > 180 else 0
        d = (
            f"M {x1_o:.1f} {y1_o:.1f} "
            f"A {radius} {radius} 0 {large} 1 {x2_o:.1f} {y2_o:.1f} "
            f"L {x1_i:.1f} {y1_i:.1f} "
            f"A {inner_r:.0f} {inner_r:.0f} 0 {large} 0 {x2_i:.1f} {y2_i:.1f} Z"
        )
        paths.append(f'<path d="{d}" fill="{color}" stroke="var(--surface)" stroke-width="2"/>')
        start_angle = end_angle

    return f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">{"".join(paths)}</svg>'


def _velocity_section(report: Report) -> str:
    v = report.velocity
    if not v.per_day:
        return ""

    days = list(v.per_day)
    max_val = max(c for _, c in days) if days else 1
    w, h = 600, 160
    margin_l, margin_b = 40, 24
    plot_w = w - margin_l
    plot_h = h - margin_b

    points: list[str] = []
    for i, (_date, count) in enumerate(days):
        x = margin_l + (i / max(len(days) - 1, 1)) * plot_w
        y = h - margin_b - (count / max(max_val, 1)) * plot_h
        points.append(f"{x:.1f},{y:.1f}")

    polyline = f'<polyline points="{" ".join(points)}" fill="none" stroke="var(--agent)" stroke-width="2" stroke-linejoin="round"/>'
    grid_lines = ""
    for step in range(0, max_val + 1, max(max_val // 4, 1)):
        y = h - margin_b - (step / max(max_val, 1)) * plot_h
        grid_lines += f'<line x1="{margin_l}" y1="{y:.1f}" x2="{w}" y2="{y:.1f}" stroke="var(--grid)" stroke-width="1"/>'
        grid_lines += f'<text x="{margin_l - 4}" y="{y:.1f}" text-anchor="end" fill="var(--text-sec)" font-size="11" dominant-baseline="middle">{step}</text>'

    first_date = days[0][0] if days else ""
    last_date = days[-1][0] if days else ""
    x_labels = (
        f'<text x="{margin_l}" y="{h - 4}" fill="var(--text-sec)" font-size="11">{first_date}</text>'
        f'<text x="{w}" y="{h - 4}" text-anchor="end" fill="var(--text-sec)" font-size="11">{last_date}</text>'
    )

    return f"""<h2>Velocity</h2>
<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">{grid_lines}{polyline}{x_labels}</svg>
<div class="stats">
<div class="stat"><div class="stat-value">{v.commits_per_day:.2f}</div><div class="stat-label">Commits/day</div></div>
<div class="stat"><div class="stat-value">{v.active_days}/{v.span_days}</div><div class="stat-label">Active days</div></div>
</div>"""


def _churn_section(report: Report) -> str:
    if not report.churn.files:
        return ""

    files = report.churn.files[:10]
    max_churn = max(f.churn for f in files) if files else 1
    bar_w = 300

    rows: list[str] = []
    for f in files:
        w = max(int((f.churn / max_churn) * bar_w), 2)
        agent_w = int(w * f.agent_share)
        bar = (
            f'<svg width="{bar_w}" height="16">'
            f'<rect x="0" y="2" width="{w}" height="12" rx="2" fill="var(--human)"/>'
            f'<rect x="0" y="2" width="{agent_w}" height="12" rx="2" fill="var(--agent)"/>'
            f"</svg>"
        )
        rows.append(
            f"<tr><td><code>{html.escape(f.path)}</code></td>"
            f'<td class="num">{f.commits}</td>'
            f'<td class="num">{f.churn}</td>'
            f"<td>{bar}</td></tr>"
        )

    legend = (
        '<div class="legend">'
        '<div class="legend-item"><div class="legend-dot" style="background:var(--agent)"></div>Agent</div>'
        '<div class="legend-item"><div class="legend-dot" style="background:var(--human)"></div>Human</div>'
        "</div>"
    )

    return f"""<h2>Most-changed files</h2>
<table><thead><tr><th>File</th><th>Commits</th><th>Churn</th><th>Agent / Human</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>{legend}"""


def _summary_metrics(report: Report) -> str:
    """Collect remaining metrics as summary cards."""
    items: list[str] = []

    s = report.sessions
    items.append(
        f"<b>{s.total_sessions}</b> sessions, <b>{s.avg_commits_per_session:.1f}</b> commits/session"
    )

    if report.hotspots.hotspots:
        items.append(f"<b>{report.hotspots.total_detected}</b> hotspots detected")

    if report.coupling.pairs:
        items.append(f"<b>{report.coupling.total_detected}</b> coupled file pairs")

    if report.ownership:
        o = report.ownership
        items.append(f"Bus factor: <b>{o.repo_bus_factor}</b> ({o.total_authors} authors)")

    if report.line_rework:
        lr = report.line_rework
        items.append(
            f"Per-line rework: <b>{lr.line_rework_rate:.0%}</b> of {lr.total_surviving_lines} lines"
        )

    cc = report.commit_classification
    if cc and (cc.total_reverts or cc.total_fixes):
        items.append(f"<b>{cc.total_reverts}</b> reverts, <b>{cc.total_fixes}</b> fixes")

    if report.survival and report.survival.total_lines:
        sv = report.survival
        med = (
            f", median {sv.overall_median_days:.0f}d" if sv.overall_median_days is not None else ""
        )
        items.append(f"Line survival: {sv.total_lines} tracked{med}")

    if report.risk and report.risk.files:
        r = report.risk
        items.append(
            f"Risk: <b>{r.hot_risk}</b> hot, {r.quiet_risk} quiet, {r.active} active, {r.stable} stable"
        )

    if report.complexity and report.complexity.files:
        c = report.complexity
        items.append(f"Complexity: avg depth {c.repo_avg_depth:.1f}, max {c.repo_max_depth}")

    if not items:
        return ""

    bullets = "\n".join(f"<li>{item}</li>" for item in items)
    warnings = ""
    if report.warnings:
        warnings = "\n".join(
            f'<p class="empty">&#9888; {html.escape(w)}</p>' for w in report.warnings
        )

    return f"<h2>Summary</h2>\n<ul>{bullets}</ul>\n{warnings}"
