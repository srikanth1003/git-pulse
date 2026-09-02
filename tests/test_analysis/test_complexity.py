from __future__ import annotations

from git_pulse.analysis.complexity import analyze_complexity
from git_pulse.gitlayer.collect import collect_history
from git_pulse.gitlayer.repo import GitRepo
from tests.helpers.repo_builder import RepoBuilder


def test_flat_code_has_low_depth(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x = 1\ny = 2\nz = 3\n").commit("add")

    history = collect_history(b.path)
    repo = GitRepo(b.path)

    result = analyze_complexity(repo, history.head_sha, ["a.py"])

    assert result.files[0].avg_depth == 0.0
    assert result.files[0].max_depth == 0


def test_nested_code_has_higher_depth(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    code = "def f():\n    if True:\n        if True:\n            x = 1\n"
    b.write("a.py", code).commit("add")

    history = collect_history(b.path)
    repo = GitRepo(b.path)

    result = analyze_complexity(repo, history.head_sha, ["a.py"])

    assert result.files[0].max_depth >= 3
    assert result.files[0].avg_depth > 0


def test_deep_line_share_counts_deep_lines(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    code = "x\n" + "    " * 5 + "y\n"
    b.write("a.py", code).commit("add")

    history = collect_history(b.path)
    repo = GitRepo(b.path)

    result = analyze_complexity(repo, history.head_sha, ["a.py"])

    assert result.files[0].deep_line_share >= 0.0


def test_empty_paths_returns_empty(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x\n").commit("add")

    repo = GitRepo(b.path)

    result = analyze_complexity(repo, "HEAD", [])

    assert result.files == ()
    assert result.repo_avg_depth == 0.0


def test_nonexistent_file_is_skipped(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x\n").commit("add")

    repo = GitRepo(b.path)

    result = analyze_complexity(repo, "HEAD", ["no_such.py"])

    assert result.files == ()


def test_files_sorted_by_avg_depth_descending(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("flat.py", "x\ny\nz\n").commit("flat")
    b.advance(hours=1)
    b.write("deep.py", "def f():\n    if True:\n        x = 1\n").commit("deep")

    history = collect_history(b.path)
    repo = GitRepo(b.path)

    result = analyze_complexity(repo, history.head_sha, ["flat.py", "deep.py"])

    assert result.files[0].path == "deep.py"
