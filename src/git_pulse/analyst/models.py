from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SEVERITIES = ("info", "low", "medium", "high")


@dataclass(frozen=True)
class Insight:
    title: str
    category: str = "general"
    severity: str = "info"
    evidence: tuple[str, ...] = ()
    recommendation: str = ""


@dataclass(frozen=True)
class AnalystReport:
    summary: str
    insights: tuple[Insight, ...] = ()
    actions: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: Any) -> AnalystReport:
        """Parse a provider response.

        Raises ``ValueError`` on anything unusable so the caller can retry once
        and then degrade. Only ``summary`` is required; a model that omits an
        optional field gets a documented default rather than a KeyError.
        """
        if not isinstance(data, dict):
            raise ValueError("response was not a JSON object")
        summary = data.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("response had no usable 'summary'")

        insights: list[Insight] = []
        for raw in data.get("insights") or []:
            if not isinstance(raw, dict) or not raw.get("title"):
                continue
            severity = str(raw.get("severity", "info")).lower()
            insights.append(
                Insight(
                    title=str(raw["title"]),
                    category=str(raw.get("category", "general")),
                    severity=severity if severity in SEVERITIES else "info",
                    evidence=tuple(str(e) for e in raw.get("evidence") or []),
                    recommendation=str(raw.get("recommendation", "")),
                )
            )

        actions = tuple(str(a) for a in data.get("actions") or data.get("top_actions") or [])
        return cls(summary=summary.strip(), insights=tuple(insights), actions=actions)
