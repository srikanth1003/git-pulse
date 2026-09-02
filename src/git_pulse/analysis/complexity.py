"""Indentation-based complexity proxy.

Measures indentation depth distribution per file from raw text at HEAD.
No language-specific parser needed.
"""

from __future__ import annotations

from collections.abc import Sequence

from git_pulse.gitlayer.repo import GitRepo
from git_pulse.models.results import ComplexityResult, FileComplexity

DEEP_THRESHOLD = 4


def analyze_complexity(
    repo: GitRepo,
    rev: str,
    paths: Sequence[str],
    *,
    indent_width: int = 4,
    max_files: int = 20,
) -> ComplexityResult:
    """Compute indentation-based complexity for ``paths`` at ``rev``."""
    if not paths:
        return ComplexityResult(files=(), repo_avg_depth=0.0, repo_max_depth=0)

    files: list[FileComplexity] = []
    all_depths: list[int] = []

    for path in paths:
        try:
            content = repo.run("show", f"{rev}:{path}")
        except Exception:
            continue

        depths = _line_depths(content, indent_width)
        if not depths:
            continue

        avg = sum(depths) / len(depths)
        mx = max(depths)
        deep = sum(1 for d in depths if d >= DEEP_THRESHOLD)
        all_depths.extend(depths)

        files.append(
            FileComplexity(
                path=path,
                avg_depth=round(avg, 2),
                max_depth=mx,
                deep_line_share=round(deep / len(depths), 4),
                total_lines=len(depths),
            )
        )

    files.sort(key=lambda f: (-f.avg_depth, -f.max_depth, f.path))

    return ComplexityResult(
        files=tuple(files[:max_files]),
        repo_avg_depth=round(sum(all_depths) / len(all_depths), 2) if all_depths else 0.0,
        repo_max_depth=max(all_depths) if all_depths else 0,
    )


def _line_depths(content: str, indent_width: int) -> list[int]:
    """Measure indentation depth for each non-blank line."""
    depths: list[int] = []
    for line in content.splitlines():
        stripped = line.lstrip()
        if not stripped:
            continue
        leading = len(line) - len(stripped)
        if line[0] == "\t":
            depths.append(leading)
        else:
            depths.append(leading // indent_width)
    return depths
