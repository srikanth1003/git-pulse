from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSignature:
    """Recognition data for one coding agent.

    Adding a provider means adding one entry here and nothing else.
    """

    provider: str
    name_tokens: tuple[str, ...]  # matched case-insensitively as substrings
    emails: tuple[str, ...]  # matched case-insensitively, exact
    bracket_tags: tuple[str, ...]  # e.g. "claude" matches "[claude]"
    message_markers: tuple[str, ...]  # literal substrings of the commit body


PROVIDERS: tuple[ProviderSignature, ...] = (
    ProviderSignature(
        provider="Claude Code",
        name_tokens=("claude",),
        emails=("noreply@anthropic.com",),
        bracket_tags=("claude", "claude-code"),
        message_markers=("🤖 Generated with [Claude Code]", "Generated with Claude Code"),
    ),
    ProviderSignature(
        provider="GitHub Copilot",
        name_tokens=("copilot",),
        emails=(
            "copilot@github.com",
            "198982749+copilot-swe-agent@users.noreply.github.com",
        ),
        bracket_tags=("copilot",),
        message_markers=("Co-authored-by: Copilot",),
    ),
    ProviderSignature(
        provider="Cursor",
        name_tokens=("cursor",),
        emails=("noreply@cursor.com", "agent@cursor.sh"),
        bracket_tags=("cursor",),
        message_markers=("Generated with Cursor",),
    ),
    ProviderSignature(
        provider="aider",
        name_tokens=("aider",),
        emails=("aider@aider.chat",),
        bracket_tags=("aider",),
        message_markers=(),
    ),
    ProviderSignature(
        provider="OpenAI Codex",
        name_tokens=("codex",),
        emails=("codex@openai.com",),
        bracket_tags=("codex",),
        message_markers=("Generated with Codex",),
    ),
    ProviderSignature(
        provider="Devin",
        name_tokens=("devin",),
        emails=("devin@cognition.ai", "devin-ai-integration@users.noreply.github.com"),
        bracket_tags=("devin",),
        message_markers=(),
    ),
    ProviderSignature(
        provider="Windsurf",
        name_tokens=("windsurf",),
        emails=("noreply@codeium.com",),
        bracket_tags=("windsurf", "codeium"),
        message_markers=(),
    ),
    ProviderSignature(
        provider="Sourcegraph Cody",
        name_tokens=("cody",),
        emails=("cody@sourcegraph.com",),
        bracket_tags=("cody",),
        message_markers=(),
    ),
    ProviderSignature(
        provider="Continue",
        name_tokens=("continue.dev", "continuedev"),
        emails=("noreply@continue.dev",),
        bracket_tags=("continue",),
        message_markers=(),
    ),
    ProviderSignature(
        provider="Sweep",
        name_tokens=("sweep",),
        emails=("sweep@sweep.dev", "sweep-ai@users.noreply.github.com"),
        bracket_tags=("sweep",),
        message_markers=(),
    ),
    ProviderSignature(
        provider="gpt-engineer",
        name_tokens=("gpt-engineer", "gpt engineer"),
        emails=(),
        bracket_tags=("gpt-engineer",),
        message_markers=(),
    ),
)


def find_provider_by_name(identity: str) -> str | None:
    """Match a name or full trailer identity against provider name tokens."""
    if not identity:
        return None
    haystack = identity.casefold()
    for provider in PROVIDERS:
        if any(token in haystack for token in provider.name_tokens):
            return provider.provider
    return None


def find_provider_by_email(email: str) -> str | None:
    """Match an author or committer email against known bot addresses."""
    if not email:
        return None
    needle = email.strip().casefold()
    for provider in PROVIDERS:
        if any(needle == known.casefold() for known in provider.emails):
            return provider.provider
    return None


def find_provider_by_bracket_tag(tag: str) -> str | None:
    """Match the inside of a bracket tag such as ``[claude]``."""
    if not tag:
        return None
    needle = tag.strip().casefold()
    for provider in PROVIDERS:
        if needle in provider.bracket_tags:
            return provider.provider
    return None
