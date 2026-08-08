from __future__ import annotations

import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from git_pulse.analyst.engine import ENV_KEYS, AnalystEngine, LLMUnavailableError
from git_pulse.config import LLMConfig

GOOD = {
    "summary": "The agent rewrote app.py wholesale within two hours.",
    "insights": [
        {
            "category": "rework",
            "title": "app.py rewritten immediately after creation",
            "severity": "medium",
            "evidence": ["app.py:1-20 edited twice in 2h"],
            "recommendation": "Review the agent's initial output before accepting.",
        }
    ],
    "actions": ["Add a test for app.py before the next agent run."],
}


def _response(content: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.fixture
def calls(monkeypatch):
    """Capture completion() calls and script their return values."""
    recorded: list[dict] = []
    queue: list[object] = []

    def fake_completion(**kwargs):
        recorded.append(kwargs)
        result = queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(
        "git_pulse.analyst.engine._completion", lambda: fake_completion, raising=False
    )
    return SimpleNamespace(recorded=recorded, queue=queue)


def _engine(**overrides) -> AnalystEngine:
    return AnalystEngine(LLMConfig(enabled=True, api_key="test-key", **overrides))


def test_valid_response_is_parsed(calls):
    calls.queue.append(_response(json.dumps(GOOD)))

    result = _engine().analyze({"repository": {"name": "r"}})

    assert result is not None
    assert result.summary.startswith("The agent rewrote")
    assert result.insights[0].category == "rework"
    assert result.actions == ("Add a test for app.py before the next agent run.",)


def test_markdown_fenced_json_is_recovered(calls):
    calls.queue.append(_response("```json\n" + json.dumps(GOOD) + "\n```"))

    assert _engine().analyze({}) is not None


def test_malformed_json_triggers_exactly_one_retry(calls):
    calls.queue.extend([_response("not json at all"), _response(json.dumps(GOOD))])

    result = _engine().analyze({})

    assert result is not None
    assert len(calls.recorded) == 2


def test_two_malformed_responses_yield_none_not_a_fake_narrative(calls):
    calls.queue.extend([_response("nope"), _response("still nope")])

    assert _engine().analyze({}) is None


def test_provider_error_yields_none(calls):
    calls.queue.append(RuntimeError("rate limited"))

    assert _engine().analyze({}) is None


def test_timeout_and_model_are_passed_to_the_provider(calls):
    calls.queue.append(_response(json.dumps(GOOD)))

    _engine(model="gpt-4o-mini", timeout_seconds=12).analyze({})

    assert calls.recorded[0]["model"] == "gpt-4o-mini"
    assert calls.recorded[0]["timeout"] == 12


def test_disabled_config_refuses_to_run(calls):
    engine = AnalystEngine(LLMConfig(enabled=False, api_key="test-key"))

    with pytest.raises(LLMUnavailableError, match="not enabled"):
        engine.analyze({})
    assert calls.recorded == []


def test_missing_api_key_raises_before_any_network_call(calls, monkeypatch):
    # Every provider key, not just the common three: a key left in the developer's
    # environment would otherwise make this pass for the wrong reason.
    for var in ENV_KEYS:
        monkeypatch.delenv(var, raising=False)
    engine = AnalystEngine(LLMConfig(enabled=True, api_key=None))

    with pytest.raises(LLMUnavailableError, match="No API key"):
        engine.analyze({})
    assert calls.recorded == []


def test_api_key_is_read_from_the_environment_when_not_configured(calls, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    calls.queue.append(_response(json.dumps(GOOD)))

    assert AnalystEngine(LLMConfig(enabled=True)).analyze({}) is not None


def test_missing_summary_field_is_treated_as_malformed(calls):
    calls.queue.extend(
        [_response(json.dumps({"insights": []})), _response(json.dumps({"insights": []}))]
    )

    assert _engine().analyze({}) is None


def test_insights_missing_optional_fields_still_parse(calls):
    payload = {"summary": "ok", "insights": [{"title": "t"}], "actions": []}
    calls.queue.append(_response(json.dumps(payload)))

    result = _engine().analyze({})

    assert result is not None
    assert result.insights[0].category == "general"
    assert result.insights[0].severity == "info"
    assert result.insights[0].evidence == ()


def test_litellm_is_not_imported_at_module_scope():
    """Importing the engine must stay fast for the default no-LLM path."""
    code = "import sys, git_pulse.analyst.engine as e; print('litellm' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    assert out.stdout.strip() == "False", out.stderr
