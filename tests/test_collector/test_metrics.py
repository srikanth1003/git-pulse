from git_pulse.collector.metrics import MetricsCalculator
from git_pulse.collector.models import FileChurnEntry, ChangeVelocity, AgentHumanRatio, WorkSession


def make_commit(hash, author, timestamp, files, is_agent=False):
    return {
        "hash": hash,
        "author": author,
        "timestamp": timestamp,
        "message": "msg",
        "files": files,
        "is_agent_attributed": is_agent,
        "attribution_source": None,
    }


def test_file_churn():
    commits = [
        make_commit("a", "dev", "2026-04-01T10:00:00+00:00", [
            {"path": "a.py", "insertions": 5, "deletions": 2, "diff": ""},
        ]),
        make_commit("b", "dev", "2026-04-01T11:00:00+00:00", [
            {"path": "a.py", "insertions": 3, "deletions": 1, "diff": ""},
            {"path": "b.py", "insertions": 10, "deletions": 0, "diff": ""},
        ]),
    ]
    calc = MetricsCalculator(commits)
    churn = calc.file_churn()
    assert len(churn) == 2
    a_entry = [c for c in churn if c.file_path == "a.py"][0]
    assert a_entry.modification_count == 2
    assert a_entry.insertions == 8
    assert a_entry.deletions == 3


def test_change_velocity():
    commits = [
        make_commit("a", "dev", "2026-04-01T10:00:00+00:00", [{"path": "a.py", "insertions": 1, "deletions": 0, "diff": ""}]),
        make_commit("b", "dev", "2026-04-01T14:00:00+00:00", [{"path": "b.py", "insertions": 1, "deletions": 0, "diff": ""}]),
        make_commit("c", "dev", "2026-04-02T10:00:00+00:00", [{"path": "a.py", "insertions": 1, "deletions": 0, "diff": ""}]),
    ]
    calc = MetricsCalculator(commits)
    vel = calc.change_velocity()
    assert isinstance(vel, ChangeVelocity)
    assert vel.commits_per_day > 0
    assert vel.avg_files_per_commit == 1.0


def test_agent_human_ratio_with_attribution():
    commits = [
        make_commit("a", "dev", "2026-04-01T10:00:00+00:00", [], is_agent=True),
        make_commit("b", "dev", "2026-04-01T11:00:00+00:00", [], is_agent=False),
        make_commit("c", "dev", "2026-04-01T12:00:00+00:00", [], is_agent=True),
    ]
    calc = MetricsCalculator(commits)
    ratio = calc.agent_human_ratio()
    assert ratio is not None
    assert ratio.agent_commits == 2
    assert ratio.human_commits == 1
    assert abs(ratio.ratio - 2 / 3) < 0.01


def test_agent_human_ratio_no_attribution():
    commits = [
        make_commit("a", "dev", "2026-04-01T10:00:00+00:00", [], is_agent=False),
        make_commit("b", "dev", "2026-04-01T11:00:00+00:00", [], is_agent=False),
    ]
    calc = MetricsCalculator(commits)
    ratio = calc.agent_human_ratio()
    assert ratio is None


def test_rework_rate():
    commits = [
        make_commit("a", "dev", "2026-04-01T10:00:00+00:00", [
            {"path": "a.py", "insertions": 10, "deletions": 0, "diff": "@@ -1,0 +1,10 @@\n+line"},
        ]),
        make_commit("b", "dev", "2026-04-01T11:00:00+00:00", [
            {"path": "a.py", "insertions": 3, "deletions": 3, "diff": "@@ -1,3 +1,3 @@\n-old\n+new"},
        ]),
    ]
    calc = MetricsCalculator(commits)
    rate = calc.rework_rate()
    assert 0 <= rate <= 1


def test_sessions():
    commits = [
        make_commit("a", "dev", "2026-04-01T10:00:00+00:00", [{"path": "a.py", "insertions": 1, "deletions": 0, "diff": ""}]),
        make_commit("b", "dev", "2026-04-01T10:15:00+00:00", [{"path": "b.py", "insertions": 1, "deletions": 0, "diff": ""}]),
        # 2 hour gap — new session
        make_commit("c", "dev", "2026-04-01T12:30:00+00:00", [{"path": "a.py", "insertions": 1, "deletions": 0, "diff": ""}]),
    ]
    calc = MetricsCalculator(commits)
    sessions = calc.sessions()
    assert len(sessions) == 2
    assert sessions[0].commit_count == 2
    assert sessions[1].commit_count == 1
