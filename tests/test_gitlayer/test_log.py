from __future__ import annotations

from git_pulse.gitlayer.log import LOG_FORMAT, build_log_args, parse_log_output


def _record(
    sha="a" * 40,
    an="Ada",
    ae="ada@example.com",
    ai="2025-01-01T09:00:00+00:00",
    ci="2025-01-01T09:00:00+00:00",
    parents="",
    body="subject",
    numstat="",
):
    """Assemble one raw log record exactly as git emits it with LOG_FORMAT."""
    fields = [sha, an, ae, ai, ci, parents, body]
    return "\x1e" + "\x1f".join(fields) + "\x1f" + numstat


def test_parses_a_single_commit_with_no_files():
    records = parse_log_output(_record(body="chore: empty"))

    assert len(records) == 1
    assert records[0].sha == "a" * 40
    assert records[0].author_name == "Ada"
    assert records[0].message == "chore: empty"
    assert records[0].files == ()


def test_parses_iso_timestamps_into_aware_datetimes():
    records = parse_log_output(_record(ai="2025-03-04T05:06:07+02:00"))

    assert records[0].authored_at.isoformat() == "2025-03-04T05:06:07+02:00"
    assert records[0].authored_at.tzinfo is not None


def test_parses_parents_into_a_tuple():
    assert parse_log_output(_record(parents=""))[0].parents == ()
    assert parse_log_output(_record(parents="p1"))[0].parents == ("p1",)
    assert parse_log_output(_record(parents="p1 p2"))[0].parents == ("p1", "p2")


def test_preserves_multiline_bodies_including_trailers():
    body = "feat: thing\n\nSome detail.\n\nCo-Authored-By: Claude <noreply@anthropic.com>"
    records = parse_log_output(_record(body=body))

    assert records[0].message == body


def test_parses_numstat_entries():
    numstat = "\n3\t1\ta.py\x0010\t0\tb/c.py\x00"
    files = parse_log_output(_record(numstat=numstat))[0].files

    assert len(files) == 2
    assert (files[0].path, files[0].insertions, files[0].deletions) == ("a.py", 3, 1)
    assert (files[1].path, files[1].insertions, files[1].deletions) == ("b/c.py", 10, 0)
    assert files[0].is_binary is False


def test_parses_binary_files_as_zero_churn():
    numstat = "\n-\t-\tlogo.png\x00"
    files = parse_log_output(_record(numstat=numstat))[0].files

    assert files[0].path == "logo.png"
    assert files[0].is_binary is True
    assert files[0].insertions == 0
    assert files[0].deletions == 0


def test_parses_renames_as_three_nul_fields():
    # git -z emits "ins\tdel\t" then oldpath\0newpath for renames.
    numstat = "\n2\t1\t\x00old/a.py\x00new/b.py\x00"
    files = parse_log_output(_record(numstat=numstat))[0].files

    assert len(files) == 1
    assert files[0].old_path == "old/a.py"
    assert files[0].path == "new/b.py"
    assert files[0].insertions == 2
    assert files[0].deletions == 1


def test_parses_multiple_commits():
    blob = _record(sha="a" * 40, body="first", numstat="\n1\t0\ta.py\x00") + _record(
        sha="b" * 40, body="second", numstat="\n2\t2\tb.py\x00"
    )
    records = parse_log_output(blob)

    assert [r.sha[0] for r in records] == ["a", "b"]
    assert records[1].files[0].path == "b.py"


def test_empty_output_yields_no_records():
    assert parse_log_output("") == []
    assert parse_log_output("\n") == []


def test_malformed_record_is_skipped_not_fatal():
    blob = "\x1enot-enough-fields" + _record(sha="b" * 40, body="good")
    records = parse_log_output(blob)

    assert len(records) == 1
    assert records[0].message == "good"


def test_build_log_args_uses_first_parent_and_numstat_by_default():
    args = build_log_args(rev="main")

    assert args[0] == "log"
    assert "main" in args
    assert "--numstat" in args
    assert "-z" in args
    assert "-M" in args
    assert "--first-parent" in args
    assert f"--format={LOG_FORMAT}" in args


def test_build_log_args_honours_include_merges():
    assert "--first-parent" not in build_log_args(rev="main", include_merges=True)


def test_build_log_args_adds_range_limits():
    args = build_log_args(rev="main", max_count=50, since="2025-01-01", until="2025-02-01")

    assert "--max-count=50" in args
    assert "--since=2025-01-01" in args
    assert "--until=2025-02-01" in args


def test_build_log_args_adds_whitespace_flag_when_requested():
    assert "-w" in build_log_args(rev="main", ignore_whitespace=True)
    assert "-w" not in build_log_args(rev="main")
