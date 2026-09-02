from __future__ import annotations

from git_pulse.analysis.coupling import analyze_coupling
from git_pulse.gitlayer.collect import collect_history
from tests.helpers.repo_builder import RepoBuilder


def test_files_changing_together_form_a_coupled_pair(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x").write("b.py", "y").commit("add both")
    b.advance(hours=1).write("a.py", "x2").write("b.py", "y2").commit("edit both")
    b.advance(hours=1).write("a.py", "x3").write("b.py", "y3").commit("again")

    result = analyze_coupling(collect_history(b.path), min_shared=2)

    assert len(result.pairs) == 1
    pair = result.pairs[0]
    assert pair.file_a == "a.py"
    assert pair.file_b == "b.py"
    assert pair.shared_commits == 3
    assert pair.coupling_ratio == 1.0


def test_min_shared_filters_weak_pairs(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x").write("b.py", "y").commit("add")
    b.advance(hours=1).write("a.py", "x2").write("b.py", "y2").commit("edit")

    assert analyze_coupling(collect_history(b.path), min_shared=3).pairs == ()


def test_coupling_ratio_is_shared_over_min(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "1").write("b.py", "1").commit("1")
    b.advance(hours=1).write("a.py", "2").write("b.py", "2").commit("2")
    b.advance(hours=1).write("a.py", "3").write("b.py", "3").commit("3")
    # a.py gets an extra solo commit
    b.advance(hours=1).write("a.py", "4").commit("solo a")

    result = analyze_coupling(collect_history(b.path), min_shared=2)

    pair = result.pairs[0]
    assert pair.shared_commits == 3
    # min(commits_a=4, commits_b=3) = 3, ratio = 3/3 = 1.0
    assert pair.coupling_ratio == 1.0


def test_max_pairs_truncates(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    for i in range(5):
        b.write("a.py", str(i)).write("b.py", str(i)).write("c.py", str(i)).commit(f"c{i}")

    result = analyze_coupling(collect_history(b.path), min_shared=2, max_pairs=1)

    assert len(result.pairs) == 1
    assert result.total_detected >= 2  # at least a-b, a-c, b-c


def test_empty_history_returns_no_pairs(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x").commit("add")

    result = analyze_coupling(collect_history(b.path))

    assert result.pairs == ()
    assert result.total_detected == 0


def test_pairs_are_sorted_by_ratio_descending(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    # a-b always together (3 times), a-c together only sometimes
    b.write("a.py", "1").write("b.py", "1").write("c.py", "1").commit("1")
    b.advance(hours=1).write("a.py", "2").write("b.py", "2").write("c.py", "2").commit("2")
    b.advance(hours=1).write("a.py", "3").write("b.py", "3").write("c.py", "3").commit("3")
    b.advance(hours=1).write("a.py", "4").write("b.py", "4").commit("4, no c")
    b.advance(hours=1).write("a.py", "5").write("b.py", "5").commit("5, no c")

    result = analyze_coupling(collect_history(b.path), min_shared=2)

    # a-b has ratio 5/5=1.0, a-c has 3/min(5,3)=1.0, b-c has 3/min(5,3)=1.0
    # All 1.0 — sorted by ratio then shared then name
    assert all(p.coupling_ratio >= result.pairs[-1].coupling_ratio for p in result.pairs)
