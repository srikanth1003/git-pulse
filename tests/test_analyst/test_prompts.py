from __future__ import annotations

import json

from git_pulse.analyst.prompts import (
    MAX_PAYLOAD_CHARS,
    build_system_prompt,
    build_user_prompt,
)


def test_system_prompt_specifies_the_json_schema():
    prompt = build_system_prompt()

    assert "summary" in prompt
    assert "insights" in prompt
    assert "actions" in prompt


def test_system_prompt_forbids_inventing_numbers():
    assert "only the data provided" in build_system_prompt().lower()


def test_user_prompt_embeds_the_payload():
    prompt = build_user_prompt({"repository": {"name": "myrepo"}})

    assert "myrepo" in prompt


def test_large_payloads_are_truncated_with_a_visible_marker():
    payload = {"churn": {"files": [{"path": f"file{i}.py"} for i in range(20000)]}}

    prompt = build_user_prompt(payload)

    assert len(prompt) < MAX_PAYLOAD_CHARS + 2000
    assert "truncated" in prompt


def test_narrative_field_is_not_fed_back_to_the_model():
    prompt = build_user_prompt({"narrative": {"summary": "earlier run"}, "scope": {}})

    assert "earlier run" not in prompt


def test_per_day_and_commit_shas_are_dropped_as_low_value_tokens():
    payload = {
        "velocity": {"commits_per_day": 1.5, "per_day": [{"date": "2025-01-01", "commits": 3}]},
        "hotspots": {"hotspots": [{"file_path": "a.py", "commit_shas": ["deadbeef"]}]},
    }

    prompt = build_user_prompt(payload)

    assert "deadbeef" not in prompt
    assert "2025-01-01" not in prompt
    assert "commits_per_day" in prompt


def test_payload_is_serialized_deterministically():
    payload = {"scope": {"total_commits": 3}}

    assert build_user_prompt(payload) == build_user_prompt(payload)
    assert json.loads(build_user_prompt(payload).split("\n", 1)[1].rsplit("\n", 1)[0] or "{}")


def test_trimming_does_not_mutate_the_caller_s_payload():
    payload = {"velocity": {"per_day": [{"date": "2025-01-01"}]}, "narrative": {"summary": "x"}}

    build_user_prompt(payload)

    assert payload["velocity"]["per_day"]
    assert "narrative" in payload
