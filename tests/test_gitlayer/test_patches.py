from __future__ import annotations

from git_pulse.gitlayer.collect import CollectOptions, collect_history
from git_pulse.gitlayer.patches import collect_patches, most_touched_paths
from git_pulse.gitlayer.repo import GitRepo
from tests.helpers.repo_builder import RepoBuilder

TEN_LINES = "".join(f"line{i}\n" for i in range(10))


def test_collect_patches_returns_one_line_range_per_hunk(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")
    b.advance(hours=1).write("a.py", TEN_LINES.replace("line1\n", "EDIT\n")).commit("edit")

    history = collect_history(b.path)
    repo = GitRepo(b.path)

    patches = collect_patches(history, repo, ["a.py"])

    assert list(patches) == ["a.py"]
    assert len(patches["a.py"]) == 2  # the add hunk, then the edit hunk


def test_collect_patches_reports_the_new_side_line_span(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")
    b.advance(hours=1).write("a.py", TEN_LINES.replace("line1\n", "EDIT\n")).commit("edit")

    history = collect_history(b.path)
    repo = GitRepo(b.path)

    patches = collect_patches(history, repo, ["a.py"])
    edit_hunk = patches["a.py"][-1]

    assert edit_hunk.line_start <= 2 <= edit_hunk.line_end
    assert edit_hunk.sha == history.commits[-1].sha


def test_collect_patches_skips_binary_files(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write_binary("img.png", b"\x89PNG\x00\x01\x02")
    b.commit("add binary")

    history = collect_history(b.path)
    repo = GitRepo(b.path)

    patches = collect_patches(history, repo, ["img.png"])

    assert patches == {}


def test_collect_patches_ignores_commits_outside_the_collected_history(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("old")
    b.advance(days=10).write("a.py", TEN_LINES.replace("line1\n", "NEW\n")).commit("new")

    history = collect_history(b.path, options=CollectOptions(commits=1))
    repo = GitRepo(b.path)

    patches = collect_patches(history, repo, ["a.py"])

    assert all(rng.sha == history.commits[0].sha for rng in patches["a.py"])


def test_collect_patches_returns_empty_dict_when_no_paths_requested(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")

    history = collect_history(b.path)
    repo = GitRepo(b.path)

    assert collect_patches(history, repo, []) == {}


def test_most_touched_paths_ranks_by_commit_count_then_name(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x").write("b.py", "y").commit("add both")
    b.advance(hours=1).write("a.py", "x2").commit("edit a")
    b.advance(hours=1).write("a.py", "x3").commit("edit a again")

    history = collect_history(b.path)

    assert most_touched_paths(history, max_files=2) == ["a.py", "b.py"]


def test_most_touched_paths_caps_at_max_files(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x").write("b.py", "y").write("c.py", "z").commit("add three")

    history = collect_history(b.path)

    assert len(most_touched_paths(history, max_files=1)) == 1
