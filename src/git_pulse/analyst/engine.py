from __future__ import annotations

import json

from litellm import completion

from git_pulse.analyst.models import AnalystReport
from git_pulse.analyst.prompts import build_system_prompt, build_user_prompt


class AnalystEngine:
    def __init__(self, model: str):
        self.model = model

    def analyze(self, report_dict: dict) -> AnalystReport:
        """Send collector report to LLM and parse the response into an AnalystReport."""
        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(report_dict)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = completion(model=self.model, messages=messages)
        content = response.choices[0].message.content

        try:
            data = json.loads(content)
            return AnalystReport.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return self._retry(messages, content)

    def _retry(self, messages: list[dict], bad_content: str) -> AnalystReport:
        """Retry with a correction prompt after malformed JSON."""
        messages = messages + [
            {"role": "assistant", "content": bad_content},
            {
                "role": "user",
                "content": "Your response was not valid JSON. Please respond with ONLY valid JSON matching the schema from the system prompt. No markdown, no explanation.",
            },
        ]

        response = completion(model=self.model, messages=messages)
        content = response.choices[0].message.content

        try:
            data = json.loads(content)
            return AnalystReport.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return AnalystReport(
                summary="Failed to parse LLM response. Run with --verbose to see raw collector data.",
                insights=[],
                top_actions=[],
            )
