from __future__ import annotations

import subprocess

from git_pulse.analysis.churn import analyze_rework
from git_pulse.gitlayer.collect import collect_history
from tests.helpers.repo_builder import RepoBuilder


def _rework(builder):
    return analyze_rework(collect_history(builder.path))


def test_a_file_touched_once_has_no_rework(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x\n" * 10).commit("once")

    result = _rework(b)

    assert result.file_rework_rate == 0.0
    assert result.reworked_files == 0
    assert result.total_files == 1


def test_a_file_touched_twice_is_entirely_counted_as_reworked(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x\n" * 10).commit("first")
    b.advance(hours=1).write("a.py", "y\n" * 10).commit("second")

    result = _rework(b)

    assert result.file_rework_rate == 1.0
    assert result.reworked_files == 1


def test_rate_is_the_line_weighted_share_not_the_file_count_share(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    # touched twice: 2 lines added, then 2 changed -> 6 churn
    b.write("hot.py", "a\nb\n").commit("hot 1")
    b.advance(hours=1).write("hot.py", "c\nd\n").commit("hot 2")
    # touched once: 96 lines -> 96 churn
    b.advance(hours=1).write("cold.py", "z\n" * 96).commit("cold")

    result = _rework(b)

    # Half the files were touched twice, but churn weighting dominates the rate.
    assert result.file_rework_rate < 0.10
    assert result.reworked_files == 1
    assert result.total_files == 2


def test_agent_reworked_share_is_reported_separately(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x\n" * 10).agent_commit("agent writes")
    b.advance(hours=1).write("a.py", "y\n" * 10).agent_commit("agent rewrites")

    result = _rework(b)

    assert result.agent_rework_rate == 1.0
    assert result.human_rework_rate == 0.0


def test_human_rework_of_agent_code_counts_against_humans(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x\n" * 10).agent_commit("agent writes")
    b.advance(hours=1).write("a.py", "y\n" * 10).commit("human rewrites")

    result = _rework(b)

    assert 0.0 < result.human_rework_rate <= 1.0
    assert result.agent_rework_rate > 0.0


def test_binary_files_are_excluded(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write_binary("logo.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).commit("add binary")
    b.advance(hours=1).write_binary("logo.png", b"\x89PNG\r\n\x1a\n" + b"\xff" * 64).commit("swap")

    result = _rework(b)

    assert result.total_files == 0
    assert result.file_rework_rate == 0.0


def test_empty_history_is_zero_not_a_division_error(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=empty, check=True)

    result = analyze_rework(collect_history(empty))

    assert result.file_rework_rate == 0.0
    assert result.total_files == 0


def test_matches_the_0_1_0_definition(tmp_path):
    """Pins the ported formula: churn of multi-touch files / total churn."""
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1\n2\n3\n4\n").commit("a")  # +4
    b.advance(hours=1).write("a.py", "1\n2\n3\n9\n").commit("a again")  # +1/-1 = 2
    b.advance(hours=1).write("b.py", "1\n2\n").commit("b")  # +2

    result = _rework(b)

    # a.py churn = 6 (multi-touch), b.py churn = 2 -> 6/8
    assert result.file_rework_rate == 0.75
