from __future__ import annotations

from itertools import combinations

from git_pulse.models.history import History
from git_pulse.models.results import CoupledPair, CouplingResult


def analyze_coupling(
    history: History,
    *,
    min_shared: int = 3,
    max_pairs: int = 20,
) -> CouplingResult:
    """Find file pairs that change together across commits.

    ``coupling_ratio`` is ``shared_commits / min(commits_a, commits_b)``, so a
    pair that always appears together scores 1.0 regardless of which file is
    busier. Only pairs with at least ``min_shared`` co-occurrences survive.
    """
    per_file: dict[str, int] = {}
    pair_commits: dict[tuple[str, str], list[str]] = {}

    for commit in history.commits:
        paths = sorted({change.path for change in commit.files})
        for path in paths:
            per_file[path] = per_file.get(path, 0) + 1
        for a, b in combinations(paths, 2):
            pair_commits.setdefault((a, b), []).append(commit.sha)

    pairs: list[CoupledPair] = []
    for (a, b), shas in pair_commits.items():
        shared = len(shas)
        if shared < min_shared:
            continue
        ratio = shared / min(per_file[a], per_file[b])
        pairs.append(
            CoupledPair(
                file_a=a,
                file_b=b,
                shared_commits=shared,
                coupling_ratio=round(ratio, 4),
                commit_shas=tuple(shas),
            )
        )

    pairs.sort(key=lambda p: (-p.coupling_ratio, -p.shared_commits, p.file_a, p.file_b))
    return CouplingResult(
        pairs=tuple(pairs[:max_pairs]),
        total_detected=len(pairs),
    )
