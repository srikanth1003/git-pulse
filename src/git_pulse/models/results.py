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
