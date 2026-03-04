from git_pulse.collector.hotspot_detector import HotspotDetector
from git_pulse.collector.models import Hotspot


def make_commit(hash, message, files, timestamp="2026-04-01T10:00:00+00:00", is_agent=False, source=None):
    return {
        "hash": hash,
        "author": "dev",
        "timestamp": timestamp,
        "message": message,
        "files": files,
        "is_agent_attributed": is_agent,
        "attribution_source": source,
    }


def make_file(path, diff, insertions=1, deletions=1):
    return {"path": path, "insertions": insertions, "deletions": deletions, "diff": diff}


def test_no_hotspots_single_commit():
    commits = [
        make_commit("aaa", "init", [make_file("app.py", "@@ -0,0 +1,5 @@\n+line1\n+line2")])
    ]
    detector = HotspotDetector(commits)
    hotspots = detector.detect()
    assert len(hotspots) == 0  # need >= 2 modifications to be a hotspot


def test_detects_hotspot_same_region():
    commits = [
        make_commit(
            "aaa", "first change",
            [make_file("app.py", "@@ -1,3 +1,3 @@\n-old\n+new1", 1, 1)],
            timestamp="2026-04-01T10:00:00+00:00",
        ),
        make_commit(
            "bbb", "second change",
            [make_file("app.py", "@@ -1,3 +1,3 @@\n-new1\n+new2", 1, 1)],
            timestamp="2026-04-01T10:30:00+00:00",
        ),
        make_commit(
            "ccc", "third change",
            [make_file("app.py", "@@ -2,3 +2,3 @@\n-new2\n+new3", 1, 1)],
            timestamp="2026-04-01T11:00:00+00:00",
        ),
    ]
    detector = HotspotDetector(commits)
    hotspots = detector.detect()
    assert len(hotspots) == 1
    assert hotspots[0].file_path == "app.py"
    assert hotspots[0].modification_count >= 3


def test_separate_files_separate_hotspots():
    commits = [
        make_commit("a", "c1", [
            make_file("a.py", "@@ -1,1 +1,1 @@\n-x\n+y"),
            make_file("b.py", "@@ -1,1 +1,1 @@\n-x\n+y"),
        ], timestamp="2026-04-01T10:00:00+00:00"),
        make_commit("b", "c2", [
            make_file("a.py", "@@ -1,1 +1,1 @@\n-y\n+z"),
            make_file("b.py", "@@ -1,1 +1,1 @@\n-y\n+z"),
        ], timestamp="2026-04-01T10:30:00+00:00"),
    ]
    detector = HotspotDetector(commits)
    hotspots = detector.detect()
    assert len(hotspots) == 2


def test_hotspots_sorted_by_score():
    commits = [
        make_commit("a", "c1", [make_file("hot.py", "@@ -1,1 +1,1 @@\n-a\n+b")], "2026-04-01T10:00:00+00:00"),
        make_commit("b", "c2", [make_file("hot.py", "@@ -1,1 +1,1 @@\n-b\n+c")], "2026-04-01T10:10:00+00:00"),
        make_commit("c", "c3", [make_file("hot.py", "@@ -1,1 +1,1 @@\n-c\n+d")], "2026-04-01T10:20:00+00:00"),
        make_commit("d", "c4", [make_file("cold.py", "@@ -1,1 +1,1 @@\n-x\n+y")], "2026-04-01T10:00:00+00:00"),
        make_commit("e", "c5", [make_file("cold.py", "@@ -1,1 +1,1 @@\n-y\n+z")], "2026-04-01T14:00:00+00:00"),
    ]
    detector = HotspotDetector(commits)
    hotspots = detector.detect()
    assert len(hotspots) == 2
    assert hotspots[0].file_path == "hot.py"  # higher score (more mods, tighter time)


def test_agent_classification():
    commits = [
        make_commit("a", "agent wrote", [make_file("f.py", "@@ -1,1 +1,1 @@\n-a\n+b")],
                    "2026-04-01T10:00:00+00:00", is_agent=True, source="Co-Authored-By: Claude"),
        make_commit("b", "human fix", [make_file("f.py", "@@ -1,1 +1,1 @@\n-b\n+c")],
                    "2026-04-01T10:30:00+00:00", is_agent=False),
    ]
    detector = HotspotDetector(commits)
    hotspots = detector.detect()
    assert len(hotspots) == 1
    assert hotspots[0].classification == "human-fixing-agent"
