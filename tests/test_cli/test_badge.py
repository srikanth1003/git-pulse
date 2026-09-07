from __future__ import annotations

from datetime import UTC, datetime

from typer.testing import CliRunner

from git_pulse.cli.main import app
from git_pulse.config import GitPulseConfig
from git_pulse.gitlayer.collect import CollectOptions
from git_pulse.render.json_output import render_json
from git_pulse.report.builder import build_report
from tests.helpers.repo_builder import RepoBuilder

runner = CliRunner()
NOW = datetime(2025, 3, 1, 12, 0, 0, tzinfo=UTC)


def _json_report(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("app.py", "".join(f"line{i}\n" for i in range(20))).commit("initial")
    b.advance(hours=2).write("app.py", "x\n" * 20).agent_commit("agent rewrite")
    report = build_report(b.path, GitPulseConfig.defaults(), options=CollectOptions(), now=NOW)
    path = tmp_path / "report.json"
    path.write_text(render_json(report), encoding="utf-8")
    return str(path)


def test_badge_generates_svgs(tmp_path):
    rpt = _json_report(tmp_path)
    out_dir = tmp_path / "badges"
    result = runner.invoke(app, ["badge", "--report", rpt, "--output", str(out_dir)])

    assert result.exit_code == 0
    assert (out_dir / "agent-share.svg").exists()
    svg = (out_dir / "agent-share.svg").read_text()
    assert "<svg" in svg
    assert "agent share" in svg


def test_badge_agent_share_value(tmp_path):
    rpt = _json_report(tmp_path)
    out_dir = tmp_path / "badges"
    runner.invoke(app, ["badge", "--report", rpt, "--output", str(out_dir)])

    svg = (out_dir / "agent-share.svg").read_text()
    assert "50%" in svg


def test_badge_missing_report(tmp_path):
    result = runner.invoke(app, ["badge", "--report", "/nonexistent.json"])
    assert result.exit_code == 2


def test_badge_creates_output_dir(tmp_path):
    rpt = _json_report(tmp_path)
    out_dir = tmp_path / "nested" / "badges"
    result = runner.invoke(app, ["badge", "--report", rpt, "--output", str(out_dir)])

    assert result.exit_code == 0
    assert out_dir.exists()
