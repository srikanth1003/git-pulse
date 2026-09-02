from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


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
class ReworkResult:
    """File-granularity rework, ported from 0.1.0.

    ``file_rework_rate`` is the share of total churn that landed in files touched
    by more than one commit. It is an **upper bound** on real rework: every line
    in a multi-touch file counts, even lines nobody revisited. Phase 2's
    line-lifetime index replaces this with a true per-line measurement.
    """

    file_rework_rate: float
    agent_rework_rate: float
    human_rework_rate: float
    reworked_files: int  # files touched by more than one commit
    total_files: int  # text files touched at all
    reworked_churn: int
    total_churn: int


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


@dataclass(frozen=True)
class WorkSession:
    """A continuous stretch of one author's work, bounded by inactivity gaps."""

    author: str  # email, the stable identity
    author_name: str  # display name from the last commit in the session
    start: datetime
    end: datetime
    commit_count: int
    files_touched: int  # distinct paths
    agent_commits: int
    human_commits: int

    @property
    def duration_minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60.0

    @property
    def agent_share(self) -> float:
        if self.commit_count == 0:
            return 0.0
        return self.agent_commits / self.commit_count


@dataclass(frozen=True)
class SessionsResult:
    sessions: tuple[WorkSession, ...]  # ordered by start, ascending
    total_sessions: int
    avg_commits_per_session: float
    avg_duration_minutes: float
    longest: WorkSession | None  # by commit count


@dataclass(frozen=True)
class Hotspot:
    """A region of a file edited repeatedly within a time window."""

    file_path: str
    line_start: int
    line_end: int
    modification_count: int  # distinct commits touching the region
    time_span_hours: float
    classification: str  # see hotspots.CLASSIFICATIONS
    commit_shas: tuple[str, ...]  # chronological, one per modification
    agent_modifications: int
    human_modifications: int
    score: float


@dataclass(frozen=True)
class HotspotsResult:
    hotspots: tuple[Hotspot, ...]  # sorted by score, descending
    total_detected: int  # before ``max_hotspots`` truncation


@dataclass(frozen=True)
class CoupledPair:
    """Two files that change together frequently."""

    file_a: str
    file_b: str
    shared_commits: int
    coupling_ratio: float  # shared / min(commits_a, commits_b)
    commit_shas: tuple[str, ...]


@dataclass(frozen=True)
class CouplingResult:
    pairs: tuple[CoupledPair, ...]  # sorted by coupling_ratio descending
    total_detected: int  # before truncation


@dataclass(frozen=True)
class FileOwnership:
    """Ownership breakdown for one file."""

    path: str
    total_lines: int
    owners: tuple[tuple[str, int], ...]  # (author_email, line_count), descending
    top_owner_share: float
    bus_factor: int


@dataclass(frozen=True)
class OwnershipResult:
    files: tuple[FileOwnership, ...]
    repo_bus_factor: int
    total_lines: int
    total_authors: int


@dataclass(frozen=True)
class ClassifiedCommit:
    """A commit classified as a revert or a fix."""

    sha: str
    kind: str  # "revert" or "fix"
    evidence: str  # what triggered the classification


@dataclass(frozen=True)
class CommitClassificationResult:
    reverts: tuple[ClassifiedCommit, ...]
    fixes: tuple[ClassifiedCommit, ...]
    total_reverts: int
    total_fixes: int


@dataclass(frozen=True)
class LineReworkResult:
    """True per-line rework, replacing the file-granularity upper bound."""

    total_surviving_lines: int
    reworked_lines: int
    line_rework_rate: float
    agent_reworked_lines: int
    human_reworked_lines: int
    agent_line_rework_rate: float
    human_line_rework_rate: float
