"""Filesystem loader for strict approved programme week documents."""

import json
from pathlib import Path

from hwa.programmes.schema import ProgrammeWeekDocument


def load_week_file(path: Path) -> ProgrammeWeekDocument:
    """Load one JSON week through the strict programme document schema."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return ProgrammeWeekDocument.model_validate(payload)
