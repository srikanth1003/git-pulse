from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from git import Repo


# Patterns that indicate agent involvement
AGENT_PATTERNS = [
    re.compile(r"Co-Authored-By:\s*(.+)", re.IGNORECASE),
    re.compile(r"\[(?:claude|copilot|cursor|aider|codeium|codex)\b", re.IGNORECASE),
    re.compile(r"(?:generated|authored)\s+(?:by|with)\s+(\w+)", re.IGNORECASE),
    re.compile(r"^aider:\s", re.IGNORECASE | re.MULTILINE),
]


class GitHistoryCollector:
    def __init__(self, repo_path: str, branch: str | None = None):
        self.repo = Repo(repo_path)
        self.branch = branch or self.repo.active_branch.name

    def collect(
        self,
        days: int | None = None,
        commits: int | None = None,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
    ) -> list[dict]:
        """Collect commit data from the repo. Returns list of commit dicts, most recent first."""
        kwargs = {}
        if days is not None:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            kwargs["since"] = since.isoformat()
        if commits is not None:
            kwargs["max_count"] = commits

        raw_commits = list(self.repo.iter_commits(self.branch, **kwargs))
        result = []

        for commit in raw_commits:
            files = self._extract_files(commit, include, exclude)
            is_agent, source = self._detect_attribution(commit.message)

            result.append(
                {
                    "hash": commit.hexsha,
                    "author": str(commit.author),
                    "timestamp": commit.committed_datetime.isoformat(),
                    "message": commit.message.strip(),
                    "files": files,
                    "is_agent_attributed": is_agent,
                    "attribution_source": source,
                }
            )

        return result

    def _extract_files(self, commit, include, exclude) -> list[dict]:
        """Extract file change data from a commit."""
        if not commit.parents:
            diffs = commit.diff(None, create_patch=True, R=True)
        else:
            diffs = commit.parents[0].diff(commit, create_patch=True)

        files = []
        for diff in diffs:
            path = diff.b_path or diff.a_path
            if not path:
                continue
            if include and not self._matches_any(path, include):
                continue
            if exclude and self._matches_any(path, exclude):
                continue

            diff_text = diff.diff.decode("utf-8", errors="replace") if diff.diff else ""
            insertions = sum(1 for line in diff_text.splitlines() if line.startswith("+") and not line.startswith("+++"))
            deletions = sum(1 for line in diff_text.splitlines() if line.startswith("-") and not line.startswith("---"))

            files.append(
                {
                    "path": path,
                    "insertions": insertions,
                    "deletions": deletions,
                    "diff": diff_text[:3000],
                }
            )

        return files

    def _detect_attribution(self, message: str) -> tuple[bool, str | None]:
        """Check commit message for agent attribution markers."""
        for pattern in AGENT_PATTERNS:
            match = pattern.search(message)
            if match:
                return True, match.group(0).strip()
        return False, None

    @staticmethod
    def _matches_any(path: str, patterns: list[str]) -> bool:
        from fnmatch import fnmatch
        return any(fnmatch(path, p) for p in patterns)
