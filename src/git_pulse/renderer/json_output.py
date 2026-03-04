from __future__ import annotations

import json
from dataclasses import asdict

from git_pulse.analyst.models import AnalystReport


def render_json(report: AnalystReport) -> str:
    """Serialize AnalystReport to JSON string."""
    return json.dumps(asdict(report), indent=2)
