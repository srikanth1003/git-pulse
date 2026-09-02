from __future__ import annotations

from git_pulse.analysis.risk import analyze_risk
from git_pulse.models.results import (
    ChurnResult,
    FileChurn,
    FileOwnership,
    OwnershipResult,
)


def _churn(*files: tuple[str, int]) -> ChurnResult:
    return ChurnResult(
        files=tuple(
            FileChurn(
                path=p,
                commits=1,
                insertions=c,
                deletions=0,
                distinct_authors=1,
                agent_commits=0,
                human_commits=1,
            )
            for p, c in files
        ),
        total_files=len(files),
        total_insertions=sum(c for _, c in files),
        total_deletions=0,
    )


def _ownership(*files: tuple[str, int, int]) -> OwnershipResult:
    return OwnershipResult(
        files=tuple(
            FileOwnership(
                path=p,
                total_lines=lines,
                owners=(("a@x.com", lines),),
                top_owner_share=1.0,
                bus_factor=bus,
            )
            for p, lines, bus in files
        ),
        repo_bus_factor=1,
        total_lines=sum(lines for _, lines, _ in files),
        total_authors=1,
    )


def test_hot_risk_file(tmp_path):
    churn = _churn(("a.py", 100), ("b.py", 10))
    ownership = _ownership(("a.py", 100, 1), ("b.py", 10, 2))

    result = analyze_risk(churn, ownership)

    hot = [f for f in result.files if f.quadrant == "hot-risk"]
    assert len(hot) == 1
    assert hot[0].path == "a.py"


def test_stable_file(tmp_path):
    churn = _churn(("a.py", 100), ("b.py", 10))
    ownership = _ownership(("a.py", 100, 2), ("b.py", 10, 2))

    result = analyze_risk(churn, ownership)

    stable = [f for f in result.files if f.quadrant == "stable"]
    assert len(stable) >= 1


def test_no_ownership_returns_empty():
    churn = _churn(("a.py", 100))
    result = analyze_risk(churn, None)
    assert result.files == ()


def test_counts_sum_to_total():
    churn = _churn(("a.py", 100), ("b.py", 50), ("c.py", 10))
    ownership = _ownership(("a.py", 100, 1), ("b.py", 50, 2), ("c.py", 10, 1))

    result = analyze_risk(churn, ownership)

    assert result.hot_risk + result.quiet_risk + result.active + result.stable == len(result.files)
