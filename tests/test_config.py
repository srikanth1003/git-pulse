from pathlib import Path

from git_pulse.config import load_config, GitPulseConfig, DEFAULT_CONFIG


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
