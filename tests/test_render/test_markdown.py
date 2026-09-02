from __future__ import annotations

from datetime import UTC, datetime

from git_pulse.config import GitPulseConfig
from git_pulse.gitlayer.collect import CollectOptions
from git_pulse.render.markdown import render_markdown
from git_pulse.report.builder import build_report
from tests.helpers.repo_builder import RepoBuilder

NOW = datetime(2025, 3, 1, 12, 0, 0, tzinfo=UTC)


def _report(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("app.py", "".join(f"line{i}\n" for i in range(20))).commit("initial")
    b.advance(hours=2).write("app.py", "x\n" * 20).agent_commit("agent rewrite")
    return build_report(b.path, GitPulseConfig.defaults(), options=CollectOptions(), now=NOW)


def test_markdown_contains_header(tmp_path):
    md = render_markdown(_report(tmp_path))
    assert "# git-pulse report:" in md


def test_markdown_contains_attribution_table(tmp_path):
    md = render_markdown(_report(tmp_path))
    assert "## Attribution" in md
    assert "Agent commits" in md


def test_markdown_contains_velocity(tmp_path):
    md = render_markdown(_report(tmp_path))
    assert "## Velocity" in md
    assert "Commits/day" in md


def test_markdown_contains_churn_table(tmp_path):
    md = render_markdown(_report(tmp_path))
    assert "## Most-changed files" in md
    assert "`app.py`" in md


def test_empty_report_renders_gracefully(tmp_path):
    import subprocess

    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=empty, check=True)
    report = build_report(empty, GitPulseConfig.defaults(), now=NOW)
    md = render_markdown(report)

    assert "No commits" in md


def test_markdown_is_a_string(tmp_path):
    md = render_markdown(_report(tmp_path))
    assert isinstance(md, str)
    assert len(md) > 100
