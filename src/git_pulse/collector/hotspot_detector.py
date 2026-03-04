from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone

from git_pulse.collector.models import Hotspot


# Max lines apart to be considered same region
LINE_PROXIMITY = 5
# Max hours apart to be considered same work session for hotspot grouping
TIME_WINDOW_HOURS = 6


class HotspotDetector:
    def __init__(self, commits: list[dict], max_hotspots: int = 20):
        self.commits = commits
        self.max_hotspots = max_hotspots

    def detect(self) -> list[Hotspot]:
        """Detect hotspots from commit data. Returns ranked list."""
        file_mods = self._group_modifications()
        hotspots = []
        for file_path, mods in file_mods.items():
            clusters = self._cluster_modifications(mods)
            for cluster in clusters:
                if len(cluster) < 2:
                    continue
                hotspot = self._build_hotspot(file_path, cluster)
                hotspots.append(hotspot)

        hotspots.sort(key=lambda h: h.score, reverse=True)
        return hotspots[: self.max_hotspots]

    def _group_modifications(self) -> dict[str, list[dict]]:
        """Group modifications by file path."""
        file_mods: dict[str, list[dict]] = defaultdict(list)
        for commit in self.commits:
            ts = self._parse_timestamp(commit["timestamp"])
            for f in commit["files"]:
                line_start = self._parse_line_start(f["diff"])
                file_mods[f["path"]].append(
                    {
                        "commit_hash": commit["hash"],
                        "timestamp": ts,
                        "line_start": line_start,
                        "lines": f["insertions"] + f["deletions"],
                        "diff_snippet": f["diff"][:500],
                        "is_agent": commit["is_agent_attributed"],
                        "attribution_source": commit.get("attribution_source"),
                    }
                )
        return file_mods

    def _cluster_modifications(self, mods: list[dict]) -> list[list[dict]]:
        """Cluster modifications by spatiotemporal proximity."""
        if not mods:
            return []
        mods.sort(key=lambda m: m["timestamp"])
        clusters: list[list[dict]] = [[mods[0]]]
        for mod in mods[1:]:
            merged = False
            for cluster in clusters:
                if self._is_nearby(mod, cluster):
                    cluster.append(mod)
                    merged = True
                    break
            if not merged:
                clusters.append([mod])
        return clusters

    def _is_nearby(self, mod: dict, cluster: list[dict]) -> bool:
        """Check if mod is spatiotemporally close to any mod in the cluster."""
        for existing in cluster:
            time_diff = abs((mod["timestamp"] - existing["timestamp"]).total_seconds()) / 3600
            line_diff = abs(mod["line_start"] - existing["line_start"])
            if time_diff <= TIME_WINDOW_HOURS and line_diff <= LINE_PROXIMITY:
                return True
        return False

    def _build_hotspot(self, file_path: str, cluster: list[dict]) -> Hotspot:
        """Build a Hotspot from a cluster of modifications."""
        timestamps = [m["timestamp"] for m in cluster]
        time_span = (max(timestamps) - min(timestamps)).total_seconds() / 3600
        time_span = max(time_span, 0.01)

        line_starts = [m["line_start"] for m in cluster]
        lines_affected = sum(m["lines"] for m in cluster)
        mod_count = len(cluster)

        score = (mod_count * 3) + (lines_affected * 0.5) + (1 / time_span * 10)
        classification = self._classify(cluster)

        return Hotspot(
            file_path=file_path,
            line_start=min(line_starts),
            line_end=max(line_starts) + LINE_PROXIMITY,
            modification_count=mod_count,
            time_span_hours=round(time_span, 2),
            classification=classification,
            commit_hashes=[m["commit_hash"] for m in cluster],
            diff_snippets=[m["diff_snippet"] for m in cluster],
            score=round(score, 2),
        )

    def _classify(self, cluster: list[dict]) -> str:
        """Classify the hotspot based on agent/human attribution patterns."""
        agent_flags = [m["is_agent"] for m in cluster]
        if not any(agent_flags):
            if all(not f for f in agent_flags):
                return "human-iteration"
            return "unknown"

        transitions = []
        for i in range(len(agent_flags) - 1):
            if agent_flags[i] and not agent_flags[i + 1]:
                transitions.append("agent-to-human")
            elif not agent_flags[i] and agent_flags[i + 1]:
                transitions.append("human-to-agent")
            elif agent_flags[i] and agent_flags[i + 1]:
                transitions.append("agent-to-agent")

        if not transitions:
            return "unknown"

        if transitions.count("agent-to-human") > len(transitions) / 2:
            return "human-fixing-agent"
        if transitions.count("agent-to-agent") > len(transitions) / 2:
            return "repeated-agent"
        if transitions.count("human-to-agent") > len(transitions) / 2:
            return "agent-reworked"
        return "unknown"

    @staticmethod
    def _parse_line_start(diff: str) -> int:
        match = re.search(r"@@ -(\d+)", diff)
        return int(match.group(1)) if match else 1

    @staticmethod
    def _parse_timestamp(ts: str) -> datetime:
        return datetime.fromisoformat(ts)
