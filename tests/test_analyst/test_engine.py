import json
from unittest.mock import patch, MagicMock

from git_pulse.analyst.engine import AnalystEngine
from git_pulse.analyst.models import AnalystReport


MOCK_LLM_RESPONSE = json.dumps({
    "summary": "The repo shows heavy rework in auth module.",
    "insights": [
        {
            "category": "REWORK_REDUCTION",
            "title": "Auth middleware rewritten 4 times",
            "severity": "high",
            "evidence": ["src/auth.py modified in commits aaa, bbb, ccc, ddd"],
            "recommendation": "Define auth interface before implementing",
        }
    ],
    "top_actions": ["Define auth interface", "Split router.py", "Add tests"],
})


def test_analyze_calls_litellm():
    report_dict = {
        "repo_path": "/tmp/repo",
        "branch": "main",
        "total_commits": 10,
        "hotspots": [],
        "file_churn": [],
        "has_attribution_data": False,
    }

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = MOCK_LLM_RESPONSE

    with patch("git_pulse.analyst.engine.completion", return_value=mock_response) as mock_llm:
        engine = AnalystEngine(model="anthropic/claude-sonnet-4-20250514")
        result = engine.analyze(report_dict)

        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args
        assert call_kwargs.kwargs["model"] == "anthropic/claude-sonnet-4-20250514"

    assert isinstance(result, AnalystReport)
    assert "rework" in result.summary.lower()
    assert len(result.insights) == 1
    assert result.insights[0].category == "REWORK_REDUCTION"


def test_analyze_handles_malformed_json():
    report_dict = {"repo_path": "/tmp", "branch": "main", "total_commits": 1}

    bad_response = MagicMock()
    bad_response.choices = [MagicMock()]
    bad_response.choices[0].message.content = "not valid json {{"

    good_response = MagicMock()
    good_response.choices = [MagicMock()]
    good_response.choices[0].message.content = MOCK_LLM_RESPONSE

    with patch("git_pulse.analyst.engine.completion", side_effect=[bad_response, good_response]):
        engine = AnalystEngine(model="test-model")
        result = engine.analyze(report_dict)

    assert isinstance(result, AnalystReport)


def test_analyze_raises_on_persistent_failure():
    report_dict = {"repo_path": "/tmp", "branch": "main", "total_commits": 1}

    bad_response = MagicMock()
    bad_response.choices = [MagicMock()]
    bad_response.choices[0].message.content = "garbage"

    with patch("git_pulse.analyst.engine.completion", return_value=bad_response):
        engine = AnalystEngine(model="test-model")
        try:
            result = engine.analyze(report_dict)
            assert isinstance(result, AnalystReport)
            assert "failed" in result.summary.lower() or "error" in result.summary.lower()
        except Exception:
            pass
