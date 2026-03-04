from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class Hotspot:
    file_path: str
    line_start: int
    line_end: int
    modification_count: int
    time_span_hours: float
    classification: str  # agent-reworked | human-fixing-agent | repeated-agent | human-iteration | unknown
    commit_hashes: list[str]
    diff_snippets: list[str]
    score: float


@dataclass
class FileChurnEntry:
    file_path: str
    modification_count: int
    insertions: int
    deletions: int
    distinct_authors: int


@dataclass
class ChangeVelocity:
    commits_per_day: float
    avg_files_per_commit: float
    peak_day: str
    peak_commits: int


@dataclass
class AgentHumanRatio:
    agent_commits: int
    human_commits: int
    ratio: float  # agent / total


@dataclass
class WorkSession:
    start: datetime
    end: datetime
    commit_count: int
    files_touched: int
    dominant_author: str


@dataclass
class CollectorReport:
    repo_path: str
    branch: str
    commit_range: tuple[str, str]
    time_range: tuple[datetime, datetime]
    total_commits: int
    total_files_changed: int
    hotspots: list[Hotspot]
    file_churn: list[FileChurnEntry]
    change_velocity: ChangeVelocity
    agent_human_ratio: AgentHumanRatio | None
    rework_rate: float
    sessions: list[WorkSession]
    has_attribution_data: bool
    attribution_source: str | None

    def to_dict(self) -> dict:
        """Serialize to dict with datetime handling for JSON."""
        d = asdict(self)

        def convert(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [convert(i) for i in obj]
            return obj

        return convert(d)
