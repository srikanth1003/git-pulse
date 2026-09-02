from __future__ import annotations

from git_pulse.analysis.line_lifetime import build_lifetime_index
from git_pulse.gitlayer.collect import CollectOptions, collect_history
from git_pulse.gitlayer.patches import collect_patches, most_touched_paths
from git_pulse.gitlayer.repo import GitRepo
from tests.helpers.repo_builder import RepoBuilder

TEN_LINES = "".join(f"line{i}\n" for i in range(10))


def _index(builder, paths=None, with_patches=True):
    history = collect_history(builder.path)
    repo = GitRepo(builder.path)
    paths = paths or most_touched_paths(history, 50)
    patches = collect_patches(history, repo, paths) if with_patches else None
    return build_lifetime_index(history, repo, paths, patches)


def test_every_line_has_a_birth_record(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")

    index = _index(b)

    assert "a.py" in index
    assert len(index["a.py"].births) == 10


def test_birth_sha_matches_introducing_commit(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    sha1 = b.write("a.py", "first\n").commit("first")
    b.advance(hours=1)
    sha2 = b.write("a.py", "first\nsecond\n").commit("second")

    index = _index(b)

    births = {birth.line_number: birth.sha for birth in index["a.py"].births}
    assert births[1] == sha1
    assert births[2] == sha2


def test_blame_records_author_metadata(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "line1\n").commit("add", author="Alice", email="alice@example.com")

    index = _index(b)

    birth = index["a.py"].births[0]
    assert birth.author_name == "Alice"
    assert birth.author_email == "alice@example.com"
    assert birth.authored_at is not None


def test_death_events_from_patches(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")
    b.advance(hours=1).write("a.py", TEN_LINES.replace("line5\n", "EDIT\n")).commit("edit")

    index = _index(b)

    assert len(index["a.py"].deaths) > 0


def test_index_without_patches_has_births_only(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")

    index = _index(b, with_patches=False)

    assert len(index["a.py"].births) == 10
    assert len(index["a.py"].deaths) == 0


def test_empty_history_returns_empty_index(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", TEN_LINES).commit("add")

    history = collect_history(b.path, options=CollectOptions(since="2099-01-01"))
    repo = GitRepo(b.path)

    assert build_lifetime_index(history, repo, ["a.py"]) == {}


def test_multiple_files_indexed(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "a\n").write("b.py", "b\n").commit("add")

    index = _index(b, paths=["a.py", "b.py"])

    assert "a.py" in index
    assert "b.py" in index


def test_nonexistent_file_is_silently_skipped(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x\n").commit("add")

    index = _index(b, paths=["no_such_file.py"])

    assert "no_such_file.py" not in index


def test_birth_lines_are_numbered_from_one(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "a\nb\nc\n").commit("add")

    index = _index(b)

    numbers = sorted(birth.line_number for birth in index["a.py"].births)
    assert numbers == [1, 2, 3]
