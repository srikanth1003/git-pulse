"""The single object every renderer consumes.

Renderers must be pure functions of a ``Report``. Nothing here holds a live
``GitRepo`` handle or a subprocess, so a report can be serialised, cached, or
rendered long after the repository is gone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from git_pulse.analyst.models import Insight
from git_pulse.models.history import AuthorClass
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


@dataclass(frozen=True)
class AuthorSummary:
    email: str
    name: str
    author_class: AuthorClass
    commits: int
    lines_added: int
    lines_removed: int


@dataclass(frozen=True)
class AttributionSummary:
    total_commits: int
    agent_commits: int
    mixed_commits: int
    human_commits: int
    agent_lines_added: int
    agent_lines_removed: int
    total_lines_added: int
    total_lines_removed: int
    signals_seen: dict[str, int]
    providers_seen: dict[str, int]
    authors: tuple[AuthorSummary, ...]

    @property
    def agent_commit_share(self) -> float:
        return self.agent_commits / self.total_commits if self.total_commits else 0.0

    @property
    def agent_line_share(self) -> float:
        if not self.total_lines_added:
            return 0.0
        return self.agent_lines_added / self.total_lines_added


@dataclass(frozen=True)
class Report:
    # Provenance
    repo_path: str
    repo_name: str
    branch: str
    head_sha: str
    generated_at: datetime
    git_pulse_version: str
    options: dict[str, Any]

    # Scope
    total_commits: int
    time_range: tuple[datetime, datetime] | None
    skipped_files: tuple[str, ...]

    # Analysis
    attribution: AttributionSummary
    churn: ChurnResult
    velocity: VelocityResult
    sessions: SessionsResult
    hotspots: HotspotsResult
    rework: ReworkResult
    coupling: CouplingResult
    ownership: OwnershipResult | None = None
    line_rework: LineReworkResult | None = None
    commit_classification: CommitClassificationResult | None = None
    survival: SurvivalResult | None = None

    # Optional LLM layer — ``narrative`` is the summary text.
    narrative: str | None = None
    insights: tuple[Insight, ...] = field(default_factory=tuple)
    actions: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        return self.total_commits == 0
