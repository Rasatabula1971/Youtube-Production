"""Which packaging briefs take the Short lane (Two Lanes, D-190).

A Short is packaged from its own Packaging Brief: the title chosen at the Title
Direction step, and a frame from the finished video as its thumbnail. The
angle, thumbnail-concept, 25-pair matrix, thumbnail-image and Final Packaging
steps are for long-form only. ``packaging_config.json`` ``short_lane_package``
switches this off, and Shorts then go through every step again.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "packaging_config.json"
VIDEO_FRAME = "VIDEO_FRAME"
CONTRACT = "SHORT_LANE_TITLE_AND_VIDEO_FRAME"


def settings() -> dict[str, Any]:
    try:
        payload = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {}
    block = payload.get("short_lane_package") if isinstance(payload, dict) else None
    return block if isinstance(block, dict) else {}


def enabled() -> bool:
    return settings().get("enabled", True) is True


def is_short_lane(brief: dict[str, Any] | None) -> bool:
    return isinstance(brief, dict) and str(brief.get("format") or "") == "short" and enabled()
