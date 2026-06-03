from __future__ import annotations

import gzip
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from git_pulse.models.history import (
    Attribution,
    AttributionSignal,
    AuthorClass,
    Commit,
    FileChange,
    History,
)

# Bump whenever the encoded shape changes; old entries then miss instead of
# deserializing into the wrong structure.
CACHE_SCHEMA_VERSION = 1


def cache_root() -> Path:
    """Base cache directory, honouring ``XDG_CACHE_HOME``."""
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "gitpulse"


@dataclass(frozen=True)
class CacheInfo:
    directory: Path
    entries: int
    bytes: int


class HistoryCache:
    """Stores parsed :class:`History` objects as gzipped JSON on disk.

    Nothing is ever written inside ``.git``.
    """

    def __init__(self, repo_root: Path | str, enabled: bool = True) -> None:
        self.repo_root = Path(repo_root)
        self.enabled = enabled
        digest = hashlib.sha256(str(self.repo_root.resolve()).encode()).hexdigest()[:16]
        self.directory = cache_root() / digest

    def key(self, *, head_sha: str, branch: str, options: dict[str, Any]) -> str:
        payload = json.dumps(
            {"head": head_sha, "branch": branch, "options": options},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    def path_for(self, key: str) -> Path:
        return self.directory / f"{key}.json.gz"

    def load(self, key: str) -> History | None:
        if not self.enabled:
            return None
        path = self.path_for(key)
        if not path.exists():
            return None
        try:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError, EOFError):
            return None  # corrupt entry — treat as a miss
        if data.get("schema") != CACHE_SCHEMA_VERSION:
            return None
        try:
            return _decode_history(data["history"])
        except (KeyError, TypeError, ValueError):
            return None

    def store(self, key: str, history: History) -> None:
        if not self.enabled:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = {"schema": CACHE_SCHEMA_VERSION, "history": _encode_history(history)}
        tmp = self.path_for(key).with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle)
        tmp.replace(self.path_for(key))  # atomic, so readers never see a partial file

    def clear(self) -> int:
        if not self.directory.exists():
            return 0
        removed = 0
        for path in self.directory.glob("*.json.gz"):
            path.unlink()
            removed += 1
        return removed

    def info(self) -> CacheInfo:
        if not self.directory.exists():
            return CacheInfo(directory=self.directory, entries=0, bytes=0)
        paths = list(self.directory.glob("*.json.gz"))
        return CacheInfo(
            directory=self.directory,
            entries=len(paths),
            bytes=sum(p.stat().st_size for p in paths),
        )


def _encode_history(history: History) -> dict[str, Any]:
    return {
        "repo_path": history.repo_path,
        "branch": history.branch,
        "head_sha": history.head_sha,
        "skipped_files": list(history.skipped_files),
        "is_shallow": history.is_shallow,
        "commits": [_encode_commit(c) for c in history.commits],
    }


def _encode_commit(commit: Commit) -> dict[str, Any]:
    return {
        "sha": commit.sha,
        "author_name": commit.author_name,
        "author_email": commit.author_email,
        "authored_at": commit.authored_at.isoformat(),
        "committed_at": commit.committed_at.isoformat(),
        "message": commit.message,
        "parents": list(commit.parents),
        "files": [
            {
                "path": f.path,
                "old_path": f.old_path,
                "insertions": f.insertions,
                "deletions": f.deletions,
                "is_binary": f.is_binary,
            }
            for f in commit.files
        ],
        "attribution": {
            "author_class": commit.attribution.author_class.value,
            "confidence": commit.attribution.confidence,
            "provider": commit.attribution.provider,
            "signals": [
                {
                    "name": s.name,
                    "weight": s.weight,
                    "provider": s.provider,
                    "evidence": s.evidence,
                }
                for s in commit.attribution.signals
            ],
        },
    }


def _decode_history(data: dict[str, Any]) -> History:
    return History(
        repo_path=data["repo_path"],
        branch=data["branch"],
        head_sha=data["head_sha"],
        commits=tuple(_decode_commit(c) for c in data["commits"]),
        skipped_files=tuple(data["skipped_files"]),
        is_shallow=data["is_shallow"],
    )


def _decode_commit(data: dict[str, Any]) -> Commit:
    attribution = data["attribution"]
    return Commit(
        sha=data["sha"],
        author_name=data["author_name"],
        author_email=data["author_email"],
        authored_at=datetime.fromisoformat(data["authored_at"]),
        committed_at=datetime.fromisoformat(data["committed_at"]),
        message=data["message"],
        parents=tuple(data["parents"]),
        files=tuple(
            FileChange(
                path=f["path"],
                old_path=f["old_path"],
                insertions=f["insertions"],
                deletions=f["deletions"],
                is_binary=f["is_binary"],
            )
            for f in data["files"]
        ),
        attribution=Attribution(
            author_class=AuthorClass(attribution["author_class"]),
            confidence=attribution["confidence"],
            provider=attribution["provider"],
            signals=tuple(
                AttributionSignal(
                    name=s["name"],
                    weight=s["weight"],
                    provider=s["provider"],
                    evidence=s["evidence"],
                )
                for s in attribution["signals"]
            ),
        ),
    )
