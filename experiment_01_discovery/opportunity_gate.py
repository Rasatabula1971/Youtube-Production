"""Human opportunity gate between Experiment 01.5 and Experiment 02.

The machine-generated study set remains immutable evidence. Human decisions are
stored separately and only an explicitly approved study set may enter
Experiment 02.
"""

from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_INTEGRITY_ROOT = Path(__file__).resolve().parent.parent
if str(_INTEGRITY_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEGRITY_ROOT))

from pipeline_integrity import atomic_write_json

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output" / "experiment_01_5"
STUDY_SET_FILE = OUTPUT_DIR / "study_set.json"
HANDOFF_PACKETS_FILE = OUTPUT_DIR / "handoff_packets.json"
DECISION_FILE = OUTPUT_DIR / "human_opportunity_decision.json"
APPROVED_STUDY_SET_FILE = OUTPUT_DIR / "approved_study_set.json"
VIDIQ_ENRICHMENT_FILE = HERE / "output" / "vidiq" / "opportunity_enrichment.json"

SCHEMA_VERSION = "1.1"

TOPIC_ACTIONS = {
    "APPROVE_TOPIC",
    "REJECT_TOPIC",
    "HOLD_TOPIC",
}
VIDEO_ACTIONS = {
    "KEEP_EXAMPLE",
    "REPLACE_EXAMPLE",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def opportunity_id(
    topic: str,
    fmt: str,
    niche: str = "",
) -> str:
    return f"{niche}:{topic}:{fmt}" if niche else f"{topic}:{fmt}"


def _group_study_set(study_set: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for item in study_set:
        topic = str(item.get("topic") or "").strip()
        niche = str(item.get("niche") or "").strip()
        fmt = str(item.get("format_candidate") or "").strip()
        if not topic or not fmt:
            continue

        key = opportunity_id(topic, fmt, niche)
        if key not in grouped:
            grouped[key] = {
                "opportunity_id": key,
                "topic": topic,
                "niche": niche,
                "format_candidate": fmt,
                "items": [],
            }
            order.append(key)
        grouped[key]["items"].append(item)

    return [grouped[key] for key in order]


def _fresh_state(study_set: list[dict[str, Any]]) -> dict[str, Any]:
    opportunities: dict[str, Any] = {}

    for group in _group_study_set(study_set):
        selected_ids = [
            str(item.get("video_id")) for item in group["items"] if item.get("video_id")
        ]
        opportunities[group["opportunity_id"]] = {
            "topic": group["topic"],
            "niche": group.get("niche", ""),
            "format_candidate": group["format_candidate"],
            "decision": "PENDING",
            "selected_video_ids": selected_ids,
            "video_decisions": {video_id: "PENDING" for video_id in selected_ids},
            "replacement_history": [],
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "source_study_set_sha256": canonical_sha256(study_set),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "opportunities": opportunities,
    }


def load_state(study_set: list[dict[str, Any]]) -> dict[str, Any]:
    source_hash = canonical_sha256(study_set)
    if DECISION_FILE.exists():
        try:
            state = load_json(DECISION_FILE)
        except (OSError, json.JSONDecodeError):
            state = None
        if (
            isinstance(state, dict)
            and state.get("schema_version") == SCHEMA_VERSION
            and state.get("source_study_set_sha256") == source_hash
            and isinstance(state.get("opportunities"), dict)
        ):
            return state

    return _fresh_state(study_set)


def save_state(state: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now()
    atomic_write_json(DECISION_FILE, state)


def _vidiq_payload(study_set: list[dict[str, Any]]) -> dict[str, Any]:
    if not VIDIQ_ENRICHMENT_FILE.exists():
        return {}
    try:
        payload = load_json(VIDIQ_ENRICHMENT_FILE)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    if payload.get("source_study_set_sha256") != canonical_sha256(study_set):
        return {}
    return payload


def _packet_lookup(
    study_set: list[dict[str, Any]],
    packets: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for item in [*packets, *study_set]:
        video_id = str(item.get("video_id") or "").strip()
        if video_id:
            lookup[video_id] = item
    return lookup


def _pass_candidates(
    packets: list[dict[str, Any]],
    topic: str,
    fmt: str,
    niche: str = "",
) -> list[dict[str, Any]]:
    candidates = [
        item
        for item in packets
        if item.get("gate_status") == "PASS"
        and str(item.get("topic")) == topic
        and str(item.get("format_candidate")) == fmt
        and (not niche or str(item.get("niche") or "") == niche)
        and item.get("video_id")
    ]

    def sort_key(item: dict[str, Any]) -> tuple[float, int, str]:
        metric = item.get("primary_metric", {}).get("value")
        metric_value = float(metric) if metric is not None else float("-inf")
        return (
            -metric_value,
            -int(item.get("views") or 0),
            str(item.get("video_id") or ""),
        )

    return sorted(candidates, key=sort_key)


def _replacement_candidate(
    *,
    opportunity: dict[str, Any],
    packets: list[dict[str, Any]],
    replaced_video_id: str,
) -> dict[str, Any] | None:
    selected_ids = [
        str(video_id)
        for video_id in opportunity.get("selected_video_ids", [])
        if str(video_id) != replaced_video_id
    ]
    used_ids = set(selected_ids)
    used_ids.update(str(value) for value in opportunity.get("replacement_history", []))

    lookup = {
        str(item.get("video_id")): item for item in packets if item.get("video_id")
    }
    used_channels = {
        str(lookup[video_id].get("channel_id"))
        for video_id in selected_ids
        if video_id in lookup and lookup[video_id].get("channel_id")
    }

    for candidate in _pass_candidates(
        packets,
        str(opportunity.get("topic") or ""),
        str(opportunity.get("format_candidate") or ""),
        str(opportunity.get("niche") or ""),
    ):
        video_id = str(candidate.get("video_id") or "")
        channel_id = str(candidate.get("channel_id") or "")
        if not video_id or video_id == replaced_video_id or video_id in used_ids:
            continue
        if channel_id and channel_id in used_channels:
            continue
        return candidate
    return None


def _all_examples_kept(opportunity: dict[str, Any]) -> bool:
    selected = [str(video_id) for video_id in opportunity.get("selected_video_ids", [])]
    decisions = opportunity.get("video_decisions", {})
    return bool(selected) and all(
        decisions.get(video_id) == "KEEP" for video_id in selected
    )


def _materialize_approved(
    state: dict[str, Any],
    study_set: list[dict[str, Any]],
    packets: list[dict[str, Any]],
) -> tuple[bool, list[dict[str, Any]]]:
    opportunities = state.get("opportunities", {})
    decisions = [
        str(item.get("decision") or "PENDING")
        for item in opportunities.values()
        if isinstance(item, dict)
    ]
    gate_complete = bool(decisions) and all(
        decision in {"APPROVE", "REJECT", "HOLD"} for decision in decisions
    )

    lookup = _packet_lookup(study_set, packets)
    approved: list[dict[str, Any]] = []

    if gate_complete:
        sequence = 0
        for key, opportunity in opportunities.items():
            if opportunity.get("decision") != "APPROVE":
                continue
            if not _all_examples_kept(opportunity):
                gate_complete = False
                approved = []
                break

            for video_id in opportunity.get("selected_video_ids", []):
                video_id = str(video_id)
                item = lookup.get(video_id)
                if not item:
                    gate_complete = False
                    approved = []
                    break

                sequence += 1
                row = deepcopy(item)
                row["study_set_sequence"] = sequence
                row["human_opportunity_gate"] = {
                    "opportunity_id": key,
                    "decision": "APPROVE",
                    "example_decision": "KEEP",
                    "approved_at": state.get("updated_at"),
                }
                approved.append(row)

            if not gate_complete:
                break

    ready = gate_complete and bool(approved)

    if ready:
        atomic_write_json(APPROVED_STUDY_SET_FILE, approved)
    elif APPROVED_STUDY_SET_FILE.exists():
        APPROVED_STUDY_SET_FILE.unlink()

    return ready, approved


def gate_snapshot() -> dict[str, Any]:
    if not STUDY_SET_FILE.exists():
        return {
            "status": "WAITING_FOR_01_5",
            "ready_for_experiment_02": False,
            "gate_complete": False,
            "opportunities": [],
        }

    study_set = load_json(STUDY_SET_FILE)
    if not isinstance(study_set, list) or not study_set:
        return {
            "status": "NO_STUDY_SET",
            "ready_for_experiment_02": False,
            "gate_complete": False,
            "opportunities": [],
        }

    packets = load_json(HANDOFF_PACKETS_FILE) if HANDOFF_PACKETS_FILE.exists() else []
    if not isinstance(packets, list):
        packets = []

    vidiq_payload = _vidiq_payload(study_set)
    vidiq_opportunities = vidiq_payload.get("opportunities", {})
    if not isinstance(vidiq_opportunities, dict):
        vidiq_opportunities = {}

    state = load_state(study_set)
    ready, approved = _materialize_approved(
        state,
        study_set,
        packets,
    )

    lookup = _packet_lookup(study_set, packets)
    opportunities_payload = []

    for key, opportunity in state.get("opportunities", {}).items():
        if not isinstance(opportunity, dict):
            continue

        selected_examples = []
        for video_id in opportunity.get("selected_video_ids", []):
            video_id = str(video_id)
            item = lookup.get(video_id, {})
            selected_examples.append(
                {
                    "video_id": video_id,
                    "title": item.get("title"),
                    "youtube_url": item.get("youtube_url"),
                    "channel_id": item.get("channel_id"),
                    "channel_title": item.get("channel_title"),
                    "views": item.get("views"),
                    "likes": item.get("likes"),
                    "age_days": item.get("age_days"),
                    "duration_seconds": item.get("duration_seconds"),
                    "matched_families": item.get("matched_families", []),
                    "replicated_families": item.get("replicated_families", []),
                    "decision": opportunity.get("video_decisions", {}).get(
                        video_id,
                        "PENDING",
                    ),
                }
            )

        alternatives = _pass_candidates(
            packets,
            str(opportunity.get("topic") or ""),
            str(opportunity.get("format_candidate") or ""),
            str(opportunity.get("niche") or ""),
        )
        selected_ids = {
            str(video_id) for video_id in opportunity.get("selected_video_ids", [])
        }
        alternative_count = sum(
            str(item.get("video_id")) not in selected_ids for item in alternatives
        )

        first = selected_examples[0] if selected_examples else {}
        first_source = lookup.get(str(first.get("video_id") or ""), {})
        topic_evidence = first_source.get("topic_evidence") or {}

        opportunities_payload.append(
            {
                "opportunity_id": key,
                "topic": opportunity.get("topic"),
                "niche": opportunity.get("niche"),
                "format_candidate": opportunity.get("format_candidate"),
                "decision": opportunity.get("decision", "PENDING"),
                "can_approve": _all_examples_kept(opportunity),
                "alternatives_available": alternative_count,
                "topic_evidence": topic_evidence,
                "vidiq_evidence": vidiq_opportunities.get(key, {}),
                "selected_examples": selected_examples,
            }
        )

    decisions = [
        str(item.get("decision") or "PENDING")
        for item in state.get("opportunities", {}).values()
        if isinstance(item, dict)
    ]
    gate_complete = bool(decisions) and all(
        decision in {"APPROVE", "REJECT", "HOLD"} for decision in decisions
    )

    if ready:
        status = "APPROVED"
    elif gate_complete:
        status = "COMPLETE_NO_APPROVED_TOPIC"
    else:
        status = "AWAITING_HUMAN_DECISION"

    return {
        "status": status,
        "ready_for_experiment_02": ready,
        "gate_complete": gate_complete,
        "approved_video_count": len(approved),
        "source_study_set_sha256": state.get("source_study_set_sha256"),
        "decision_file": str(DECISION_FILE),
        "approved_study_set": str(APPROVED_STUDY_SET_FILE),
        "vidiq": {
            "status": vidiq_payload.get("status") if vidiq_payload else "NOT_RUN",
            "provider_remaining_credits": (
                vidiq_payload.get("provider_remaining_credits")
                if vidiq_payload
                else None
            ),
            "local_charged_credits": (
                vidiq_payload.get("local_charged_credits")
                if vidiq_payload
                else None
            ),
            "hard_credit_cap": (
                vidiq_payload.get("hard_credit_cap")
                if vidiq_payload
                else 149
            ),
            "paid_calls_this_run": (
                vidiq_payload.get("paid_calls_this_run")
                if vidiq_payload
                else 0
            ),
        },
        "opportunities": opportunities_payload,
    }


def apply_gate_action(
    *,
    action: str,
    opportunity_key: str,
    video_id: str | None = None,
) -> dict[str, Any]:
    if action not in TOPIC_ACTIONS | VIDEO_ACTIONS:
        raise ValueError(f"Unsupported opportunity-gate action: {action}")

    study_set = load_json(STUDY_SET_FILE)
    if not isinstance(study_set, list) or not study_set:
        raise ValueError("Experiment 01.5 study set is missing or empty.")

    packets = load_json(HANDOFF_PACKETS_FILE) if HANDOFF_PACKETS_FILE.exists() else []
    if not isinstance(packets, list):
        packets = []

    state = load_state(study_set)
    opportunities = state.get("opportunities", {})
    opportunity = opportunities.get(opportunity_key)
    if not isinstance(opportunity, dict):
        raise ValueError("Unknown opportunity.")

    if action == "KEEP_EXAMPLE":
        if not video_id or video_id not in opportunity.get("selected_video_ids", []):
            raise ValueError("The selected example is not part of this opportunity.")
        opportunity.setdefault("video_decisions", {})[video_id] = "KEEP"
        if opportunity.get("decision") == "APPROVE":
            opportunity["decision"] = "PENDING"

    elif action == "REPLACE_EXAMPLE":
        if not video_id or video_id not in opportunity.get("selected_video_ids", []):
            raise ValueError("The selected example is not part of this opportunity.")

        replacement = _replacement_candidate(
            opportunity=opportunity,
            packets=packets,
            replaced_video_id=video_id,
        )
        if replacement is None:
            raise ValueError("No additional PASS example is available for replacement.")

        replacement_id = str(replacement["video_id"])
        selected = list(opportunity.get("selected_video_ids", []))
        index = selected.index(video_id)
        selected[index] = replacement_id
        opportunity["selected_video_ids"] = selected

        opportunity.setdefault("replacement_history", []).append(video_id)
        decisions = opportunity.setdefault("video_decisions", {})
        decisions.pop(video_id, None)
        decisions[replacement_id] = "PENDING"
        opportunity["decision"] = "PENDING"

    elif action == "APPROVE_TOPIC":
        if not _all_examples_kept(opportunity):
            raise ValueError(
                "Review every selected example first. Mark each one KEEP or replace it."
            )
        opportunity["decision"] = "APPROVE"

    elif action == "REJECT_TOPIC":
        opportunity["decision"] = "REJECT"

    elif action == "HOLD_TOPIC":
        opportunity["decision"] = "HOLD"

    save_state(state)
    _materialize_approved(state, study_set, packets)
    return gate_snapshot()
