"""Markdown report — paste-able into a PR or wiki."""

from __future__ import annotations

from git_pulse.models.report import Report


def render_markdown(report: Report) -> str:
    """Render a complete markdown report from a Report object."""
    parts: list[str] = []
    parts.append(_header(report))

    if report.is_empty:
        parts.append("*No commits matched the selected range and filters.*\n")
        return "\n".join(parts)

    parts.append(_attribution(report))
    parts.append(_churn(report))
    parts.append(_velocity(report))
    parts.append(_sessions(report))
    parts.append(_hotspots(report))
    parts.append(_coupling(report))
    parts.append(_ownership(report))
    parts.append(_line_rework(report))
    parts.append(_commit_classification(report))
    parts.append(_survival(report))
    parts.append(_szz(report))
    parts.append(_risk(report))
    parts.append(_complexity(report))
    parts.append(_warnings(report))

    return "\n".join(p for p in parts if p)


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _header(report: Report) -> str:
    lines = [f"# git-pulse report: {report.repo_name}"]
    lines.append(f"\n**Branch:** {report.branch} · **HEAD:** `{report.head_sha[:8]}`")
    if report.time_range:
        first, last = report.time_range
        lines.append(
            f"**Range:** {first:%Y-%m-%d} → {last:%Y-%m-%d} · **Commits:** {report.total_commits}"
        )
    lines.append(f"**Version:** {report.git_pulse_version}\n")
    return "\n".join(lines)


def _attribution(report: Report) -> str:
    a = report.attribution
    lines = ["## Attribution\n"]
    lines.append("| Metric | Value |")
    lines.append("|--------|------:|")
    lines.append(f"| Agent commits | {a.agent_commits} ({_pct(a.agent_commit_share)}) |")
    lines.append(f"| Human commits | {a.human_commits} |")
    lines.append(f"| Agent lines added | {a.agent_lines_added} ({_pct(a.agent_line_share)}) |")

    if a.providers_seen:
        providers = ", ".join(f"{k} ({v})" for k, v in sorted(a.providers_seen.items()))
        lines.append(f"| Providers | {providers} |")

    if a.authors:
        lines.append("\n### Authors\n")
        lines.append("| Author | Class | Commits | +/- |")
        lines.append("|--------|-------|--------:|----:|")
        for author in a.authors[:10]:
            lines.append(
                f"| {author.name} | {author.author_class.value} | "
                f"{author.commits} | +{author.lines_added}/-{author.lines_removed} |"
            )

    lines.append("")
    return "\n".join(lines)


def _churn(report: Report) -> str:
    if not report.churn.files:
        return ""
    lines = ["## Most-changed files\n"]
    lines.append("| File | Commits | Churn | Agent |")
    lines.append("|------|--------:|------:|------:|")
    for f in report.churn.files:
        lines.append(f"| `{f.path}` | {f.commits} | {f.churn} | {_pct(f.agent_share)} |")

    r = report.rework
    lines.append(
        f"\nRework (file-level): {r.file_rework_rate * 100:.0f}% of churn "
        f"in {r.reworked_files}/{r.total_files} files"
    )
    lines.append("")
    return "\n".join(lines)


def _velocity(report: Report) -> str:
    v = report.velocity
    lines = ["## Velocity\n"]
    lines.append("| Metric | Value |")
    lines.append("|--------|------:|")
    lines.append(f"| Commits/day | {v.commits_per_day:.2f} |")
    lines.append(f"| Active days | {v.active_days}/{v.span_days} |")
    lines.append(f"| Files/commit | {v.avg_files_per_commit:.1f} |")
    if v.peak_day:
        lines.append(f"| Busiest day | {v.peak_day} ({v.peak_commits}) |")
    lines.append("")
    return "\n".join(lines)


def _sessions(report: Report) -> str:
    s = report.sessions
    lines = ["## Sessions\n"]
    lines.append(
        f"**{s.total_sessions}** sessions · "
        f"**{s.avg_commits_per_session:.1f}** commits/session · "
        f"**{s.avg_duration_minutes:.0f}** min avg\n"
    )
    return "\n".join(lines)


