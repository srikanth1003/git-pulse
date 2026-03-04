import subprocess
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from git_pulse.cli import app


runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "analyze" in result.output


def test_analyze_help():
    result = runner.invoke(app, ["analyze", "--help"])
    assert result.exit_code == 0
    assert "--days" in result.output
    assert "--commits" in result.output
    assert "--json" in result.output
    assert "--model" in result.output


def test_analyze_nonexistent_repo():
    result = runner.invoke(app, ["analyze", "/nonexistent/repo"])
    assert result.exit_code != 0


def test_analyze_not_a_git_repo(tmp_path):
    result = runner.invoke(app, ["analyze", str(tmp_path)])
    assert result.exit_code != 0


def test_analyze_runs_pipeline(tmp_path):
    """Integration test: create a real repo and run analyze with mocked LLM."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, capture_output=True)
    (repo / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)
    (repo / "a.py").write_text("x = 2\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "change"], cwd=repo, capture_output=True)

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"summary":"Test","insights":[],"top_actions":[]}'

    with patch("git_pulse.analyst.engine.completion", return_value=mock_response):
        result = runner.invoke(app, ["analyze", str(repo), "--days", "1"])
        assert result.exit_code == 0
