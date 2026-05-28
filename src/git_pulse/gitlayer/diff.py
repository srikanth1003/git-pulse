from __future__ import annotations

import re
from dataclasses import dataclass

_HUNK_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


@dataclass(frozen=True)
class HunkLine:
    kind: str  # "+", "-", or " "
    content: str


@dataclass(frozen=True)
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: tuple[HunkLine, ...]

    @property
    def insertions(self) -> int:
        return sum(1 for line in self.lines if line.kind == "+")

    @property
    def deletions(self) -> int:
        return sum(1 for line in self.lines if line.kind == "-")


@dataclass
class FileDiff:
    """One file's diff. Mutable during parsing, read as a value afterwards."""

    path: str
    old_path: str | None
    hunks: tuple[Hunk, ...] = ()
    is_binary: bool = False
    is_new: bool = False
    is_deleted: bool = False

    @property
    def insertions(self) -> int:
        return sum(hunk.insertions for hunk in self.hunks)

    @property
    def deletions(self) -> int:
        return sum(hunk.deletions for hunk in self.hunks)


def parse_unified_diff(text: str) -> list[FileDiff]:
    """Parse ``git diff``/``git diff-tree -p`` output into per-file hunks."""
    files: list[FileDiff] = []
    current: FileDiff | None = None
    hunks: list[Hunk] = []
    hunk_header: re.Match[str] | None = None
    hunk_lines: list[HunkLine] = []

    def close_hunk() -> None:
        nonlocal hunk_header, hunk_lines
        if hunk_header is None:
            return
        hunks.append(
            Hunk(
                old_start=int(hunk_header.group("old_start")),
                old_count=int(hunk_header.group("old_count") or 1),
                new_start=int(hunk_header.group("new_start")),
                new_count=int(hunk_header.group("new_count") or 1),
                lines=tuple(hunk_lines),
            )
        )
        hunk_header = None
        hunk_lines = []

    def close_file() -> None:
        nonlocal current, hunks
        close_hunk()
        if current is not None:
            current.hunks = tuple(hunks)
            files.append(current)
        current = None
        hunks = []

    for line in text.splitlines():
        if line.startswith("diff --git "):
            close_file()
            path = _parse_diff_git_paths(line)
            current = FileDiff(path=path, old_path=path)
            continue

        if current is None:
            continue

        if line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            current.is_binary = True
            continue
        if line.startswith("new file mode"):
            current.is_new = True
            current.old_path = None
            continue
        if line.startswith("deleted file mode"):
            current.is_deleted = True
            continue
        if line.startswith("--- "):
            source = line[4:]
            current.old_path = None if source == "/dev/null" else _strip_prefix(source)
            continue
        if line.startswith("+++ "):
            target = line[4:]
            if target != "/dev/null":
                current.path = _strip_prefix(target)
            continue
        if line.startswith("\\ "):
            # "\ No newline at end of file" — metadata, not content.
            continue

        match = _HUNK_RE.match(line)
        if match:
            close_hunk()
            hunk_header = match
            continue

        if hunk_header is not None and line[:1] in ("+", "-", " "):
            hunk_lines.append(HunkLine(kind=line[0], content=line[1:]))

    close_file()
    return files


def _parse_diff_git_paths(line: str) -> str:
    """Extract the b-side path from a ``diff --git a/x b/x`` header.

    Paths may contain spaces, so the halves are split on the ``" b/"`` marker
    rather than on whitespace.
    """
    remainder = line[len("diff --git ") :]
    marker = " b/"
    index = remainder.rfind(marker)
    if index == -1:
        return remainder.strip()
    return remainder[index + len(marker) :].strip()


def _strip_prefix(path: str) -> str:
    """Remove git's ``a/`` or ``b/`` diff prefix."""
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path
