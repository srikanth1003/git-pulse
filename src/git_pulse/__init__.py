"""git-pulse — git history analysis with LLM-powered insights."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    # Populated at build time from the git tag (hatch-vcs).
    __version__ = _pkg_version("gitpulse-ai")
except PackageNotFoundError:  # pragma: no cover - running from an uninstalled tree
    try:
        from git_pulse._version import __version__
    except ImportError:
        __version__ = "0.0.0.dev0"

__all__ = ["__version__"]
