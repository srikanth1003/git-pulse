from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AuthorClass(StrEnum):
    """How a commit's authorship is classified by the attribution engine."""

    HUMAN = "human"
    AGENT = "agent"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AttributionSignal:
    """One piece of evidence that a commit was agent-assisted."""

    name: str
    weight: float
    provider: str | None
    evidence: str


@dataclass(frozen=True)
class Attribution:
    """The attribution verdict for a commit, with the evidence behind it."""

    author_class: AuthorClass
    confidence: float
    provider: str | None
    signals: tuple[AttributionSignal, ...]


@dataclass(frozen=True)
class FileChange:
    """One file's change within a single commit."""

    path: str
    old_path: str | None  # set only on rename
    insertions: int
    deletions: int
    is_binary: bool

    @property
    def is_rename(self) -> bool:
        return self.old_path is not None

    @property
    def churn(self) -> int:
        return self.insertions + self.deletions


@dataclass(frozen=True)
class Commit:
    sha: str
    author_name: str
    author_email: str
    authored_at: datetime
    committed_at: datetime
    message: str
    parents: tuple[str, ...]
    files: tuple[FileChange, ...]
    attribution: Attribution

    @property
    def subject(self) -> str:
        return self.message.split("\n", 1)[0].strip()

    @property
    def is_merge(self) -> bool:
        return len(self.parents) > 1

    @property
    def is_root(self) -> bool:
        return len(self.parents) == 0

    @property
    def author_class(self) -> AuthorClass:
        return self.attribution.author_class

    @property
    def short_sha(self) -> str:
        return self.sha[:8]


@dataclass(frozen=True)
class History:
    """An immutable slice of repository history, newest commit first."""

    repo_path: str
    branch: str
    head_sha: str
    commits: tuple[Commit, ...]
    skipped_files: tuple[str, ...]
    is_shallow: bool

    def __len__(self) -> int:
        return len(self.commits)

    @property
    def newest(self) -> Commit:
        if not self.commits:
            raise ValueError("cannot take newest commit of an empty history")
        return self.commits[0]

    @property
    def oldest(self) -> Commit:
        if not self.commits:
            raise ValueError("cannot take oldest commit of an empty history")
        return self.commits[-1]

    @property
    def time_range(self) -> tuple[datetime, datetime]:
        if not self.commits:
            raise ValueError("cannot take time range of an empty history")
        stamps = [c.authored_at for c in self.commits]
        return min(stamps), max(stamps)

    @property
    def has_attribution_data(self) -> bool:
        return any(c.author_class is AuthorClass.AGENT for c in self.commits)
