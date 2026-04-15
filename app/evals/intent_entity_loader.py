from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATASET_DIR = Path(__file__).parent / "datasets"


def load_intent_entity_cases(path: Path | None = None) -> list[dict[str, Any]]:
    """Load intent/entity regression cases from a JSONL file.

    Each line should be a JSON object with at least ``utterance`` and ``expected``.
    Blank lines and lines starting with ``#`` are skipped.
    """
    path = path or DATASET_DIR / "intent_entity_cases.jsonl"
    cases: list[dict[str, Any]] = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            cases.append(json.loads(line))
    return cases
