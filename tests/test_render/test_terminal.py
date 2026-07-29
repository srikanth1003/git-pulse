from __future__ import annotations

import subprocess
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from rich.console import Console

from git_pulse.config import GitPulseConfig
from git_pulse.render.terminal import render_terminal
from git_pulse.report.builder import build_report
from tests.helpers.repo_builder import RepoBuilder

# Inside the default 30-day window relative to RepoBuilder's 2025-01-01 epoch,
# so the default CollectOptions(days=30) actually sees the fixture's commits.
NOW = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)


def _text(report) -> str:
    console = Console(width=100, no_color=True, force_terminal=False, record=True)
    render_terminal(report, console=console)
    return console.export_text()


@pytest.fixture
def report(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("app.py", "".join(f"line{i}\n" for i in range(20))).commit("initial")
    b.advance(hours=2).write("app.py", "x\n" * 20).agent_commit("agent rewrite")
    b.advance(hours=1).write("util.py", "y\n").commit("util")
    return build_report(b.path, GitPulseConfig.defaults(), now=NOW)


def test_header_names_the_repository_and_branch(report):
    out = _text(report)

    assert report.repo_name in out
    assert "main" in out


def test_attribution_section_shows_the_agent_share(report):
    out = _text(report)

    assert "Attribution" in out
    assert "33" in out  # 1 of 3 commits is agent-authored


def test_churned_files_are_listed(report):
    out = _text(report)

    assert "app.py" in out
    assert "util.py" in out


def test_velocity_and_sessions_sections_are_present(report):
    out = _text(report)

    assert "Velocity" in out
    assert "Sessions" in out


def test_narrative_is_shown_when_present(report):
    out = _text(replace(report, narrative="The agent rewrote app.py wholesale."))

    assert "rewrote app.py wholesale" in out


def test_narrative_section_is_omitted_when_absent(report):
    assert "Narrative" not in _text(report)


def test_warnings_are_surfaced(report):
    out = _text(replace(report, warnings=("Repository is a shallow clone.",)))

    assert "shallow clone" in out


def test_empty_report_prints_a_clear_message_not_a_traceback(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=empty, check=True)
    out = _text(build_report(empty, GitPulseConfig.defaults(), now=NOW))

    assert "No commits" in out


def test_long_paths_do_not_break_rendering(tmp_path):
    deep = "a/" * 30 + "file.py"
    b = RepoBuilder(tmp_path / "r")
    b.write(deep, "x\n").commit("deep")

    assert "file.py" in _text(build_report(b.path, GitPulseConfig.defaults(), now=NOW))
