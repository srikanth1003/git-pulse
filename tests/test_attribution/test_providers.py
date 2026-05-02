from __future__ import annotations

from git_pulse.attribution.providers import PROVIDERS, find_provider_by_email, find_provider_by_name


def test_every_provider_has_a_display_name():
    assert PROVIDERS
    for provider in PROVIDERS:
        assert provider.provider.strip()


def test_expected_providers_are_present():
    names = {p.provider for p in PROVIDERS}
    for expected in [
        "Claude Code",
        "GitHub Copilot",
        "Cursor",
        "aider",
        "OpenAI Codex",
        "Devin",
        "Windsurf",
        "Sourcegraph Cody",
        "Continue",
        "Sweep",
        "gpt-engineer",
    ]:
        assert expected in names


def test_lookup_by_coauthor_name_is_case_insensitive():
    assert find_provider_by_name("CLAUDE") == "Claude Code"
    assert find_provider_by_name("Claude") == "Claude Code"
    assert find_provider_by_name("copilot") == "GitHub Copilot"


def test_lookup_by_name_matches_substrings_of_full_identities():
    # Trailers look like "Claude <noreply@anthropic.com>" or "Copilot Autofix".
    assert find_provider_by_name("Copilot Autofix") == "GitHub Copilot"


def test_lookup_by_name_rejects_unrelated_humans():
    assert find_provider_by_name("Ada Lovelace") is None
    assert find_provider_by_name("") is None


def test_lookup_by_email():
    assert find_provider_by_email("noreply@anthropic.com") == "Claude Code"
    assert find_provider_by_email("NOREPLY@ANTHROPIC.COM") == "Claude Code"
    assert find_provider_by_email("ada@example.com") is None


def test_no_duplicate_provider_names():
    names = [p.provider for p in PROVIDERS]
    assert len(names) == len(set(names))
