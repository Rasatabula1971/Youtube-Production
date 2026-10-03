"""The one active study set when it comes from a human-submitted video (R9).

Experiment 02 reads a single approved study set. When the human chooses
"Analyze why it worked" on a HUMAN_VIDEO packet, this module records that
video as the active source; the Human Opportunity Gate then materialises it as
the approved study set instead of a historical topic. Approving a historical
topic clears it again.

The study-set row is frozen when the human decides (R8): re-measuring the video
later does not change or invalidate it. Only losing the packet itself (its
video was removed from the inbox) clears the decision.
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

from opportunity_engine import human_video_intake, models  # noqa: E402

HERE = Path(__file__).resolve().parent
ACTIVE_FILE = HERE / "output" / "active_study_source.json"
SCHEMA_VERSION = 1


def study_row(packet: dict[str, Any], activated_at: str) -> dict[str, Any]:
    """Shape one HUMAN_VIDEO packet like an approved 01.5 study-set row."""
    video = packet["candidate_videos"][0]
    video_id = str(video["video_id"])
    return {
        "experiment_id": "HUMAN_VIDEO",
        "handoff_id": f"human_video:{video_id}",
        "gate_status": "HUMAN_SEEDED",
        "gate_reasons": ["submitted by the human; no historical demand gate applied"],
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
        "study_set_sequence": 1,
        "selection_basis": ["human-submitted video (Analyze why it worked)"],
        "human_opportunity_gate": {
            "opportunity_id": packet["opportunity_id"],
            "source_type": models.SOURCE_HUMAN_VIDEO,
            "decision": "APPROVE",
            "example_decision": "KEEP",
            "approved_at": activated_at,
        },
    }


def set_active(video_id: str, *, allow_excluded: bool = False) -> dict[str, Any]:
    packet = human_video_intake.load_packet(video_id)
    if packet is None:
        raise ValueError("Submit this video first; no saved packet was found.")
    route = (packet.get("channel") or {}).get("route")
    if route == models.ROUTE_EXCLUDED and not allow_excluded:
        rule = (packet.get("channel") or {}).get("rule_id")
        raise ValueError(
            f"This video is excluded by rule {rule}. Confirm the override to analyse it anyway."
        )
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
    video_id = str(record.get("video_id") or "")
    if (
        not isinstance(rows, list)
        or len(rows) != 1
        or not isinstance(rows[0], dict)
        or rows[0].get("video_id") != video_id
    ):
        return None
    if human_video_intake.load_packet(video_id) is None:
        return None
    return record


def summary(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not record:
        return None
    row = record["study_set"][0]
    return {
        "opportunity_id": record.get("opportunity_id"),
        "video_id": record.get("video_id"),
        "title": record.get("title"),
        "channel_title": row.get("channel_title"),
        "youtube_url": row.get("youtube_url"),
        "activated_at": record.get("activated_at"),
    }
