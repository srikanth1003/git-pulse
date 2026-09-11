from __future__ import annotations

import json
from pathlib import Path

from git_pulse.attribution.trace import (
    get_line_attribution,
    load_traces,
)


def _write_trace(trace_dir: Path, filename: str, data: dict) -> None:
    trace_dir.mkdir(parents=True, exist_ok=True)
    (trace_dir / filename).write_text(json.dumps(data), encoding="utf-8")


def _minimal_trace(revision="abc123def456", file_path="app.py", ranges=None):
    if ranges is None:
        ranges = [{"start_line": 1, "end_line": 10}]
    return {
        "version": "1.0",
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": "2026-01-01T00:00:00Z",
        "vcs": {"type": "git", "revision": revision},
        "tool": {"name": "cursor", "version": "2.4.0"},
        "files": [
            {
                "path": file_path,
                "conversations": [
                    {
                        "url": "https://cursor.com/session/123",
                        "contributor": {
                            "type": "ai",
                            "model_id": "anthropic/claude-sonnet-4-20250514",
                        },
                        "ranges": ranges,
                    }
                ],
            }
        ],
    }


def test_load_traces_from_directory(tmp_path):
    _write_trace(tmp_path / ".agent-trace", "trace1.json", _minimal_trace())

    index = load_traces(tmp_path)

    assert len(index.records) == 1
    assert index.total_ranges == 1
    assert index.total_files == 1


def test_no_trace_dir_returns_empty(tmp_path):
    index = load_traces(tmp_path)

    assert index.records == ()
    assert index.total_ranges == 0


def test_trace_indexes_by_revision(tmp_path):
    _write_trace(tmp_path / ".agent-trace", "t1.json", _minimal_trace(revision="abc123"))

    index = load_traces(tmp_path)

    assert "abc123" in index.by_revision
    assert len(index.by_revision["abc123"]) == 1


def test_trace_indexes_by_file(tmp_path):
    _write_trace(tmp_path / ".agent-trace", "t1.json", _minimal_trace(file_path="utils.py"))

    index = load_traces(tmp_path)

    assert "utils.py" in index.by_file
    assert len(index.by_file["utils.py"]) == 1


def test_model_id_tracked(tmp_path):
    _write_trace(tmp_path / ".agent-trace", "t1.json", _minimal_trace())

    index = load_traces(tmp_path)

    assert "anthropic/claude-sonnet-4-20250514" in index.models_seen


def test_get_line_attribution_finds_range(tmp_path):
    _write_trace(
        tmp_path / ".agent-trace",
        "t1.json",
        _minimal_trace(ranges=[{"start_line": 5, "end_line": 15}]),
    )

    index = load_traces(tmp_path)

    result = get_line_attribution(index, "app.py", 10)
    assert result is not None
    assert result.contributor_type == "ai"
    assert result.model_id == "anthropic/claude-sonnet-4-20250514"


def test_get_line_attribution_misses_outside_range(tmp_path):
    _write_trace(
        tmp_path / ".agent-trace",
        "t1.json",
        _minimal_trace(ranges=[{"start_line": 5, "end_line": 10}]),
    )

    index = load_traces(tmp_path)

    assert get_line_attribution(index, "app.py", 20) is None


def test_range_contributor_overrides_conversation(tmp_path):
    trace = _minimal_trace()
    trace["files"][0]["conversations"][0]["ranges"][0]["contributor"] = {
        "type": "human",
    }
    _write_trace(tmp_path / ".agent-trace", "t1.json", trace)

    index = load_traces(tmp_path)

    result = get_line_attribution(index, "app.py", 5)
    assert result is not None
    assert result.contributor_type == "human"


def test_invalid_json_skipped(tmp_path):
    trace_dir = tmp_path / ".agent-trace"
    trace_dir.mkdir()
    (trace_dir / "bad.json").write_text("not json")
    _write_trace(trace_dir, "good.json", _minimal_trace())

    index = load_traces(tmp_path)

    assert len(index.records) == 1


def test_multiple_files_in_one_trace(tmp_path):
    trace = {
        "version": "1.0",
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "timestamp": "2026-01-01T00:00:00Z",
        "files": [
            {
                "path": "a.py",
                "conversations": [
                    {"contributor": {"type": "ai"}, "ranges": [{"start_line": 1, "end_line": 5}]}
                ],
            },
            {
                "path": "b.py",
                "conversations": [
                    {"contributor": {"type": "human"}, "ranges": [{"start_line": 1, "end_line": 3}]}
                ],
            },
        ],
    }
    _write_trace(tmp_path / ".agent-trace", "t1.json", trace)

    index = load_traces(tmp_path)

    assert index.total_files == 2
    assert index.total_ranges == 2
