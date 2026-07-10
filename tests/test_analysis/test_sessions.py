from __future__ import annotations

import subprocess

from git_pulse.analysis.sessions import analyze_sessions
from git_pulse.gitlayer.collect import collect_history
from tests.helpers.repo_builder import RepoBuilder


def _sessions(builder, **kwargs):
    return analyze_sessions(collect_history(builder.path), **kwargs)


def test_commits_within_the_gap_form_one_session(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("c1")
    b.advance(minutes=30).write("a.py", "2\n").commit("c2")
    b.advance(minutes=30).write("a.py", "3\n").commit("c3")

    result = _sessions(b)

    assert result.total_sessions == 1
    assert result.sessions[0].commit_count == 3
    assert result.sessions[0].duration_minutes == 60.0


def test_a_gap_larger_than_the_threshold_splits_sessions(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("morning")
    b.advance(hours=5).write("a.py", "2\n").commit("afternoon")

    result = _sessions(b)

    assert result.total_sessions == 2
    assert [s.commit_count for s in result.sessions] == [1, 1]


def test_a_gap_exactly_at_the_threshold_stays_in_one_session(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("c1")
    b.advance(minutes=90).write("a.py", "2\n").commit("c2")

    assert _sessions(b, gap_minutes=90).total_sessions == 1


def test_gap_threshold_is_configurable(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("c1")
    b.advance(minutes=45).write("a.py", "2\n").commit("c2")

    assert _sessions(b, gap_minutes=90).total_sessions == 1
    assert _sessions(b, gap_minutes=30).total_sessions == 2


def test_different_authors_get_separate_sessions(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("ada", author="Ada", email="ada@example.com")
    b.advance(minutes=10).write("b.py", "1\n").commit(
        "grace", author="Grace", email="grace@example.com"
    )

    result = _sessions(b)

    assert result.total_sessions == 2
    assert {s.author for s in result.sessions} == {"ada@example.com", "grace@example.com"}


def test_sessions_are_ordered_by_start_time(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("first", author="Ada", email="ada@example.com")
    b.advance(hours=5).write("b.py", "1\n").commit(
        "second", author="Grace", email="grace@example.com"
    )

    starts = [s.start for s in _sessions(b).sessions]

    assert starts == sorted(starts)


def test_distinct_files_touched_are_counted_once(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").write("b.py", "1\n").commit("c1")
    b.advance(minutes=10).write("a.py", "2\n").commit("c2")  # a.py again

    assert _sessions(b).sessions[0].files_touched == 2


def test_agent_and_human_commits_are_split_per_session(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("human")
    b.advance(minutes=10).write("a.py", "2\n").agent_commit("agent")

    session = _sessions(b).sessions[0]

    assert session.agent_commits == 1
    assert session.human_commits == 1
    assert session.agent_share == 0.5


def test_aggregates_across_sessions(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("c1")
    b.advance(minutes=60).write("a.py", "2\n").commit("c2")  # session 1, 60 min, 2 commits
    b.advance(hours=6).write("a.py", "3\n").commit("c3")  # session 2, 0 min, 1 commit

    result = _sessions(b)

    assert result.total_sessions == 2
    assert result.avg_commits_per_session == 1.5
    assert result.avg_duration_minutes == 30.0
    assert result.longest is not None
    assert result.longest.commit_count == 2


def test_empty_history_yields_no_sessions(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=empty, check=True)

    result = analyze_sessions(collect_history(empty))

    assert result.sessions == ()
    assert result.total_sessions == 0
    assert result.avg_commits_per_session == 0.0
    assert result.avg_duration_minutes == 0.0
    assert result.longest is None
