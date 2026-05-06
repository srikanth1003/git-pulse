from __future__ import annotations

import re

from git_pulse.attribution.providers import (
    PROVIDERS,
    find_provider_by_bracket_tag,
    find_provider_by_email,
    find_provider_by_name,
)
from git_pulse.models.history import Attribution, AttributionSignal, AuthorClass

# Weight per signal kind. The final score is the maximum matching weight, not a
# sum — that keeps the score explainable and bounded at 1.0.
SIGNAL_WEIGHTS: dict[str, float] = {
    "coauthor_trailer": 0.95,
    "bot_identity": 0.90,
    "generated_by_trailer": 0.90,
    "aider_prefix": 0.90,
    "generated_with_marker": 0.90,
    "git_note": 0.90,
    "bracket_tag": 0.85,
    "cadence": 0.20,
}

DEFAULT_AGENT_THRESHOLD = 0.70
DEFAULT_HUMAN_THRESHOLD = 0.30

_COAUTHOR_RE = re.compile(r"^\s*co-authored-by:\s*(?P<identity>.+)$", re.IGNORECASE | re.MULTILINE)
_GENERATED_BY_RE = re.compile(
    r"^\s*(?:generated-by|assisted-by|created-by):\s*(?P<identity>.+)$",
    re.IGNORECASE | re.MULTILINE,
)
_AIDER_PREFIX_RE = re.compile(r"^\s*aider:\s", re.IGNORECASE)
_BRACKET_TAG_RE = re.compile(r"\[(?P<tag>[a-z0-9][a-z0-9 _.-]{1,30})\]", re.IGNORECASE)
_EMAIL_IN_IDENTITY_RE = re.compile(r"<(?P<email>[^>]+)>")


class AttributionEngine:
    """Classifies a commit's authorship with a confidence score and evidence."""

    def __init__(
        self,
        agent_threshold: float = DEFAULT_AGENT_THRESHOLD,
        human_threshold: float = DEFAULT_HUMAN_THRESHOLD,
        enable_cadence_heuristic: bool = False,
    ) -> None:
        self.agent_threshold = agent_threshold
        self.human_threshold = human_threshold
        self.cadence_enabled = enable_cadence_heuristic

    def attribute(
        self,
        *,
        message: str,
        author_name: str,
        author_email: str,
        committer_name: str,
        committer_email: str,
        notes: str = "",
    ) -> Attribution:
        signals: list[AttributionSignal] = []

        signals.extend(self._coauthor_signals(message))
        signals.extend(self._generated_by_signals(message))
        signals.extend(
            self._identity_signals(author_name, author_email, committer_name, committer_email)
        )
        signals.extend(self._message_marker_signals(message))
        signals.extend(self._aider_signals(message))
        signals.extend(self._bracket_tag_signals(message))
        signals.extend(self._note_signals(notes))

        if not signals:
            return Attribution(
                author_class=AuthorClass.HUMAN, confidence=0.0, provider=None, signals=()
            )

        best = max(signals, key=lambda s: s.weight)
        provider = next((s.provider for s in signals if s.provider), None)

        return Attribution(
            author_class=self._classify(best.weight),
            confidence=best.weight,
            provider=provider,
            signals=tuple(signals),
        )

    def _classify(self, score: float) -> AuthorClass:
        if score >= self.agent_threshold:
            return AuthorClass.AGENT
        if score < self.human_threshold:
            return AuthorClass.HUMAN
        return AuthorClass.MIXED

    @staticmethod
    def _signal(name: str, provider: str | None, evidence: str) -> AttributionSignal:
        return AttributionSignal(
            name=name, weight=SIGNAL_WEIGHTS[name], provider=provider, evidence=evidence.strip()
        )

    def _coauthor_signals(self, message: str) -> list[AttributionSignal]:
        found = []
        for match in _COAUTHOR_RE.finditer(message):
            identity = match.group("identity").strip()
            provider = find_provider_by_name(identity)
            if provider is None:
                email_match = _EMAIL_IN_IDENTITY_RE.search(identity)
                if email_match:
                    provider = find_provider_by_email(email_match.group("email"))
            if provider:
                found.append(self._signal("coauthor_trailer", provider, match.group(0)))
        return found

    def _generated_by_signals(self, message: str) -> list[AttributionSignal]:
        found = []
        for match in _GENERATED_BY_RE.finditer(message):
            provider = find_provider_by_name(match.group("identity"))
            if provider:
                found.append(self._signal("generated_by_trailer", provider, match.group(0)))
        return found

    def _identity_signals(
        self, author_name: str, author_email: str, committer_name: str, committer_email: str
    ) -> list[AttributionSignal]:
        found = []
        for label, email in (("author", author_email), ("committer", committer_email)):
            provider = find_provider_by_email(email)
            if provider:
                found.append(self._signal("bot_identity", provider, f"{label} email {email}"))
        return found

    def _message_marker_signals(self, message: str) -> list[AttributionSignal]:
        found = []
        for provider in PROVIDERS:
            for marker in provider.message_markers:
                if marker.casefold() in message.casefold():
                    found.append(self._signal("generated_with_marker", provider.provider, marker))
                    break
        return found

    def _aider_signals(self, message: str) -> list[AttributionSignal]:
        if _AIDER_PREFIX_RE.match(message):
            return [self._signal("aider_prefix", "aider", message.split("\n", 1)[0])]
        return []

    def _bracket_tag_signals(self, message: str) -> list[AttributionSignal]:
        found = []
        subject = message.split("\n", 1)[0]
        for match in _BRACKET_TAG_RE.finditer(subject):
            provider = find_provider_by_bracket_tag(match.group("tag"))
            if provider:
                found.append(self._signal("bracket_tag", provider, match.group(0)))
        return found

    def _note_signals(self, notes: str) -> list[AttributionSignal]:
        if not notes.strip():
            return []
        provider = find_provider_by_name(notes)
        if provider:
            return [self._signal("git_note", provider, notes.strip()[:120])]
        return []
