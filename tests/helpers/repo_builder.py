from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Fixed epoch so every test repo has byte-identical timestamps across machines.
EPOCH = datetime(2025, 1, 1, 9, 0, 0, tzinfo=UTC)

DEFAULT_AUTHOR = "Test Human"
DEFAULT_EMAIL = "human@example.com"


class RepoBuilder:
    """Builds a real temporary git repository with fully controlled history.

    Timestamps advance only when ``advance()`` is called, so histories are
    reproducible. Every mutating method returns ``self`` for chaining.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self._clock = EPOCH
        self._run("init", "-q", "-b", "main")
        self._run("config", "user.name", DEFAULT_AUTHOR)
        self._run("config", "user.email", DEFAULT_EMAIL)
        self._run("config", "commit.gpgsign", "false")

    def _run(self, *args: str, env: dict[str, str] | None = None) -> str:
        merged = {**os.environ, **env} if env else None
        result = subprocess.run(
            ["git", *args],
            cwd=self.path,
            env=merged,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def advance(self, *, minutes: float = 0, hours: float = 0, days: float = 0) -> RepoBuilder:
        self._clock += timedelta(minutes=minutes, hours=hours, days=days)
        return self

    def write(self, rel_path: str, content: str) -> RepoBuilder:
        target = self.path / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return self

    def write_binary(self, rel_path: str, data: bytes) -> RepoBuilder:
        target = self.path / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return self

    def delete(self, rel_path: str) -> RepoBuilder:
        self._run("rm", "-q", "--", rel_path)
        return self

    def move(self, src: str, dst: str) -> RepoBuilder:
        (self.path / dst).parent.mkdir(parents=True, exist_ok=True)
        self._run("mv", src, dst)
        return self

    def commit(
        self,
        message: str,
        *,
        author: str = DEFAULT_AUTHOR,
        email: str = DEFAULT_EMAIL,
        trailers: str = "",
    ) -> str:
        body = f"{message}\n\n{trailers}" if trailers else message
        stamp = self._clock.isoformat()
        self._run("add", "-A")
        self._run(
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            body,
            env={
                "GIT_AUTHOR_NAME": author,
                "GIT_AUTHOR_EMAIL": email,
                "GIT_AUTHOR_DATE": stamp,
                "GIT_COMMITTER_NAME": author,
                "GIT_COMMITTER_EMAIL": email,
                "GIT_COMMITTER_DATE": stamp,
            },
        )
        return self.head()

    def agent_commit(
        self,
        message: str,
        *,
        provider: str = "Claude",
        provider_email: str = "noreply@anthropic.com",
        author: str = DEFAULT_AUTHOR,
        email: str = DEFAULT_EMAIL,
    ) -> str:
        return self.commit(
            message,
            author=author,
            email=email,
            trailers=f"Co-Authored-By: {provider} <{provider_email}>",
        )

    def head(self) -> str:
        return self._run("rev-parse", "HEAD").strip()
