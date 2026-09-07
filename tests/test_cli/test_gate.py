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


def test_gate_passes_when_under_threshold(tmp_path):
    rpt = _json_report(tmp_path)
    result = runner.invoke(app, ["gate", "--report", rpt, "--max-agent-share", "0.99"])
    assert result.exit_code == 0
    assert "PASSED" in result.output


def test_gate_fails_when_over_threshold(tmp_path):
    rpt = _json_report(tmp_path)
    result = runner.invoke(app, ["gate", "--report", rpt, "--max-agent-share", "0.01"])
    assert result.exit_code == 1
    assert "FAILED" in result.output


def test_gate_no_thresholds_passes_with_warning(tmp_path):
    rpt = _json_report(tmp_path)
    result = runner.invoke(app, ["gate", "--report", rpt])
    assert result.exit_code == 0
    assert "no thresholds" in result.output.lower()


def test_gate_multiple_failures(tmp_path):
    rpt = _json_report(tmp_path)
    result = runner.invoke(
        app,
        [
            "gate",
            "--report",
            rpt,
            "--max-agent-share",
            "0.01",
            "--max-rework",
            "0.01",
        ],
    )
    assert result.exit_code == 1
    assert "2 threshold" in result.output


def test_gate_missing_report_file(tmp_path):
    result = runner.invoke(app, ["gate", "--report", "/nonexistent.json"])
    assert result.exit_code == 2


def test_gate_inline_analysis(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("app.py", "hello\n").commit("add")
    result = runner.invoke(app, ["gate", "--path", str(b.path), "--max-agent-share", "0.99"])
    assert result.exit_code == 0
    assert "PASSED" in result.output
