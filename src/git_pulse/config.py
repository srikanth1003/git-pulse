from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

DEFAULT_CONFIG = {
    "llm": {
        "model": "anthropic/claude-sonnet-4-20250514",
    },
    "analysis": {
        "default_days": 30,
        "max_hotspots": 20,
        "exclude": [],
    },
}


@dataclass
class GitPulseConfig:
    model: str = DEFAULT_CONFIG["llm"]["model"]
    default_days: int = DEFAULT_CONFIG["analysis"]["default_days"]
    max_hotspots: int = DEFAULT_CONFIG["analysis"]["max_hotspots"]
    exclude: list[str] = field(default_factory=list)


def load_config(
    config_path: str | None = None,
    repo_path: str | None = None,
) -> GitPulseConfig:
    """Load config with precedence: --config flag > repo .gitpulse.toml > ~/.config/gitpulse/config.toml > defaults."""
    paths_to_try = []

    if config_path:
        paths_to_try.append(Path(config_path))
    if repo_path:
        paths_to_try.append(Path(repo_path) / ".gitpulse.toml")
    paths_to_try.append(Path.home() / ".config" / "gitpulse" / "config.toml")

    for path in paths_to_try:
        if path.exists():
            return _parse_config(path)

    return GitPulseConfig()


def _parse_config(path: Path) -> GitPulseConfig:
    """Parse a TOML config file into GitPulseConfig."""
    with open(path, "rb") as f:
        data = tomllib.load(f)

    llm = data.get("llm", {})
    analysis = data.get("analysis", {})

    return GitPulseConfig(
        model=llm.get("model", DEFAULT_CONFIG["llm"]["model"]),
        default_days=analysis.get("default_days", DEFAULT_CONFIG["analysis"]["default_days"]),
        max_hotspots=analysis.get("max_hotspots", DEFAULT_CONFIG["analysis"]["max_hotspots"]),
        exclude=analysis.get("exclude", []),
    )
