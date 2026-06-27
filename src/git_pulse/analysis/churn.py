from __future__ import annotations

from dataclasses import dataclass, field

from git_pulse.models.history import AuthorClass, History
from git_pulse.models.results import ChurnResult, FileChurn


@dataclass
class _Accumulator:
    insertions: int = 0
    deletions: int = 0
    commits: int = 0
    agent_commits: int = 0
    human_commits: int = 0
    authors: set[str] = field(default_factory=set)


def analyze_churn(history: History, *, limit: int | None = None) -> ChurnResult:
    """Aggregate per-file churn across ``history``.

    History is newest-first, so rename mappings are recorded as they are
    encountered and then apply to the older commits seen afterwards. That
    collapses a renamed file's whole history onto its current path.
    """
    canonical: dict[str, str] = {}
    totals: dict[str, _Accumulator] = {}

    for commit in history.commits:
        for change in commit.files:
            path = canonical.get(change.path, change.path)

            entry = totals.setdefault(path, _Accumulator())
            entry.insertions += change.insertions
            entry.deletions += change.deletions
            entry.commits += 1
            entry.authors.add(commit.author_email)
            if commit.author_class is AuthorClass.AGENT:
                entry.agent_commits += 1
            else:
                entry.human_commits += 1

            if change.old_path is not None:
                canonical[change.old_path] = path

    files = [
        FileChurn(
            path=path,
            commits=acc.commits,
            insertions=acc.insertions,
            deletions=acc.deletions,
            distinct_authors=len(acc.authors),
            agent_commits=acc.agent_commits,
            human_commits=acc.human_commits,
        )
        for path, acc in totals.items()
    ]
    files.sort(key=lambda f: (-f.churn, f.path))

    return ChurnResult(
        files=tuple(files[:limit] if limit is not None else files),
        total_files=len(files),
        total_insertions=sum(f.insertions for f in files),
        total_deletions=sum(f.deletions for f in files),
    )
