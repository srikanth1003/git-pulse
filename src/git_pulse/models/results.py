from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FileChurn:
    """Churn for one file, with renames already followed to its current path."""

    path: str
    commits: int
    insertions: int
    deletions: int
    distinct_authors: int
    agent_commits: int
    human_commits: int

    @property
    def churn(self) -> int:
        return self.insertions + self.deletions

    @property
    def agent_share(self) -> float:
        if self.commits == 0:
            return 0.0
        return self.agent_commits / self.commits


@dataclass(frozen=True)
class ChurnResult:
    files: tuple[FileChurn, ...]  # sorted by churn, descending
    total_files: int  # before any ``limit`` truncation
    total_insertions: int
    total_deletions: int


@dataclass(frozen=True)
class VelocityResult:
    total_commits: int
    span_days: int  # calendar days from first to last commit, inclusive
    active_days: int  # days that actually had at least one commit
    commits_per_day: float  # total_commits / span_days
    avg_files_per_commit: float
    peak_day: str | None  # ISO date; None for empty history
    peak_commits: int
    agent_commits: int
    human_commits: int
    per_day: tuple[tuple[str, int], ...]  # (ISO date, commits), ascending

    @property
    def agent_ratio(self) -> float:
        if self.total_commits == 0:
            return 0.0
        return self.agent_commits / self.total_commits
