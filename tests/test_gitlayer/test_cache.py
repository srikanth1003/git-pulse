from __future__ import annotations

from datetime import UTC, datetime

from git_pulse.gitlayer.cache import (
    CACHE_SCHEMA_VERSION,
    HistoryCache,
    cache_root,
    clear_all,
    global_info,
)
from git_pulse.models.history import (
    Attribution,
    AttributionSignal,
    AuthorClass,
    Commit,
    FileChange,
    History,
)


def _history(repo="/tmp/r", sha="abc") -> History:
    ts = datetime(2025, 1, 1, 9, tzinfo=UTC)
    return History(
        repo_path=repo,
        branch="main",
        head_sha=sha,
        commits=(
            Commit(
                sha=sha,
                author_name="Ada",
                author_email="ada@example.com",
                authored_at=ts,
                committed_at=ts,
                message="feat: thing\n\nCo-Authored-By: Claude <noreply@anthropic.com>",
                parents=("p1",),
                files=(
                    FileChange(
                        path="a.py",
                        old_path=None,
                        insertions=3,
                        deletions=1,
                        is_binary=False,
                    ),
                    FileChange(
                        path="new.py",
                        old_path="old.py",
                        insertions=0,
                        deletions=0,
                        is_binary=True,
                    ),
                ),
                attribution=Attribution(
                    author_class=AuthorClass.AGENT,
                    confidence=0.95,
                    provider="Claude Code",
                    signals=(
                        AttributionSignal(
                            "coauthor_trailer",
                            0.95,
                            "Claude Code",
                            "Co-Authored-By: Claude",
                        ),
                    ),
                ),
            ),
        ),
        skipped_files=("logo.png",),
        is_shallow=False,
    )


def test_cache_root_honours_xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert cache_root() == tmp_path / "gitpulse"


def test_miss_on_empty_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    cache = HistoryCache(tmp_path / "repo")
    assert cache.load(cache.key(head_sha="abc", branch="main", options={})) is None


def test_round_trip_preserves_every_field(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    cache = HistoryCache(tmp_path / "repo")
    key = cache.key(head_sha="abc", branch="main", options={"days": 30})
    original = _history()

    cache.store(key, original)
    loaded = cache.load(key)

    assert loaded == original


def test_key_changes_with_head_sha(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    cache = HistoryCache(tmp_path / "repo")
    a = cache.key(head_sha="aaa", branch="main", options={})
    b = cache.key(head_sha="bbb", branch="main", options={})
    assert a != b


def test_key_changes_with_options_but_not_their_order(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    cache = HistoryCache(tmp_path / "repo")
    assert cache.key(head_sha="a", branch="main", options={"days": 30}) != cache.key(
        head_sha="a", branch="main", options={"days": 14}
    )
    assert cache.key(head_sha="a", branch="main", options={"days": 30, "x": 1}) == cache.key(
        head_sha="a", branch="main", options={"x": 1, "days": 30}
    )


def test_disabled_cache_never_stores_or_loads(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    cache = HistoryCache(tmp_path / "repo", enabled=False)
    key = cache.key(head_sha="abc", branch="main", options={})

    cache.store(key, _history())

    assert cache.load(key) is None


def test_schema_version_bump_invalidates_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    cache = HistoryCache(tmp_path / "repo")
    key = cache.key(head_sha="abc", branch="main", options={})
    cache.store(key, _history())

    monkeypatch.setattr("git_pulse.gitlayer.cache.CACHE_SCHEMA_VERSION", CACHE_SCHEMA_VERSION + 1)

    assert cache.load(key) is None


def test_corrupt_entry_is_treated_as_a_miss(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    cache = HistoryCache(tmp_path / "repo")
    key = cache.key(head_sha="abc", branch="main", options={})
    cache.store(key, _history())

    cache.path_for(key).write_bytes(b"not gzip")

    assert cache.load(key) is None


def test_clear_removes_entries_and_reports_the_count(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    cache = HistoryCache(tmp_path / "repo")
    cache.store(cache.key(head_sha="a", branch="main", options={}), _history(sha="a"))
    cache.store(cache.key(head_sha="b", branch="main", options={}), _history(sha="b"))

    assert cache.clear() == 2
    assert cache.info().entries == 0


def test_info_reports_entries_and_bytes(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    cache = HistoryCache(tmp_path / "repo")
    cache.store(cache.key(head_sha="a", branch="main", options={}), _history())

    info = cache.info()

    assert info.entries == 1
    assert info.bytes > 0


def test_separate_repos_do_not_share_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    one = HistoryCache(tmp_path / "repo-one")
    two = HistoryCache(tmp_path / "repo-two")
    key = one.key(head_sha="abc", branch="main", options={})

    one.store(key, _history())

    assert two.load(two.key(head_sha="abc", branch="main", options={})) is None


def test_write_only_cache_never_reads_but_still_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    cache = HistoryCache(tmp_path / "repo", write_only=True)
    key = cache.key(head_sha="abc", branch="main", options={})

    cache.store(key, _history())

    assert cache.load(key) is None
    assert HistoryCache(tmp_path / "repo").load(key) is not None


def test_global_info_aggregates_across_repositories(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    for name in ("repo-one", "repo-two"):
        cache = HistoryCache(tmp_path / name)
        cache.store(cache.key(head_sha="a", branch="main", options={}), _history())

    info = global_info()

    assert info.entries == 2
    assert info.bytes > 0


def test_clear_all_empties_every_repository(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    for name in ("repo-one", "repo-two"):
        cache = HistoryCache(tmp_path / name)
        cache.store(cache.key(head_sha="a", branch="main", options={}), _history())

    assert clear_all() == 2
    assert global_info().entries == 0


def test_global_info_on_a_missing_root_reports_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "nothing-here"))

    assert global_info().entries == 0
    assert clear_all() == 0
