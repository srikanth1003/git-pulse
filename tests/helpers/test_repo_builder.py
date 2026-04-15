from __future__ import annotations

import subprocess

from tests.helpers.repo_builder import RepoBuilder


def _git(path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=path, capture_output=True, text=True, check=True
    ).stdout


def test_builds_repo_with_deterministic_timestamps(tmp_path):
    repo = RepoBuilder(tmp_path / "r")
    repo.write("a.txt", "one\n").commit("first")
    repo.advance(hours=2).write("a.txt", "one\ntwo\n").commit("second")

    log = _git(repo.path, "log", "--format=%s|%aI", "--reverse").strip().splitlines()

    assert log[0] == "first|2025-01-01T09:00:00Z"
    assert log[1] == "second|2025-01-01T11:00:00Z"


def test_agent_commit_adds_coauthor_trailer(tmp_path):
    repo = RepoBuilder(tmp_path / "r")
    repo.write("a.txt", "x\n").agent_commit("agent change")

    body = _git(repo.path, "log", "-1", "--format=%B")

    assert "Co-Authored-By: Claude <noreply@anthropic.com>" in body


def test_custom_author_is_recorded(tmp_path):
    repo = RepoBuilder(tmp_path / "r")
    repo.write("a.txt", "x\n").commit("c", author="Ada", email="ada@example.com")

    assert _git(repo.path, "log", "-1", "--format=%an|%ae").strip() == "Ada|ada@example.com"


def test_rename_is_detectable(tmp_path):
    repo = RepoBuilder(tmp_path / "r")
    repo.write("old.txt", "content\n").commit("add")
    repo.move("old.txt", "new.txt").commit("rename")

    out = _git(repo.path, "log", "-1", "--name-status", "-M", "--format=")

    assert "R100" in out
    assert "new.txt" in out


def test_head_returns_current_sha(tmp_path):
    repo = RepoBuilder(tmp_path / "r")
    sha = repo.write("a.txt", "x\n").commit("only")

    assert repo.head() == sha
    assert len(sha) == 40
