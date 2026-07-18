from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from git_pulse.gitlayer.diff import parse_unified_diff
from git_pulse.gitlayer.repo import GitRepo
from git_pulse.models.history import AuthorClass, History
from git_pulse.models.results import Hotspot, HotspotsResult

CLASSIFICATIONS = (
    "repeated-agent",
    "human-fixing-agent",
    "agent-reworked",
    "human-iteration",
    "unknown",
)

_SENTINEL = "\x1e"


@dataclass(frozen=True)
class HotspotParams:
    window_hours: float = 72.0  # edits further apart than this are separate
    region_lines: int = 25  # width of the fixed line regions edits are binned into
    min_modifications: int = 2  # a single edit is not a hotspot
    max_hotspots: int = 20
    max_files: int = 200  # cap the diff fetch on large repos


@dataclass(frozen=True)
class _Modification:
    """One hunk from one commit."""

    sha: str
    when: datetime
    author_class: AuthorClass
    line_start: int
    line_end: int


@dataclass(frozen=True)
class _Touch:
    """One commit's contribution to a region, with per-hunk detail collapsed."""

    sha: str
    when: datetime
    author_class: AuthorClass


@dataclass
class _Region:
    first_bucket: int
    last_bucket: int
    touches: list[_Touch] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0

    @property
    def shas(self) -> frozenset[str]:
        return frozenset(touch.sha for touch in self.touches)


def analyze_hotspots(
    history: History, repo: GitRepo, params: HotspotParams | None = None
) -> HotspotsResult:
    """Cluster repeated edits to the same file region.

    Edits are binned into fixed-width line regions rather than merged by
    proximity. Binning matters: a commit that adds a whole file produces one
    enormous hunk, and under proximity merging that hunk bridges every later
    edit in the file into a single meaningless cluster. Binning lets the same
    large hunk contribute to each region it actually spans.

    Scoring is ``modification_count ** 2 / (1 + time_span_hours)``: repeated
    edits are the signal, and the same number of edits spread over weeks is far
    less interesting than the same number within an afternoon.
    """
    params = params or HotspotParams()
    if not history.commits:
        return HotspotsResult(hotspots=(), total_detected=0)

    paths = _select_paths(history, params.max_files)
    if not paths:
        return HotspotsResult(hotspots=(), total_detected=0)

    per_path = _collect_modifications(history, repo, paths)

    hotspots = [
        _to_hotspot(path, region)
        for path, mods in sorted(per_path.items())
        for region in _regions(mods, params)
    ]
    hotspots.sort(key=lambda h: (-h.score, h.file_path, h.line_start))

    return HotspotsResult(
        hotspots=tuple(hotspots[: params.max_hotspots]),
        total_detected=len(hotspots),
    )


