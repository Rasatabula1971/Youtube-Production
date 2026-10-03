"""Canonical Opportunity Packet contract (spec v2.1, slice O1).

Every source lane (historical, human topic, human video, viral radar) produces
this one shape so the Human Opportunity Gate never needs lane-specific logic.
Validation is hand-written, like channel_profiles, to stay dependency-free.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from opportunity_engine import models  # noqa: E402
from opportunity_engine.provenance import packet_sha256  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def evidence(level: str, rule_id: str | None = None, basis: list[str] | None = None) -> dict[str, Any]:
    """One evidence dimension: its level, the written rule that set it, and why."""
    return {"level": level, "rule_id": rule_id, "basis": list(basis or [])}


def unassessed_evidence_state() -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for dimension, levels in models.EVIDENCE_DIMENSIONS.items():
        default = "UNASSESSED" if "UNASSESSED" in levels else "HYPOTHESIS"
        state[dimension] = evidence(default)
    return state


def build_packet(
    *,
    opportunity_id: str,
    source_type: str,
    title: str,
    summary: str,
    channel: dict[str, Any],
    topic: str = "",
    niche: str = "",
    formats: list[str] | None = None,
    seed: dict[str, Any] | None = None,
    evidence_state: dict[str, dict[str, Any]] | None = None,
    viral_evidence: dict[str, Any] | None = None,
    historical_evidence: dict[str, Any] | None = None,
    candidate_videos: list[dict[str, Any]] | None = None,
    source_artifacts: list[dict[str, str]] | None = None,
    generator: str = "",
    created_at: str | None = None,
) -> dict[str, Any]:
    state = unassessed_evidence_state()
    state.update(evidence_state or {})
    packet: dict[str, Any] = {
        "schema_version": models.SCHEMA_VERSION,
        "opportunity_id": opportunity_id,
        "source_type": source_type,
        "created_at": created_at or utc_now(),
        "title": title,
        "summary": summary,
        "topic": topic,
        "niche": niche,
        "formats": sorted(formats or []),
        "channel": dict(channel),
        "seed": {"topic": None, "question": None, "video_url": None, **(seed or {})},
        "evidence_state": state,
        "viral_evidence": viral_evidence,
        "historical_evidence": historical_evidence,
        "candidate_videos": list(candidate_videos or []),
        "human_notes": [],
        "provenance": {
            "generator": generator,
            "source_artifacts": list(source_artifacts or []),
        },
    }
    packet["packet_sha256"] = packet_sha256(packet)
    errors = validate_packet(packet)
    if errors:
        raise ValueError("Invalid Opportunity Packet: " + "; ".join(errors))
    return packet


def _validate_channel(channel: Any, errors: list[str]) -> None:
    if not isinstance(channel, dict):
        errors.append("channel must be an object")
        return
    route = channel.get("route")
    if route not in models.ROUTES:
        errors.append(f"channel.route must be one of {', '.join(models.ROUTES)}")
    if route in (models.ROUTE_ACTIVE, models.ROUTE_FUTURE) and not str(
        channel.get("channel_id") or ""
    ).strip():
        errors.append(f"channel.channel_id is required for {route}")
    if route == models.ROUTE_EXCLUDED and not channel.get("rule_id"):
        errors.append("an EXCLUDED packet must name the exclusion rule_id")


def _validate_evidence(state: Any, errors: list[str]) -> None:
    if not isinstance(state, dict):
        errors.append("evidence_state must be an object")
        return
    for dimension, levels in models.EVIDENCE_DIMENSIONS.items():
        item = state.get(dimension)
        if not isinstance(item, dict):
            errors.append(f"evidence_state.{dimension} is required")
            continue
        level = item.get("level")
        if level not in levels:
            errors.append(f"evidence_state.{dimension}.level must be one of {', '.join(levels)}")
        elif level not in models.RULE_FREE_LEVELS and not item.get("rule_id"):
            errors.append(f"evidence_state.{dimension} level {level} needs a rule_id")
        if not isinstance(item.get("basis"), list):
            errors.append(f"evidence_state.{dimension}.basis must be a list")
    unknown = sorted(set(state) - set(models.EVIDENCE_DIMENSIONS))
    if unknown:
        errors.append("unknown evidence dimensions: " + ", ".join(unknown))


def _validate_viral(viral: Any, errors: list[str]) -> None:
    if viral is None:
        return
    if not isinstance(viral, dict):
        errors.append("viral_evidence must be an object or null")
        return
    for axis, values in models.BREAKOUT_AXES.items():
        if viral.get(axis) not in values:
            errors.append(f"viral_evidence.{axis} must be one of {', '.join(values)}")
    if not isinstance(viral.get("trajectory_history_available"), bool):
        errors.append("viral_evidence.trajectory_history_available must be boolean")


def validate_packet(packet: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(packet, dict):
        return ["packet must be an object"]
    if packet.get("schema_version") != models.SCHEMA_VERSION:
        errors.append(f"schema_version must equal {models.SCHEMA_VERSION}")
    if not str(packet.get("opportunity_id") or "").startswith("opp_"):
        errors.append("opportunity_id must start with opp_")
    source = packet.get("source_type")
    if source not in models.SOURCE_TYPES:
        errors.append(f"source_type must be one of {', '.join(models.SOURCE_TYPES)}")
    if not str(packet.get("title") or "").strip():
        errors.append("title is required")
    bad_formats = [f for f in packet.get("formats") or [] if f not in models.FORMATS]
    if bad_formats:
        errors.append("unknown formats: " + ", ".join(map(str, bad_formats)))
    _validate_channel(packet.get("channel"), errors)
    _validate_evidence(packet.get("evidence_state"), errors)
    _validate_viral(packet.get("viral_evidence"), errors)
    if source == models.SOURCE_HISTORICAL and not isinstance(
        packet.get("historical_evidence"), dict
    ):
        errors.append("HISTORICAL packets require historical_evidence")
    if source == models.SOURCE_VIRAL_RADAR and packet.get("viral_evidence") is None:
        errors.append("VIRAL_RADAR packets require viral_evidence")
    if source in (models.SOURCE_HUMAN_TOPIC, models.SOURCE_HUMAN_VIDEO):
        seed = packet.get("seed") or {}
        if not any(seed.get(key) for key in ("topic", "question", "video_url")):
            errors.append(f"{source} packets require a seed topic, question or video_url")
    provenance = packet.get("provenance")
    if not isinstance(provenance, dict) or not str(provenance.get("generator") or "").strip():
        errors.append("provenance.generator is required")
    if packet.get("packet_sha256") != packet_sha256(packet):
        errors.append("packet_sha256 does not match packet content")
    return errors
