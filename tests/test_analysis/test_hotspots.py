from __future__ import annotations

import subprocess

from git_pulse.analysis.hotspots import HotspotParams, analyze_hotspots
from git_pulse.gitlayer.collect import collect_history
from git_pulse.gitlayer.repo import GitRepo
from tests.helpers.repo_builder import RepoBuilder

TEN_LINES = "".join(f"line{i}\n" for i in range(10))


def _hotspots(builder, params=None):
    repo = GitRepo(builder.path)
    return analyze_hotspots(collect_history(builder.path), repo, params or HotspotParams())


def test_repeated_edits_to_the_same_region_form_one_hotspot(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")
    b.advance(hours=1).write("a.py", TEN_LINES.replace("line1\n", "EDIT1\n")).commit("edit 1")
    b.advance(hours=1).write("a.py", TEN_LINES.replace("line1\n", "EDIT2\n")).commit("edit 2")

    result = _hotspots(b)

    assert len(result.hotspots) >= 1
    top = result.hotspots[0]
    assert top.file_path == "a.py"
    assert top.modification_count >= 3
    assert top.time_span_hours == 2.0
    assert len(top.commit_shas) == top.modification_count


def test_edits_far_apart_in_the_file_are_separate_hotspots(tmp_path):
    wide = "".join(f"line{i}\n" for i in range(200))
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", wide).commit("add")
    b.advance(hours=1).write("a.py", wide.replace("line5\n", "TOP\n")).commit("edit top")
    b.advance(hours=1).write("a.py", wide.replace("line150\n", "BOTTOM\n")).commit("edit bottom")

    result = _hotspots(b)
    starts = sorted(h.line_start for h in result.hotspots if h.file_path == "a.py")

    assert len(starts) >= 2
    assert starts[-1] - starts[0] > 50


def test_edits_outside_the_time_window_are_separate(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")
    b.advance(hours=1).write("a.py", TEN_LINES.replace("line1\n", "SOON\n")).commit("soon")
    b.advance(days=30).write("a.py", TEN_LINES.replace("line1\n", "LATER\n")).commit("later")

    result = _hotspots(b, HotspotParams(window_hours=24))

    # The two same-day edits cluster; the one 30 days later does not join them,
    # and on its own it is a single modification, so it is not a hotspot.
    assert len(result.hotspots) == 1
    assert result.hotspots[0].modification_count == 2
    assert result.hotspots[0].time_span_hours <= 24


def test_repeated_agent_edits_are_classified(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).agent_commit("agent add")
    b.advance(hours=1).write("a.py", TEN_LINES.replace("line1\n", "A1\n")).agent_commit(
        "agent edit"
    )
    b.advance(hours=1).write("a.py", TEN_LINES.replace("line1\n", "A2\n")).agent_commit(
        "agent edit 2"
    )

    assert _hotspots(b).hotspots[0].classification == "repeated-agent"


def test_human_following_an_agent_is_classified(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).agent_commit("agent add")
    b.advance(hours=1).write("a.py", TEN_LINES.replace("line1\n", "FIXED\n")).commit("human fix")

    assert _hotspots(b).hotspots[0].classification == "human-fixing-agent"


def test_human_only_iteration_is_classified(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")
    b.advance(hours=1).write("a.py", TEN_LINES.replace("line1\n", "H1\n")).commit("edit")

    assert _hotspots(b).hotspots[0].classification == "human-iteration"


def test_score_rewards_many_edits_in_a_short_span(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")
    b.advance(hours=1).write("a.py", TEN_LINES.replace("line1\n", "X\n")).commit("e1")

    top = _hotspots(b).hotspots[0]

    # score = modification_count^2 / (1 + time_span_hours) = 4 / 2 = 2.0
    assert top.modification_count == 2
    assert top.time_span_hours == 1.0
    assert top.score == 2.0


def test_hotspots_are_sorted_by_score_descending(tmp_path):
    wide = "".join(f"line{i}\n" for i in range(200))
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", wide).commit("add")
    for i in range(3):
        b.advance(hours=1).write("a.py", wide.replace("line5\n", f"HOT{i}\n")).commit(f"hot {i}")
    b.advance(hours=1).write("a.py", wide.replace("line150\n", "COLD\n")).commit("cold")

    scores = [h.score for h in _hotspots(b).hotspots]

    assert scores == sorted(scores, reverse=True)


def test_max_hotspots_truncates_but_total_is_preserved(tmp_path):
    wide = "".join(f"line{i}\n" for i in range(500))
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", wide).commit("add")
    for i, line in enumerate([10, 100, 200, 300, 400]):
        b.advance(hours=1).write("a.py", wide.replace(f"line{line}\n", f"E{i}\n")).commit(f"e{i}")

    result = _hotspots(b, HotspotParams(max_hotspots=2))

    assert len(result.hotspots) == 2
    assert result.total_detected >= 5


def test_single_modification_regions_are_not_hotspots(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add once")

    assert _hotspots(b, HotspotParams(min_modifications=2)).hotspots == ()


def test_empty_history_yields_no_hotspots(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=empty, check=True)

    result = analyze_hotspots(collect_history(empty), GitRepo(empty), HotspotParams())

    assert result.hotspots == ()
    assert result.total_detected == 0
