"""Code ownership and bus factor from line-level blame data.

Bus factor is the minimum number of authors whose combined line ownership
exceeds 50% of the file (or repo). A bus factor of 1 means one person wrote
more than half the surviving code.
"""

from __future__ import annotations

from collections import Counter

from git_pulse.analysis.line_lifetime import LifetimeIndex
from git_pulse.models.results import FileOwnership, OwnershipResult


def analyze_ownership(index: LifetimeIndex, *, max_files: int = 20) -> OwnershipResult:
    """Compute per-file and repo-wide ownership from the lifetime index."""
    if not index:
        return OwnershipResult(files=(), repo_bus_factor=0, total_lines=0, total_authors=0)

    repo_counter: Counter[str] = Counter()
    files: list[FileOwnership] = []

    for path, lifetime in sorted(index.items()):
        file_counter: Counter[str] = Counter()
        for birth in lifetime.births:
            file_counter[birth.author_email] += 1
            repo_counter[birth.author_email] += 1

        total = sum(file_counter.values())
        if total == 0:
            continue

        owners = tuple(file_counter.most_common())
        top_share = owners[0][1] / total if owners else 0.0

        files.append(
            FileOwnership(
                path=path,
                total_lines=total,
                owners=owners,
                top_owner_share=round(top_share, 4),
                bus_factor=_bus_factor(file_counter, total),
            )
        )

    files.sort(key=lambda f: (f.bus_factor, -f.total_lines, f.path))

    repo_total = sum(repo_counter.values())
    return OwnershipResult(
        files=tuple(files[:max_files]),
        repo_bus_factor=_bus_factor(repo_counter, repo_total),
        total_lines=repo_total,
        total_authors=len(repo_counter),
    )


def _bus_factor(counter: Counter[str], total: int) -> int:
    """Minimum authors owning >50% of lines."""
    if total == 0:
        return 0
    threshold = total * 0.5
    cumulative = 0
    for i, (_author, count) in enumerate(counter.most_common(), 1):
        cumulative += count
        if cumulative > threshold:
            return i
    return len(counter)
