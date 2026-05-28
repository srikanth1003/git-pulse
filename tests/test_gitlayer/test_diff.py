from __future__ import annotations

from git_pulse.gitlayer.diff import parse_unified_diff
from git_pulse.gitlayer.repo import GitRepo
from tests.helpers.repo_builder import RepoBuilder

SIMPLE = """diff --git a/a.py b/a.py
index 1111111..2222222 100644
--- a/a.py
+++ b/a.py
@@ -1,3 +1,4 @@
 one
-two
+TWO
+two-and-a-half
 three
"""


def test_parses_one_file_with_one_hunk():
    files = parse_unified_diff(SIMPLE)

    assert len(files) == 1
    assert files[0].path == "a.py"
    assert files[0].old_path == "a.py"
    assert len(files[0].hunks) == 1


def test_parses_hunk_header_ranges():
    hunk = parse_unified_diff(SIMPLE)[0].hunks[0]

    assert (hunk.old_start, hunk.old_count) == (1, 3)
    assert (hunk.new_start, hunk.new_count) == (1, 4)


def test_classifies_hunk_lines():
    hunk = parse_unified_diff(SIMPLE)[0].hunks[0]
    kinds = [line.kind for line in hunk.lines]

    assert kinds == [" ", "-", "+", "+", " "]
    assert [line.content for line in hunk.lines if line.kind == "+"] == ["TWO", "two-and-a-half"]
    assert [line.content for line in hunk.lines if line.kind == "-"] == ["two"]


def test_counts_insertions_and_deletions_per_file():
    file_diff = parse_unified_diff(SIMPLE)[0]

    assert file_diff.insertions == 2
    assert file_diff.deletions == 1


def test_omitted_count_in_hunk_header_defaults_to_one():
    text = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -5 +5 @@
-old
+new
"""
    hunk = parse_unified_diff(text)[0].hunks[0]

    assert (hunk.old_start, hunk.old_count) == (5, 1)
    assert (hunk.new_start, hunk.new_count) == (5, 1)


def test_parses_multiple_hunks():
    text = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,2 +1,2 @@
-a
+A
 b
@@ -10,2 +10,2 @@
-y
+Y
 z
"""
    hunks = parse_unified_diff(text)[0].hunks

    assert len(hunks) == 2
    assert hunks[1].old_start == 10


def test_parses_multiple_files():
    text = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-a
+A
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -1 +1 @@
-b
+B
"""
    files = parse_unified_diff(text)

    assert [f.path for f in files] == ["a.py", "b.py"]


def test_detects_a_new_file():
    text = """diff --git a/new.py b/new.py
new file mode 100644
--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+one
+two
"""
    file_diff = parse_unified_diff(text)[0]

    assert file_diff.path == "new.py"
    assert file_diff.old_path is None
    assert file_diff.is_new is True
    assert file_diff.insertions == 2


def test_detects_a_deleted_file():
    text = """diff --git a/gone.py b/gone.py
deleted file mode 100644
--- a/gone.py
+++ /dev/null
@@ -1,2 +0,0 @@
-one
-two
"""
    file_diff = parse_unified_diff(text)[0]

    assert file_diff.old_path == "gone.py"
    assert file_diff.path == "gone.py"
    assert file_diff.is_deleted is True
    assert file_diff.deletions == 2


def test_binary_file_yields_no_hunks_but_is_flagged():
    text = """diff --git a/logo.png b/logo.png
index 1111111..2222222 100644
Binary files a/logo.png and b/logo.png differ
"""
    file_diff = parse_unified_diff(text)[0]

    assert file_diff.path == "logo.png"
    assert file_diff.is_binary is True
    assert file_diff.hunks == ()


def test_no_newline_marker_is_ignored():
    text = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-old
\\ No newline at end of file
+new
"""
    hunk = parse_unified_diff(text)[0].hunks[0]

    assert [line.kind for line in hunk.lines] == ["-", "+"]


def test_paths_with_spaces_are_parsed():
    text = """diff --git a/my dir/a b.py b/my dir/a b.py
--- a/my dir/a b.py
+++ b/my dir/a b.py
@@ -1 +1 @@
-x
+y
"""
    assert parse_unified_diff(text)[0].path == "my dir/a b.py"


def test_empty_input_yields_nothing():
    assert parse_unified_diff("") == []


def test_parses_a_real_git_diff(tmp_path):
    builder = RepoBuilder(tmp_path / "r")
    builder.write("a.py", "one\ntwo\nthree\n").commit("add")
    builder.advance(hours=1).write("a.py", "one\nTWO\nthree\nfour\n").commit("edit")

    repo = GitRepo(builder.path)
    text = repo.run("diff-tree", "-p", "--no-commit-id", "HEAD")
    files = parse_unified_diff(text)

    assert len(files) == 1
    assert files[0].path == "a.py"
    assert files[0].insertions == 2
    assert files[0].deletions == 1
