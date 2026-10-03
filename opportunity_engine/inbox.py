"""Opportunity Inbox: every idea from every lane in one list (slice O3).

The inbox is a view. Evidence stays in the packets and historical decisions
stay in the existing Human Opportunity Gate; this module only merges them and
stores the human's inbox choices (save / reject / restore) for human-seeded
ideas in a separate state file, outside every evidence hash.

Statuses follow the spec tabs: NEEDS_REVIEW, WATCHING, APPROVED, SAVED,
REJECTED. WATCHING is reserved for the viral radar (R11).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import atomic_write_json  # noqa: E402

from opportunity_engine import (  # noqa: E402
    active_source,
    historical_adapter,
    human_topic_search,
    human_video_intake,
    models,
)

HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / "output" / "inbox_state.json"
SCHEMA_VERSION = 1

NEEDS_REVIEW = "NEEDS_REVIEW"
WATCHING = "WATCHING"
APPROVED = "APPROVED"
SAVED = "SAVED"
REJECTED = "REJECTED"
STATUSES = (NEEDS_REVIEW, WATCHING, APPROVED, SAVED, REJECTED)

INBOX_ACTIONS = {"SAVE": SAVED, "REJECT": REJECTED, "RESTORE": None}
HISTORICAL_DECISIONS = {
    "APPROVE": APPROVED,
    "REJECT": REJECTED,
    "HOLD": SAVED,
    "PENDING": NEEDS_REVIEW,
}
SOURCE_LABELS = {
    models.SOURCE_HISTORICAL: "HISTORICAL",
    models.SOURCE_HUMAN_TOPIC: "YOUR TOPIC",
    models.SOURCE_HUMAN_VIDEO: "YOUR VIDEO",
    models.SOURCE_VIRAL_RADAR: "VIRAL",
}
EVIDENCE_LABELS = {
    "historical_demand": "Demand",
    "current_breakout": "Breakout",
    "cross_channel_replication": "Replication",
    "viewer_need": "Viewer need",
    "mechanism_evidence": "Mechanism",
    "content_gap": "Content gap",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> dict[str, Any]:
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = None
    if not isinstance(state, dict) or not isinstance(state.get("items"), dict):
        return {"schema_version": SCHEMA_VERSION, "items": {}}
    return state


def _evidence_chips(packet: dict[str, Any]) -> list[dict[str, Any]]:
    chips = []
    for dimension, label in EVIDENCE_LABELS.items():
        item = (packet.get("evidence_state") or {}).get(dimension) or {}
        level = item.get("level")
        if level and level not in models.RULE_FREE_LEVELS:
            chips.append(
                {
                    "dimension": dimension,
                    "label": label,
                    "level": level,
                    "rule_id": item.get("rule_id"),
                    "basis": item.get("basis") or [],
                }
            )
    return chips


def _videos(packet: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    return [
        {
            "video_id": video.get("video_id"),
            "title": video.get("title"),
            "youtube_url": video.get("youtube_url"),
            "channel_title": video.get("channel_title"),
            "views": video.get("views"),
            "format": video.get("format"),
            "age_days": video.get("age_days"),
        }
        for video in (packet.get("candidate_videos") or [])[:limit]
    ]


def _base_item(packet: dict[str, Any]) -> dict[str, Any]:
    channel = packet.get("channel") or {}
    intake = packet.get("intake") or {}
    return {
        "opportunity_id": packet.get("opportunity_id"),
        "source_type": packet.get("source_type"),
        "source_label": SOURCE_LABELS.get(str(packet.get("source_type")), "OTHER"),
        "title": packet.get("title"),
        "summary": packet.get("summary"),
        "route": channel.get("route"),
        "route_channel_id": channel.get("channel_id"),
        "route_rule_id": channel.get("rule_id"),
        "route_reason": channel.get("reason"),
        "evidence": _evidence_chips(packet),
        "video_count": len(packet.get("candidate_videos") or []),
        "videos": _videos(packet),
        "notes": packet.get("human_notes") or [],
        "created_at": packet.get("created_at"),
        "measurement_source": (intake.get("measurement") or {}).get("source")
        or ((packet.get("candidate_videos") or [{}])[0].get("measurement_source")),
        "measurement_error": (intake.get("measurement") or {}).get("error"),
        "failed_searches": sum(
            1 for entry in intake.get("search_log") or [] if entry.get("status") != "COMPLETE"
        ),
        "search_count": len(intake.get("search_log") or []),
        "excluded_result_count": len(intake.get("excluded_videos") or []),
        "is_active": False,
        "status": NEEDS_REVIEW,
        "status_reason": "",
        "actions": [],
    }


def _human_item(
    packet: dict[str, Any],
    state_items: dict[str, Any],
    active: dict[str, Any] | None,
) -> dict[str, Any]:
    item = _base_item(packet)
    source = packet.get("source_type")
    if source == models.SOURCE_HUMAN_VIDEO:
        key = {"video_id": (packet.get("candidate_videos") or [{}])[0].get("video_id")}
    else:
        key = {"topic_key": (packet.get("intake") or {}).get("topic_key")}
    item.update(key)
    if active and active.get("opportunity_id") == packet.get("opportunity_id"):
        item.update(
            status=APPROVED,
            is_active=True,
            status_reason="The active study set: Experiment 02 is analysing it.",
            actions=["STOP"],
        )
        return item
    saved = state_items.get(str(packet.get("opportunity_id"))) or {}
    analyze = "ANALYZE" if item["video_count"] else None
    if saved.get("status") in (SAVED, REJECTED):
        item.update(
            status=saved["status"],
            status_reason=saved.get("note") or "",
            actions=[a for a in ("RESTORE", analyze) if a],
        )
    elif item["route"] == models.ROUTE_FUTURE:
        item.update(
            status=SAVED,
            status_reason=f"Parked on the future-channel shelf: {item['route_channel_id']}.",
            actions=[a for a in (analyze, "REJECT") if a],
        )
    else:
        item.update(actions=[a for a in (analyze, "SAVE", "REJECT") if a])
    return item


def _historical_items(
    gate: dict[str, Any],
    active: dict[str, Any] | None,
    builder: Callable[[], dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        result = builder()
    except (OSError, ValueError) as exc:
        return [], f"Historical opportunities could not be read: {exc}"
    decisions = {
        str(item.get("opportunity_id")): str(item.get("decision") or "PENDING")
        for item in gate.get("opportunities") or []
        if isinstance(item, dict)
    }
    items = []
    for packet in result.get("packets") or []:
        item = _base_item(packet)
        gate_key = (packet.get("historical_evidence") or {}).get("gate_opportunity_id")
        decision = decisions.get(str(gate_key), "PENDING")
        status = HISTORICAL_DECISIONS.get(decision, NEEDS_REVIEW)
        is_active = (
            status == APPROVED and not active and bool(gate.get("ready_for_experiment_02"))
        )
        reasons = {
            APPROVED: "Approved at the historical gate."
            + ("" if is_active or not active else " Your own idea is the active study set right now."),
            REJECTED: "Rejected at the historical gate.",
            SAVED: "Held at the historical gate.",
            NEEDS_REVIEW: "Decide in Historical review below.",
        }
        item.update(
            gate_opportunity_id=gate_key,
            status=status,
            is_active=is_active,
            status_reason=reasons[status],
            actions=["REVIEW_BELOW"],
        )
        items.append(item)
    return items, None


def build_inbox(
    gate: dict[str, Any],
    *,
    historical_builder: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    state_items = load_state()["items"]
    active = active_source.load_active()
    historical, error = _historical_items(
        gate, active, historical_builder or historical_adapter.build
    )
    human = [
        _human_item(packet, state_items, active)
        for packet in (*human_video_intake.list_packets(), *human_topic_search.list_packets())
    ]
    # The active idea is pinned to the top; everything else is newest first.
    everything = historical + human
    items = [i for i in everything if i["is_active"]] + sorted(
        (i for i in everything if not i["is_active"]),
        key=lambda i: str(i.get("created_at") or ""),
        reverse=True,
    )
    return {
        "items": items,
        "counts": {status: sum(1 for i in items if i["status"] == status) for status in STATUSES},
        "active": active_source.summary(active),
        "historical_error": error,
    }


def _find_human_packet(opportunity_id: str) -> dict[str, Any] | None:
    for packet in (*human_video_intake.list_packets(), *human_topic_search.list_packets()):
        if packet.get("opportunity_id") == opportunity_id:
            return packet
    return None


def apply_action(opportunity_id: str, action: str, note: str = "") -> None:
    """Save, reject or restore a human-seeded idea."""
    if action not in INBOX_ACTIONS:
        raise ValueError(f"Unsupported inbox action: {action}")
    if str(opportunity_id).startswith("opp_historical__"):
        raise ValueError("Historical opportunities are decided in Historical review.")
    packet = _find_human_packet(opportunity_id)
    if packet is None:
        raise ValueError("Unknown opportunity.")
    active = active_source.load_active()
    if active and active.get("opportunity_id") == opportunity_id:
        raise ValueError("This idea is being analysed. Stop analysing it first.")
    state = load_state()
    if action == "RESTORE":
        state["items"].pop(opportunity_id, None)
    else:
        state["items"][opportunity_id] = {
            "status": INBOX_ACTIONS[action],
            "note": note.strip()[:500],
            "updated_at": utc_now(),
        }
    state["schema_version"] = SCHEMA_VERSION
    atomic_write_json(STATE_FILE, state)
