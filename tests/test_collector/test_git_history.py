import os
import subprocess
from pathlib import Path

import pytest

from git_pulse.collector.git_history import GitHistoryCollector


@pytest.fixture
def sample_repo(tmp_path):
    """Create a small git repo with a few commits."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True)

    # Commit 1: create file
    (repo / "app.py").write_text("def hello():\n    return 'hello'\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo, capture_output=True)

    # Commit 2: modify file
    (repo / "app.py").write_text("def hello():\n    return 'world'\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "update hello"], cwd=repo, capture_output=True)

    # Commit 3: add file with agent attribution
    (repo / "utils.py").write_text("def add(a, b):\n    return a + b\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add utils\n\nCo-Authored-By: Claude <noreply@anthropic.com>"],
        cwd=repo,
        capture_output=True,
    )

    return repo


def test_collect_commits(sample_repo):
    collector = GitHistoryCollector(str(sample_repo))
    commits = collector.collect(commits=10)
    assert len(commits) == 3


def test_collect_by_days(sample_repo):
    collector = GitHistoryCollector(str(sample_repo))
    commits = collector.collect(days=1)
    assert len(commits) == 3  # all commits are from today


def test_commit_data_fields(sample_repo):
    collector = GitHistoryCollector(str(sample_repo))
    commits = collector.collect(commits=10)
    c = commits[0]  # most recent
    assert c["hash"] is not None
    assert c["author"] is not None
    assert c["timestamp"] is not None
    assert c["message"] is not None
    assert isinstance(c["files"], list)


def test_diff_stats(sample_repo):
    collector = GitHistoryCollector(str(sample_repo))
    commits = collector.collect(commits=10)
    # The second commit modifies app.py
    modify_commit = [c for c in commits if "update hello" in c["message"]][0]
    assert len(modify_commit["files"]) > 0
    f = modify_commit["files"][0]
    assert f["path"] == "app.py"
    assert "insertions" in f
    assert "deletions" in f
    assert "diff" in f


def test_attribution_detection(sample_repo):
    collector = GitHistoryCollector(str(sample_repo))
    commits = collector.collect(commits=10)
    agent_commit = [c for c in commits if "add utils" in c["message"]][0]
    assert agent_commit["is_agent_attributed"] is True
    assert "Claude" in agent_commit["attribution_source"]

    human_commit = [c for c in commits if "initial commit" in c["message"]][0]
    assert human_commit["is_agent_attributed"] is False
