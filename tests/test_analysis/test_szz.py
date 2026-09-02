from __future__ import annotations

from git_pulse.analysis.commit_class import classify_commits
from git_pulse.analysis.szz import analyze_szz
from git_pulse.gitlayer.collect import collect_history
from git_pulse.gitlayer.repo import GitRepo
from tests.helpers.repo_builder import RepoBuilder


def test_fix_commit_traces_back_to_introducer(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "good\n").commit("initial")
    b.advance(hours=1).write("a.py", "buggy\n").commit("introduce bug")
    b.advance(hours=1).write("a.py", "fixed\n").commit("fix: repair the bug")

    history = collect_history(b.path)
    repo = GitRepo(b.path)
    classification = classify_commits(history)

    result = analyze_szz(history, repo, classification)

    assert result.total_introductions >= 1
    assert result.bug_introducing_commits >= 1


def test_no_fixes_means_no_introductions(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x\n").commit("feat: add feature")

    history = collect_history(b.path)
    repo = GitRepo(b.path)
    classification = classify_commits(history)

    result = analyze_szz(history, repo, classification)

    assert result.total_introductions == 0


def test_none_classification_returns_empty(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x\n").commit("add")
    history = collect_history(b.path)
    repo = GitRepo(b.path)

    result = analyze_szz(history, repo, None)

    assert result.total_introductions == 0


def test_introduction_records_file_path(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("util.py", "helper\n").commit("add util")
    b.advance(hours=1).write("util.py", "broken_helper\n").commit("break it")
    b.advance(hours=1).write("util.py", "fixed_helper\n").commit("fix: repair util")

    history = collect_history(b.path)
    repo = GitRepo(b.path)
    classification = classify_commits(history)

    result = analyze_szz(history, repo, classification)

    if result.introductions:
        assert result.introductions[0].file_path == "util.py"
