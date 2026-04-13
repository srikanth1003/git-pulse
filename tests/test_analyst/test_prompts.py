from git_pulse.analyst.prompts import build_system_prompt, build_user_prompt
from git_pulse.analyst.models import Insight, AnalystReport


def test_build_system_prompt():
    prompt = build_system_prompt()
    assert "REWORK_REDUCTION" in prompt
    assert "AGENT_EFFECTIVENESS" in prompt
    assert "CODEBASE_HEALTH" in prompt
    assert "PROMPT_GUIDANCE" in prompt
    assert "WORKFLOW_OPTIMIZATION" in prompt
    assert "JSON" in prompt


def test_build_user_prompt():
    report_dict = {
        "repo_path": "/tmp/repo",
        "branch": "main",
        "total_commits": 5,
        "hotspots": [],
        "file_churn": [],
    }
    prompt = build_user_prompt(report_dict)
    assert "/tmp/repo" in prompt
    assert "main" in prompt


def test_insight_creation():
    i = Insight(
        category="REWORK_REDUCTION",
        title="Auth rewritten 6 times",
        severity="high",
        evidence=["src/auth.py modified in 6 commits"],
        recommendation="Define interface before implementing",
    )
    assert i.severity == "high"


def test_analyst_report_from_dict():
    data = {
        "summary": "Test summary",
        "insights": [
            {
                "category": "CODEBASE_HEALTH",
                "title": "Large file",
                "severity": "medium",
                "evidence": ["router.py is 800 lines"],
                "recommendation": "Split it",
            }
        ],
        "top_actions": ["Split router.py"],
    }
    report = AnalystReport.from_dict(data)
    assert report.summary == "Test summary"
    assert len(report.insights) == 1
    assert report.insights[0].category == "CODEBASE_HEALTH"