def _hotspots(report: Report) -> str:
    if not report.hotspots.hotspots:
        return ""
    lines = [f"## Hotspots ({report.hotspots.total_detected} detected)\n"]
    lines.append("| Location | Edits | Span | Pattern |")
    lines.append("|----------|------:|-----:|---------|")
    for h in report.hotspots.hotspots:
        lines.append(
            f"| `{h.file_path}:{h.line_start}-{h.line_end}` | "
            f"{h.modification_count} | {h.time_span_hours:.1f}h | {h.classification} |"
        )
    lines.append("")
    return "\n".join(lines)


def _coupling(report: Report) -> str:
    if not report.coupling.pairs:
        return ""
    lines = [f"## Temporal coupling ({report.coupling.total_detected} pairs)\n"]
    lines.append("| File A | File B | Shared | Ratio |")
    lines.append("|--------|--------|-------:|------:|")
    for p in report.coupling.pairs:
        lines.append(
            f"| `{p.file_a}` | `{p.file_b}` | {p.shared_commits} | {_pct(p.coupling_ratio)} |"
        )
    lines.append("")
    return "\n".join(lines)


def _ownership(report: Report) -> str:
    if report.ownership is None or not report.ownership.files:
        return ""
    o = report.ownership
    lines = ["## Ownership\n"]
    lines.append(
        f"**Bus factor (repo):** {o.repo_bus_factor} "
        f"({o.total_authors} authors, {o.total_lines} lines)\n"
    )
    lines.append("| File | Lines | Top owner | Share | Bus |")
    lines.append("|------|------:|-----------|------:|----:|")
    for f in o.files[:10]:
        top = f.owners[0][0] if f.owners else ""
        lines.append(
            f"| `{f.path}` | {f.total_lines} | {top} | {_pct(f.top_owner_share)} | {f.bus_factor} |"
        )
    lines.append("")
    return "\n".join(lines)


def _line_rework(report: Report) -> str:
    if report.line_rework is None:
        return ""
    lr = report.line_rework
    return (
        f"**Per-line rework:** {lr.line_rework_rate * 100:.0f}% of "
        f"{lr.total_surviving_lines} surviving lines "
        f"(agent {lr.agent_line_rework_rate * 100:.0f}%, "
        f"human {lr.human_line_rework_rate * 100:.0f}%)\n"
    )


def _commit_classification(report: Report) -> str:
    cc = report.commit_classification
    if cc is None or (cc.total_reverts == 0 and cc.total_fixes == 0):
        return ""
    return f"**Reverts:** {cc.total_reverts} · **Fixes:** {cc.total_fixes}\n"


def _survival(report: Report) -> str:
    s = report.survival
    if s is None or s.total_lines == 0:
        return ""
    parts = [f"**Line survival:** {s.total_lines} lines, {s.censored_lines} censored"]
    if s.overall_median_days is not None:
        parts.append(f"median {s.overall_median_days:.0f}d")
    if s.agent_median_days is not None:
        parts.append(f"agent {s.agent_median_days:.0f}d")
    if s.human_median_days is not None:
        parts.append(f"human {s.human_median_days:.0f}d")
    return " · ".join(parts) + "\n"


def _szz(report: Report) -> str:
    s = report.szz
    if s is None or s.total_introductions == 0:
        return ""
    return (
        f"**Bug introductions (SZZ):** {s.total_introductions} across "
        f"{s.bug_introducing_commits} commits\n"
    )


def _risk(report: Report) -> str:
    r = report.risk
    if r is None or not r.files:
        return ""
    return (
        f"**Risk:** {r.hot_risk} hot, {r.quiet_risk} quiet, {r.active} active, {r.stable} stable\n"
    )


def _complexity(report: Report) -> str:
    c = report.complexity
    if c is None or not c.files:
        return ""
    return (
        f"**Complexity (indentation):** avg depth {c.repo_avg_depth:.1f}, max {c.repo_max_depth}\n"
    )


def _warnings(report: Report) -> str:
    if not report.warnings:
        return ""
    lines = ["\n---\n"]
    for w in report.warnings:
        lines.append(f"> **warning:** {w}")
    lines.append("")
    return "\n".join(lines)
