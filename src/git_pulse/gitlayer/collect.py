from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from git_pulse.attribution.engine import AttributionEngine
from git_pulse.gitlayer.cache import HistoryCache
from git_pulse.gitlayer.log import LogRecord, build_log_args, parse_log_output
from git_pulse.gitlayer.repo import GitRepo
from git_pulse.models.history import Commit, FileChange, History


@dataclass(frozen=True)
class CollectOptions:
    """Everything that narrows which history is collected.

    Note on globs: patterns are matched with :func:`fnmatch.fnmatch` against the
    full repo-relative path, so ``*`` also crosses ``/``. That makes ``*.lock``
    match ``sub/dir/a.lock`` and ``vendor/**`` match everything under
    ``vendor/``, which is what users expect from an exclude list.
    """

    days: int | None = None
    commits: int | None = None
    since: str | None = None
    until: str | None = None
    branch: str | None = None
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    include_merges: bool = False
    ignore_whitespace: bool = False

    @property
    def has_path_filters(self) -> bool:
        return bool(self.include or self.exclude)

    def as_cache_dict(self) -> dict[str, Any]:
        return {
            "days": self.days,
            "commits": self.commits,
            "since": self.since,
            "until": self.until,
            "include": list(self.include),
            "exclude": list(self.exclude),
            "include_merges": self.include_merges,
            "ignore_whitespace": self.ignore_whitespace,
        }


def collect_history(
    repo_path: Path | str,
    options: CollectOptions | None = None,
    *,
    cache: HistoryCache | None = None,
    engine: AttributionEngine | None = None,
    now: datetime | None = None,
) -> History:
    """Collect a :class:`History` slice, using ``cache`` when it hits."""
    options = options or CollectOptions()
    engine = engine or AttributionEngine()
    repo = GitRepo(repo_path)

    if not repo.has_commits():
        return History(
            repo_path=str(repo.root),
            branch=options.branch or "main",
            head_sha="",
            commits=(),
            skipped_files=(),
            is_shallow=repo.is_shallow(),
        )

    rev = options.branch or repo.current_branch()
    head_sha = repo.resolve_rev(rev)

    key = ""
    if cache is not None:
        key = cache.key(head_sha=head_sha, branch=rev, options=options.as_cache_dict())
        cached = cache.load(key)
        if cached is not None:
            return cached

    records = _run_log(repo, rev, options, now=now)
    commits, skipped = _to_commits(records, options, engine)

    history = History(
        repo_path=str(repo.root),
        branch=rev,
        head_sha=head_sha,
        commits=commits,
        skipped_files=skipped,
        is_shallow=repo.is_shallow(),
    )

    if cache is not None:
        cache.store(key, history)

    return history


def _run_log(
    repo: GitRepo, rev: str, options: CollectOptions, *, now: datetime | None
) -> list[LogRecord]:
    since = options.since
    if since is None and options.days is not None:
        reference = now or datetime.now(UTC)
        since = (reference - timedelta(days=options.days)).isoformat()

    args = build_log_args(
        rev=rev,
        max_count=options.commits,
        since=since,
        until=options.until,
        include_merges=options.include_merges,
        ignore_whitespace=options.ignore_whitespace,
    )
    return parse_log_output(repo.run(*args))


def _to_commits(
    records: list[LogRecord], options: CollectOptions, engine: AttributionEngine
) -> tuple[tuple[Commit, ...], tuple[str, ...]]:
    commits: list[Commit] = []
    skipped: set[str] = set()

    for record in records:
        kept: list[FileChange] = []
        for change in record.files:
            if change.is_binary:
                skipped.add(change.path)
                continue
            if not _path_allowed(change.path, options):
                continue
            kept.append(change)

        # When filters are active, a commit left with nothing is noise. Without
        # filters, keep it — genuinely empty commits are real history.
        if options.has_path_filters and not kept:
            continue

        commits.append(
            Commit(
                sha=record.sha,
                author_name=record.author_name,
                author_email=record.author_email,
                authored_at=record.authored_at,
                committed_at=record.committed_at,
                message=record.message,
                parents=record.parents,
                files=tuple(kept),
                attribution=engine.attribute(
                    message=record.message,
                    author_name=record.author_name,
                    author_email=record.author_email,
                    committer_name=record.author_name,
                    committer_email=record.author_email,
                ),
            )
        )

    return tuple(commits), tuple(sorted(skipped))


def _path_allowed(path: str, options: CollectOptions) -> bool:
    if options.include and not any(fnmatch(path, p) for p in options.include):
        return False
    return not any(fnmatch(path, p) for p in options.exclude)
