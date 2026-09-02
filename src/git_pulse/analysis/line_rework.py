"""Per-line rework: the share of surviving lines that overwrote earlier work.

Unlike the Phase 1 file-granularity rework (which counts all churn in
multi-touch files), this measures only lines that actually replaced existing
content. A commit that appends 50 lines to a file is not rework; a commit
that rewrites 50 lines that were already there is.
"""

from __future__ import annotations

from git_pulse.analysis.line_lifetime import LifetimeIndex
from git_pulse.models.history import AuthorClass, History
from git_pulse.models.results import LineReworkResult


def analyze_line_rework(history: History, index: LifetimeIndex) -> LineReworkResult:
    """Compute per-line rework from the lifetime index.

    A surviving line counts as "reworked" if its introducing commit is not the
    earliest commit that touched the file. The first commit creates the file and
    those lines replaced nothing; every later commit that writes surviving lines
    is by definition overwriting or extending prior content.
    """
    commit_class = {c.sha: c.author_class for c in history.commits}
    commit_time = {c.sha: c.authored_at for c in history.commits}

    total = 0
    reworked = 0
    agent_reworked = 0
    human_reworked = 0

    for _path, lifetime in index.items():
        all_shas = {b.sha for b in lifetime.births}
        if not all_shas:
            continue
        earliest_sha = min(
            all_shas, key=lambda s: commit_time.get(s, lifetime.births[0].authored_at)
        )

        for birth in lifetime.births:
            total += 1
            if birth.sha != earliest_sha:
                reworked += 1
                cls = commit_class.get(birth.sha)
                if cls is AuthorClass.AGENT:
                    agent_reworked += 1
                else:
                    human_reworked += 1

    agent_total = sum(
        1
        for lt in index.values()
        for b in lt.births
        if commit_class.get(b.sha) is AuthorClass.AGENT
    )
    human_total = total - agent_total

    return LineReworkResult(
        total_surviving_lines=total,
        reworked_lines=reworked,
        line_rework_rate=reworked / total if total else 0.0,
        agent_reworked_lines=agent_reworked,
        human_reworked_lines=human_reworked,
        agent_line_rework_rate=agent_reworked / agent_total if agent_total else 0.0,
        human_line_rework_rate=human_reworked / human_total if human_total else 0.0,
    )
