from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from git_pulse.models.history import FileChange

# Record separator between commits, unit separator between fields. The body
# (%B) comes last and is followed by a trailing %x1f so the numstat block that
# git appends lands in its own field — bodies may contain newlines but never
# these control characters.
RS = "\x1e"
US = "\x1f"

LOG_FORMAT = f"{RS}%H{US}%an{US}%ae{US}%aI{US}%cI{US}%P{US}%B{US}"

_EXPECTED_FIELDS = 8  # sha, an, ae, aI, cI, P, body, numstat


@dataclass(frozen=True)
class LogRecord:
    """One commit as parsed from git log output, before attribution runs."""

    sha: str
    author_name: str
    author_email: str
    authored_at: datetime
    committed_at: datetime
    parents: tuple[str, ...]
    message: str
    files: tuple[FileChange, ...]


def build_log_args(
    *,
    rev: str,
    max_count: int | None = None,
    since: str | None = None,
    until: str | None = None,
    include_merges: bool = False,
    ignore_whitespace: bool = False,
) -> list[str]:
    """Build the argv for the history-collecting git log invocation."""
    args = ["log", rev, f"--format={LOG_FORMAT}", "--numstat", "-z", "-M"]

    if not include_merges:
        # First-parent keeps merge commits from double-counting their branch's work.
        args.append("--first-parent")
    if ignore_whitespace:
        args.append("-w")
    if max_count is not None:
        args.append(f"--max-count={max_count}")
    if since is not None:
        args.append(f"--since={since}")
    if until is not None:
        args.append(f"--until={until}")

    return args


def parse_log_output(output: str) -> list[LogRecord]:
    """Parse raw ``git log`` output produced with :data:`LOG_FORMAT`."""
    records: list[LogRecord] = []

    for chunk in output.split(RS):
        if not chunk.strip():
            continue
        fields = chunk.split(US)
        if len(fields) < _EXPECTED_FIELDS:
            # Truncated or unexpected record — skip rather than abort the run.
            continue

        sha, author_name, author_email, authored, committed, parents, message = fields[:7]
        numstat_blob = fields[7]

        try:
            authored_at = datetime.fromisoformat(authored)
            committed_at = datetime.fromisoformat(committed)
        except ValueError:
            continue

        records.append(
            LogRecord(
                sha=sha.strip(),
                author_name=author_name,
                author_email=author_email,
                authored_at=authored_at,
                committed_at=committed_at,
                parents=tuple(p for p in parents.split() if p),
                message=message,
                files=_parse_numstat(numstat_blob),
            )
        )

    return records


def _parse_numstat(blob: str) -> tuple[FileChange, ...]:
    """Parse a ``--numstat -z`` block.

    Ordinary entries are one NUL-terminated ``ins\\tdel\\tpath`` token. Renames
    emit ``ins\\tdel\\t`` followed by two further NUL-terminated tokens holding
    the old and new paths.
    """
    tokens = [token.strip("\n") for token in blob.split("\0")]
    tokens = [token for token in tokens if token != ""]

    changes: list[FileChange] = []
    i = 0
    while i < len(tokens):
        parts = tokens[i].split("\t")
        if len(parts) < 3:
            i += 1
            continue

        raw_ins, raw_del, first_path = parts[0], parts[1], parts[2]
        is_binary = raw_ins == "-" or raw_del == "-"
        insertions = 0 if is_binary else _to_int(raw_ins)
        deletions = 0 if is_binary else _to_int(raw_del)

        if first_path:
            changes.append(
                FileChange(
                    path=first_path,
                    old_path=None,
                    insertions=insertions,
                    deletions=deletions,
                    is_binary=is_binary,
                )
            )
            i += 1
        elif i + 2 < len(tokens):
            changes.append(
                FileChange(
                    path=tokens[i + 2],
                    old_path=tokens[i + 1],
                    insertions=insertions,
                    deletions=deletions,
                    is_binary=is_binary,
                )
            )
            i += 3
        else:
            i += 1

    return tuple(changes)


def _to_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0
