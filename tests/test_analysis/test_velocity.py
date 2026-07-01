from __future__ import annotations

import subprocess

from git_pulse.analysis.velocity import analyze_velocity
from git_pulse.gitlayer.collect import collect_history
from tests.helpers.repo_builder import RepoBuilder


def _velocity(builder):
    return analyze_velocity(collect_history(builder.path))


def test_single_day_of_commits(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("c1")
    b.advance(hours=2).write("a.py", "2\n").commit("c2")

    result = _velocity(b)

    assert result.span_days == 1
    assert result.active_days == 1
    assert result.commits_per_day == 2.0
    assert result.peak_day == "2025-01-01"
    assert result.peak_commits == 2


def test_span_counts_calendar_days_inclusive_including_gaps(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("c1")  # 2025-01-01
    b.advance(days=4).write("a.py", "2\n").commit("c2")  # 2025-01-05

    result = _velocity(b)

    assert result.span_days == 5  # Jan 1 through Jan 5
    assert result.active_days == 2  # only two days had commits
    assert result.commits_per_day == 2 / 5


def test_peak_day_is_the_busiest_and_ties_go_to_the_earliest(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("c1")
    b.advance(days=1).write("a.py", "2\n").commit("c2")

    result = _velocity(b)

    assert result.peak_commits == 1
    assert result.peak_day == "2025-01-01"


def test_average_files_per_commit(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").write("b.py", "1\n").commit("two files")
    b.advance(hours=1).write("a.py", "2\n").commit("one file")

    assert _velocity(b).avg_files_per_commit == 1.5


def test_agent_and_human_commits_are_split(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("human")
    b.advance(hours=1).write("a.py", "2\n").agent_commit("agent")
    b.advance(hours=1).write("a.py", "3\n").agent_commit("agent 2")

    result = _velocity(b)

    assert result.agent_commits == 2
    assert result.human_commits == 1
    assert result.agent_ratio == 2 / 3


def test_per_day_series_is_ascending_and_only_lists_active_days(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n").commit("c1")
    b.advance(days=2).write("a.py", "2\n").commit("c2")
    b.advance(hours=1).write("a.py", "3\n").commit("c3")

    assert _velocity(b).per_day == (("2025-01-01", 1), ("2025-01-03", 2))


def test_empty_history_is_all_zeros(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=empty, check=True)

    result = analyze_velocity(collect_history(empty))

    assert result.total_commits == 0
    assert result.commits_per_day == 0.0
    assert result.avg_files_per_commit == 0.0
    assert result.peak_day is None
    assert result.peak_commits == 0
    assert result.agent_ratio == 0.0
    assert result.per_day == ()
