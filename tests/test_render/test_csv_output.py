from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from git_pulse.config import GitPulseConfig
from git_pulse.gitlayer.collect import CollectOptions
from git_pulse.render.csv_output import COLUMNS, render_csv
from git_pulse.report.builder import build_report
from tests.helpers.repo_builder import RepoBuilder

NOW = datetime(2025, 3, 1, 12, 0, 0, tzinfo=UTC)


def _report(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("app.py", "".join(f"line{i}\n" for i in range(20))).commit("initial")
    b.advance(hours=2).write("app.py", "x\n" * 20).agent_commit("agent rewrite")
    return build_report(b.path, GitPulseConfig.defaults(), options=CollectOptions(), now=NOW)


def test_csv_has_header_row(tmp_path):
    output = render_csv(_report(tmp_path))
    reader = csv.reader(io.StringIO(output))
    header = next(reader)
    assert header == COLUMNS


def test_csv_has_data_rows(tmp_path):
    output = render_csv(_report(tmp_path))
    reader = csv.reader(io.StringIO(output))
    next(reader)  # skip header
    rows = list(reader)
    assert len(rows) >= 1
    assert rows[0][0] == "app.py"


def test_csv_is_valid(tmp_path):
    output = render_csv(_report(tmp_path))
    reader = csv.reader(io.StringIO(output))
    rows = list(reader)
    for row in rows:
        assert len(row) == len(COLUMNS)


def test_empty_report_has_only_header(tmp_path):
    import subprocess

    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=empty, check=True)
    report = build_report(empty, GitPulseConfig.defaults(), now=NOW)
    output = render_csv(report)

    reader = csv.reader(io.StringIO(output))
    header = next(reader)
    assert header == COLUMNS
    assert list(reader) == []
