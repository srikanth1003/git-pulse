import json

from git_pulse.analyst.models import AnalystReport, Insight
from git_pulse.renderer.json_output import render_json


def test_render_json():
    report = AnalystReport(
        summary="Test",
        insights=[
            Insight(
                category="CODEBASE_HEALTH",
                title="Big file",
                severity="low",
                evidence=["evidence"],
                recommendation="fix it",
            )
        ],
        top_actions=["action1"],
    )
    output = render_json(report)
    data = json.loads(output)
    assert data["summary"] == "Test"
    assert len(data["insights"]) == 1
    assert data["top_actions"] == ["action1"]
