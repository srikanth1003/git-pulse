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


def _json_file(tmp_path, name, commits):
    b = RepoBuilder(tmp_path / name)
    for i in range(commits):
        b.write("a.py", f"v{i}\n").commit(f"commit {i}")
        b.advance(hours=1)
    report = build_report(b.path, GitPulseConfig.defaults(), options=CollectOptions(), now=NOW)
    path = tmp_path / f"{name}.json"
    path.write_text(render_json(report), encoding="utf-8")
    return str(path)


def test_compare_shows_deltas(tmp_path):
    before = _json_file(tmp_path, "before", 3)
    after = _json_file(tmp_path, "after", 6)

    result = runner.invoke(app, ["compare", before, after])

    assert result.exit_code == 0
    assert "Total commits" in result.output
    assert "Delta" in result.output


def test_compare_rejects_missing_file(tmp_path):
    before = _json_file(tmp_path, "before", 3)

    result = runner.invoke(app, ["compare", before, "/nonexistent.json"])

    assert result.exit_code == 2


def test_compare_rejects_non_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    before = _json_file(tmp_path, "before", 3)

    result = runner.invoke(app, ["compare", before, str(bad)])

    assert result.exit_code == 2
