"""Stable JSON output.

``SCHEMA_VERSION`` is a public contract consumed by the GitHub Action and by
``git-pulse compare``. Adding a key is a minor change; renaming or removing one
requires a version bump.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from git_pulse.models.report import AttributionSummary, Report
from git_pulse.models.results import (
    ChurnResult,
    CommitClassificationResult,
    CouplingResult,
    HotspotsResult,
    LineReworkResult,
    OwnershipResult,
    ReworkResult,
    SessionsResult,
    SurvivalResult,
    VelocityResult,
)

SCHEMA_VERSION = 1


def render_json(report: Report, *, indent: int | None = 2) -> str:
    """Serialise a report. ``indent=None`` yields compact single-line output."""
    return json.dumps(_payload(report), indent=indent, sort_keys=False)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _payload(report: Report) -> dict[str, Any]:
    first, last = report.time_range or (None, None)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso(report.generated_at),
        "git_pulse_version": report.git_pulse_version,
        "repository": {
            "name": report.repo_name,
            "path": report.repo_path,
            "branch": report.branch,
            "head_sha": report.head_sha,
        },
        "scope": {
            "total_commits": report.total_commits,
            "first_commit_at": _iso(first),
            "last_commit_at": _iso(last),
            "options": report.options,
            "skipped_files": list(report.skipped_files),
        },
        "attribution": _attribution(report.attribution),
        "churn": _churn(report.churn),
        "rework": _rework(report.rework),
        "velocity": _velocity(report.velocity),
        "sessions": _sessions(report.sessions),
        "hotspots": _hotspots(report.hotspots),
        "coupling": _coupling(report.coupling),
        "ownership": _ownership(report.ownership),
        "line_rework": _line_rework(report.line_rework),
        "commit_classification": _commit_classification(report.commit_classification),
        "survival": _survival(report.survival),
        "narrative": _narrative(report),
        "warnings": list(report.warnings),
    }


def _narrative(report: Report) -> dict[str, Any] | None:
    """``null`` when no narrative was produced, so consumers can test one key."""
    if report.narrative is None:
        return None
    return {
        "summary": report.narrative,
        "insights": [
            {
                "title": i.title,
                "category": i.category,
                "severity": i.severity,
                "evidence": list(i.evidence),
                "recommendation": i.recommendation,
            }
            for i in report.insights
        ],
        "actions": list(report.actions),
    }


def _attribution(a: AttributionSummary) -> dict[str, Any]:
    return {
        "total_commits": a.total_commits,
        "agent_commits": a.agent_commits,
        "mixed_commits": a.mixed_commits,
        "human_commits": a.human_commits,
        "agent_commit_share": a.agent_commit_share,
        "agent_lines_added": a.agent_lines_added,
        "agent_lines_removed": a.agent_lines_removed,
        "total_lines_added": a.total_lines_added,
        "total_lines_removed": a.total_lines_removed,
        "agent_line_share": a.agent_line_share,
        "signals_seen": a.signals_seen,
        "providers_seen": a.providers_seen,
        "authors": [
            {
                "email": author.email,
                "name": author.name,
                "author_class": author.author_class.value,
                "commits": author.commits,
                "lines_added": author.lines_added,
                "lines_removed": author.lines_removed,
            }
            for author in a.authors
        ],
    }


def _churn(c: ChurnResult) -> dict[str, Any]:
    return {
        "total_files": c.total_files,
        "total_insertions": c.total_insertions,
        "total_deletions": c.total_deletions,
        "files": [
            {
                "path": f.path,
                "commits": f.commits,
                "insertions": f.insertions,
                "deletions": f.deletions,
                "churn": f.churn,
                "distinct_authors": f.distinct_authors,
                "agent_commits": f.agent_commits,
                "human_commits": f.human_commits,
                "agent_share": f.agent_share,
            }
            for f in c.files
        ],
    }


def _rework(r: ReworkResult) -> dict[str, Any]:
    return {
        "file_rework_rate": r.file_rework_rate,
        "agent_rework_rate": r.agent_rework_rate,
        "human_rework_rate": r.human_rework_rate,
        "reworked_files": r.reworked_files,
        "total_files": r.total_files,
        "reworked_churn": r.reworked_churn,
        "total_churn": r.total_churn,
    }


def _velocity(v: VelocityResult) -> dict[str, Any]:
    return {
        "total_commits": v.total_commits,
        "span_days": v.span_days,
        "active_days": v.active_days,
        "commits_per_day": v.commits_per_day,
        "avg_files_per_commit": v.avg_files_per_commit,
        "peak_day": v.peak_day,
        "peak_commits": v.peak_commits,
        "agent_commits": v.agent_commits,
        "human_commits": v.human_commits,
        "agent_ratio": v.agent_ratio,
        "per_day": [{"date": day, "commits": count} for day, count in v.per_day],
    }


def _sessions(s: SessionsResult) -> dict[str, Any]:
    return {
        "total_sessions": s.total_sessions,
        "avg_commits_per_session": s.avg_commits_per_session,
        "avg_duration_minutes": s.avg_duration_minutes,
        "sessions": [
            {
                "author_email": w.author,
                "author_name": w.author_name,
                "start": _iso(w.start),
                "end": _iso(w.end),
                "duration_minutes": w.duration_minutes,
                "commit_count": w.commit_count,
                "files_touched": w.files_touched,
                "agent_commits": w.agent_commits,
                "human_commits": w.human_commits,
                "agent_share": w.agent_share,
            }
            for w in s.sessions
        ],
    }


def _hotspots(h: HotspotsResult) -> dict[str, Any]:
    return {
        "total_detected": h.total_detected,
        "hotspots": [
            {
                "file_path": s.file_path,
                "line_start": s.line_start,
                "line_end": s.line_end,
                "modification_count": s.modification_count,
                "time_span_hours": s.time_span_hours,
                "classification": s.classification,
                "commit_shas": list(s.commit_shas),
                "agent_modifications": s.agent_modifications,
                "human_modifications": s.human_modifications,
                "score": s.score,
            }
            for s in h.hotspots
        ],
    }


def _coupling(c: CouplingResult) -> dict[str, Any]:
    return {
        "total_detected": c.total_detected,
        "pairs": [
            {
                "file_a": p.file_a,
                "file_b": p.file_b,
                "shared_commits": p.shared_commits,
                "coupling_ratio": p.coupling_ratio,
                "commit_shas": list(p.commit_shas),
            }
            for p in c.pairs
        ],
    }


def _ownership(o: OwnershipResult | None) -> dict[str, Any] | None:
    if o is None:
        return None
    return {
        "repo_bus_factor": o.repo_bus_factor,
        "total_lines": o.total_lines,
        "total_authors": o.total_authors,
        "files": [
            {
                "path": f.path,
                "total_lines": f.total_lines,
                "top_owner_share": f.top_owner_share,
                "bus_factor": f.bus_factor,
                "owners": [{"email": email, "lines": count} for email, count in f.owners],
            }
            for f in o.files
        ],
    }


def _line_rework(lr: LineReworkResult | None) -> dict[str, Any] | None:
    if lr is None:
        return None
    return {
        "total_surviving_lines": lr.total_surviving_lines,
        "reworked_lines": lr.reworked_lines,
        "line_rework_rate": lr.line_rework_rate,
        "agent_reworked_lines": lr.agent_reworked_lines,
        "human_reworked_lines": lr.human_reworked_lines,
        "agent_line_rework_rate": lr.agent_line_rework_rate,
        "human_line_rework_rate": lr.human_line_rework_rate,
    }


def _commit_classification(cc: CommitClassificationResult | None) -> dict[str, Any] | None:
    if cc is None:
        return None
    return {
        "total_reverts": cc.total_reverts,
        "total_fixes": cc.total_fixes,
        "reverts": [{"sha": c.sha, "evidence": c.evidence} for c in cc.reverts],
        "fixes": [{"sha": c.sha, "evidence": c.evidence} for c in cc.fixes],
    }


def _survival(s: SurvivalResult | None) -> dict[str, Any] | None:
    if s is None:
        return None
    return {
        "overall_median_days": s.overall_median_days,
        "agent_median_days": s.agent_median_days,
        "human_median_days": s.human_median_days,
        "total_lines": s.total_lines,
        "censored_lines": s.censored_lines,
        "overall_curve": [
            {
                "time_days": p.time_days,
                "survival": p.survival,
                "at_risk": p.at_risk,
                "events": p.events,
            }
            for p in s.overall_curve
        ],
        "agent_curve": [
            {
                "time_days": p.time_days,
                "survival": p.survival,
                "at_risk": p.at_risk,
                "events": p.events,
            }
            for p in s.agent_curve
        ],
        "human_curve": [
            {
                "time_days": p.time_days,
                "survival": p.survival,
                "at_risk": p.at_risk,
                "events": p.events,
            }
            for p in s.human_curve
        ],
    }
