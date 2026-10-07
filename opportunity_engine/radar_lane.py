"""Lane classification for the Viral Radar page (D-162).

The radar scans wide and brings back finance, fitness, history-for-sleep and
game videos beside the mechanism explainers the channel makes. This sorts
each tracked video into a lane from its title and channel, with the terms in
``radar_lane_config.json``, so the page can show the channel's lane first.
No model call: the rules are plain word lists the operator can edit.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

CONFIG_FILE = Path(__file__).resolve().parent / "radar_lane_config.json"

ON_LANE = "ON_LANE"
OFF_LANE = "OFF_LANE"
UNCLEAR = "UNCLEAR"
OTHER_LANGUAGE = "OTHER_LANGUAGE"
LANES = (ON_LANE, UNCLEAR, OFF_LANE, OTHER_LANGUAGE)


@lru_cache(maxsize=1)
def _compiled() -> tuple[list[tuple[str, re.Pattern[str]]], list[tuple[str, re.Pattern[str]]], float]:
    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        config = {}

    def patterns(terms: Any) -> list[tuple[str, re.Pattern[str]]]:
        out = []
        for term in terms or []:
            text = str(term).strip().lower()
            if not text:
                continue
            stem = text.endswith("*")
            body = re.escape(text.rstrip("*")).replace(r"\ ", r"\s+")
            out.append((text, re.compile(r"(?<![a-z0-9])" + body + (r"[a-z0-9-]*" if stem else "") + r"(?![a-z0-9])")))
        return out

    share = config.get("other_language_non_latin_share", 0.3)
    return patterns(config.get("on_lane")), patterns(config.get("off_lane")), float(share)


def reload() -> None:
    _compiled.cache_clear()


def _non_latin_share(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    foreign = sum(1 for ch in letters if not unicodedata.name(ch, "").startswith("LATIN"))
    return foreign / len(letters)


def classify(title: Any, channel_title: Any = "") -> dict[str, Any]:
    """The lane of one video, and the terms that decided it."""
    on_terms, off_terms, share = _compiled()
    title_text = str(title or "")
    if _non_latin_share(title_text) >= share:
        return {"lane": OTHER_LANGUAGE, "hits": []}
    text = (title_text + " " + str(channel_title or "")).lower()
    off_hits = [term for term, pattern in off_terms if pattern.search(text)]
    if off_hits:
        return {"lane": OFF_LANE, "hits": off_hits[:4]}
    on_hits = [term for term, pattern in on_terms if pattern.search(text)]
    if on_hits:
        return {"lane": ON_LANE, "hits": on_hits[:4]}
    return {"lane": UNCLEAR, "hits": []}


def theme_lane(lanes: list[str]) -> str:
    """A theme is on lane if any member is; off only if nothing in it is for the channel."""
    if ON_LANE in lanes:
        return ON_LANE
    if UNCLEAR in lanes:
        return UNCLEAR
    if lanes and all(lane == OTHER_LANGUAGE for lane in lanes):
        return OTHER_LANGUAGE
    return OFF_LANE if lanes else UNCLEAR
