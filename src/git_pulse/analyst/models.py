from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Insight:
    category: str
    title: str
    severity: str
    evidence: list[str]
    recommendation: str

@dataclass
class AnalystReport:
    summary: str
    insights: list[Insight]
    top_actions: list[str]

    @classmethod
    def from_dict(cls, data: dict) -> AnalystReport:
        insights = [
            Insight(
                category=i["category"],
                title=i["title"],
                severity=i["severity"],
                evidence=i["evidence"],
                recommendation=i["recommendation"],
            )
            for i in data.get("insights", [])
        ]
        return cls(
            summary=data["summary"],
            insights=insights,
            top_actions=data.get("top_actions", []),
        )
