"""Market-intelligence helpers for Experiment 01.2.

Adds transparent query competition profiles, repeated-snapshot velocity,
and topic-level evidence aggregation. No final opportunity score is produced.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VELOCITY_NO_PRIOR = "NO_PRIOR"
VELOCITY_VALID = "VALID"
VELOCITY_NEGATIVE_ADJUSTMENT = "NEGATIVE_ADJUSTMENT"


def _median_or_none(values: list[float | int]) -> float | None:
    if not values:
        return None
    return round(float(statistics.median(values)), 2)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_query_competition_profile(
    *,
    query: str,
    video_ids: list[str],
    details: dict[str, dict[str, Any]],
    channels: dict[str, dict[str, Any]],
    now: datetime | None = None,
    recent_days: int = 365,
    large_channel_subscribers: int = 1_000_000,
) -> dict[str, Any]:
    """Describe the search surface without collapsing it into one score."""

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    items = [details[video_id] for video_id in video_ids if video_id in details]

    views: list[int] = []
    subscribers: list[int] = []
    channel_ids: list[str] = []
    recent_count = 0
    large_channel_count = 0

    for item in items:
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        channel_id = snippet.get("channelId")
        if channel_id:
            channel_ids.append(channel_id)

        try:
            views.append(int(stats.get("viewCount", 0) or 0))
        except (TypeError, ValueError):
            pass

        channel = channels.get(channel_id or "", {})
        channel_stats = channel.get("statistics", {})
        try:
            subscriber_count = int(channel_stats.get("subscriberCount", 0) or 0)
        except (TypeError, ValueError):
            subscriber_count = 0

        subscribers.append(subscriber_count)
        if subscriber_count >= large_channel_subscribers:
            large_channel_count += 1

        published_at = snippet.get("publishedAt")
        if published_at:
            try:
                age_days = (now - _parse_time(published_at)).total_seconds() / 86400
            except ValueError:
                age_days = None
            if age_days is not None and age_days <= recent_days:
                recent_count += 1

    detail_count = len(items)
    channel_counts = Counter(channel_ids)
    top_counts = sorted(channel_counts.values(), reverse=True)

    return {
        "query": query,
        "search_order": "viewCount",
        "result_position_semantics": (
            "position_in_viewCount_ordered_API_results;"
            "not_organic_relevance_rank"
        ),
        "results_returned": len(video_ids),
        "results_with_details": detail_count,
        "unique_channels": len(channel_counts),
        "unique_channel_ratio": (
            round(len(channel_counts) / detail_count, 4)
            if detail_count else None
        ),
        "top_channel_share": (
            round(top_counts[0] / detail_count, 4)
            if detail_count and top_counts else None
        ),
        "top3_channel_share": (
            round(sum(top_counts[:3]) / detail_count, 4)
            if detail_count and top_counts else None
        ),
        "median_views": _median_or_none(views),
        "median_channel_subscribers": _median_or_none(subscribers),
        "large_channel_share": (
            round(large_channel_count / detail_count, 4)
            if detail_count else None
        ),
        "recent_result_share": (
            round(recent_count / detail_count, 4)
            if detail_count else None
        ),
        "profile_parameters": {
            "recent_days": recent_days,
            "large_channel_subscribers": large_channel_subscribers,
        },
    }


def enrich_query_profiles_with_evidence(
    profiles: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach analyzed >=500K evidence counts to query profiles."""

    rows_by_query: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for match in row.get("query_matches", []):
            niche = str(match.get("niche", ""))
            query = str(match.get("query", ""))
            if query:
                rows_by_query[(niche, query)].append(row)

    result: list[dict[str, Any]] = []
    for profile in profiles:
        query = profile["query"]
        niche = str(profile.get("niche", ""))
        matched = rows_by_query.get((niche, query), [])
        trusted_ratios = [
            float(row["outlier_ratio"])
            for row in matched
            if row.get("outlier_reliability") == "TRUSTED"
            and row.get("outlier_ratio") is not None
        ]

        result.append(
            {
                **profile,
                "analyzed_500k_plus": len(matched),
                "on_intent_500k_plus": sum(
                    row.get("relevance") == "ON_INTENT"
                    for row in matched
                ),
                "adjacent_500k_plus": sum(
                    row.get("relevance") == "ADJACENT"
                    for row in matched
                ),
                "off_intent_500k_plus": sum(
                    row.get("relevance") == "OFF_INTENT"
                    for row in matched
                ),
                "trusted_outlier_observations": sum(
                    row.get("outlier_reliability") == "TRUSTED"
                    for row in matched
                ),
                "caution_outlier_observations": sum(
                    row.get("outlier_reliability") == "CAUTION"
                    for row in matched
                ),
                "median_trusted_outlier_ratio": _median_or_none(trusted_ratios),
            }
        )

    return result


