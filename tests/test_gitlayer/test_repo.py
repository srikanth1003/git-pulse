from __future__ import annotations

import subprocess

import pytest

from git_pulse.gitlayer.repo import GitRepo, NotARepositoryError
from tests.helpers.repo_builder import RepoBuilder


def test_opens_a_valid_repo_and_reports_branch_and_head(tmp_path):
    builder = RepoBuilder(tmp_path / "r")
    sha = builder.write("a.txt", "x\n").commit("first")

    repo = GitRepo(builder.path)

    assert repo.current_branch() == "main"
    assert repo.head_sha() == sha


def test_rejects_a_non_repository(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()

    with pytest.raises(NotARepositoryError):
        GitRepo(plain)


def test_rejects_a_missing_path(tmp_path):
    with pytest.raises(NotARepositoryError):
        GitRepo(tmp_path / "does-not-exist")


def test_finds_the_repo_from_a_subdirectory(tmp_path):
    builder = RepoBuilder(tmp_path / "r")
    builder.write("pkg/mod.py", "x\n").commit("first")

    repo = GitRepo(builder.path / "pkg")

    assert repo.root == builder.path.resolve()


def test_detects_a_non_shallow_repo(tmp_path):
    builder = RepoBuilder(tmp_path / "r")
    builder.write("a.txt", "x\n").commit("first")

    assert GitRepo(builder.path).is_shallow() is False


def test_detects_a_shallow_clone(tmp_path):
    builder = RepoBuilder(tmp_path / "src")
    builder.write("a.txt", "1\n").commit("c1")
    builder.advance(hours=1).write("a.txt", "2\n").commit("c2")
    builder.advance(hours=1).write("a.txt", "3\n").commit("c3")

    clone = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "--depth", "1", f"file://{builder.path}", str(clone)],
        capture_output=True,
        check=True,
    )

    assert GitRepo(clone).is_shallow() is True


def test_reports_empty_repo_as_having_no_head(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=empty, check=True)

    repo = GitRepo(empty)

    assert repo.has_commits() is False


def test_resolves_an_explicit_branch(tmp_path):
    builder = RepoBuilder(tmp_path / "r")
    builder.write("a.txt", "x\n").commit("first")
    subprocess.run(["git", "branch", "feature"], cwd=builder.path, check=True)

    assert GitRepo(builder.path).resolve_rev("feature") == builder.head()


def test_unknown_rev_raises(tmp_path):
    builder = RepoBuilder(tmp_path / "r")
    builder.write("a.txt", "x\n").commit("first")

    with pytest.raises(ValueError, match="unknown revision"):
        GitRepo(builder.path).resolve_rev("no-such-branch")
