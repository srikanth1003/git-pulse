from __future__ import annotations

from git_pulse.gitlayer.log import build_log_args, parse_log_output
from git_pulse.gitlayer.repo import GitRepo
from tests.helpers.repo_builder import RepoBuilder


def _records(builder: RepoBuilder, **kwargs):
    repo = GitRepo(builder.path)
    return parse_log_output(repo.run(*build_log_args(rev="main", **kwargs)))


def test_reads_real_history_newest_first(tmp_path):
    builder = RepoBuilder(tmp_path / "r")
    builder.write("a.py", "one\n").commit("first")
    builder.advance(hours=1).write("a.py", "one\ntwo\n").commit("second")

    records = _records(builder)

    assert [r.message.strip() for r in records] == ["second", "first"]


def test_reads_real_insertions_and_deletions(tmp_path):
    builder = RepoBuilder(tmp_path / "r")
    builder.write("a.py", "one\ntwo\nthree\n").commit("add three lines")
    builder.advance(hours=1).write("a.py", "one\nCHANGED\nthree\nfour\n").commit("edit")

    newest = _records(builder)[0]

    assert newest.files[0].path == "a.py"
    assert newest.files[0].insertions == 2
    assert newest.files[0].deletions == 1


def test_reads_a_real_rename(tmp_path):
    builder = RepoBuilder(tmp_path / "r")
    builder.write("old.py", "content\nmore\n").commit("add")
    builder.advance(hours=1).move("old.py", "new.py").commit("rename")

    newest = _records(builder)[0]

    assert newest.files[0].old_path == "old.py"
    assert newest.files[0].path == "new.py"


def test_reads_a_real_binary_file(tmp_path):
    builder = RepoBuilder(tmp_path / "r")
    builder.write_binary("logo.png", bytes(range(256))).commit("add binary")

    newest = _records(builder)[0]

    assert newest.files[0].path == "logo.png"
    assert newest.files[0].is_binary is True


def test_root_commit_has_no_parents(tmp_path):
    builder = RepoBuilder(tmp_path / "r")
    builder.write("a.py", "x\n").commit("root")

    assert _records(builder)[0].parents == ()


def test_multiline_body_with_trailer_survives_the_round_trip(tmp_path):
    builder = RepoBuilder(tmp_path / "r")
    builder.write("a.py", "x\n").agent_commit("feat: thing")

    newest = _records(builder)[0]

    assert "Co-Authored-By: Claude <noreply@anthropic.com>" in newest.message


def test_max_count_limits_results(tmp_path):
    builder = RepoBuilder(tmp_path / "r")
    for i in range(5):
        builder.advance(hours=1).write("a.py", f"{i}\n").commit(f"c{i}")

    assert len(_records(builder, max_count=2)) == 2


def test_multiple_files_in_one_commit(tmp_path):
    builder = RepoBuilder(tmp_path / "r")
    builder.write("a.py", "a\n").write("b/c.py", "c\n").commit("two files")

    paths = {f.path for f in _records(builder)[0].files}

    assert paths == {"a.py", "b/c.py"}
