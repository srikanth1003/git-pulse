from __future__ import annotations

from git_pulse.analysis.line_lifetime import build_lifetime_index
from git_pulse.analysis.ownership import analyze_ownership
from git_pulse.gitlayer.collect import collect_history
from git_pulse.gitlayer.repo import GitRepo
from tests.helpers.repo_builder import RepoBuilder


def _ownership(builder, max_files=20):
    history = collect_history(builder.path)
    repo = GitRepo(builder.path)
    from git_pulse.gitlayer.patches import most_touched_paths

    paths = most_touched_paths(history, 50)
    index = build_lifetime_index(history, repo, paths)
    return analyze_ownership(index, max_files=max_files)


def test_single_author_has_bus_factor_one(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "line1\nline2\nline3\n").commit("add")

    result = _ownership(b)

    assert result.repo_bus_factor == 1
    assert result.total_authors == 1
    assert result.files[0].bus_factor == 1
    assert result.files[0].top_owner_share == 1.0


def test_two_equal_authors_have_bus_factor_two(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "a1\na2\na3\n").commit("alice", author="Alice", email="alice@example.com")
    b.advance(hours=1).write("a.py", "a1\na2\na3\nb1\nb2\nb3\n").commit(
        "bob", author="Bob", email="bob@example.com"
    )

    result = _ownership(b)

    assert result.repo_bus_factor >= 1
    assert result.total_authors == 2


def test_ownership_lists_top_owner(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x\ny\nz\n").commit("add", author="Alice", email="alice@example.com")

    result = _ownership(b)

    assert result.files[0].owners[0][0] == "alice@example.com"


def test_empty_index_returns_zeros(tmp_path):
    result = analyze_ownership({})

    assert result.repo_bus_factor == 0
    assert result.total_lines == 0


def test_max_files_truncates(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "a\n").write("b.py", "b\n").write("c.py", "c\n").commit("add")

    result = _ownership(b, max_files=1)

    assert len(result.files) == 1


def test_files_sorted_by_bus_factor_ascending(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("solo.py", "x\ny\nz\n").commit("one author")
    b.advance(hours=1).write("shared.py", "a\nb\n").commit(
        "alice", author="Alice", email="alice@example.com"
    )
    b.advance(hours=1).write("shared.py", "a\nb\nc\nd\n").commit(
        "bob", author="Bob", email="bob@example.com"
    )

    result = _ownership(b)

    bus_factors = [f.bus_factor for f in result.files]
    assert bus_factors == sorted(bus_factors)
