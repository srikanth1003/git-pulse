from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """Raised when a config file exists but cannot be used."""


DEFAULT_MODEL = "anthropic/claude-sonnet-4-20250514"

# Retained for backwards compatibility with existing callers and tests.
DEFAULT_CONFIG: dict[str, Any] = {
    "llm": {"enabled": False, "model": DEFAULT_MODEL},
    "analysis": {
        "default_days": 30,
        "max_hotspots": 20,
        "hotspot_window_hours": 72.0,
        "hotspot_region_lines": 25,
        "exclude": [],
    },
}


@dataclass
class LLMConfig:
    enabled: bool = False
    model: str = DEFAULT_MODEL


@dataclass
class AnalysisConfig:
    default_days: int = 30
    max_hotspots: int = 20
    ignore_whitespace: bool = False
    include_merges: bool = False
    bulk_commit_threshold: int = 100
    max_file_lines: int = 50000
    hotspot_window_hours: float = 72.0
    hotspot_region_lines: int = 25
    exclude: list[str] = field(default_factory=list)


@dataclass
class AttributionConfig:
    agent_threshold: float = 0.70
    human_threshold: float = 0.30
    enable_cadence_heuristic: bool = False


@dataclass
class SurvivalConfig:
    window_days: int = 7


@dataclass
class CouplingConfig:
    min_shared_commits: int = 5


@dataclass
class SessionsConfig:
    gap_minutes: int = 90


@dataclass
class RevertsConfig:
    storm_commits: int = 4
    storm_hours: int = 3


@dataclass
class CIConfig:
    """Threshold gates for ``git-pulse ci``. ``None`` means the gate is off."""

    fail_on_agent_only_exposure: float | None = None
    fail_on_bus_factor_below: int | None = None
    fail_on_rework_rate_above: float | None = None


@dataclass
class GitPulseConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    attribution: AttributionConfig = field(default_factory=AttributionConfig)
    survival: SurvivalConfig = field(default_factory=SurvivalConfig)
    coupling: CouplingConfig = field(default_factory=CouplingConfig)
    sessions: SessionsConfig = field(default_factory=SessionsConfig)
    reverts: RevertsConfig = field(default_factory=RevertsConfig)
    ci: CIConfig = field(default_factory=CIConfig)

    @classmethod
    def defaults(cls) -> GitPulseConfig:
        """A config with no file or environment input. Used by tests and ``--no-config``."""
        return cls()

    # Flat accessors kept so existing callers need no change.
    @property
    def model(self) -> str:
        return self.llm.model

    @property
    def default_days(self) -> int:
        return self.analysis.default_days

    @property
    def max_hotspots(self) -> int:
        return self.analysis.max_hotspots

    @property
    def exclude(self) -> list[str]:
        return self.analysis.exclude


def load_config(
    config_path: str | None = None,
    repo_path: str | None = None,
) -> GitPulseConfig:
    """Load config: --config flag > repo .gitpulse.toml > ~/.config > defaults."""
    candidates: list[Path] = []
    if config_path:
        candidates.append(Path(config_path))
    if repo_path:
        candidates.append(Path(repo_path) / ".gitpulse.toml")
    candidates.append(Path.home() / ".config" / "gitpulse" / "config.toml")

    for path in candidates:
        if path.exists():
            return _parse_config(path)

    return GitPulseConfig()


def _parse_config(path: Path) -> GitPulseConfig:
    try:
        with open(path, "rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc

    return GitPulseConfig(
        llm=_build(LLMConfig, data.get("llm")),
        analysis=_build(AnalysisConfig, data.get("analysis")),
        attribution=_build(AttributionConfig, data.get("attribution")),
        survival=_build(SurvivalConfig, data.get("survival")),
        coupling=_build(CouplingConfig, data.get("coupling")),
        sessions=_build(SessionsConfig, data.get("sessions")),
        reverts=_build(RevertsConfig, data.get("reverts")),
        ci=_build(CIConfig, data.get("ci")),
    )


def _build(cls: type, section: dict[str, Any] | None) -> Any:
    """Instantiate ``cls`` from a TOML table, ignoring unknown keys."""
    if not section:
        return cls()
    known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    return cls(**{k: v for k, v in section.items() if k in known})
