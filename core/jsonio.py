"""JSON file reading shared by the engines (D-114)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    """Parse a JSON file. Missing file: FileNotFoundError(path).
    Invalid JSON: json.JSONDecodeError propagates."""
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_or_exit(path: Path) -> Any:
    """Parse a JSON file. Missing file: FileNotFoundError(path).
    Invalid JSON: SystemExit with a readable message."""
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
