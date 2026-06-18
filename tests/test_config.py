from pathlib import Path

import pytest

from git_pulse.config import DEFAULT_CONFIG, ConfigError, load_config


@pytest.fixture(autouse=True)
def isolate_home(tmp_path, monkeypatch):
    """Keep the developer's real ~/.config/gitpulse out of these tests."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)


def test_default_config():
    config = load_config()
    assert config.model == DEFAULT_CONFIG["llm"]["model"]
    assert config.default_days == 30
    assert config.max_hotspots == 20


def test_load_from_file(tmp_path):
    config_file = tmp_path / ".gitpulse.toml"
    config_file.write_text("""
[llm]
model = "openai/gpt-4o"

[analysis]
default_days = 14
max_hotspots = 10
exclude = ["*.lock"]
""")
    config = load_config(config_path=str(config_file))
    assert config.model == "openai/gpt-4o"
    assert config.default_days == 14
    assert config.max_hotspots == 10
    assert config.exclude == ["*.lock"]


def test_config_file_not_found_uses_defaults():
    config = load_config(config_path="/nonexistent/.gitpulse.toml")
    assert config.model == DEFAULT_CONFIG["llm"]["model"]


def test_new_sections_have_documented_defaults():
    config = load_config()

    assert config.llm.enabled is False
    assert config.analysis.ignore_whitespace is False
    assert config.analysis.include_merges is False
    assert config.analysis.bulk_commit_threshold == 100
    assert config.analysis.max_file_lines == 50000
    assert config.attribution.agent_threshold == 0.70
    assert config.attribution.human_threshold == 0.30
    assert config.attribution.enable_cadence_heuristic is False
    assert config.survival.window_days == 7
    assert config.coupling.min_shared_commits == 5
    assert config.sessions.gap_minutes == 90
    assert config.reverts.storm_commits == 4
    assert config.reverts.storm_hours == 3


def test_ci_thresholds_default_to_disabled():
    config = load_config()

    assert config.ci.fail_on_agent_only_exposure is None
    assert config.ci.fail_on_bus_factor_below is None
    assert config.ci.fail_on_rework_rate_above is None


def test_every_section_can_be_overridden(tmp_path):
    config_file = tmp_path / ".gitpulse.toml"
    config_file.write_text("""
[llm]
enabled = true
model = "openai/gpt-4o"

[analysis]
default_days = 14
ignore_whitespace = true
include_merges = true
bulk_commit_threshold = 50
max_file_lines = 1000

[attribution]
agent_threshold = 0.9
human_threshold = 0.1
enable_cadence_heuristic = true

[survival]
window_days = 14

[coupling]
min_shared_commits = 3

[sessions]
gap_minutes = 45

[reverts]
storm_commits = 6
storm_hours = 1

[ci]
fail_on_agent_only_exposure = 0.5
fail_on_bus_factor_below = 2
fail_on_rework_rate_above = 0.4
""")
    config = load_config(config_path=str(config_file))

    assert config.llm.enabled is True
    assert config.llm.model == "openai/gpt-4o"
    assert config.analysis.ignore_whitespace is True
    assert config.analysis.include_merges is True
    assert config.analysis.bulk_commit_threshold == 50
    assert config.analysis.max_file_lines == 1000
    assert config.attribution.agent_threshold == 0.9
    assert config.attribution.human_threshold == 0.1
    assert config.attribution.enable_cadence_heuristic is True
    assert config.survival.window_days == 14
    assert config.coupling.min_shared_commits == 3
    assert config.sessions.gap_minutes == 45
    assert config.reverts.storm_commits == 6
    assert config.reverts.storm_hours == 1
    assert config.ci.fail_on_agent_only_exposure == 0.5
    assert config.ci.fail_on_bus_factor_below == 2
    assert config.ci.fail_on_rework_rate_above == 0.4


def test_flat_accessors_still_delegate_to_sections(tmp_path):
    config_file = tmp_path / ".gitpulse.toml"
    config_file.write_text("""
[llm]
model = "anthropic/claude-3-5-haiku-latest"

[analysis]
default_days = 7
max_hotspots = 5
exclude = ["vendor/**"]
""")
    config = load_config(config_path=str(config_file))

    assert config.model == config.llm.model == "anthropic/claude-3-5-haiku-latest"
    assert config.default_days == config.analysis.default_days == 7
    assert config.max_hotspots == config.analysis.max_hotspots == 5
    assert config.exclude == config.analysis.exclude == ["vendor/**"]


def test_unknown_keys_and_sections_are_ignored(tmp_path):
    config_file = tmp_path / ".gitpulse.toml"
    config_file.write_text("""
[llm]
model = "openai/gpt-4o"
nonsense = 1

[not_a_real_section]
whatever = true
""")
    config = load_config(config_path=str(config_file))

    assert config.model == "openai/gpt-4o"


def test_malformed_toml_raises_a_clear_error(tmp_path):
    config_file = tmp_path / ".gitpulse.toml"
    config_file.write_text("this is not = = valid toml [[[")

    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(config_path=str(config_file))
