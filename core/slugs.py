"""File-name-safe identifiers shared by the engines (D-175)."""

from __future__ import annotations


def safe_slug(value: str) -> str:
    """Keep letters, digits and -_. ; replace everything else with _."""
    cleaned = "".join(
        char if char.isalnum() or char in "-_." else "_" for char in value
    ).strip("._")
    return cleaned or "unknown"
