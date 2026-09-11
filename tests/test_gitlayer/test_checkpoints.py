from __future__ import annotations

import subprocess

from git_pulse.gitlayer.checkpoints import discover_checkpoints
from git_pulse.gitlayer.repo import GitRepo
from tests.helpers.repo_builder import RepoBuilder


def _create_checkpoint_refs(repo_path, session="session-1", count=3):
    """Create fake checkpoint refs in the repo."""
    for i in range(count):
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", f"checkpoint {i}"],
            cwd=repo_path,
            capture_output=True,
            check=True,
            env={
                "GIT_AUTHOR_NAME": "Agent",
                "GIT_AUTHOR_EMAIL": "agent@example.com",
                "GIT_COMMITTER_NAME": "Agent",
                "GIT_COMMITTER_EMAIL": "agent@example.com",
                "PATH": "/usr/bin:/bin:/usr/local/bin",
            },
        )
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "update-ref", f"refs/agent-checkpoints/{session}/{i}", sha],
            cwd=repo_path,
            check=True,
        )
    subprocess.run(
        ["git", "reset", "--hard", "HEAD~" + str(count)],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )


def test_discovers_checkpoint_refs(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x\n").commit("initial")
    _create_checkpoint_refs(b.path)

    stats = discover_checkpoints(GitRepo(b.path))

    assert stats.total_sessions == 1
    assert stats.total_checkpoints == 3


def test_no_checkpoints_returns_empty(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x\n").commit("initial")

    stats = discover_checkpoints(GitRepo(b.path))

    assert stats.total_sessions == 0
    assert stats.total_checkpoints == 0


def test_multiple_sessions_discovered(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x\n").commit("initial")
    _create_checkpoint_refs(b.path, session="session-1", count=2)
    _create_checkpoint_refs(b.path, session="session-2", count=2)

    stats = discover_checkpoints(GitRepo(b.path))

    assert stats.total_sessions == 2


def test_diffs_computed_between_checkpoints(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "line1\n").commit("initial")

    # Create checkpoints with actual file changes
    subprocess.run(["git", "checkout", "-b", "tmp-cp"], cwd=b.path, capture_output=True, check=True)
    for i in range(3):
        (b.path / "a.py").write_text(f"version {i}\n")
        subprocess.run(["git", "add", "-A"], cwd=b.path, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"cp {i}"],
            cwd=b.path,
            capture_output=True,
            check=True,
            env={
                "GIT_AUTHOR_NAME": "Agent",
                "GIT_AUTHOR_EMAIL": "agent@example.com",
                "GIT_COMMITTER_NAME": "Agent",
                "GIT_COMMITTER_EMAIL": "agent@example.com",
                "PATH": "/usr/bin:/bin:/usr/local/bin",
            },
        )
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=b.path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "update-ref", f"refs/agent-checkpoints/s1/{i}", sha],
            cwd=b.path,
            check=True,
        )
    subprocess.run(["git", "checkout", "main"], cwd=b.path, capture_output=True, check=True)

    stats = discover_checkpoints(GitRepo(b.path))

    assert stats.total_checkpoints == 3
    assert len(stats.diffs) == 2  # between 3 checkpoints = 2 diffs


def test_checkpoint_session_has_tool_from_agent_ref(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x\n").commit("initial")

    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=b.path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "update-ref", "refs/agent/cursor/mysession/0", sha],
        cwd=b.path,
        check=True,
    )

    stats = discover_checkpoints(GitRepo(b.path))

    assert stats.total_sessions == 1
    assert stats.sessions[0].tool == "cursor"
