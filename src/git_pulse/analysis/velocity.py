from __future__ import annotations

from collections import Counter

from git_pulse.models.history import AuthorClass, History
from git_pulse.models.results import VelocityResult


def analyze_velocity(history: History) -> VelocityResult:
    """Commit cadence over the analyzed span.

    ``span_days`` is calendar days from the first to the last commit inclusive,
    so quiet days count against the rate. ``active_days`` reports how many days
    actually saw work, which is the honest denominator for "how hard was this
    stretch" questions.
    """
    if not history.commits:
        return VelocityResult(
            total_commits=0,
            span_days=0,
            active_days=0,
            commits_per_day=0.0,
            avg_files_per_commit=0.0,
            peak_day=None,
            peak_commits=0,
            agent_commits=0,
            human_commits=0,
            per_day=(),
        )

    per_day: Counter[str] = Counter()
    agent_commits = 0
    total_files = 0

    for commit in history.commits:
        per_day[commit.authored_at.date().isoformat()] += 1
        total_files += len(commit.files)
        if commit.author_class is AuthorClass.AGENT:
            agent_commits += 1

    total_commits = len(history.commits)
    start, end = history.time_range
    span_days = (end.date() - start.date()).days + 1

    # Sort by count descending, then date ascending, so ties resolve to the
    # earliest day rather than to dict ordering.
    peak_day, peak_commits = sorted(per_day.items(), key=lambda kv: (-kv[1], kv[0]))[0]

    return VelocityResult(
        total_commits=total_commits,
        span_days=span_days,
        active_days=len(per_day),
        commits_per_day=total_commits / span_days,
        avg_files_per_commit=total_files / total_commits,
        peak_day=peak_day,
        peak_commits=peak_commits,
        agent_commits=agent_commits,
        human_commits=total_commits - agent_commits,
        per_day=tuple(sorted(per_day.items())),
    )
