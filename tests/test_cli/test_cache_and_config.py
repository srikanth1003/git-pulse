from __future__ import annotations

import pytest
from typer.testing import CliRunner

from git_pulse.cli import app
from tests.helpers.repo_builder import RepoBuilder

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)


@pytest.fixture
def repo(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("a.py", "x\n").commit("initial")
    return b


def test_cache_info_reports_an_empty_cache():
    result = runner.invoke(app, ["cache", "info"])

    assert result.exit_code == 0
    assert "entries  : 0" in result.output


def test_cache_info_reports_entries_after_an_analysis(repo):
    runner.invoke(app, ["analyze", str(repo.path)])

    result = runner.invoke(app, ["cache", "info"])

    assert result.exit_code == 0
    assert "entries  : 1" in result.output


def test_cache_clear_empties_the_cache(repo):
    runner.invoke(app, ["analyze", str(repo.path)])

    clear = runner.invoke(app, ["cache", "clear"])

    assert clear.exit_code == 0
    assert "Removed 1 cache entry" in clear.output
    assert "entries  : 0" in runner.invoke(app, ["cache", "info"]).output


def test_config_show_prints_effective_settings():
    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    assert "default_days" in result.output


def test_config_init_writes_a_commented_toml(tmp_path):
    target = tmp_path / "gitpulse.toml"

    result = runner.invoke(app, ["config", "init", "--output", str(target)])

    assert result.exit_code == 0
    body = target.read_text()
    assert "[llm]" in body
    assert "api_key" not in body  # never write a key placeholder into a file


def test_config_init_output_is_loadable_by_the_config_parser(tmp_path):
    from git_pulse.config import load_config

    target = tmp_path / "gitpulse.toml"
    runner.invoke(app, ["config", "init", "--output", str(target)])

    config = load_config(config_path=str(target))

    assert config.llm.enabled is False
    assert config.default_days == 30


def test_config_init_refuses_to_clobber_without_force(tmp_path):
    target = tmp_path / "gitpulse.toml"
    target.write_text("# mine\n")

    result = runner.invoke(app, ["config", "init", "--output", str(target)])

    assert result.exit_code == 1
    assert target.read_text() == "# mine\n"


def test_config_init_force_overwrites(tmp_path):
    target = tmp_path / "gitpulse.toml"
    target.write_text("# mine\n")

    result = runner.invoke(app, ["config", "init", "--output", str(target), "--force"])

    assert result.exit_code == 0
    assert "[llm]" in target.read_text()
