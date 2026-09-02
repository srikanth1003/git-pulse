"""Line-lifetime index: which commit introduced each surviving line.

The index is built from ``git blame --porcelain`` output, which gives the
introducing commit for every line in the file at a given revision. Combined
with the patch history (which records deletions), this tells you:

- which lines survived to HEAD and who wrote them (ownership, bus factor),
- which lines were overwritten and how long they lasted (rework, survival).

The index is file-scoped: callers choose which paths to index, typically the
most-churn files, so cost stays bounded.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from git_pulse.gitlayer.patches import PatchIndex
from git_pulse.gitlayer.repo import GitRepo
from git_pulse.models.history import History


@dataclass(frozen=True)
class LineBirth:
    """One line in the file at ``rev``, with the commit that introduced it."""

    line_number: int
    sha: str
    author_name: str
    author_email: str
    authored_at: datetime


@dataclass(frozen=True)
class LineDeath:
    """A range of lines removed by a commit (detected from the old side of a hunk)."""

    sha: str
    old_start: int
    old_end: int


@dataclass(frozen=True)
class FileLifetime:
    """Line-level lifetime data for one file."""

    path: str
    births: tuple[LineBirth, ...]
    deaths: tuple[LineDeath, ...]


LifetimeIndex = dict[str, FileLifetime]


def build_lifetime_index(
    history: History,
    repo: GitRepo,
    paths: Sequence[str],
    patches: PatchIndex | None = None,
) -> LifetimeIndex:
    """Build the line-lifetime index for ``paths``.

    ``patches`` is optional — when provided, death events are extracted from
    the old side of each hunk. Without it, only birth data is available (which
    still enables ownership and bus-factor analysis).
    """
    if not paths or not history.commits:
        return {}

    known_shas = {c.sha for c in history.commits}
    index: LifetimeIndex = {}

    for path in paths:
        births = _blame(repo, history.head_sha, path, known_shas)
        deaths = _deaths_from_patches(path, patches) if patches else ()
        if births or deaths:
            index[path] = FileLifetime(path=path, births=births, deaths=deaths)

    return index


_BLAME_SHA_RE = re.compile(r"^([0-9a-f]{40}) \d+ (\d+)")
_AUTHOR_RE = re.compile(r"^author (.+)")
_AUTHOR_MAIL_RE = re.compile(r"^author-mail <(.+)>")
_AUTHOR_TIME_RE = re.compile(r"^author-time (\d+)")
_AUTHOR_TZ_RE = re.compile(r"^author-tz ([+-]\d{4})")


def _blame(repo: GitRepo, rev: str, path: str, known_shas: set[str]) -> tuple[LineBirth, ...]:
    """Parse ``git blame --porcelain`` into per-line birth records."""
    try:
        output = repo.run("blame", "--porcelain", rev, "--", path)
    except Exception:
        return ()

    births: list[LineBirth] = []
    current_sha = ""
    current_line = 0
    sha_meta: dict[str, dict[str, str]] = {}

    for line in output.splitlines():
        m = _BLAME_SHA_RE.match(line)
        if m:
            current_sha = m.group(1)
            current_line = int(m.group(2))
            sha_meta.setdefault(current_sha, {})
            continue

        if current_sha not in sha_meta:
            continue

        meta = sha_meta[current_sha]

        m = _AUTHOR_RE.match(line)
        if m:
            meta["author"] = m.group(1)
            continue
        m = _AUTHOR_MAIL_RE.match(line)
        if m:
            meta["email"] = m.group(1)
            continue
        m = _AUTHOR_TIME_RE.match(line)
        if m:
            meta["time"] = m.group(1)
            continue
        m = _AUTHOR_TZ_RE.match(line)
        if m:
            meta["tz"] = m.group(1)
            continue

        if line.startswith("\t") and "time" in meta:
            births.append(
                LineBirth(
                    line_number=current_line,
                    sha=current_sha,
                    author_name=meta.get("author", ""),
                    author_email=meta.get("email", ""),
                    authored_at=datetime.fromtimestamp(int(meta["time"]), tz=UTC),
                )
            )

    return tuple(births)


def _deaths_from_patches(path: str, patches: PatchIndex | None) -> tuple[LineDeath, ...]:
    """Extract death events from the patch index.

    Each ``LineRange`` records the *new* side. The old side (deleted lines) is
    inferred: any hunk with new_count < old_count implies lines were removed.
    We record the removing commit and the old-side span.

    Since ``LineRange`` only stores the new side, we use a simpler heuristic:
    each hunk that appears in the patch index is a modification event. If the
    hunk exists, *something* was deleted or replaced. We record each hunk's
    commit as a death event covering the range, since we know that commit
    touched those lines.
    """
    if not patches or path not in patches:
        return ()

    deaths: list[LineDeath] = []
    for rng in patches[path]:
        deaths.append(
            LineDeath(
                sha=rng.sha,
                old_start=rng.line_start,
                old_end=rng.line_end,
            )
        )
    return tuple(deaths)
