"""Risk quadrant analysis: churn x bus factor.

Each file is placed in a 2x2 matrix:
- High churn + risky (bus=1) = "hot-risk"
- Low churn + risky (bus=1) = "quiet-risk"
- High churn + safe (bus>=2) = "active"
- Low churn + safe (bus>=2) = "stable"

Churn threshold is the median across all analyzed files.
"""

from __future__ import annotations

from statistics import median

from git_pulse.models.results import (
    ChurnResult,
    FileRisk,
    OwnershipResult,
    RiskResult,
)


def analyze_risk(churn: ChurnResult, ownership: OwnershipResult | None) -> RiskResult:
    """Classify files into risk quadrants."""
    if ownership is None or not churn.files:
        return RiskResult(files=(), hot_risk=0, quiet_risk=0, active=0, stable=0)

    ownership_by_path = {f.path: f for f in ownership.files}
    churns = [f.churn for f in churn.files if f.churn > 0]
    churn_threshold = median(churns) if churns else 0

    files: list[FileRisk] = []
    counts = {"hot-risk": 0, "quiet-risk": 0, "active": 0, "stable": 0}

    for fc in churn.files:
        own = ownership_by_path.get(fc.path)
        bus = own.bus_factor if own else 0
        high_churn = fc.churn > churn_threshold
        risky = bus <= 1

        if high_churn and risky:
            quadrant = "hot-risk"
        elif not high_churn and risky:
            quadrant = "quiet-risk"
        elif high_churn and not risky:
            quadrant = "active"
        else:
            quadrant = "stable"

        counts[quadrant] += 1
        files.append(FileRisk(path=fc.path, quadrant=quadrant, churn=fc.churn, bus_factor=bus))

    files.sort(key=lambda f: (f.quadrant != "hot-risk", f.quadrant != "quiet-risk", -f.churn))

    return RiskResult(
        files=tuple(files),
        hot_risk=counts["hot-risk"],
        quiet_risk=counts["quiet-risk"],
        active=counts["active"],
        stable=counts["stable"],
    )
