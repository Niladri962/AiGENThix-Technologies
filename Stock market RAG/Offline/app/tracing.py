"""One JSON trace line per request. See SPEC.md section 10.3."""
from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings


def write_trace(record: dict) -> None:
    settings = get_settings()
    path = Path(settings.trace_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
