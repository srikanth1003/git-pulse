from io import StringIO
from datetime import datetime

from rich.console import Console

from git_pulse.analyst.models import AnalystReport, Insight
from git_pulse.collector.models import CollectorReport, ChangeVelocity
from git_pulse.renderer.terminal import render_terminal


def make_report():
    return AnalystReport(
        summary="Auth module has heavy rework. Consider defining interfaces first.",
        insights=[
            Insight(
                category="REWORK_REDUCTION",
                title="Auth rewritten 6 times",
                severity="high",
                evidence=["src/auth.py modified in 6 commits over 4 hours"],
                recommendation="Define auth interface before implementation",
            ),
            Insight(
                category="CODEBASE_HEALTH",
                title="router.py is 800 lines",
                severity="medium",
                evidence=["router.py accounts for 40% of all hotspots"],
                recommendation="Split into sub-routers",
            ),
        ],
        top_actions=["Define auth interface", "Split router.py", "Add tests for auth"],
    )


def make_collector_report():
    return CollectorReport(
        repo_path="/tmp/myproject",
        branch="main",
        commit_range=("aaa", "bbb"),
        time_range=(datetime(2026, 3, 1), datetime(2026, 3, 31)),
        total_commits=142,
        total_files_changed=47,
        hotspots=[],
        file_churn=[],
        change_velocity=ChangeVelocity(
            commits_per_day=4.7, avg_files_per_commit=2.1, peak_day="2026-03-15", peak_commits=12
        ),
        agent_human_ratio=None,
        rework_rate=0.23,
        sessions=[],
        has_attribution_data=False,
        attribution_source=None,
    )


def test_render_terminal_produces_output():
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=100)
    render_terminal(
        analyst_report=make_report(),
        collector_report=make_collector_report(),
        console=console,
    )
    output = buf.getvalue()
    assert "myproject" in output or "main" in output
    assert "Auth rewritten" in output and "times" in output
    assert "Define auth interface" in output


def test_render_terminal_verbose():
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=100)
    render_terminal(
        analyst_report=make_report(),
        collector_report=make_collector_report(),
        console=console,
        verbose=True,
    )
    output = buf.getvalue()
    assert "142" in output  # total commits shown in verbose
