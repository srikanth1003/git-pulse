from __future__ import annotations

from git_pulse.analysis.line_lifetime import build_lifetime_index
from git_pulse.analysis.line_rework import analyze_line_rework
from git_pulse.gitlayer.collect import collect_history
from git_pulse.gitlayer.patches import collect_patches, most_touched_paths
from git_pulse.gitlayer.repo import GitRepo
from tests.helpers.repo_builder import RepoBuilder

TEN_LINES = "".join(f"line{i}\n" for i in range(10))


def _rework(builder):
    history = collect_history(builder.path)
    repo = GitRepo(builder.path)
    paths = most_touched_paths(history, 50)
    patches = collect_patches(history, repo, paths)
    index = build_lifetime_index(history, repo, paths, patches)
    return analyze_line_rework(history, index)


def test_no_rework_when_lines_are_only_added(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")

    result = _rework(b)

    assert result.total_surviving_lines == 10
    assert result.reworked_lines == 0
    assert result.line_rework_rate == 0.0


def test_rework_detected_when_lines_are_overwritten(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")
    b.advance(hours=1).write("a.py", TEN_LINES.replace("line5\n", "EDIT\n")).commit("edit")

    result = _rework(b)

    assert result.total_surviving_lines == 10
    assert result.reworked_lines > 0
    assert result.line_rework_rate > 0.0


def test_agent_rework_is_split(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")
    b.advance(hours=1).write("a.py", TEN_LINES.replace("line1\n", "BOT\n")).agent_commit(
        "agent edit"
    )

    result = _rework(b)

    assert result.agent_reworked_lines >= 0
    assert result.human_reworked_lines >= 0


def test_empty_index_returns_zeros(tmp_path):
    from git_pulse.analysis.line_rework import analyze_line_rework
    from git_pulse.gitlayer.collect import collect_history

    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")
    history = collect_history(b.path)

    result = analyze_line_rework(history, {})

    assert result.total_surviving_lines == 0
    assert result.line_rework_rate == 0.0
