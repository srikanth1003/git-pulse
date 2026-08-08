"""Optional LLM narrative layer.

Strictly opt-in: nothing here runs unless ``[llm] enabled`` is true (set by
``--llm`` or the config file). Every failure path returns ``None`` rather than a
placeholder narrative — a report that silently contains "failed to parse" text
where analysis should be is worse than a report with no narrative at all.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Callable
from typing import Any

from git_pulse.analyst.models import AnalystReport
from git_pulse.analyst.prompts import build_system_prompt, build_user_prompt
from git_pulse.config import LLMConfig

logger = logging.getLogger(__name__)

ENV_KEYS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "AZURE_API_KEY",
    "OPENROUTER_API_KEY",
)

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)

_RETRY_PROMPT = (
    "Your response was not valid JSON matching the schema. Respond with ONLY a "
    "JSON object. No markdown fences, no prose."
)


class LLMUnavailableError(RuntimeError):
    """Raised when the narrative was requested but cannot be produced."""


def _completion() -> Callable[..., Any]:
    """Import litellm lazily — it costs seconds and the default path never needs it."""
    from litellm import completion

    return completion


class AnalystEngine:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def resolve_api_key(self) -> str | None:
        if self.config.api_key:
            return self.config.api_key
        return next((os.environ[k] for k in ENV_KEYS if os.environ.get(k)), None)

    def check_available(self) -> None:
        """Raise ``LLMUnavailableError`` if a narrative cannot be attempted."""
        if not self.config.enabled:
            raise LLMUnavailableError(
                "LLM narrative is not enabled; pass --llm or set [llm] enabled = true"
            )
        if not self.resolve_api_key():
            raise LLMUnavailableError(
                "No API key found. Set ANTHROPIC_API_KEY (or another provider key) "
                "or [llm] api_key in your config."
            )

    def analyze(self, payload: dict[str, Any]) -> AnalystReport | None:
        """Produce a narrative, or ``None`` if the model could not deliver one."""
        self.check_available()

        messages = [
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": build_user_prompt(payload)},
        ]

        content = self._call(messages)
        if content is None:
            return None
        try:
            return AnalystReport.from_dict(_extract_json(content))
        except ValueError as exc:
            logger.debug("first LLM response unusable (%s); retrying once", exc)

        retry = messages + [
            {"role": "assistant", "content": content},
            {"role": "user", "content": _RETRY_PROMPT},
        ]
        content = self._call(retry)
        if content is None:
            return None
        try:
            return AnalystReport.from_dict(_extract_json(content))
        except ValueError as exc:
            logger.warning("LLM response unusable after retry (%s); skipping narrative", exc)
            return None

    def _call(self, messages: list[dict[str, str]]) -> str | None:
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "timeout": self.config.timeout_seconds,
        }
        if self.config.temperature is not None:
            kwargs["temperature"] = self.config.temperature
        if self.config.max_tokens:
            kwargs["max_tokens"] = self.config.max_tokens

        try:
            response = _completion()(**kwargs)
            return str(response.choices[0].message.content or "")
        except Exception as exc:  # provider errors, timeouts, auth, import failures
            logger.warning("LLM call failed: %s", exc)
            return None


def _extract_json(content: str) -> Any:
    """Parse JSON, tolerating the markdown fences models add despite instructions."""
    text = content.strip()
    match = _FENCE.match(text)
    if match:
        text = match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"response was not JSON: {exc}") from exc
