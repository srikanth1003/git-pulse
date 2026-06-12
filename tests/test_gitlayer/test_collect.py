from __future__ import annotations

import subprocess
from datetime import UTC, datetime

import pytest

from git_pulse.gitlayer.cache import HistoryCache
from git_pulse.gitlayer.collect import CollectOptions, collect_history
from git_pulse.gitlayer.repo import NotARepositoryError
from git_pulse.models.history import AuthorClass
from tests.helpers.repo_builder import RepoBuilder

NOW = datetime(2025, 1, 10, 9, tzinfo=UTC)


def _collect(path, options=None, **kwargs):
    return collect_history(path, options or CollectOptions(), now=NOW, **kwargs)


def test_collects_commits_newest_first(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("first")
    b.advance(hours=1).write("a.py", "2\n").commit("second")

    history = _collect(b.path)

    assert [c.subject for c in history.commits] == ["second", "first"]
    assert history.branch == "main"
    assert history.head_sha == b.head()


def test_attribution_is_applied_per_commit(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("human work")
    b.advance(hours=1).write("a.py", "2\n").agent_commit("agent work")

    history = _collect(b.path)
    by_subject = {c.subject: c for c in history.commits}

    assert by_subject["agent work"].author_class is AuthorClass.AGENT
    assert by_subject["agent work"].attribution.provider == "Claude Code"
    assert by_subject["human work"].author_class is AuthorClass.HUMAN
    assert history.has_attribution_data is True


def test_commits_limit_is_honoured(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    for i in range(5):
        b.advance(hours=1).write("a.py", f"{i}\n").commit(f"c{i}")

    assert len(_collect(b.path, CollectOptions(commits=2))) == 2


def test_days_is_converted_to_a_since_bound(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "old\n").commit("ancient")  # 2025-01-01
    b.advance(days=8).write("a.py", "new\n").commit("recent")  # 2025-01-09

    history = _collect(b.path, CollectOptions(days=3))  # NOW is 2025-01-10

    assert [c.subject for c in history.commits] == ["recent"]


def test_exclude_filters_files(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").write("out.lock", "x\n").commit("both")

    history = _collect(b.path, CollectOptions(exclude=("*.lock",)))

    assert [f.path for f in history.commits[0].files] == ["a.py"]


def test_include_keeps_only_matching_files(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").write("b.md", "x\n").commit("both")

    history = _collect(b.path, CollectOptions(include=("*.py",)))

    assert [f.path for f in history.commits[0].files] == ["a.py"]


def test_commits_emptied_by_filters_are_dropped(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("code")
    b.advance(hours=1).write("notes.md", "x\n").commit("docs only")

    history = _collect(b.path, CollectOptions(include=("*.py",)))

    assert [c.subject for c in history.commits] == ["code"]


def test_commits_are_kept_when_no_filters_are_active(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("real")
    b.advance(hours=1).commit("empty commit")  # --allow-empty, no files

    history = _collect(b.path)

    assert [c.subject for c in history.commits] == ["empty commit", "real"]


def test_binary_files_are_recorded_as_skipped(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").write_binary("logo.png", bytes(range(256))).commit("mixed")

    history = _collect(b.path)

    assert "logo.png" in history.skipped_files
    assert [f.path for f in history.commits[0].files] == ["a.py"]


def test_empty_repo_yields_empty_history(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=empty, check=True)

    history = _collect(empty)

    assert len(history) == 0
    assert history.commits == ()


def test_non_repository_raises(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()

    with pytest.raises(NotARepositoryError):
        _collect(plain)


def test_explicit_branch_is_used(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("on main")
    subprocess.run(["git", "checkout", "-q", "-b", "feature"], cwd=b.path, check=True)
    b.advance(hours=1).write("a.py", "2\n").commit("on feature")
    subprocess.run(["git", "checkout", "-q", "main"], cwd=b.path, check=True)

    history = _collect(b.path, CollectOptions(branch="feature"))

    assert [c.subject for c in history.commits] == ["on feature", "on main"]
    assert history.branch == "feature"


def test_second_call_is_served_from_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("first")

    cache = HistoryCache(b.path)
    first = _collect(b.path, cache=cache)

    # Break the git binary lookup; a cache hit must not need it.
    monkeypatch.setattr(
        "git_pulse.gitlayer.collect._run_log",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("git log should not run")),
    )
    second = _collect(b.path, cache=cache)

    assert second == first


def test_a_new_commit_invalidates_the_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("first")
    cache = HistoryCache(b.path)

    assert len(_collect(b.path, cache=cache)) == 1

    b.advance(hours=1).write("a.py", "2\n").commit("second")

    assert len(_collect(b.path, cache=cache)) == 2


def test_shallow_flag_is_propagated(tmp_path):
    b = RepoBuilder(tmp_path / "src")
    b.write("a.py", "1\n").commit("c1")
    b.advance(hours=1).write("a.py", "2\n").commit("c2")
    clone = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "--depth", "1", f"file://{b.path}", str(clone)],
        capture_output=True,
        check=True,
    )

    assert _collect(clone).is_shallow is True
