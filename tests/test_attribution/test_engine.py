from __future__ import annotations

from git_pulse.attribution.engine import AttributionEngine
from git_pulse.models.history import AuthorClass


def attribute(message: str = "chore: something", **kwargs):
    engine = AttributionEngine()
    defaults = dict(
        message=message,
        author_name="Ada",
        author_email="ada@example.com",
        committer_name="Ada",
        committer_email="ada@example.com",
        notes="",
    )
    defaults.update(kwargs)
    return engine.attribute(**defaults)


def test_plain_human_commit_is_human_with_zero_confidence():
    result = attribute("fix: correct off-by-one")

    assert result.author_class is AuthorClass.HUMAN
    assert result.confidence == 0.0
    assert result.provider is None
    assert result.signals == ()


def test_coauthor_trailer_scores_highest_and_names_provider():
    result = attribute("feat: thing\n\nCo-Authored-By: Claude <noreply@anthropic.com>")

    assert result.author_class is AuthorClass.AGENT
    assert result.confidence == 0.95
    assert result.provider == "Claude Code"
    assert any(s.name == "coauthor_trailer" for s in result.signals)


def test_coauthor_trailer_for_a_human_is_not_an_agent_signal():
    result = attribute("feat: pairing\n\nCo-Authored-By: Grace <grace@example.com>")

    assert result.author_class is AuthorClass.HUMAN
    assert result.confidence == 0.0


def test_bot_identity_in_author_email_is_detected():
    result = attribute("Automated fix", author_email="copilot@github.com")

    assert result.author_class is AuthorClass.AGENT
    assert result.confidence == 0.90
    assert result.provider == "GitHub Copilot"
    assert any(s.name == "bot_identity" for s in result.signals)


def test_bot_identity_in_committer_email_is_detected():
    result = attribute("Automated fix", committer_email="devin@cognition.ai")

    assert result.provider == "Devin"
    assert any(s.name == "bot_identity" for s in result.signals)


def test_aider_message_prefix_is_detected():
    result = attribute("aider: refactor the parser")

    assert result.author_class is AuthorClass.AGENT
    assert result.confidence == 0.90
    assert result.provider == "aider"


def test_generated_with_marker_is_detected():
    result = attribute("feat: thing\n\n🤖 Generated with [Claude Code](https://claude.com)")

    assert result.author_class is AuthorClass.AGENT
    assert result.provider == "Claude Code"


def test_generated_by_trailer_is_detected():
    result = attribute("feat: thing\n\nGenerated-By: Cursor")

    assert result.confidence == 0.90
    assert result.provider == "Cursor"


def test_bracket_tag_scores_below_trailers():
    result = attribute("[copilot] update deps")

    assert result.author_class is AuthorClass.AGENT
    assert result.confidence == 0.85
    assert result.provider == "GitHub Copilot"


def test_git_note_on_agent_ref_is_detected():
    result = attribute("feat: thing", notes="agent: claude-code session 12")

    assert result.confidence == 0.90
    assert result.provider == "Claude Code"


def test_score_is_the_maximum_signal_not_a_sum():
    # Bracket tag (0.85) plus co-author trailer (0.95) must yield 0.95, never more.
    result = attribute("[claude] thing\n\nCo-Authored-By: Claude <noreply@anthropic.com>")

    assert result.confidence == 0.95
    assert len(result.signals) >= 2


def test_all_matched_signals_are_retained_as_evidence():
    result = attribute("[claude] thing\n\nCo-Authored-By: Claude <noreply@anthropic.com>")

    names = {s.name for s in result.signals}
    assert {"bracket_tag", "coauthor_trailer"} <= names
    for signal in result.signals:
        assert signal.evidence.strip()


def test_thresholds_are_configurable_to_produce_mixed():
    engine = AttributionEngine(agent_threshold=0.90, human_threshold=0.30)
    result = engine.attribute(
        message="[copilot] update deps",  # bracket tag scores 0.85
        author_name="Ada",
        author_email="ada@example.com",
        committer_name="Ada",
        committer_email="ada@example.com",
        notes="",
    )

    assert result.author_class is AuthorClass.MIXED
    assert result.confidence == 0.85


def test_cadence_heuristic_is_off_by_default_and_opt_in():
    off = AttributionEngine()
    assert off.cadence_enabled is False

    on = AttributionEngine(enable_cadence_heuristic=True)
    assert on.cadence_enabled is True


def test_trailer_matching_ignores_case_of_the_key():
    result = attribute("feat: thing\n\nco-authored-by: Claude <noreply@anthropic.com>")

    assert result.author_class is AuthorClass.AGENT
