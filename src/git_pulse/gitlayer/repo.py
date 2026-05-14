from __future__ import annotations

import subprocess
from pathlib import Path


class NotARepositoryError(Exception):
    """Raised when the given path is not inside a git repository."""


class GitError(Exception):
    """Raised when a git command fails unexpectedly."""


class GitRepo:
    """Thin, typed wrapper over git plumbing commands for one repository."""

    def __init__(self, path: Path | str) -> None:
        candidate = Path(path)
        if not candidate.exists():
            raise NotARepositoryError(f"path does not exist: {candidate}")

        self._cwd = candidate if candidate.is_dir() else candidate.parent
        try:
            top = self._run("rev-parse", "--show-toplevel").strip()
        except GitError as exc:
            raise NotARepositoryError(f"not a git repository: {candidate}") from exc

        self.root = Path(top).resolve()

    def _run(self, *args: str, check: bool = True) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self._cwd,
            capture_output=True,
            text=True,
            errors="replace",
        )
        if check and result.returncode != 0:
            raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout

    def run(self, *args: str) -> str:
        """Run a git command in this repository and return stdout."""
        return self._run(*args)

    def has_commits(self) -> bool:
        return self._run("rev-parse", "--verify", "-q", "HEAD", check=False).strip() != ""

    def head_sha(self) -> str:
        sha = self._run("rev-parse", "HEAD").strip()
        if not sha:
            raise GitError("repository has no HEAD commit")
        return sha

    def current_branch(self) -> str:
        name = self._run("rev-parse", "--abbrev-ref", "HEAD").strip()
        return name if name != "HEAD" else self.head_sha()[:8]

    def resolve_rev(self, rev: str) -> str:
        sha = self._run("rev-parse", "--verify", "-q", f"{rev}^{{commit}}", check=False).strip()
        if not sha:
            raise ValueError(f"unknown revision: {rev}")
        return sha

    def is_shallow(self) -> bool:
        return self._run("rev-parse", "--is-shallow-repository").strip() == "true"