def _select_paths(history: History, max_files: int) -> list[str]:
    """The most-touched paths, so the diff fetch stays bounded."""
    counts: dict[str, int] = {}
    for commit in history.commits:
        for change in commit.files:
            counts[change.path] = counts.get(change.path, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [path for path, _ in ranked[:max_files]]


def _collect_modifications(
    history: History, repo: GitRepo, paths: list[str]
) -> dict[str, list[_Modification]]:
    """Fetch every relevant diff in one ``git log -p`` call and parse hunks."""
    known = {c.sha: c for c in history.commits}

    output = repo.run(
        "log",
        history.head_sha,
        f"--format={_SENTINEL}%H",
        "-p",
        "-M",
        "--first-parent",
        "--no-color",
        "--",
        *paths,
    )

    per_path: dict[str, list[_Modification]] = {}
    for chunk in output.split(_SENTINEL):
        if not chunk.strip():
            continue
        sha, _, diff_text = chunk.partition("\n")
        commit = known.get(sha.strip())
        if commit is None:
            continue  # outside the analyzed range (e.g. --days narrowed it)

        for file_diff in parse_unified_diff(diff_text):
            if file_diff.is_binary:
                continue
            for hunk in file_diff.hunks:
                per_path.setdefault(file_diff.path, []).append(
                    _Modification(
                        sha=commit.sha,
                        when=commit.authored_at,
                        author_class=commit.author_class,
                        line_start=hunk.new_start,
                        line_end=max(hunk.new_start + hunk.new_count - 1, hunk.new_start),
                    )
                )

    return per_path


def _regions(mods: list[_Modification], params: HotspotParams) -> list[_Region]:
    """Bin modifications into line regions, split on time gaps, then coalesce.

    A hunk is recorded against every region it spans, so a wide hunk counts
    towards each part of the file it actually rewrote. Only regions that clear
    ``min_modifications`` survive, and neighbouring survivors touched by exactly
    the same commits are coalesced so one edit does not report as two adjacent
    hotspots.
    """
    width = max(params.region_lines, 1)

    buckets: dict[int, list[_Modification]] = {}
    for mod in mods:
        first = (max(mod.line_start, 1) - 1) // width
        last = (max(mod.line_end, 1) - 1) // width
        for index in range(first, last + 1):
            buckets.setdefault(index, []).append(mod)

    surviving: list[_Region] = []
    for index in sorted(buckets):
        for run in _split_on_time_gaps(buckets[index], params.window_hours):
            touches = _distinct_commits(run)
            if len(touches) < params.min_modifications:
                continue
            surviving.append(
                _Region(
                    first_bucket=index,
                    last_bucket=index,
                    touches=touches,
                    # Clip to the bucket so neighbouring regions report distinct
                    # line ranges even when a wide hunk spans them all.
                    line_start=max(index * width + 1, min(m.line_start for m in run)),
                    line_end=min((index + 1) * width, max(m.line_end for m in run)),
                )
            )

    coalesced: list[_Region] = []
    for region in surviving:
        previous = coalesced[-1] if coalesced else None
        if (
            previous is not None
            and region.first_bucket == previous.last_bucket + 1
            and previous.shas == region.shas
        ):
            previous.last_bucket = region.last_bucket
            previous.line_end = region.line_end
        else:
            coalesced.append(region)

    return coalesced


def _split_on_time_gaps(
    mods: list[_Modification], window_hours: float
) -> list[list[_Modification]]:
    """Split one region's modifications wherever the pause exceeds the window."""
    runs: list[list[_Modification]] = []
    current: list[_Modification] = []

    for mod in sorted(mods, key=lambda m: (m.when, m.sha)):
        if current:
            gap = (mod.when - current[-1].when).total_seconds() / 3600.0
            if gap > window_hours:
                runs.append(current)
                current = []
        current.append(mod)

    if current:
        runs.append(current)
    return runs


def _distinct_commits(mods: list[_Modification]) -> list[_Touch]:
    """Collapse per-hunk modifications to one entry per commit, chronological."""
    seen: dict[str, _Touch] = {}
    for mod in mods:
        if mod.sha not in seen:
            seen[mod.sha] = _Touch(mod.sha, mod.when, mod.author_class)
    return sorted(seen.values(), key=lambda t: (t.when, t.sha))


def _to_hotspot(path: str, region: _Region) -> Hotspot:
    touches = region.touches
    span_hours = (touches[-1].when - touches[0].when).total_seconds() / 3600.0
    count = len(touches)
    agent = sum(1 for t in touches if t.author_class is AuthorClass.AGENT)

    return Hotspot(
        file_path=path,
        line_start=region.line_start,
        line_end=max(region.line_end, region.line_start),
        modification_count=count,
        time_span_hours=span_hours,
        classification=_classify(touches),
        commit_shas=tuple(t.sha for t in touches),
        agent_modifications=agent,
        human_modifications=count - agent,
        score=(count**2) / (1.0 + span_hours),
    )


def _classify(touches: list[_Touch]) -> str:
    """Classify a region from the chronological sequence of author classes."""
    classes = [t.author_class for t in touches]
    agent = sum(1 for c in classes if c is AuthorClass.AGENT)
    human = len(classes) - agent

    if not agent:
        return "human-iteration" if human else "unknown"
    if not human:
        return "repeated-agent"

    # Both wrote here; whoever touched it last says which way the rework ran.
    last_agent = max(i for i, c in enumerate(classes) if c is AuthorClass.AGENT)
    last_human = max(i for i, c in enumerate(classes) if c is not AuthorClass.AGENT)
    return "human-fixing-agent" if last_human > last_agent else "agent-reworked"
