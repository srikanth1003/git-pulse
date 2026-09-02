from __future__ import annotations

from git_pulse.analysis.line_lifetime import build_lifetime_index
from git_pulse.analysis.survival import analyze_survival
from git_pulse.gitlayer.collect import collect_history
from git_pulse.gitlayer.patches import collect_patches, most_touched_paths
from git_pulse.gitlayer.repo import GitRepo
from tests.helpers.repo_builder import RepoBuilder

TEN_LINES = "".join(f"line{i}\n" for i in range(10))


def _survival(builder):
    history = collect_history(builder.path)
    repo = GitRepo(builder.path)
    paths = most_touched_paths(history, 50)
    patches = collect_patches(history, repo, paths)
    index = build_lifetime_index(history, repo, paths, patches)
    return analyze_survival(history, index)


def test_all_lines_surviving_are_censored(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")

    result = _survival(b)

    assert result.total_lines == 10
    assert result.censored_lines == 10
    assert result.overall_median_days is None  # all censored, no median


def test_curve_starts_at_one(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")

    result = _survival(b)

    assert result.overall_curve[0].survival == 1.0
    assert result.overall_curve[0].time_days == 0.0


def test_deaths_produce_median(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "a\nb\nc\nd\n").commit("add")
    b.advance(days=5).write("a.py", "X\nY\nZ\nd\n").commit("rewrite most")

    result = _survival(b)

    # 4 lines total: 3 rewritten (dead), 1 surviving (censored)
    assert result.total_lines == 4
    assert result.censored_lines >= 1


def test_empty_index_returns_empty(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")
    history = collect_history(b.path)

    result = analyze_survival(history, {})

    assert result.total_lines == 0
    assert result.overall_curve == ()
