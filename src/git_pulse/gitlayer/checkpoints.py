"""Discover and analyze agent checkpoint refs.

Agent coding tools may create local checkpoint refs that record intermediate
states — code the agent tried before the final commit. These refs never reach
the remote but carry signal about agent effort and rework.

Supported ref patterns:
  - refs/agent-checkpoints/<session>/<n>
  - refs/checkpoints/<session>/<n>
  - refs/agent/<tool>/<session>/<n>

Each checkpoint is a commit object. We diff consecutive checkpoints and the
final checkpoint against the corresponding main-branch commit to measure how
much the agent changed between attempts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from git_pulse.gitlayer.repo import GitRepo

_CHECKPOINT_PREFIXES = (
    "refs/agent-checkpoints/",
    "refs/checkpoints/",
    "refs/agent/",
)


@dataclass(frozen=True)
class Checkpoint:
    """One checkpoint ref."""

    ref: str
    sha: str
    authored_at: datetime
    message: str


@dataclass(frozen=True)
class CheckpointSession:
    """A sequence of checkpoints from one agent session."""

    session_id: str
    tool: str
    checkpoints: tuple[Checkpoint, ...]
    final_sha: str | None


@dataclass(frozen=True)
class CheckpointDiff:
    """Diff between two consecutive checkpoints or checkpoint-to-final."""

    from_sha: str
    to_sha: str
    files_changed: int
    insertions: int
    deletions: int


@dataclass(frozen=True)
class CheckpointStats:
    """Aggregate stats from all discovered checkpoint sessions."""

    total_sessions: int
    total_checkpoints: int
    total_attempts_insertions: int
    total_attempts_deletions: int
    sessions: tuple[CheckpointSession, ...]
    diffs: tuple[CheckpointDiff, ...]


def discover_checkpoints(repo: GitRepo) -> CheckpointStats:
    """Discover all checkpoint refs and compute attempt stats."""
    refs = _list_checkpoint_refs(repo)
    if not refs:
        return CheckpointStats(
            total_sessions=0,
            total_checkpoints=0,
            total_attempts_insertions=0,
            total_attempts_deletions=0,
            sessions=(),
            diffs=(),
        )

    sessions = _group_into_sessions(refs, repo)
    diffs = _compute_diffs(sessions, repo)

    return CheckpointStats(
        total_sessions=len(sessions),
        total_checkpoints=sum(len(s.checkpoints) for s in sessions),
        total_attempts_insertions=sum(d.insertions for d in diffs),
        total_attempts_deletions=sum(d.deletions for d in diffs),
        sessions=tuple(sessions),
        diffs=tuple(diffs),
    )


def _list_checkpoint_refs(repo: GitRepo) -> list[tuple[str, str]]:
    """Return (ref, sha) pairs for all checkpoint refs."""
    try:
        output = repo.run("for-each-ref", "--format=%(refname) %(objectname)", "refs/")
    except Exception:
        return []

    results: list[tuple[str, str]] = []
    for line in output.splitlines():
        parts = line.strip().split(" ", 1)
        if len(parts) != 2:
            continue
        ref, sha = parts
        if any(ref.startswith(prefix) for prefix in _CHECKPOINT_PREFIXES):
            results.append((ref, sha))

    return sorted(results)


def _group_into_sessions(refs: list[tuple[str, str]], repo: GitRepo) -> list[CheckpointSession]:
    """Group checkpoint refs into sessions by their path structure."""
    session_map: dict[str, list[tuple[str, str]]] = {}

    for ref, sha in refs:
        for prefix in _CHECKPOINT_PREFIXES:
            if ref.startswith(prefix):
                remainder = ref[len(prefix) :]
                parts = remainder.rsplit("/", 1)
                session_id = parts[0] if len(parts) > 1 else remainder
                session_map.setdefault(session_id, []).append((ref, sha))
                break

    sessions: list[CheckpointSession] = []
    for session_id, session_refs in sorted(session_map.items()):
        checkpoints: list[Checkpoint] = []
        tool = _extract_tool(session_refs[0][0])

        for ref, sha in session_refs:
            try:
                log_out = repo.run("log", "-1", "--format=%aI%n%s", sha)
                lines = log_out.strip().splitlines()
                authored_at = datetime.fromisoformat(lines[0]) if lines else datetime.min
                message = lines[1] if len(lines) > 1 else ""
            except Exception:
                authored_at = datetime.min
                message = ""

            checkpoints.append(
                Checkpoint(ref=ref, sha=sha, authored_at=authored_at, message=message)
            )

        checkpoints.sort(key=lambda c: (c.authored_at, c.ref))

        sessions.append(
            CheckpointSession(
                session_id=session_id,
                tool=tool,
                checkpoints=tuple(checkpoints),
                final_sha=checkpoints[-1].sha if checkpoints else None,
            )
        )

    return sessions


def _extract_tool(ref: str) -> str:
    """Try to extract tool name from ref path like refs/agent/<tool>/..."""
    if ref.startswith("refs/agent/"):
        parts = ref[len("refs/agent/") :].split("/")
        if len(parts) >= 2:
            return parts[0]
    return "unknown"


def _compute_diffs(sessions: list[CheckpointSession], repo: GitRepo) -> list[CheckpointDiff]:
    """Diff consecutive checkpoints within each session."""
    diffs: list[CheckpointDiff] = []

    for session in sessions:
        cps = session.checkpoints
        for i in range(1, len(cps)):
            diff = _diff_commits(repo, cps[i - 1].sha, cps[i].sha)
            if diff:
                diffs.append(diff)

    return diffs


def _diff_commits(repo: GitRepo, from_sha: str, to_sha: str) -> CheckpointDiff | None:
    """Compute numstat diff between two commits."""
    try:
        output = repo.run("diff", "--numstat", from_sha, to_sha)
    except Exception:
        return None

    files = 0
    insertions = 0
    deletions = 0

    for line in output.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            files += 1
            try:
                insertions += int(parts[0])
                deletions += int(parts[1])
            except ValueError:
                pass

    return CheckpointDiff(
        from_sha=from_sha,
        to_sha=to_sha,
        files_changed=files,
        insertions=insertions,
        deletions=deletions,
    )
