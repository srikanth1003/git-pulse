from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from git_pulse import __version__
from git_pulse.analysis.churn import analyze_churn, analyze_rework
from git_pulse.analysis.commit_class import classify_commits
from git_pulse.analysis.complexity import analyze_complexity
from git_pulse.analysis.coupling import analyze_coupling
from git_pulse.analysis.hotspots import HotspotParams, analyze_hotspots
from git_pulse.analysis.line_lifetime import build_lifetime_index
from git_pulse.analysis.line_rework import analyze_line_rework
from git_pulse.analysis.ownership import analyze_ownership
from git_pulse.analysis.risk import analyze_risk
from git_pulse.analysis.sessions import analyze_sessions
from git_pulse.analysis.survival import analyze_survival
from git_pulse.analysis.szz import analyze_szz
from git_pulse.analysis.velocity import analyze_velocity
from git_pulse.attribution.engine import AttributionEngine
from git_pulse.config import GitPulseConfig
from git_pulse.gitlayer.cache import HistoryCache
from git_pulse.gitlayer.collect import CollectOptions, collect_history
from git_pulse.gitlayer.patches import collect_patches, most_touched_paths
from git_pulse.gitlayer.repo import GitRepo
from git_pulse.models.history import AuthorClass, History
from git_pulse.models.report import AttributionSummary, AuthorSummary, Report


def build_report(
    repo_path: Path | str,
    config: GitPulseConfig,
    *,
    options: CollectOptions | None = None,
    cache: HistoryCache | None = None,
    now: datetime | None = None,
) -> Report:
    """Collect history and run every deterministic analyzer.

    The LLM narrative is deliberately *not* produced here — see
    :mod:`git_pulse.llm`. This function must stay free of network calls so that
    ``--json`` output is reproducible.
    """
    path = Path(repo_path)
    now = now or datetime.now(UTC)
    options = options or CollectOptions(days=config.default_days, exclude=tuple(config.exclude))

    repo = GitRepo(path)
    engine = AttributionEngine(
        agent_threshold=config.attribution.agent_threshold,
        human_threshold=config.attribution.human_threshold,
        enable_cadence_heuristic=config.attribution.enable_cadence_heuristic,
    )
    history = collect_history(path, options, cache=cache, engine=engine, now=now)

    hotspot_params = HotspotParams(
        window_hours=config.analysis.hotspot_window_hours,
        region_lines=config.analysis.hotspot_region_lines,
        max_hotspots=config.analysis.max_hotspots,
    )

    top_paths = most_touched_paths(history, hotspot_params.max_files)
    patches = collect_patches(history, repo, top_paths) if top_paths else {}
    lifetime_idx = build_lifetime_index(history, repo, top_paths, patches) if top_paths else {}
    ownership = analyze_ownership(lifetime_idx) if lifetime_idx else None
    line_rework = analyze_line_rework(history, lifetime_idx) if lifetime_idx else None
    classification = classify_commits(history)
    churn_result = analyze_churn(history, limit=config.analysis.max_hotspots)

    return Report(
        repo_path=str(path),
        repo_name=path.resolve().name,
        branch=history.branch,
        head_sha=history.head_sha,
        generated_at=now,
        git_pulse_version=__version__,
        options={**options.as_cache_dict(), "branch": history.branch},
        total_commits=len(history.commits),
        time_range=history.time_range if history.commits else None,
        skipped_files=history.skipped_files,
        attribution=_summarize_attribution(history),
        churn=churn_result,
        velocity=analyze_velocity(history),
        sessions=analyze_sessions(history, gap_minutes=config.sessions.gap_minutes),
        hotspots=analyze_hotspots(history, repo, hotspot_params),
        rework=analyze_rework(history),
        coupling=analyze_coupling(history),
        ownership=ownership,
        line_rework=line_rework,
        commit_classification=classification,
        survival=analyze_survival(history, lifetime_idx) if lifetime_idx else None,
        szz=analyze_szz(history, repo, classification),
        risk=analyze_risk(churn_result, ownership),
        complexity=analyze_complexity(repo, history.head_sha, top_paths) if top_paths else None,
        warnings=_warnings(history),
    )


