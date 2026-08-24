from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from git_pulse.gitlayer.diff import parse_unified_diff
from git_pulse.gitlayer.repo import GitRepo
from git_pulse.models.history import History

_SENTINEL = "\x1e"


@dataclass(frozen=True)
class LineRange:
    """One hunk's new-side line span, from one commit, in one file."""

    sha: str
    line_start: int
    line_end: int


PatchIndex = dict[str, tuple[LineRange, ...]]


def most_touched_paths(history: History, max_files: int) -> list[str]:
    """The most-touched paths, so a diff fetch over them stays bounded."""
    counts: dict[str, int] = {}
    for commit in history.commits:
        for change in commit.files:
            counts[change.path] = counts.get(change.path, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [path for path, _ in ranked[:max_files]]


def collect_patches(history: History, repo: GitRepo, paths: Sequence[str]) -> PatchIndex:
    """Fetch every hunk touching ``paths`` in one ``git log -p`` call.

    Restricted to commits ``history`` already knows about, so callers that
    narrowed the range with ``--days``/``--since``/``--commits`` get patches
    narrowed the same way, even though this walks from ``head_sha``. Binary
    files are dropped; there is nothing line-level to say about them.
    """
    if not paths or not history.commits:
        return {}

    known = {c.sha for c in history.commits}
    output = repo.run(
        "log",
        history.head_sha,
        f"--format={_SENTINEL}%H",
        "-p",
        "-M",
        "--first-parent",
        "--no-color",
        "--",
        *paths,
    )

    per_path: dict[str, list[LineRange]] = {}
    for chunk in output.split(_SENTINEL):
        if not chunk.strip():
            continue
        sha, _, diff_text = chunk.partition("\n")
        sha = sha.strip()
        if sha not in known:
            continue  # outside the analyzed range (e.g. --days narrowed it)

        for file_diff in parse_unified_diff(diff_text):
            if file_diff.is_binary:
                continue
            for hunk in file_diff.hunks:
                per_path.setdefault(file_diff.path, []).append(
                    LineRange(
                        sha=sha,
                        line_start=hunk.new_start,
                        line_end=max(hunk.new_start + hunk.new_count - 1, hunk.new_start),
                    )
                )

    return {path: tuple(ranges) for path, ranges in per_path.items()}
