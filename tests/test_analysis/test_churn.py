from __future__ import annotations

import subprocess

from git_pulse.analysis.churn import analyze_churn
from git_pulse.gitlayer.collect import collect_history
from tests.helpers.repo_builder import RepoBuilder


def _churn(builder, **kwargs):
    return analyze_churn(collect_history(builder.path), **kwargs)


def test_counts_commits_insertions_and_deletions_per_file(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "one\ntwo\n").commit("add")
    b.advance(hours=1).write("a.py", "one\nTWO\nthree\n").commit("edit")

    result = _churn(b)
    entry = next(f for f in result.files if f.path == "a.py")

    assert entry.commits == 2
    assert entry.insertions == 4  # 2 on add, 2 on edit
    assert entry.deletions == 1  # 1 on edit
    assert entry.churn == 5


def test_sorted_by_churn_descending(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("small.py", "x\n").write("big.py", "\n".join(str(i) for i in range(20)) + "\n").commit(
        "add"
    )

    result = _churn(b)

    assert [f.path for f in result.files] == ["big.py", "small.py"]


def test_limit_truncates_but_totals_still_cover_everything(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    for name in ["a.py", "b.py", "c.py"]:
        b.write(name, "x\n")
    b.commit("add three")

    result = _churn(b, limit=2)

    assert len(result.files) == 2
    assert result.total_files == 3
    assert result.total_insertions == 3


def test_distinct_authors_are_counted_by_email(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("c1", author="Ada", email="ada@example.com")
    b.advance(hours=1).write("a.py", "2\n").commit("c2", author="Grace", email="grace@example.com")
    b.advance(hours=1).write("a.py", "3\n").commit(
        "c3", author="Ada Again", email="ada@example.com"
    )

    entry = _churn(b).files[0]

    assert entry.commits == 3
    assert entry.distinct_authors == 2


def test_agent_and_human_commits_are_split(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("human")
    b.advance(hours=1).write("a.py", "2\n").agent_commit("agent")
    b.advance(hours=1).write("a.py", "3\n").agent_commit("agent again")

    entry = _churn(b).files[0]

    assert entry.agent_commits == 2
    assert entry.human_commits == 1
    assert entry.agent_share == 2 / 3


def test_renames_are_followed_onto_the_current_path(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("old.py", "one\ntwo\n").commit("add as old")
    b.advance(hours=1).move("old.py", "new.py").commit("rename")
    b.advance(hours=1).write("new.py", "one\ntwo\nthree\n").commit("edit as new")

    result = _churn(b)
    paths = [f.path for f in result.files]

    assert "old.py" not in paths
    assert "new.py" in paths
    entry = next(f for f in result.files if f.path == "new.py")
    assert entry.commits == 3  # add + rename + edit all attributed to new.py


def test_empty_history_yields_empty_result(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=empty, check=True)

    result = analyze_churn(collect_history(empty))

    assert result.files == ()
    assert result.total_files == 0
    assert result.total_insertions == 0


def test_agent_share_is_zero_when_no_agent_commits(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("human only")

    assert _churn(b).files[0].agent_share == 0.0
