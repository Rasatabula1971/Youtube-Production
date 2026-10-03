"""Route an opportunity to the active channel, a future-channel shelf, or out.

Spec v2.1 §R10: one channel (Science Inside) is built now; ideas that fit a
future channel are parked on that channel's shelf rather than discarded, and
excluded material always records the rule that excluded it so the human can
audit and reverse it. Matching is whole-word and case-insensitive; a rule's
unless_terms rescue mechanism-led videos from subject exclusions.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from opportunity_engine import models

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "config.json"


def load_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = validate_config(config)
    if errors:
        raise ValueError("Invalid opportunity_engine config: " + "; ".join(errors))
    return config


def validate_config(config: Any) -> list[str]:
    if not isinstance(config, dict):
        return ["config must be an object"]
    errors: list[str] = []
    channels = config.get("channels")
    if not isinstance(channels, dict) or not channels:
        return ["channels must be a non-empty object"]
    active = config.get("active_channel_id")
    if channels.get(active, {}).get("status") != "ACTIVE":
        errors.append("active_channel_id must name a channel with status ACTIVE")
    active_count = sum(1 for c in channels.values() if c.get("status") == "ACTIVE")
    if active_count != 1:
        errors.append("exactly one channel may be ACTIVE")
    for channel_id, channel in channels.items():
        if channel.get("status") not in ("ACTIVE", "FUTURE"):
            errors.append(f"channel {channel_id} status must be ACTIVE or FUTURE")
    for niche, channel_id in (config.get("niche_routes") or {}).items():
        if channel_id not in channels:
            errors.append(f"niche_routes.{niche} names unknown channel {channel_id}")
    seen: set[str] = set()
    for rule in config.get("exclusions") or []:
        rule_id = str(rule.get("rule_id") or "")
        if not rule_id or rule_id in seen:
            errors.append(f"exclusion rule_id missing or duplicated: {rule_id!r}")
        seen.add(rule_id)
        if rule.get("layer") not in ("SUBJECT", "FORMAT", "RISK"):
            errors.append(f"exclusion {rule_id} layer must be SUBJECT, FORMAT or RISK")
        if not rule.get("terms") or not rule.get("reason"):
            errors.append(f"exclusion {rule_id} needs terms and a reason")
    return errors


def _normalise(text: str) -> str:
    return " " + re.sub(r"[^a-z0-9#'+-]+", " ", text.lower()).strip() + " "


def matched_terms(text: str, terms: list[str]) -> list[str]:
    haystack = _normalise(text)
    hits = []
    for term in terms:
        needle = _normalise(term)
        if needle.strip() and needle in haystack:
            hits.append(term)
    return hits


def route(
    text: str,
    *,
    niche: str = "",
    made_for_kids: bool = False,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Decide where one opportunity or video belongs, with the reason."""
    config = config or load_config()
    if made_for_kids and config.get("made_for_kids_excluded", True):
        return {
            "route": models.ROUTE_EXCLUDED,
            "channel_id": None,
            "rule_id": "EX-MADE-FOR-KIDS",
            "reason": "YouTube marks this video as made for kids.",
            "matched_terms": [],
        }
    for rule in config.get("exclusions") or []:
        hits = matched_terms(text, rule["terms"])
        if hits and not matched_terms(text, rule.get("unless_terms") or []):
            return {
                "route": models.ROUTE_EXCLUDED,
                "channel_id": None,
                "rule_id": rule["rule_id"],
                "reason": rule["reason"],
                "matched_terms": hits,
            }
    for channel_id, channel in config["channels"].items():
        if channel.get("status") != "FUTURE":
            continue
        hits = matched_terms(text, channel.get("route_terms") or [])
        if hits:
            return {
                "route": models.ROUTE_FUTURE,
                "channel_id": channel_id,
                "rule_id": f"FUTURE-{channel_id}",
                "reason": f"Fits the future channel: {channel.get('name', channel_id)}.",
                "matched_terms": hits,
            }
    channel_id = (config.get("niche_routes") or {}).get(niche)
    if channel_id:
        status = config["channels"][channel_id]["status"]
        return {
            "route": models.ROUTE_ACTIVE if status == "ACTIVE" else models.ROUTE_FUTURE,
            "channel_id": channel_id,
            "rule_id": f"NICHE-{niche}",
            "reason": f"Niche {niche} belongs to {channel_id}.",
            "matched_terms": [],
        }
    return {
        "route": models.ROUTE_UNSCOPED,
        "channel_id": None,
        "rule_id": None,
        "reason": "No niche route or channel term matched; needs a human or model fit check.",
        "matched_terms": [],
    }
