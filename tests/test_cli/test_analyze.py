from __future__ import annotations

import json
import subprocess

import pytest
from typer.testing import CliRunner

from git_pulse.analyst.engine import ENV_KEYS
from git_pulse.cli import app
from tests.helpers.repo_builder import RepoBuilder

runner = CliRunner()

# RepoBuilder commits at a fixed 2025-01-01 epoch, which the default 30-day
# window excludes once wall-clock time moves past it. Every test that needs the
# fixture's commits in scope passes this instead of relying on the default.
WIDE = ["--since", "2024-12-01"]


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)


@pytest.fixture
def repo(tmp_path):
    b = RepoBuilder(tmp_path / "r")
    b.write("app.py", "".join(f"line{i}\n" for i in range(20))).commit("initial")
    b.advance(hours=2).write("app.py", "x\n" * 20).agent_commit("agent rewrite")
    return b


def test_help_lists_the_commands():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("analyze", "cache", "config", "version"):
        assert command in result.output


def test_version_prints_the_package_version():
    from git_pulse import __version__

    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_analyze_succeeds_without_any_api_key(repo, monkeypatch):
    for var in ENV_KEYS:
        monkeypatch.delenv(var, raising=False)

    result = runner.invoke(app, ["analyze", str(repo.path), *WIDE])

    assert result.exit_code == 0
    assert "app.py" in result.output


def test_analyze_json_output_is_parseable(repo):
    result = runner.invoke(app, ["analyze", str(repo.path), *WIDE, "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 1
    assert payload["attribution"]["agent_commits"] == 1


def test_json_output_contains_no_progress_chatter(repo):
    """--json must be machine-parseable, so status lines go to stderr or nowhere."""
    result = runner.invoke(app, ["analyze", str(repo.path), *WIDE, "--json"])

    json.loads(result.stdout)  # would raise if a "Reading history…" line leaked in


def test_output_flag_writes_a_file(repo, tmp_path):
    target = tmp_path / "out.json"

    result = runner.invoke(app, ["analyze", str(repo.path), *WIDE, "--output", str(target)])

    assert result.exit_code == 0
    assert json.loads(target.read_text())["schema_version"] == 1


def test_llm_flag_enables_the_narrative(repo, monkeypatch):
    from git_pulse.analyst.models import AnalystReport

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        "git_pulse.analyst.engine.AnalystEngine.analyze",
        lambda self, payload: AnalystReport(summary="Narrated."),
    )

    result = runner.invoke(app, ["analyze", str(repo.path), *WIDE, "--llm"])

    assert result.exit_code == 0
    assert "Narrated." in result.output


def test_llm_without_a_key_warns_but_still_exits_zero(repo, monkeypatch):
    for var in ENV_KEYS:
        monkeypatch.delenv(var, raising=False)

    result = runner.invoke(app, ["analyze", str(repo.path), *WIDE, "--llm"])

    assert result.exit_code == 0
    assert "API key" in result.output


def test_nonexistent_path_exits_two_with_a_clear_message(tmp_path):
    result = runner.invoke(app, ["analyze", str(tmp_path / "nope")])

    assert result.exit_code == 2
    assert "does not exist" in result.output


def test_non_repository_exits_two(tmp_path):
    result = runner.invoke(app, ["analyze", str(tmp_path)])

    assert result.exit_code == 2
    assert "not a git repository" in result.output.lower()


def test_days_and_commits_are_mutually_exclusive(repo):
    result = runner.invoke(app, ["analyze", str(repo.path), "--days", "7", "--commits", "5"])

    assert result.exit_code == 2
    assert "mutually exclusive" in result.output


def test_invalid_since_date_is_a_usage_error(repo):
    result = runner.invoke(app, ["analyze", str(repo.path), "--since", "last tuesday"])

    assert result.exit_code == 2
    assert "ISO 8601" in result.output


def test_exclude_filters_files(repo):
    repo.advance(hours=1).write("vendor/lib.py", "z\n" * 40).commit("vendor")

    result = runner.invoke(
        app, ["analyze", str(repo.path), *WIDE, "--exclude", "vendor/*", "--json"]
    )

    paths = [f["path"] for f in json.loads(result.stdout)["churn"]["files"]]
    assert "vendor/lib.py" not in paths


def test_empty_repository_exits_zero_with_a_message(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=empty, check=True)

    result = runner.invoke(app, ["analyze", str(empty)])

    assert result.exit_code == 0
    assert "No commits" in result.output


def test_second_run_hits_the_cache(repo):
    runner.invoke(app, ["analyze", str(repo.path), *WIDE, "--json"])
    result = runner.invoke(app, ["analyze", str(repo.path), *WIDE, "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["scope"]["total_commits"] == 2


def test_no_cache_flag_skips_the_cache(repo):
    result = runner.invoke(app, ["analyze", str(repo.path), *WIDE, "--no-cache", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["scope"]["total_commits"] == 2


def test_refresh_recomputes_and_overwrites_the_cached_entry(repo):
    runner.invoke(app, ["analyze", str(repo.path), *WIDE, "--json"])

    result = runner.invoke(app, ["analyze", str(repo.path), *WIDE, "--refresh", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["scope"]["total_commits"] == 2
