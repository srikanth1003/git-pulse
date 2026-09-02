"""Classify commits as reverts or fixes from message patterns.

Revert detection:
  - Subject starts with "Revert " (git's default revert message)
  - Subject starts with "revert:" or "revert(" (conventional-commit style)

Fix detection:
  - Subject starts with "fix:", "fix(", "bugfix:", "hotfix:"
  - Body contains "fixes #N", "closes #N", "resolves #N"
"""

from __future__ import annotations

import re

from git_pulse.models.history import History
from git_pulse.models.results import ClassifiedCommit, CommitClassificationResult

_REVERT_RE = re.compile(r"^(?:Revert |revert[:(])", re.IGNORECASE)
_FIX_SUBJECT_RE = re.compile(r"^(?:fix|bugfix|hotfix)[:(]", re.IGNORECASE)
_FIX_BODY_RE = re.compile(r"(?:fix(?:es)?|close[sd]?|resolve[sd]?)\s+#\d+", re.IGNORECASE)


def classify_commits(history: History) -> CommitClassificationResult:
    """Scan every commit for revert and fix patterns."""
    reverts: list[ClassifiedCommit] = []
    fixes: list[ClassifiedCommit] = []

    for commit in history.commits:
        subject = commit.message.split("\n", 1)[0]

        if _REVERT_RE.match(subject):
            reverts.append(ClassifiedCommit(sha=commit.sha, kind="revert", evidence=subject))
            continue

        evidence = _fix_evidence(subject, commit.message)
        if evidence:
            fixes.append(ClassifiedCommit(sha=commit.sha, kind="fix", evidence=evidence))

    return CommitClassificationResult(
        reverts=tuple(reverts),
        fixes=tuple(fixes),
        total_reverts=len(reverts),
        total_fixes=len(fixes),
    )


def _fix_evidence(subject: str, full_message: str) -> str | None:
    if _FIX_SUBJECT_RE.match(subject):
        return subject
    m = _FIX_BODY_RE.search(full_message)
    if m:
        return m.group(0)
    return None
