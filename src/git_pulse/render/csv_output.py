"""CSV output — per-file metrics in a flat table for spreadsheets and pipelines."""

from __future__ import annotations

import csv
import io

from git_pulse.models.report import Report
from git_pulse.models.results import FileComplexity, FileOwnership, FileRisk

COLUMNS = [
    "file",
    "commits",
    "insertions",
    "deletions",
    "churn",
    "agent_commits",
    "human_commits",
    "agent_share",
    "bus_factor",
    "top_owner",
    "top_owner_share",
    "avg_depth",
    "max_depth",
    "risk_quadrant",
]


def render_csv(report: Report) -> str:
    """Render per-file metrics as CSV. One row per file in the churn list."""
    ownership_map: dict[str, FileOwnership] = {}
    if report.ownership:
        for fo in report.ownership.files:
            ownership_map[fo.path] = fo

    complexity_map: dict[str, FileComplexity] = {}
    if report.complexity:
        for fcx in report.complexity.files:
            complexity_map[fcx.path] = fcx

    risk_map: dict[str, FileRisk] = {}
    if report.risk:
        for fr in report.risk.files:
            risk_map[fr.path] = fr

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(COLUMNS)

    for fc in report.churn.files:
        own = ownership_map.get(fc.path)
        cplx = complexity_map.get(fc.path)
        risk = risk_map.get(fc.path)

        writer.writerow(
            [
                fc.path,
                fc.commits,
                fc.insertions,
                fc.deletions,
                fc.churn,
                fc.agent_commits,
                fc.human_commits,
                f"{fc.agent_share:.4f}",
                own.bus_factor if own else "",
                own.owners[0][0] if own and own.owners else "",
                f"{own.top_owner_share:.4f}" if own else "",
                f"{cplx.avg_depth:.2f}" if cplx else "",
                cplx.max_depth if cplx else "",
                risk.quadrant if risk else "",
            ]
        )

    return buf.getvalue()