def load_snapshot_history(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Load JSONL snapshots, ignoring malformed lines rather than failing a run."""

    history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not path.exists():
        return {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        video_id = item.get("video_id")
        observed_at = item.get("observed_at")
        views = item.get("views")
        if not video_id or not observed_at:
            continue
        try:
            views = int(views)
            _parse_time(observed_at)
        except (TypeError, ValueError):
            continue
        history[str(video_id)].append(
            {
                "video_id": str(video_id),
                "observed_at": str(observed_at),
                "views": views,
            }
        )

    for snapshots in history.values():
        snapshots.sort(key=lambda item: _parse_time(item["observed_at"]))

    return dict(history)


def calculate_snapshot_velocity(
    *,
    video_id: str,
    current_views: int,
    observed_at: str,
    history: dict[str, list[dict[str, Any]]],
    minimum_interval_hours: float = 1.0,
) -> dict[str, Any]:
    """Calculate actual view accumulation between two API observations."""

    current_time = _parse_time(observed_at)
    minimum_seconds = minimum_interval_hours * 3600

    eligible: list[dict[str, Any]] = []
    for snapshot in history.get(video_id, []):
        previous_time = _parse_time(snapshot["observed_at"])
        elapsed = (current_time - previous_time).total_seconds()
        if elapsed >= minimum_seconds:
            eligible.append(snapshot)

    if not eligible:
        return {
            "velocity_status": VELOCITY_NO_PRIOR,
            "velocity_previous_at": None,
            "velocity_previous_views": None,
            "velocity_interval_hours": None,
            "view_delta_since_snapshot": None,
            "current_views_per_hour": None,
            "current_views_per_day": None,
        }

    previous = eligible[-1]
    previous_time = _parse_time(previous["observed_at"])
    interval_hours = (current_time - previous_time).total_seconds() / 3600
    delta = int(current_views) - int(previous["views"])

    if delta < 0:
        return {
            "velocity_status": VELOCITY_NEGATIVE_ADJUSTMENT,
            "velocity_previous_at": previous["observed_at"],
            "velocity_previous_views": int(previous["views"]),
            "velocity_interval_hours": round(interval_hours, 2),
            "view_delta_since_snapshot": delta,
            "current_views_per_hour": None,
            "current_views_per_day": None,
        }

    per_hour = delta / interval_hours
    return {
        "velocity_status": VELOCITY_VALID,
        "velocity_previous_at": previous["observed_at"],
        "velocity_previous_views": int(previous["views"]),
        "velocity_interval_hours": round(interval_hours, 2),
        "view_delta_since_snapshot": delta,
        "current_views_per_hour": round(per_hour, 2),
        "current_views_per_day": round(per_hour * 24, 2),
    }


def append_snapshots(
    path: Path,
    rows: list[dict[str, Any]],
    observed_at: str,
) -> None:
    """Append one immutable view snapshot per analyzed video."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    {
                        "video_id": row["video_id"],
                        "observed_at": observed_at,
                        "views": int(row["views"]),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def _aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    views = [int(row["views"]) for row in rows]
    all_outliers = [
        float(row["outlier_ratio"])
        for row in rows
        if row.get("outlier_ratio") is not None
    ]
    trusted_outliers = [
        float(row["outlier_ratio"])
        for row in rows
        if row.get("outlier_reliability") == "TRUSTED"
        and row.get("outlier_ratio") is not None
    ]
    velocity_values = [
        float(row["current_views_per_day"])
        for row in rows
        if row.get("current_views_per_day") is not None
    ]

    return {
        "video_count": len(rows),
        "unique_channels": len(
            {
                row.get("channel_id")
                for row in rows
                if row.get("channel_id")
            }
        ),
        "on_intent_count": sum(
            row.get("relevance") == "ON_INTENT"
            for row in rows
        ),
        "adjacent_count": sum(
            row.get("relevance") == "ADJACENT"
            for row in rows
        ),
        "trusted_outlier_count": sum(
            row.get("outlier_reliability") == "TRUSTED"
            for row in rows
        ),
        "caution_outlier_count": sum(
            row.get("outlier_reliability") == "CAUTION"
            for row in rows
        ),
        "median_views": _median_or_none(views),
        "median_outlier_ratio": _median_or_none(all_outliers),
        "median_trusted_outlier_ratio": _median_or_none(trusted_outliers),
        "velocity_sample_count": len(velocity_values),
        "median_current_views_per_day": _median_or_none(velocity_values),
    }


def aggregate_topic_evidence(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate repeatable topic evidence, keeping Shorts/long-form separate."""

    topic_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    topic_format_rows: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        if row.get("relevance") == "OFF_INTENT":
            continue
        for topic in row.get("topics", []):
            topic_rows[topic].append(row)
            topic_format_rows[(topic, row.get("format_candidate", "unknown"))].append(row)

    result: dict[str, Any] = {}
    for topic in sorted(topic_rows):
        by_format: dict[str, Any] = {}
        for (topic_name, format_name), group in topic_format_rows.items():
            if topic_name == topic:
                by_format[format_name] = _aggregate_rows(group)

        result[topic] = {
            "overall": _aggregate_rows(topic_rows[topic]),
            "by_format": dict(sorted(by_format.items())),
        }

    return result
