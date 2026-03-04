from datetime import datetime
from git_pulse.collector.models import (
    Hotspot,
    FileChurnEntry,
    ChangeVelocity,
    AgentHumanRatio,
    WorkSession,
    CollectorReport,
)


def test_hotspot_creation():
    h = Hotspot(
        file_path="src/auth.py",
        line_start=10,
        line_end=25,
        modification_count=5,
        time_span_hours=2.5,
        classification="unknown",
        commit_hashes=["abc123", "def456"],
        diff_snippets=["- old\n+ new"],
        score=0.0,
    )
    assert h.file_path == "src/auth.py"
    assert h.modification_count == 5


def test_collector_report_creation():
    report = CollectorReport(
        repo_path="/tmp/repo",
        branch="main",
        commit_range=("aaa", "bbb"),
        time_range=(datetime(2026, 1, 1), datetime(2026, 1, 31)),
        total_commits=10,
        total_files_changed=5,
        hotspots=[],
        file_churn=[],
        change_velocity=ChangeVelocity(
            commits_per_day=1.0,
            avg_files_per_commit=2.0,
            peak_day="2026-01-15",
            peak_commits=3,
        ),
        agent_human_ratio=None,
        rework_rate=0.15,
        sessions=[],
        has_attribution_data=False,
        attribution_source=None,
    )
    assert report.total_commits == 10
    assert report.agent_human_ratio is None


def test_collector_report_to_dict():
    report = CollectorReport(
        repo_path="/tmp/repo",
        branch="main",
        commit_range=("aaa", "bbb"),
        time_range=(datetime(2026, 1, 1), datetime(2026, 1, 31)),
        total_commits=10,
        total_files_changed=5,
        hotspots=[],
        file_churn=[],
        change_velocity=ChangeVelocity(
            commits_per_day=1.0,
            avg_files_per_commit=2.0,
            peak_day="2026-01-15",
            peak_commits=3,
        ),
        agent_human_ratio=None,
        rework_rate=0.15,
        sessions=[],
        has_attribution_data=False,
        attribution_source=None,
    )
    d = report.to_dict()
    assert isinstance(d, dict)
    assert d["repo_path"] == "/tmp/repo"
    assert d["time_range"][0] == "2026-01-01T00:00:00"
