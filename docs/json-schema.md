# JSON output schema

`git-pulse analyze --json` emits a single object. `schema_version` is currently
`1`.

## Compatibility

Adding a key is a minor change and will not bump `schema_version`. Renaming or
removing a key, or changing a value's type, bumps `schema_version`. Pin on
`schema_version` if you parse this output.

## Top-level keys

| Key | Type | Notes |
|---|---|---|
| `schema_version` | int | `1` |
| `generated_at` | string | ISO 8601 with UTC offset |
| `git_pulse_version` | string | version that produced the report |
| `repository` | object | `name`, `path`, `branch`, `head_sha` |
| `scope` | object | `total_commits`, `first_commit_at`, `last_commit_at`, `options`, `skipped_files` |
| `attribution` | object | commit and line counts per author class, plus `signals_seen` and `providers_seen` |
| `churn` | object | `total_files`, `total_insertions`, `total_deletions`, `files[]` |
| `rework` | object | file-granularity rework rates, overall and split by agent/human |
| `velocity` | object | rates, `peak_day`, and a `per_day[]` series |
| `sessions` | object | gap-clustered work sessions per author |
| `hotspots` | object | `total_detected` plus the top-scoring `hotspots[]` |
| `narrative` | object or null | `null` unless `--llm` produced a result |
| `warnings` | array of string | conditions that reduce trust in the numbers — always check this |

## Values worth knowing

- `attribution.agent_commit_share` and `agent_line_share` are precomputed floats
  in `[0, 1]`; you do not need to divide anything yourself.
- `attribution.authors[].author_class` is one of `human`, `mixed`, `agent`. A
  fourth value, `unknown`, is reserved and not currently emitted — treat it as
  "do not count this author either way" rather than as an error.
- `attribution.signals_seen` counts signal *instances*, not commits. The
  `bot_identity` signal is tested against both the author and the committer
  field, so a run of 48 bot commits reports 96 matches.
- `hotspots.hotspots[].classification` is one of `repeated-agent`,
  `human-fixing-agent`, `agent-reworked`, `human-iteration`, `unknown`.
- `hotspots.hotspots[].score` is `modification_count² / (1 + time_span_hours)`.
  It is comparable within one report; do not compare scores across repositories.
- `rework.file_rework_rate` is a file-granularity upper bound: it counts files
  that came back for another edit, not lines that were overwritten. A true
  per-line measurement needs a line-lifetime index, which is planned.
- On an empty history every collection is empty, `scope.first_commit_at` is
  `null`, and `warnings` explains why.

## Reading it in CI

```python
import json
import subprocess

report = json.loads(
    subprocess.run(
        ["git-pulse", "analyze", "--json", "--days", "30"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
)

if report["schema_version"] != 1:
    raise SystemExit(f"unsupported schema_version {report['schema_version']}")

for warning in report["warnings"]:
    print(f"::warning::{warning}")

share = report["attribution"]["agent_commit_share"]
print(f"agent share: {share:.1%}")
```
