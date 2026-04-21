from __future__ import annotations

from datetime import UTC, datetime

import pytest

from git_pulse.models.history import (
    Attribution,
    AttributionSignal,
    AuthorClass,
    Commit,
    FileChange,
    History,
)


def _commit(
    sha: str,
    *,
    hour: int,
    author_class: AuthorClass = AuthorClass.HUMAN,
    parents: tuple[str, ...] = ("parent",),
) -> Commit:
    ts = datetime(2025, 1, 1, hour, tzinfo=UTC)
    return Commit(
        sha=sha,
        author_name="Ada",
        author_email="ada@example.com",
        authored_at=ts,
        committed_at=ts,
        message="subject line\n\nbody text",
        parents=parents,
        files=(FileChange(path="a.py", old_path=None, insertions=3, deletions=1, is_binary=False),),
        attribution=Attribution(
            author_class=author_class,
            confidence=0.0 if author_class is AuthorClass.HUMAN else 0.95,
            provider=None,
            signals=(),
        ),
    )


def test_subject_is_first_line_only():
    assert _commit("a", hour=9).subject == "subject line"


def test_is_merge_detects_multiple_parents():
    assert _commit("a", hour=9, parents=("p1", "p2")).is_merge is True
    assert _commit("a", hour=9, parents=("p1",)).is_merge is False


def test_author_class_proxies_attribution():
    assert _commit("a", hour=9, author_class=AuthorClass.AGENT).author_class is AuthorClass.AGENT


def test_history_orders_newest_first_and_exposes_range():
    history = History(
        repo_path="/tmp/r",
        branch="main",
        head_sha="newest",
        commits=(_commit("newest", hour=17), _commit("oldest", hour=9)),
        skipped_files=(),
        is_shallow=False,
    )

    assert len(history) == 2
    assert history.newest.sha == "newest"
    assert history.oldest.sha == "oldest"
    start, end = history.time_range
    assert start.hour == 9
    assert end.hour == 17


def test_empty_history_has_no_time_range():
    history = History(
        repo_path="/tmp/r",
        branch="main",
        head_sha="x",
        commits=(),
        skipped_files=(),
        is_shallow=False,
    )

    assert len(history) == 0
    with pytest.raises(ValueError, match="empty history"):
        _ = history.time_range


def test_author_class_is_a_string_enum():
    assert AuthorClass.AGENT.value == "agent"
    assert AuthorClass("human") is AuthorClass.HUMAN


def test_attribution_signal_is_hashable():
    signal = AttributionSignal(
        name="coauthor_trailer",
        weight=0.95,
        provider="Claude Code",
        evidence="Co-Authored-By: Claude",
    )
    assert {signal}  # frozen dataclasses are hashable, so they can live in sets
