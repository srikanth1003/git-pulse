"""Kaplan-Meier line survival analysis.

Each line's lifetime runs from its introducing commit to the commit that
modified/deleted it. Lines still alive at the analysis boundary are
right-censored.
"""

from __future__ import annotations

from datetime import datetime

from git_pulse.analysis.line_lifetime import LifetimeIndex
from git_pulse.models.history import AuthorClass, History
from git_pulse.models.results import SurvivalPoint, SurvivalResult


def analyze_survival(history: History, index: LifetimeIndex) -> SurvivalResult:
    """Build Kaplan-Meier survival curves for lines, split by agent/human."""
    if not history.commits or not index:
        return _empty()

    commit_time = {c.sha: c.authored_at for c in history.commits}
    commit_class = {c.sha: c.author_class for c in history.commits}
    boundary = max(c.authored_at for c in history.commits)

    overall: list[tuple[float, bool]] = []
    agent: list[tuple[float, bool]] = []
    human: list[tuple[float, bool]] = []

    censored_count = 0
    total_count = 0

    for _path, lifetime in index.items():
        death_shas = {d.sha for d in lifetime.deaths}
        for birth in lifetime.births:
            birth_time = commit_time.get(birth.sha, birth.authored_at)
            total_count += 1

            died = birth.sha in death_shas and _has_later_death(
                birth.sha, death_shas, commit_time, birth_time
            )
            if died:
                death_time = _earliest_death_time(birth.sha, death_shas, commit_time, birth_time)
                duration = (death_time - birth_time).total_seconds() / 86400.0
                event = (max(duration, 0.0), False)
            else:
                duration = (boundary - birth_time).total_seconds() / 86400.0
                event = (max(duration, 0.0), True)
                censored_count += 1

            overall.append(event)
            cls = commit_class.get(birth.sha)
            if cls is AuthorClass.AGENT:
                agent.append(event)
            else:
                human.append(event)

    return SurvivalResult(
        overall_median_days=_km_median(_km_curve(overall)),
        agent_median_days=_km_median(_km_curve(agent)),
        human_median_days=_km_median(_km_curve(human)),
        overall_curve=_km_curve(overall),
        agent_curve=_km_curve(agent),
        human_curve=_km_curve(human),
        total_lines=total_count,
        censored_lines=censored_count,
    )


def _has_later_death(
    birth_sha: str, death_shas: set[str], commit_time: dict[str, datetime], birth_time: datetime
) -> bool:
    """Check if any death commit is later than the birth."""
    for sha in death_shas:
        if sha != birth_sha and sha in commit_time and commit_time[sha] > birth_time:
            return True
    return False


def _earliest_death_time(
    birth_sha: str, death_shas: set[str], commit_time: dict[str, datetime], birth_time: datetime
) -> datetime:
    """Find the earliest death after birth."""
    candidates = [
        commit_time[sha]
        for sha in death_shas
        if sha != birth_sha and sha in commit_time and commit_time[sha] > birth_time
    ]
    return min(candidates) if candidates else birth_time


def _km_curve(events: list[tuple[float, bool]]) -> tuple[SurvivalPoint, ...]:
    """Compute a Kaplan-Meier survival curve.

    events: list of (time_days, is_censored).
    """
    if not events:
        return ()

    events.sort(key=lambda e: (e[0], e[1]))

    at_risk = len(events)
    survival = 1.0
    points: list[SurvivalPoint] = [
        SurvivalPoint(time_days=0.0, survival=1.0, at_risk=at_risk, events=0)
    ]

    i = 0
    while i < len(events):
        t = events[i][0]
        deaths = 0
        censored = 0
        while i < len(events) and events[i][0] == t:
            if events[i][1]:
                censored += 1
            else:
                deaths += 1
            i += 1

        if deaths > 0:
            survival *= (at_risk - deaths) / at_risk
            points.append(
                SurvivalPoint(time_days=t, survival=survival, at_risk=at_risk, events=deaths)
            )

        at_risk -= deaths + censored

    return tuple(points)


def _km_median(curve: tuple[SurvivalPoint, ...]) -> float | None:
    """Median survival time — the first point where survival <= 0.5."""
    for point in curve:
        if point.survival <= 0.5:
            return point.time_days
    return None


def _empty() -> SurvivalResult:
    return SurvivalResult(
        overall_median_days=None,
        agent_median_days=None,
        human_median_days=None,
        overall_curve=(),
        agent_curve=(),
        human_curve=(),
        total_lines=0,
        censored_lines=0,
    )
