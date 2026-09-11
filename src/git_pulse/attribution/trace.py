"""Read Agent Trace spec (agent-trace.dev) v1 JSON records.

Trace records provide per-line attribution with contributor type (human, ai,
mixed, unknown) and optional model_id. When available, these override the
commit-level attribution for affected line ranges.

Discovery: scans .agent-trace/ in the repo root, or a configured directory.
Each .json file is parsed as a trace record per the v1 schema.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TraceContributor:
    """Per-range contributor from a trace record."""

    contributor_type: str  # "human", "ai", "mixed", "unknown"
    model_id: str | None


@dataclass(frozen=True)
class TraceRange:
    """A line range with attribution from a trace record."""

    file_path: str
    start_line: int
    end_line: int
    contributor: TraceContributor
    conversation_url: str | None
    content_hash: str | None


@dataclass(frozen=True)
class TraceRecord:
    """One parsed agent-trace.dev v1 record."""

    record_id: str
    version: str
    timestamp: str
    revision: str | None
    tool_name: str | None
    tool_version: str | None
    ranges: tuple[TraceRange, ...]


@dataclass(frozen=True)
class TraceIndex:
    """All trace data for a repository, keyed by file path and revision."""

    records: tuple[TraceRecord, ...]
    by_revision: dict[str, tuple[TraceRecord, ...]]
    by_file: dict[str, tuple[TraceRange, ...]]
    total_ranges: int
    total_files: int
    models_seen: dict[str, int]


def load_traces(repo_root: Path, trace_dir: str = ".agent-trace") -> TraceIndex:
    """Discover and parse all trace records in the trace directory."""
    trace_path = repo_root / trace_dir
    if not trace_path.is_dir():
        return _empty_index()

    records: list[TraceRecord] = []
    for json_file in sorted(trace_path.rglob("*.json")):
        record = _parse_record(json_file)
        if record:
            records.append(record)

    if not records:
        return _empty_index()

    return _build_index(tuple(records))


def _parse_record(path: Path) -> TraceRecord | None:
    """Parse one trace record JSON file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    if "version" not in data or "files" not in data:
        return None

    vcs = data.get("vcs", {})
    tool = data.get("tool", {})

    ranges: list[TraceRange] = []
    for file_entry in data.get("files", []):
        file_path = file_entry.get("path", "")
        if not file_path:
            continue

        for conv in file_entry.get("conversations", []):
            conv_url = conv.get("url")
            conv_contributor = _parse_contributor(conv.get("contributor"))

            for rng in conv.get("ranges", []):
                range_contributor = _parse_contributor(rng.get("contributor"))
                contributor = range_contributor or conv_contributor
                if contributor is None:
                    contributor = TraceContributor(contributor_type="unknown", model_id=None)

                ranges.append(
                    TraceRange(
                        file_path=file_path,
                        start_line=rng.get("start_line", 0),
                        end_line=rng.get("end_line", 0),
                        contributor=contributor,
                        conversation_url=conv_url,
                        content_hash=rng.get("content_hash"),
                    )
                )

    return TraceRecord(
        record_id=data.get("id", ""),
        version=data.get("version", ""),
        timestamp=data.get("timestamp", ""),
        revision=vcs.get("revision"),
        tool_name=tool.get("name"),
        tool_version=tool.get("version"),
        ranges=tuple(ranges),
    )


def _parse_contributor(data: dict | None) -> TraceContributor | None:
    if data is None:
        return None
    ctype = data.get("type")
    if ctype is None:
        return None
    return TraceContributor(
        contributor_type=ctype,
        model_id=data.get("model_id"),
    )


def _build_index(records: tuple[TraceRecord, ...]) -> TraceIndex:
    by_revision: dict[str, list[TraceRecord]] = {}
    by_file: dict[str, list[TraceRange]] = {}
    models: dict[str, int] = {}

    total_ranges = 0
    files_seen: set[str] = set()

    for record in records:
        if record.revision:
            by_revision.setdefault(record.revision, []).append(record)

        for rng in record.ranges:
            by_file.setdefault(rng.file_path, []).append(rng)
            files_seen.add(rng.file_path)
            total_ranges += 1

            if rng.contributor.model_id:
                models[rng.contributor.model_id] = models.get(rng.contributor.model_id, 0) + 1

    return TraceIndex(
        records=records,
        by_revision={k: tuple(v) for k, v in by_revision.items()},
        by_file={k: tuple(v) for k, v in by_file.items()},
        total_ranges=total_ranges,
        total_files=len(files_seen),
        models_seen=models,
    )


def _empty_index() -> TraceIndex:
    return TraceIndex(
        records=(),
        by_revision={},
        by_file={},
        total_ranges=0,
        total_files=0,
        models_seen={},
    )


def get_line_attribution(
    index: TraceIndex, file_path: str, line_number: int, revision: str | None = None
) -> TraceContributor | None:
    """Look up per-line attribution from trace data.

    Follows the spec's lookup procedure: find ranges for this file that
    contain the line number, optionally filtering by revision.
    """
    ranges = index.by_file.get(file_path, ())
    for rng in ranges:
        if rng.start_line <= line_number <= rng.end_line:
            return rng.contributor
    return None
