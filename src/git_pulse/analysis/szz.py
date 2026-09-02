"""SZZ bug-introduction attribution.

Given fix commits (from commit_class), uses ``git blame`` on the parent of each
fix to find which commits introduced the lines that were fixed. Those
introducing commits are labeled as bug-introducing.
"""

from __future__ import annotations

import re

from git_pulse.gitlayer.repo import GitRepo
from git_pulse.models.history import History
from git_pulse.models.results import BugIntroduction, CommitClassificationResult, SZZResult

_BLAME_RE = re.compile(r"^([0-9a-f]{40}) \d+ (\d+)")
_AUTHOR_MAIL_RE = re.compile(r"^author-mail <(.+)>")


def analyze_szz(
    history: History, repo: GitRepo, classification: CommitClassificationResult | None
) -> SZZResult:
    """Trace fix commits back to their bug-introducing commits."""
    if classification is None or not classification.fixes:
        return SZZResult(introductions=(), total_introductions=0, bug_introducing_commits=0)

    known = {c.sha for c in history.commits}
    introductions: list[BugIntroduction] = []

    for fix in classification.fixes:
        if fix.sha not in known:
            continue

        commit = next((c for c in history.commits if c.sha == fix.sha), None)
        if commit is None or not commit.parents:
            continue

        parent_sha = commit.parents[0]
        for change in commit.files:
            if change.is_binary or change.deletions == 0:
                continue

            blamed = _blame_parent(repo, parent_sha, change.path)
            for intro_sha, email in blamed:
                if intro_sha != fix.sha and intro_sha in known:
                    introductions.append(
                        BugIntroduction(
                            introducing_sha=intro_sha,
                            fix_sha=fix.sha,
                            file_path=change.path,
                            author_email=email,
                        )
                    )

    distinct = len({i.introducing_sha for i in introductions})
    return SZZResult(
        introductions=tuple(introductions),
        total_introductions=len(introductions),
        bug_introducing_commits=distinct,
    )


def _blame_parent(repo: GitRepo, parent_sha: str, path: str) -> list[tuple[str, str]]:
    """Blame the file at ``parent_sha`` and return (sha, email) pairs."""
    try:
        output = repo.run("blame", "--porcelain", parent_sha, "--", path)
    except Exception:
        return []

    results: list[tuple[str, str]] = []
    current_sha = ""
    sha_email: dict[str, str] = {}

    for line in output.splitlines():
        m = _BLAME_RE.match(line)
        if m:
            current_sha = m.group(1)
            continue
        m = _AUTHOR_MAIL_RE.match(line)
        if m and current_sha:
            sha_email[current_sha] = m.group(1)
            continue
        if line.startswith("\t") and current_sha:
            results.append((current_sha, sha_email.get(current_sha, "")))

    return results
