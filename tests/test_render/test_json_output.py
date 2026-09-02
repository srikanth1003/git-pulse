from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime

import pytest

from git_pulse.config import GitPulseConfig
from git_pulse.gitlayer.collect import CollectOptions
from git_pulse.render.json_output import SCHEMA_VERSION, render_json
from git_pulse.report.builder import build_report
from tests.helpers.repo_builder import RepoBuilder

NOW = datetime(2025, 3, 1, 12, 0, 0, tzinfo=UTC)

TOP_LEVEL_KEYS = {
    "schema_version",
    "generated_at",
    "git_pulse_version",
    "repository",
    "scope",
    "attribution",
    "churn",
    "rework",
    "velocity",
    "sessions",
    "hotspots",
    "coupling",
    "ownership",
    "line_rework",
    "commit_classification",
    "survival",
    "szz",
    "risk",
    "narrative",
    "warnings",
}


@pytest.fixture
def report(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("app.py", "".join(f"line{i}\n" for i in range(20))).commit("initial")
    b.advance(hours=2).write("app.py", "x\n" * 20).agent_commit("agent rewrite")
    # No day window, so the fixed epoch stays in scope no matter what NOW is.
    return build_report(b.path, GitPulseConfig.defaults(), options=CollectOptions(), now=NOW)


def test_output_is_valid_json(report):
    assert isinstance(json.loads(render_json(report)), dict)


def test_top_level_keys_are_the_documented_contract(report):
    assert set(json.loads(render_json(report))) == TOP_LEVEL_KEYS


def test_schema_version_is_present(report):
    assert json.loads(render_json(report))["schema_version"] == SCHEMA_VERSION


def test_datetimes_are_iso_8601_with_offset(report):
    payload = json.loads(render_json(report))

    assert payload["generated_at"] == "2025-03-01T12:00:00+00:00"
    assert datetime.fromisoformat(payload["scope"]["first_commit_at"]).tzinfo is not None


def test_enums_are_serialized_as_strings(report):
    author = json.loads(render_json(report))["attribution"]["authors"][0]

    assert author["author_class"] in {"human", "mixed", "agent"}


def test_derived_shares_are_included_not_left_to_the_consumer(report):
    attribution = json.loads(render_json(report))["attribution"]

    assert "agent_commit_share" in attribution
    assert "agent_line_share" in attribution


def test_output_is_deterministic(report):
    assert render_json(report) == render_json(report)


def test_indent_none_produces_a_single_line(report):
    assert "\n" not in render_json(report, indent=None)


def test_empty_report_still_matches_the_schema(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=empty, check=True)
    payload = json.loads(render_json(build_report(empty, GitPulseConfig.defaults(), now=NOW)))

    assert set(payload) == TOP_LEVEL_KEYS
    assert payload["scope"]["first_commit_at"] is None
    assert payload["churn"]["files"] == []
