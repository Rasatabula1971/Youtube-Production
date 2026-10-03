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

from opportunity_engine import (  # noqa: E402
    channel_scope,
    human_topic_search,
    human_video_intake,
    models,
    viral_radar,
)

HERE = Path(__file__).resolve().parent
ACTIVE_FILE = HERE / "output" / "active_study_source.json"
SCHEMA_VERSION = 1


HUMAN_HANDOFF_PREFIXES = ("human_video:", "human_topic:", "viral_radar:", "viral_cluster:")


def opportunity_context(packet: dict[str, Any]) -> dict[str, Any]:
    """What Experiment 02 is told about where a human-seeded or radar video came from.

    Context only: performance evidence never proves a creative mechanism.
    """
    viral = packet.get("viral_evidence") or {}
    metrics = viral.get("metrics") or {}
    cluster = viral.get("cluster") or {}
    seed = packet.get("seed") or {}
    context: dict[str, Any] = {
        "source_type": packet.get("source_type"),
        "opportunity_title": packet.get("title"),
        "seed_question": seed.get("question"),
        "seed_topic": seed.get("topic"),
        "channel_route": (packet.get("channel") or {}).get("route"),
        "human_notes": packet.get("human_notes") or [],
    }
    if viral:
        context["breakout"] = {
            "strength": viral.get("strength"),
            "trajectory": viral.get("trajectory"),
            "breadth": viral.get("breadth"),
            "channel_multiple": metrics.get("lifetime_ratio"),
            "views_per_hour_multiple": metrics.get("vph_ratio"),
            "ratio_basis": metrics.get("ratio_basis") or [],
            "age_hours": metrics.get("age_hours"),
            "theme": cluster.get("label"),
            "theme_kind": cluster.get("kind"),
            "theme_independent_channels": cluster.get("independent_channel_count"),
        }
    return context


def study_row(
    packet: dict[str, Any],
    activated_at: str,
    *,
    video: dict[str, Any] | None = None,
    sequence: int = 1,
    handoff_override: str | None = None,
    context_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Shape one human-seeded video like an approved 01.5 study-set row."""
    video = video or packet["candidate_videos"][0]
    video_id = str(video["video_id"])
    if packet["source_type"] == models.SOURCE_HUMAN_TOPIC:
        handoff_id = f"human_topic:{packet['intake']['topic_key']}:{video_id}"
        basis = "video found for your topic (Analyze these videos)"
        reason = "found by a human-seeded topic search; no historical demand gate applied"
    elif packet["source_type"] == models.SOURCE_VIRAL_RADAR:
        handoff_id = f"viral_radar:{video_id}"
        basis = "viral radar breakout chosen by the human (Analyze why it worked)"
        reason = "breakout against its own channel; no historical demand gate applied"
    else:
        handoff_id = f"human_video:{video_id}"
        basis = "human-submitted video (Analyze why it worked)"
        reason = "submitted by the human; no historical demand gate applied"
    handoff_id = handoff_override or handoff_id
    return {
        "experiment_id": packet["source_type"],
        "handoff_id": handoff_id,
        "opportunity_context": opportunity_context(context_packet or packet),
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


def set_active(
    video_id: str, *, allow_excluded: bool = False, source_type: str = models.SOURCE_HUMAN_VIDEO
) -> dict[str, Any]:
    """A single video (submitted by the human, or a radar breakout) as the study set."""
    if source_type == models.SOURCE_VIRAL_RADAR:
        packet = viral_radar.load_packet(video_id)
        missing = "Run the viral radar first; no saved packet was found for this video."
    else:
        packet = human_video_intake.load_packet(video_id)
        missing = "Submit this video first; no saved packet was found."
    if packet is None:
        raise ValueError(missing)
    route = _check_route(packet, allow_excluded)
    activated_at = datetime.now(timezone.utc).isoformat()
    record = {
        "schema_version": SCHEMA_VERSION,
        "source_type": source_type,
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


def set_active_cluster(cluster_id: str) -> dict[str, Any]:
    """A replicated radar theme: its strongest independent videos become the study set.

    Excluded breakouts never get packets, so no excluded video can be selected.
    """
    found = viral_radar.load_cluster(cluster_id)
    if found is None:
        raise ValueError("That theme is no longer in the latest radar run. Run the radar again.")
    settings = channel_scope.load_config()["viral_clustering"]
    members = sorted(
        (m for m in found.get("members") or [] if m.get("independence") == "INDEPENDENT"),
        key=lambda m: -(m.get("lifetime_ratio") or 0),
    )
    packets = [p for p in (viral_radar.load_packet(m["video_id"]) for m in members) if p]
    packets = packets[: int(settings["max_study_videos"])]
    if not packets:
        raise ValueError("None of this theme's videos has a saved radar packet.")
    activated_at = datetime.now(timezone.utc).isoformat()
    record = {
        "schema_version": SCHEMA_VERSION,
        "source_type": models.SOURCE_VIRAL_RADAR,
        "opportunity_id": "opp_viral_cluster__" + cluster_id,
        "cluster_id": cluster_id,
        "title": f"Theme: {found.get('label')} ({found.get('independent_channel_count')} channels)",
        "channel_route": models.ROUTE_ACTIVE,
        "activated_at": activated_at,
        "study_set": [
            study_row(
                packet,
                activated_at,
                sequence=index,
                handoff_override=f"viral_cluster:{cluster_id}:{packet['candidate_videos'][0]['video_id']}",
            )
            for index, packet in enumerate(packets, start=1)
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
    if source == models.SOURCE_VIRAL_RADAR and record.get("cluster_id"):
        # A theme: every frozen row must still have its radar packet.
        if any(viral_radar.load_packet(str(row["video_id"])) is None for row in rows):
            return None
        return record
    if source in (models.SOURCE_HUMAN_VIDEO, models.SOURCE_VIRAL_RADAR):
        video_id = str(record.get("video_id") or "")
        if len(rows) != 1 or rows[0].get("video_id") != video_id:
            return None
        loader = (
            viral_radar.load_packet
            if source == models.SOURCE_VIRAL_RADAR
            else human_video_intake.load_packet
        )
        packet = loader(video_id)
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
        "cluster_id": record.get("cluster_id"),
        "title": record.get("title"),
        "channel_title": row.get("channel_title"),
        "youtube_url": row.get("youtube_url"),
        "video_count": len(record["study_set"]),
        "activated_at": record.get("activated_at"),
    }
