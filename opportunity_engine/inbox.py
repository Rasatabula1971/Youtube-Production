"""Opportunity Inbox and unified Human Opportunity Gate (slices O3 and O12).

Every idea from every lane appears in one list, and every decision is made
here: APPROVE, REWORK (note required), WATCH (radar only), SAVE and REJECT
(R11). Evidence stays in the packets. Decisions about human-seeded and radar
ideas are stored in a separate state file, outside every evidence hash, with
their history and the packet hash they were made against: when the evidence
moves later the card says so, but the decision stands (R8). Historical topics
keep their decisions in the existing gate, which the server calls.

Statuses follow the spec tabs: NEEDS_REVIEW, WATCHING, APPROVED, SAVED,
REJECTED.
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
    viral_radar,
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

INBOX_ACTIONS = {
    "SAVE": SAVED,
    "REJECT": REJECTED,
    "WATCH": WATCHING,
    "REWORK": NEEDS_REVIEW,
    # Explicit, so a future-channel idea moved back to review stays there.
    "RESTORE": NEEDS_REVIEW,
}
HISTORY_LIMIT = 30
EVIDENCE_ORDER = (
    "historical_demand",
    "current_breakout",
    "cross_channel_replication",
    "viewer_need",
    "mechanism_evidence",
    "content_gap",
)
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


def _evidence_matrix(packet: dict[str, Any]) -> list[dict[str, Any]]:
    """All six evidence dimensions, including the unassessed ones."""
    state = packet.get("evidence_state") or {}
    return [
        {
            "dimension": dimension,
            "label": EVIDENCE_LABELS[dimension],
            "level": (state.get(dimension) or {}).get("level") or "UNASSESSED",
            "rule_id": (state.get(dimension) or {}).get("rule_id"),
            "basis": (state.get(dimension) or {}).get("basis") or [],
        }
        for dimension in EVIDENCE_ORDER
    ]


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
        "matrix": _evidence_matrix(packet),
        "packet_sha256": packet.get("packet_sha256"),
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
        "seed": packet.get("seed") or {},
        "historical_evidence": packet.get("historical_evidence"),
        "provenance": {
            "generator": (packet.get("provenance") or {}).get("generator"),
            "source_artifacts": [
                {"role": a.get("role"), "path": a.get("path"), "sha256": str(a.get("sha256") or "")[:12]}
                for a in (packet.get("provenance") or {}).get("source_artifacts") or []
            ],
            "packet_sha256": str(packet.get("packet_sha256") or "")[:12],
            "created_at": packet.get("created_at"),
        },
        "is_active": False,
        "status": NEEDS_REVIEW,
        "status_reason": "",
        "actions": [],
    }


def _is_active(packet: dict[str, Any], active: dict[str, Any] | None) -> bool:
    if not active:
        return False
    if active.get("opportunity_id") == packet.get("opportunity_id"):
        return True
    # A radar theme makes each of its member breakouts active.
    if active.get("cluster_id") and packet.get("source_type") == models.SOURCE_VIRAL_RADAR:
        video_id = (packet.get("candidate_videos") or [{}])[0].get("video_id")
        return any(row.get("video_id") == video_id for row in active.get("study_set") or [])
    return False


def _human_item(
    packet: dict[str, Any],
    state_items: dict[str, Any],
    active: dict[str, Any] | None,
) -> dict[str, Any]:
    item = _base_item(packet)
    source = packet.get("source_type")
    is_viral = source == models.SOURCE_VIRAL_RADAR
    if source in (models.SOURCE_HUMAN_VIDEO, models.SOURCE_VIRAL_RADAR):
        key = {"video_id": (packet.get("candidate_videos") or [{}])[0].get("video_id")}
    else:
        key = {"topic_key": (packet.get("intake") or {}).get("topic_key")}
    item.update(key)
    saved = state_items.get(str(packet.get("opportunity_id"))) or {}
    item["decision_history"] = saved.get("history") or []
    item["evidence_moved"] = bool(
        saved.get("packet_sha256") and saved.get("packet_sha256") != packet.get("packet_sha256")
    )
    if is_viral:
        item["viral"] = _viral_summary(packet)
    theme = "APPROVE_THEME" if is_viral and (item["viral"] or {}).get("breadth") == "REPLICATED" else None
    if _is_active(packet, active):
        item.update(
            status=APPROVED,
            is_active=True,
            status_reason="The active study set: Experiment 02 is analysing it.",
            actions=["STOP"],
        )
        return item
    approve = "APPROVE" if item["video_count"] else None
    watch = "WATCH" if is_viral else None
    status = saved.get("status")
    if status == WATCHING and is_viral:
        item.update(
            status=WATCHING,
            status_reason=saved.get("note") or "You are watching this breakout; the radar keeps tracking it.",
            actions=[a for a in (approve, theme, "REWORK", "SAVE", "REJECT", "RESTORE") if a],
        )
    elif status in (SAVED, REJECTED):
        item.update(
            status=status,
            status_reason=saved.get("note") or "",
            actions=[a for a in ("RESTORE", approve) if a],
        )
    elif item["route"] == models.ROUTE_FUTURE and status != NEEDS_REVIEW:
        item.update(
            status=SAVED,
            status_reason=f"Parked on the future-channel shelf: {item['route_channel_id']}.",
            actions=[a for a in (approve, "REJECT", "RESTORE") if a],
        )
    else:
        reason = ""
        if status == NEEDS_REVIEW and saved.get("note"):
            reason = "Reworked: " + saved["note"]
        item.update(
            status=NEEDS_REVIEW,
            status_reason=reason,
            actions=[a for a in (approve, theme, "REWORK", watch, "SAVE", "REJECT") if a],
        )
    return item


def _viral_summary(packet: dict[str, Any]) -> dict[str, Any]:
    viral = packet.get("viral_evidence") or {}
    metrics = viral.get("metrics") or {}
    baseline = viral.get("baseline") or {}
    return {
        "strength": viral.get("strength"),
        "strength_rule_id": viral.get("strength_rule_id"),
        "trajectory": viral.get("trajectory"),
        "breadth": viral.get("breadth"),
        "historical_alignment": viral.get("historical_alignment"),
        "tracking_status": viral.get("tracking_status"),
        "age_hours": metrics.get("age_hours"),
        "views": metrics.get("views"),
        "lifetime_ratio": metrics.get("lifetime_ratio"),
        "vph_ratio": metrics.get("vph_ratio"),
        "lifetime_vph": metrics.get("lifetime_vph"),
        "ratio_basis": metrics.get("ratio_basis") or [],
        "views_per_follower": metrics.get("views_per_follower"),
        "likes_per_view": metrics.get("likes_per_view"),
        "comments_per_view": metrics.get("comments_per_view"),
        "subscriber_outlier": metrics.get("subscriber_outlier"),
        "baseline_median_vph": baseline.get("median_lifetime_vph"),
        "baseline_rule": baseline.get("rule"),
        "baseline_age_days": baseline.get("sample_age_days"),
        "published_at": ((packet.get("candidate_videos") or [{}])[0]).get("published_at"),
        "classification_history": viral.get("classification_history") or [],
        "baseline_median_views": baseline.get("median_views"),
        "baseline_sample_size": baseline.get("sample_size"),
        "cluster": viral.get("cluster"),
        "intervals": viral.get("intervals") or [],
        "trajectory_history_available": viral.get("trajectory_history_available"),
        "outcome": viral.get("outcome"),
    }


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
            # Approval needs the examples kept or replaced, so it stays in
            # Historical review; save (hold) and reject can happen here.
            actions=["REVIEW_BELOW"]
            + [a for a, s in (("SAVE", SAVED), ("REJECT", REJECTED)) if status != s],
            decision_history=[],
            evidence_moved=False,
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
        for packet in (
            *human_video_intake.list_packets(),
            *human_topic_search.list_packets(),
            *viral_radar.list_packets(),
        )
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
    for packet in (
        *human_video_intake.list_packets(),
        *human_topic_search.list_packets(),
        *viral_radar.list_packets(),
    ):
        if packet.get("opportunity_id") == opportunity_id:
            return packet
    return None


def _save_decision(
    state: dict[str, Any], packet: dict[str, Any], action: str, status: str | None, note: str
) -> None:
    opportunity_id = str(packet["opportunity_id"])
    entry = state["items"].get(opportunity_id) or {}
    history = list(entry.get("history") or [])
    history.append(
        {
            "action": action,
            "note": note.strip()[:500],
            "at": utc_now(),
            "packet_sha256": packet.get("packet_sha256"),
        }
    )
    if status is None:
        entry = {"history": history[-HISTORY_LIMIT:]}
    else:
        entry = {
            "status": status,
            "note": note.strip()[:500],
            "updated_at": utc_now(),
            "packet_sha256": packet.get("packet_sha256"),
            "history": history[-HISTORY_LIMIT:],
        }
    state["items"][opportunity_id] = entry


def apply_action(opportunity_id: str, action: str, note: str = "") -> None:
    """SAVE, REJECT, WATCH (radar only), REWORK (note required) or RESTORE an idea."""
    if action not in INBOX_ACTIONS:
        raise ValueError(f"Unsupported inbox action: {action}")
    if str(opportunity_id).startswith("opp_historical__"):
        raise ValueError("Historical opportunities are decided through the historical gate.")
    packet = _find_human_packet(opportunity_id)
    if packet is None:
        raise ValueError("Unknown opportunity.")
    if action == "WATCH" and packet.get("source_type") != models.SOURCE_VIRAL_RADAR:
        raise ValueError("Only viral-radar candidates can be watched.")
    if action == "REWORK" and not note.strip():
        raise ValueError("Say what evidence is missing: a rework needs a note.")
    if _is_active(packet, active_source.load_active()):
        raise ValueError("This idea is being analysed. Stop analysing it first.")
    if action == "REWORK":
        packet = _refresh_evidence(packet, note) or packet
    state = load_state()
    status = INBOX_ACTIONS[action]
    if action == "REWORK" and packet.get("source_type") == models.SOURCE_VIRAL_RADAR:
        status = WATCHING  # more evidence for a breakout means more snapshots
    _save_decision(state, packet, action, status, note)
    state["schema_version"] = SCHEMA_VERSION
    atomic_write_json(STATE_FILE, state)


def _refresh_evidence(packet: dict[str, Any], note: str) -> dict[str, Any] | None:
    """REWORK gathers fresh evidence where that is cheap and immediate."""
    source = packet.get("source_type")
    if source == models.SOURCE_HUMAN_VIDEO:
        video_id = packet["candidate_videos"][0]["video_id"]
        return human_video_intake.intake(
            human_video_intake.watch_url(video_id), note=note, topic=str(packet.get("topic") or "")
        )
    if source == models.SOURCE_HUMAN_TOPIC:
        return human_topic_search.explore(str(packet.get("title") or ""), note=note)
    return None  # radar: the next runs add snapshots


def record_decision(opportunity_id: str, action: str, note: str = "") -> None:
    """Record an APPROVE made through the analyze routes in the same history."""
    packet = _find_human_packet(opportunity_id)
    if packet is None:
        return
    state = load_state()
    _save_decision(state, packet, action, None, note)
    state["schema_version"] = SCHEMA_VERSION
    atomic_write_json(STATE_FILE, state)
