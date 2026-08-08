from __future__ import annotations

import subprocess
from datetime import UTC, datetime

import pytest

from git_pulse.analyst.engine import ENV_KEYS
from git_pulse.analyst.models import AnalystReport, Insight
from git_pulse.config import GitPulseConfig
from git_pulse.report.builder import add_narrative, build_report
from tests.helpers.repo_builder import RepoBuilder

# Inside the default 30-day window relative to RepoBuilder's 2025-01-01 epoch,
# so the default CollectOptions(days=30) actually sees the fixture's commits —
# an empty report would skip the narrative and make every test below vacuous.
NOW = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
RESULT = AnalystReport(
    summary="Steady progress.",
    insights=(Insight(title="app.py churns", severity="medium"),),
    actions=("Add tests.",),
)


@pytest.fixture
def report(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("app.py", "x\n").commit("initial")
    b.advance(hours=1).write("app.py", "y\n").agent_commit("agent edit")
    return build_report(b.path, GitPulseConfig.defaults(), now=NOW)


def _enabled() -> GitPulseConfig:
    config = GitPulseConfig.defaults()
    config.llm.enabled = True
    config.llm.api_key = "test-key"
    return config


def test_disabled_llm_leaves_the_report_untouched(report, monkeypatch):
    monkeypatch.setattr(
        "git_pulse.analyst.engine.AnalystEngine.analyze",
        lambda self, payload: pytest.fail("must not be called"),
    )

    assert add_narrative(report, GitPulseConfig.defaults()).narrative is None


def test_enabled_llm_attaches_summary_insights_and_actions(report, monkeypatch):
    monkeypatch.setattr(
        "git_pulse.analyst.engine.AnalystEngine.analyze", lambda self, payload: RESULT
    )

    result = add_narrative(report, _enabled())

    assert result.narrative == "Steady progress."
    assert result.insights[0].title == "app.py churns"
    assert result.actions == ("Add tests.",)


def test_failed_call_degrades_to_a_warning(report, monkeypatch):
    monkeypatch.setattr(
        "git_pulse.analyst.engine.AnalystEngine.analyze", lambda self, payload: None
    )

    result = add_narrative(report, _enabled())

    assert result.narrative is None
    assert any("unavailable" in w for w in result.warnings)
    assert result.velocity.total_commits == 2  # metrics survive intact


def test_missing_key_degrades_to_a_warning_naming_the_env_var(report, monkeypatch):
    for var in ENV_KEYS:
        monkeypatch.delenv(var, raising=False)
    config = GitPulseConfig.defaults()
    config.llm.enabled = True

    result = add_narrative(report, config)

    assert result.narrative is None
    assert any("ANTHROPIC_API_KEY" in w for w in result.warnings)


def test_empty_report_skips_the_llm_entirely(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "git_pulse.analyst.engine.AnalystEngine.analyze",
        lambda self, payload: pytest.fail("must not be called"),
    )
    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=empty, check=True)

    assert add_narrative(build_report(empty, GitPulseConfig.defaults(), now=NOW), _enabled())


def test_the_payload_sent_to_the_model_is_the_json_schema(report, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "git_pulse.analyst.engine.AnalystEngine.analyze",
        lambda self, payload: captured.update(payload) or RESULT,
    )

    add_narrative(report, _enabled())

    assert captured["schema_version"] == 1
    assert captured["attribution"]["agent_commits"] == 1