def add_narrative(report: Report, config: GitPulseConfig) -> Report:
    """Attach an LLM narrative if configured. Never raises; degrades to a warning.

    Kept separate from ``build_report`` so the deterministic path stays free of
    network calls and remains reproducible.
    """
    from dataclasses import replace

    from git_pulse.analyst.engine import AnalystEngine, LLMUnavailableError
    from git_pulse.render.json_output import render_json

    if not config.llm.enabled or report.is_empty:
        return report

    engine = AnalystEngine(config.llm)
    try:
        engine.check_available()
        result = engine.analyze(json.loads(render_json(report, indent=None)))
    except LLMUnavailableError as exc:
        return replace(report, warnings=report.warnings + (str(exc),))

    if result is None:
        return replace(
            report,
            warnings=report.warnings
            + ("LLM narrative unavailable; deterministic metrics are unaffected.",),
        )
    return replace(
        report, narrative=result.summary, insights=result.insights, actions=result.actions
    )


@dataclass
class _AuthorTally:
    name: str
    author_class: AuthorClass
    commits: int = 0
    added: int = 0
    removed: int = 0


@dataclass
class _Totals:
    added: int = 0
    removed: int = 0
    agent_added: int = 0
    agent_removed: int = 0
    classes: Counter[AuthorClass] = field(default_factory=Counter)
    signals: Counter[str] = field(default_factory=Counter)
    providers: Counter[str] = field(default_factory=Counter)


def _summarize_attribution(history: History) -> AttributionSummary:
    totals = _Totals()
    per_author: dict[str, _AuthorTally] = {}

    for commit in history.commits:
        totals.classes[commit.author_class] += 1
        for signal in commit.attribution.signals:
            totals.signals[signal.name] += 1
        if commit.attribution.provider:
            totals.providers[commit.attribution.provider] += 1

        added = sum(c.insertions for c in commit.files)
        removed = sum(c.deletions for c in commit.files)
        totals.added += added
        totals.removed += removed
        is_agent = commit.author_class is AuthorClass.AGENT
        if is_agent:
            totals.agent_added += added
            totals.agent_removed += removed

        tally = per_author.setdefault(
            commit.author_email,
            _AuthorTally(name=commit.author_name, author_class=commit.author_class),
        )
        tally.commits += 1
        tally.added += added
        tally.removed += removed
        # An author seen as an agent even once is reported as an agent identity:
        # a bot account never reverts to being human.
        if is_agent:
            tally.author_class = AuthorClass.AGENT

    authors = tuple(
        sorted(
            (
                AuthorSummary(
                    email=email,
                    name=tally.name,
                    author_class=tally.author_class,
                    commits=tally.commits,
                    lines_added=tally.added,
                    lines_removed=tally.removed,
                )
                for email, tally in per_author.items()
            ),
            key=lambda a: (-a.commits, a.email),
        )
    )

    return AttributionSummary(
        total_commits=len(history.commits),
        agent_commits=totals.classes[AuthorClass.AGENT],
        mixed_commits=totals.classes[AuthorClass.MIXED],
        human_commits=totals.classes[AuthorClass.HUMAN],
        agent_lines_added=totals.agent_added,
        agent_lines_removed=totals.agent_removed,
        total_lines_added=totals.added,
        total_lines_removed=totals.removed,
        signals_seen=dict(totals.signals),
        providers_seen=dict(totals.providers),
        authors=authors,
    )


def _warnings(history: History) -> tuple[str, ...]:
    """Conditions that make the numbers less trustworthy — always surfaced."""
    warnings: list[str] = []
    if history.is_shallow:
        warnings.append("Repository is a shallow clone; history before the graft point is missing.")
    if not history.commits:
        warnings.append("No commits matched the selected range and filters.")
    if history.skipped_files:
        warnings.append(f"{len(history.skipped_files)} binary file(s) excluded from line counts.")
    return tuple(warnings)
