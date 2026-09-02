from __future__ import annotations

import subprocess
from datetime import UTC, datetime

from git_pulse.config import GitPulseConfig
from git_pulse.gitlayer.collect import CollectOptions
from git_pulse.render.html_report import render_html
from git_pulse.report.builder import build_report
from tests.helpers.repo_builder import RepoBuilder

NOW = datetime(2025, 3, 1, 12, 0, 0, tzinfo=UTC)


def _report(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("app.py", "".join(f"line{i}\n" for i in range(20))).commit("initial")
    b.advance(hours=2).write("app.py", "x\n" * 20).agent_commit("agent rewrite")
    return build_report(b.path, GitPulseConfig.defaults(), options=CollectOptions(), now=NOW)


def test_html_is_valid_document(tmp_path):
    html = render_html(_report(tmp_path))
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html


def test_html_contains_svg_chart(tmp_path):
    html = render_html(_report(tmp_path))
    assert "<svg" in html
    assert "</svg>" in html


def test_html_contains_attribution(tmp_path):
    html = render_html(_report(tmp_path))
    assert "Attribution" in html
    assert "Agent" in html


def test_html_contains_velocity(tmp_path):
    html = render_html(_report(tmp_path))
    assert "Velocity" in html


def test_html_contains_dark_mode(tmp_path):
    html = render_html(_report(tmp_path))
    assert "prefers-color-scheme: dark" in html


def test_empty_report_renders(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=empty, check=True)
    report = build_report(empty, GitPulseConfig.defaults(), now=NOW)
    html = render_html(report)

    assert "<!DOCTYPE html>" in html
    assert "No commits" in html
