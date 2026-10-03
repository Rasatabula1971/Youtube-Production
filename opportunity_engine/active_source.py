"""The one active study set when it comes from a human seed (R9).

Experiment 02 reads a single approved study set. When the human chooses
"Analyze why it worked" on a HUMAN_VIDEO packet, or "Analyze these videos" on
a HUMAN_TOPIC packet, this module records it as the active source; the Human
Opportunity Gate then materialises it as the approved study set instead of a
historical topic. Approving a historical topic clears it again.

The study-set rows are frozen when the human decides (R8): re-measuring or
re-exploring later does not change or invalidate them. Only losing the packet
itself clears the decision.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import atomic_write_json  # noqa: E402

from opportunity_engine import human_topic_search, human_video_intake, models  # noqa: E402

HERE = Path(__file__).resolve().parent
ACTIVE_FILE = HERE / "output" / "active_study_source.json"
SCHEMA_VERSION = 1


HUMAN_HANDOFF_PREFIXES = ("human_video:", "human_topic:")


def study_row(
    packet: dict[str, Any],
    activated_at: str,
    *,
    video: dict[str, Any] | None = None,
    sequence: int = 1,
) -> dict[str, Any]:
    """Shape one human-seeded video like an approved 01.5 study-set row."""
    video = video or packet["candidate_videos"][0]
    video_id = str(video["video_id"])
    if packet["source_type"] == models.SOURCE_HUMAN_TOPIC:
        handoff_id = f"human_topic:{packet['intake']['topic_key']}:{video_id}"
        basis = "video found for your topic (Analyze these videos)"
        reason = "found by a human-seeded topic search; no historical demand gate applied"
    else:
        handoff_id = f"human_video:{video_id}"
        basis = "human-submitted video (Analyze why it worked)"
        reason = "submitted by the human; no historical demand gate applied"
    return {
        "experiment_id": packet["source_type"],
        "handoff_id": handoff_id,
        "gate_status": "HUMAN_SEEDED",
        "gate_reasons": [reason],
        "video_id": video_id,
        "youtube_url": video.get("youtube_url"),
        "title": video.get("title"),
        "channel_id": video.get("channel_id"),
        "channel_title": video.get("channel_title"),
        "published_at": video.get("published_at"),
        "age_days": video.get("age_days"),
        "duration_seconds": video.get("duration_seconds"),
        "format_candidate": models.format_candidate(video["format"]),
        "niche": packet.get("niche") or "everyday_science",
        "views": video.get("views"),
        "likes": video.get("likes"),
        "topic": packet.get("topic") or "human_video",
        "matched_families": [],
        "replicated_families": [],
        "study_set_sequence": sequence,
        "selection_basis": [basis],
        "human_opportunity_gate": {
            "opportunity_id": packet["opportunity_id"],
            "source_type": packet["source_type"],
            "decision": "APPROVE",
            "example_decision": "KEEP",
            "approved_at": activated_at,
        },
    }


def _check_route(packet: dict[str, Any], allow_excluded: bool) -> str | None:
    route = (packet.get("channel") or {}).get("route")
    if route == models.ROUTE_EXCLUDED and not allow_excluded:
        rule = (packet.get("channel") or {}).get("rule_id")
        raise ValueError(
            f"This idea is excluded by rule {rule}. Confirm the override to analyse it anyway."
        )
    return route


def set_active(video_id: str, *, allow_excluded: bool = False) -> dict[str, Any]:
    packet = human_video_intake.load_packet(video_id)
    if packet is None:
        raise ValueError("Submit this video first; no saved packet was found.")
    route = _check_route(packet, allow_excluded)
    activated_at = datetime.now(timezone.utc).isoformat()
    record = {
        "schema_version": SCHEMA_VERSION,
        "source_type": models.SOURCE_HUMAN_VIDEO,
        "opportunity_id": packet["opportunity_id"],
        "video_id": video_id,
        "title": packet.get("title"),
        "channel_route": route,
        "activated_at": activated_at,
        "study_set": [study_row(packet, activated_at)],
    }
    atomic_write_json(ACTIVE_FILE, record)
    return record


def select_topic_videos(packet: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    """Most-viewed relevant videos, capped per channel and in total."""
    per_channel = int(settings["max_study_videos_per_channel"])
    chosen: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for video in sorted(
        packet.get("candidate_videos") or [], key=lambda v: int(v.get("views") or 0), reverse=True
    ):
        channel = str(video.get("channel_id") or video.get("channel_title") or video["video_id"])
        if counts.get(channel, 0) >= per_channel:
            continue
        counts[channel] = counts.get(channel, 0) + 1
        chosen.append(video)
        if len(chosen) >= int(settings["max_study_videos"]):
            break
    return chosen


def set_active_topic(topic_key: str, *, allow_excluded: bool = False) -> dict[str, Any]:
    packet = human_topic_search.load_packet(topic_key)
    if packet is None:
        raise ValueError("Explore this topic first; no saved packet was found.")
    route = _check_route(packet, allow_excluded)
    videos = select_topic_videos(packet, human_topic_search.topic_config())
    if not videos:
        raise ValueError("This topic has no relevant videos to analyse yet.")
    activated_at = datetime.now(timezone.utc).isoformat()
    record = {
        "schema_version": SCHEMA_VERSION,
        "source_type": models.SOURCE_HUMAN_TOPIC,
        "opportunity_id": packet["opportunity_id"],
        "topic_key": topic_key,
        "title": packet.get("title"),
        "channel_route": route,
        "activated_at": activated_at,
        "study_set": [
            study_row(packet, activated_at, video=video, sequence=index)
            for index, video in enumerate(videos, start=1)
        ],
    }
    atomic_write_json(ACTIVE_FILE, record)
    return record


def clear_active() -> bool:
    if ACTIVE_FILE.exists():
        ACTIVE_FILE.unlink()
        return True
    return False


def load_active() -> dict[str, Any] | None:
    """The active record, or None when absent, unreadable or orphaned."""
    try:
        record = json.loads(ACTIVE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict) or record.get("schema_version") != SCHEMA_VERSION:
        return None
    rows = record.get("study_set")
    if not isinstance(rows, list) or not rows or not all(
        isinstance(row, dict) and row.get("video_id") for row in rows
    ):
        return None
    source = record.get("source_type")
    if source == models.SOURCE_HUMAN_VIDEO:
        video_id = str(record.get("video_id") or "")
        if len(rows) != 1 or rows[0].get("video_id") != video_id:
            return None
        packet = human_video_intake.load_packet(video_id)
    elif source == models.SOURCE_HUMAN_TOPIC:
        packet = human_topic_search.load_packet(str(record.get("topic_key") or ""))
    else:
        return None
    if packet is None or packet.get("opportunity_id") != record.get("opportunity_id"):
        return None
    return record


def summary(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not record:
        return None
    row = record["study_set"][0]
    return {
        "source_type": record.get("source_type"),
        "opportunity_id": record.get("opportunity_id"),
        "video_id": record.get("video_id"),
        "topic_key": record.get("topic_key"),
        "title": record.get("title"),
        "channel_title": row.get("channel_title"),
        "youtube_url": row.get("youtube_url"),
        "video_count": len(record["study_set"]),
        "activated_at": record.get("activated_at"),
    }
