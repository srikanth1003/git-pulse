from __future__ import annotations

from git_pulse.analysis.commit_class import classify_commits
from git_pulse.gitlayer.collect import collect_history
from tests.helpers.repo_builder import RepoBuilder


def test_revert_detected_from_git_default_message(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x").commit("initial")
    b.advance(hours=1).write("a.py", "y").commit('Revert "initial"')

    result = classify_commits(collect_history(b.path))

    assert result.total_reverts == 1
    assert result.reverts[0].kind == "revert"


def test_revert_detected_from_conventional_commit(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x").commit("initial")
    b.advance(hours=1).write("a.py", "y").commit("revert: undo the thing")

    result = classify_commits(collect_history(b.path))

    assert result.total_reverts == 1


def test_fix_detected_from_subject_prefix(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x").commit("fix: null pointer in parser")

    result = classify_commits(collect_history(b.path))

    assert result.total_fixes == 1
    assert result.fixes[0].kind == "fix"


def test_fix_detected_from_body_closes_pattern(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x").commit("improve error handling\n\nFixes #42")

    result = classify_commits(collect_history(b.path))

    assert result.total_fixes == 1
    assert "#42" in result.fixes[0].evidence


def test_hotfix_and_bugfix_prefixes_detected(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x").commit("hotfix: critical path")
    b.advance(hours=1).write("a.py", "y").commit("bugfix: edge case")

    result = classify_commits(collect_history(b.path))

    assert result.total_fixes == 2


def test_normal_commits_are_not_classified(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x").commit("feat: add feature")
    b.advance(hours=1).write("a.py", "y").commit("refactor: clean up")

    result = classify_commits(collect_history(b.path))

    assert result.total_reverts == 0
    assert result.total_fixes == 0


def test_empty_history_returns_empty_result(tmp_path):
    from git_pulse.gitlayer.collect import CollectOptions

    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x").commit("add")

    result = classify_commits(collect_history(b.path, options=CollectOptions(since="2099-01-01")))

    assert result.total_reverts == 0
    assert result.total_fixes == 0
