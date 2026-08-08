"""Prompt construction for the optional narrative layer.

The payload is the same JSON a user gets from ``--json``, minus fields that cost
many tokens and add no interpretive value (per-day series, raw SHAs) and minus
any narrative from an earlier run, which would let the model launder its own
prior output back in as evidence.
"""

from __future__ import annotations

import copy
import json
from typing import Any

MAX_PAYLOAD_CHARS = 24_000

_DROP_TOP_LEVEL = ("narrative",)
_DROP_NESTED = {
    "velocity": ("per_day",),
    "hotspots": ("commit_shas",),
    "sessions": ("sessions",),
}

_SYSTEM_PROMPT = """\
You are a software engineering analyst. You receive deterministic metrics about \
a git repository's recent history, including which commits were authored by AI \
coding agents and which by humans.

Interpret the metrics. Reason from only the data provided — never invent a \
number, file name, author, or date that does not appear in the input. If the \
data is insufficient to support a claim, say so instead of speculating.

Respond with ONLY a JSON object, no markdown fences and no prose, matching:

{
  "summary": "2-4 sentences on what happened in this history",
  "insights": [
    {
      "title": "short specific finding",
      "category": "rework | velocity | risk | ownership | quality | process",
      "severity": "info | low | medium | high",
      "evidence": ["metric or path from the input that supports this"],
      "recommendation": "one concrete next step"
    }
  ],
  "actions": ["up to 3 prioritised next steps"]
}

Prefer three well-evidenced insights over eight weak ones. An empty insights \
list is a valid answer for a quiet history.
"""


def build_system_prompt() -> str:
    return _SYSTEM_PROMPT


def build_user_prompt(payload: dict[str, Any]) -> str:
    trimmed = _trim(payload)
    body = json.dumps(trimmed, indent=2, sort_keys=True, default=str)
    truncated = False
    if len(body) > MAX_PAYLOAD_CHARS:
        body = body[:MAX_PAYLOAD_CHARS]
        truncated = True

    prompt = f"Repository metrics:\n{body}\n"
    if truncated:
        prompt += (
            "\n[payload truncated at the character limit — analyse only what is "
            "shown above and do not speculate about the omitted remainder]\n"
        )
    return prompt


def _trim(payload: dict[str, Any]) -> dict[str, Any]:
    """Copy first: the caller's report payload must come back unmodified."""
    data = copy.deepcopy(payload)
    for key in _DROP_TOP_LEVEL:
        data.pop(key, None)

    for section, keys in _DROP_NESTED.items():
        node = data.get(section)
        if not isinstance(node, dict):
            continue
        for key in keys:
            node.pop(key, None)
        for item in node.get("hotspots", []) or []:
            if isinstance(item, dict):
                for key in keys:
                    item.pop(key, None)
    return data
