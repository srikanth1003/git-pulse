from __future__ import annotations

from dataclasses import dataclass, field

from git_pulse.models.history import AuthorClass, History
from git_pulse.models.results import ChurnResult, FileChurn, ReworkResult


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


def analyze_rework(history: History) -> ReworkResult:
    """Compute file-granularity rework rates.

    Ported from ``MetricsCalculator.rework_rate`` in 0.1.0 so that upgrading does
    not lose a metric. See :class:`ReworkResult` for why this over-reports.
    """
    churn_by_file: dict[str, int] = {}
    commits_by_file: dict[str, int] = {}
    agent_churn_by_file: dict[str, int] = {}
    human_churn_by_file: dict[str, int] = {}

    for commit in history.commits:
        for change in commit.files:
            # Collection already drops binaries; guard anyway, since a binary has
            # no line count and would inflate ``total_files`` with zero churn.
            if change.is_binary:
                continue
            churn = change.insertions + change.deletions
            churn_by_file[change.path] = churn_by_file.get(change.path, 0) + churn
            commits_by_file[change.path] = commits_by_file.get(change.path, 0) + 1
            bucket = (
                agent_churn_by_file
                if commit.author_class is AuthorClass.AGENT
                else human_churn_by_file
            )
            bucket[change.path] = bucket.get(change.path, 0) + churn

    total_churn = sum(churn_by_file.values())
    reworked = {p for p, n in commits_by_file.items() if n > 1}
    reworked_churn = sum(churn_by_file[p] for p in reworked)

    def _rate(source: dict[str, int]) -> float:
        total = sum(source.values())
        if not total:
            return 0.0
        return sum(source.get(p, 0) for p in reworked) / total

    return ReworkResult(
        file_rework_rate=(reworked_churn / total_churn) if total_churn else 0.0,
        agent_rework_rate=_rate(agent_churn_by_file),
        human_rework_rate=_rate(human_churn_by_file),
        reworked_files=len(reworked),
        total_files=len(churn_by_file),
        reworked_churn=reworked_churn,
        total_churn=total_churn,
    )
