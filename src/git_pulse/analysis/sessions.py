from __future__ import annotations

from collections import defaultdict

from git_pulse.models.history import AuthorClass, Commit, History
from git_pulse.models.results import SessionsResult, WorkSession

DEFAULT_GAP_MINUTES = 90


def analyze_sessions(history: History, *, gap_minutes: int = DEFAULT_GAP_MINUTES) -> SessionsResult:
    """Cluster each author's commits into sessions on inactivity gaps.

    A gap *exceeding* ``gap_minutes`` starts a new session; a gap of exactly
    ``gap_minutes`` does not. Clustering is per author so concurrent work by
    different people is not merged.
    """
    by_author: dict[str, list[Commit]] = defaultdict(list)
    for commit in history.commits:
        by_author[commit.author_email].append(commit)

    sessions: list[WorkSession] = []
    for email, commits in by_author.items():
        ordered = sorted(commits, key=lambda c: c.authored_at)
        group: list[Commit] = []
        for commit in ordered:
            if group:
                gap = (commit.authored_at - group[-1].authored_at).total_seconds() / 60.0
                if gap > gap_minutes:
                    sessions.append(_build_session(email, group))
                    group = []
            group.append(commit)
        if group:
            sessions.append(_build_session(email, group))

    sessions.sort(key=lambda s: (s.start, s.author))

    if not sessions:
        return SessionsResult(
            sessions=(),
            total_sessions=0,
            avg_commits_per_session=0.0,
            avg_duration_minutes=0.0,
            longest=None,
        )

    return SessionsResult(
        sessions=tuple(sessions),
        total_sessions=len(sessions),
        avg_commits_per_session=sum(s.commit_count for s in sessions) / len(sessions),
        avg_duration_minutes=sum(s.duration_minutes for s in sessions) / len(sessions),
        longest=max(sessions, key=lambda s: (s.commit_count, s.duration_minutes)),
    )


def _build_session(email: str, commits: list[Commit]) -> WorkSession:
    paths = {change.path for commit in commits for change in commit.files}
    agent_commits = sum(1 for c in commits if c.author_class is AuthorClass.AGENT)

    return WorkSession(
        author=email,
        author_name=commits[-1].author_name,
        start=commits[0].authored_at,
        end=commits[-1].authored_at,
        commit_count=len(commits),
        files_touched=len(paths),
        agent_commits=agent_commits,
        human_commits=len(commits) - agent_commits,
    )
