from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime

import pytest

from git_pulse.config import GitPulseConfig
from git_pulse.gitlayer.collect import CollectOptions
from git_pulse.models.history import AuthorClass
from git_pulse.report.builder import build_report
from tests.helpers.repo_builder import RepoBuilder

# Inside the default 30-day window relative to RepoBuilder's 2025-01-01 epoch,
# so the default CollectOptions(days=30) actually sees the fixture's commits.
NOW = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def repo(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("app.py", "".join(f"line{i}\n" for i in range(20))).commit("initial")
    b.advance(hours=2).write("app.py", "x\n" * 20).agent_commit("agent rewrite")
    b.advance(hours=1).write("README.md", "# docs\n").commit("docs")
    return b


@pytest.fixture
def empty_repo(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=empty, check=True)
    return empty


def test_report_carries_repository_metadata(repo):
    report = build_report(repo.path, GitPulseConfig.defaults(), now=NOW)

    assert report.repo_path == str(repo.path)
    assert report.repo_name == repo.path.name
    assert report.branch == "main"
    assert report.head_sha == repo.head()
    assert report.generated_at == NOW
    assert report.git_pulse_version  # non-empty


def test_report_includes_every_analyzer_section(repo):
    report = build_report(repo.path, GitPulseConfig.defaults(), now=NOW)

    assert report.churn.files
    assert report.velocity.total_commits == 3
    assert report.sessions.total_sessions >= 1
    assert report.hotspots is not None
    assert report.rework is not None


def test_attribution_summary_counts_commit_classes(repo):
    summary = build_report(repo.path, GitPulseConfig.defaults(), now=NOW).attribution

    assert summary.total_commits == 3
    assert summary.agent_commits == 1
    assert summary.human_commits == 2
    assert summary.agent_commit_share == pytest.approx(1 / 3)
    assert summary.signals_seen["coauthor_trailer"] == 1


def test_attribution_summary_reports_agent_line_share(repo):
    summary = build_report(repo.path, GitPulseConfig.defaults(), now=NOW).attribution

    assert summary.agent_lines_added > 0
    assert 0.0 < summary.agent_line_share <= 1.0


def test_report_records_the_options_used(repo):
    options = CollectOptions(days=7, branch="main")
    report = build_report(repo.path, GitPulseConfig.defaults(), options=options, now=NOW)

    assert report.options["days"] == 7
    assert report.options["branch"] == "main"


def test_narrative_is_none_when_the_llm_is_disabled(repo):
    assert build_report(repo.path, GitPulseConfig.defaults(), now=NOW).narrative is None


def test_config_limits_reach_the_analyzers(repo):
    config = GitPulseConfig.defaults()
    config.analysis.max_hotspots = 1

    report = build_report(repo.path, config, now=NOW)

    assert len(report.hotspots.hotspots) <= 1


def test_empty_repository_produces_an_empty_report(empty_repo):
    report = build_report(empty_repo, GitPulseConfig.defaults(), now=NOW)

    assert report.is_empty
    assert report.velocity.total_commits == 0
    assert report.churn.files == ()
    assert report.hotspots.hotspots == ()
    assert report.head_sha == ""


def test_time_range_is_none_for_an_empty_report(empty_repo):
    assert build_report(empty_repo, GitPulseConfig.defaults(), now=NOW).time_range is None


def test_report_is_reusable_without_the_repository(repo):
    """A renderer must work from the report alone — no live git access."""
    report = build_report(repo.path, GitPulseConfig.defaults(), now=NOW)
    shutil.rmtree(repo.path)

    assert report.velocity.total_commits == 3
    assert report.churn.files[0].path
    assert report.attribution.agent_commits == 1


def test_top_agent_authors_are_ranked(repo):
    summary = build_report(repo.path, GitPulseConfig.defaults(), now=NOW).attribution

    assert summary.authors
    assert summary.authors == tuple(sorted(summary.authors, key=lambda a: (-a.commits, a.email)))
    assert any(a.author_class is AuthorClass.AGENT for a in summary.authors)
