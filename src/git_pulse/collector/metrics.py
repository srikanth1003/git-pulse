from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from git_pulse.collector.models import (
    AgentHumanRatio,
    ChangeVelocity,
    FileChurnEntry,
    WorkSession,
)

SESSION_GAP_MINUTES = 30


class MetricsCalculator:
    def __init__(self, commits: list[dict]):
        self.commits = commits

    def file_churn(self) -> list[FileChurnEntry]:
        """Rank files by modification count."""
        files: dict[str, dict] = defaultdict(
            lambda: {"count": 0, "ins": 0, "del": 0, "authors": set()}
        )
        for commit in self.commits:
            for f in commit["files"]:
                entry = files[f["path"]]
                entry["count"] += 1
                entry["ins"] += f["insertions"]
                entry["del"] += f["deletions"]
                entry["authors"].add(commit["author"])

        result = [
            FileChurnEntry(
                file_path=path,
                modification_count=data["count"],
                insertions=data["ins"],
                deletions=data["del"],
                distinct_authors=len(data["authors"]),
            )
            for path, data in files.items()
        ]
        result.sort(key=lambda e: e.modification_count, reverse=True)
        return result

    def change_velocity(self) -> ChangeVelocity:
        """Calculate commit velocity stats."""
        if not self.commits:
            return ChangeVelocity(
                commits_per_day=0, avg_files_per_commit=0, peak_day="", peak_commits=0
            )

        timestamps = [datetime.fromisoformat(c["timestamp"]) for c in self.commits]
        day_counts: Counter[str] = Counter()
        for ts in timestamps:
            day_counts[ts.strftime("%Y-%m-%d")] += 1

        time_span = (max(timestamps) - min(timestamps)).total_seconds() / 86400
        time_span = max(time_span, 1)

        total_files = sum(len(c["files"]) for c in self.commits)
        peak_day = day_counts.most_common(1)[0][0]
        peak_commits = day_counts.most_common(1)[0][1]

        return ChangeVelocity(
            commits_per_day=round(len(self.commits) / time_span, 2),
            avg_files_per_commit=round(total_files / len(self.commits), 2),
            peak_day=peak_day,
            peak_commits=peak_commits,
        )

    def agent_human_ratio(self) -> AgentHumanRatio | None:
        """Calculate agent vs human commit ratio. Returns None if no agent commits."""
        agent = sum(1 for c in self.commits if c["is_agent_attributed"])
        if agent == 0:
            return None
        human = len(self.commits) - agent
        return AgentHumanRatio(
            agent_commits=agent,
            human_commits=human,
            ratio=round(agent / len(self.commits), 4),
        )

    def rework_rate(self) -> float:
        """Calculate what fraction of changed lines were modified more than once."""
        file_line_counts: dict[str, int] = Counter()
        file_commit_count: Counter[str] = Counter()

        for commit in self.commits:
            for f in commit["files"]:
                file_line_counts[f["path"]] += f["insertions"] + f["deletions"]
                file_commit_count[f["path"]] += 1

        total_lines = sum(file_line_counts.values())
        if total_lines == 0:
            return 0.0

        reworked_lines = sum(
            file_line_counts[path]
            for path, count in file_commit_count.items()
            if count > 1
        )
        return round(reworked_lines / total_lines, 4)

    def sessions(self) -> list[WorkSession]:
        """Group commits into work sessions separated by time gaps."""
        if not self.commits:
            return []

        sorted_commits = sorted(
            self.commits, key=lambda c: datetime.fromisoformat(c["timestamp"])
        )

        gap = timedelta(minutes=SESSION_GAP_MINUTES)
        sessions: list[list[dict]] = [[sorted_commits[0]]]

        for commit in sorted_commits[1:]:
            prev_ts = datetime.fromisoformat(sessions[-1][-1]["timestamp"])
            curr_ts = datetime.fromisoformat(commit["timestamp"])
            if curr_ts - prev_ts > gap:
                sessions.append([commit])
            else:
                sessions[-1].append(commit)

        result = []
        for session_commits in sessions:
            timestamps = [datetime.fromisoformat(c["timestamp"]) for c in session_commits]
            authors = Counter(c["author"] for c in session_commits)
            files = set()
            for c in session_commits:
                for f in c["files"]:
                    files.add(f["path"])

            result.append(
                WorkSession(
                    start=min(timestamps),
                    end=max(timestamps),
                    commit_count=len(session_commits),
                    files_touched=len(files),
                    dominant_author=authors.most_common(1)[0][0],
                )
            )

        return result
