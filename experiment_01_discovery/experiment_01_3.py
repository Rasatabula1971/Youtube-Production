"""Stage 2 Experiment 01.3 — Age-Matched Velocity Validation.

Discover a fixed cohort of motorsport-engineering videos at roughly the same
age, then refresh only those exact video IDs to measure current velocity.
Shorts and long-form candidates are benchmarked separately. No final score.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from evidence_quality import classify_outlier_reliability
from market_intelligence import append_snapshots, calculate_snapshot_velocity, load_snapshot_history
from youtube_discovery import (
    age_days,
    api_get,
    baseline_confidence,
    baseline_warning,
    calculate_channel_baseline,
    classify_format_candidate,
    get_channel_details,
    get_recent_upload_ids,
    get_video_details,
    load_env_file,
    parse_duration_seconds,
)

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
ENV_FILE = PROJECT_ROOT / ".env"
CONFIG_FILE = HERE / "experiment_01_3_config.json"
OUTPUT_DIR = HERE / "output" / "experiment_01_3"
MANIFEST_FILE = OUTPUT_DIR / "cohort_manifest.json"
SNAPSHOT_FILE = OUTPUT_DIR / "video_snapshots.jsonl"
CANDIDATES_FILE = OUTPUT_DIR / "candidates.csv"
RAW_FILE = OUTPUT_DIR / "raw_results.json"
REJECTED_FILE = OUTPUT_DIR / "rejected_candidates.json"
TOPIC_FILE = OUTPUT_DIR / "topic_velocity.json"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"
EXPERIMENT_ID = "01.3"


def median_or_none(values: list[float | int]) -> float | None:
    return round(float(statistics.median(values)), 2) if values else None


def normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def contains_term(text: str, term: str) -> bool:
    text = normalize(text)
    term = normalize(term)
    if not term:
        return False
    pattern = re.escape(term)
    if term[0].isalnum():
        pattern = r"(?<!\w)" + pattern
    if term[-1].isalnum():
        pattern += r"(?!\w)"
    return re.search(pattern, text) is not None


def matching_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if contains_term(text, term)]


def format_rfc3339(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def calculate_age_window(
    observed_at: datetime,
    target_age_days: int = 120,
    tolerance_days: int = 15,
) -> dict[str, Any]:
    if target_age_days <= 0:
        raise ValueError("target_age_days must be greater than zero")
    if tolerance_days < 0 or tolerance_days >= target_age_days:
        raise ValueError("invalid age tolerance")

    observed_at = observed_at.astimezone(timezone.utc)
    minimum_age = target_age_days - tolerance_days
    maximum_age = target_age_days + tolerance_days
    return {
        "target_age_days": target_age_days,
        "tolerance_days": tolerance_days,
        "minimum_age_days": minimum_age,
        "maximum_age_days": maximum_age,
        "published_after": format_rfc3339(observed_at - timedelta(days=maximum_age)),
        "published_before": format_rfc3339(observed_at - timedelta(days=minimum_age)),
    }


def classify_topic_relevance(
    title: str,
    topic_terms: list[str],
    motorsport_context_terms: list[str],
    exclude_title_terms: list[str] | None = None,
) -> dict[str, Any]:
    """Strict title-only topic validation for Experiment 01.3."""

    excluded = matching_terms(title, exclude_title_terms or [])
    topic_matches = matching_terms(title, topic_terms)
    context_matches = matching_terms(title, motorsport_context_terms)

    if excluded:
        return {
            "topic_relevance": "OFF_TOPIC",
            "topic_relevance_reason": "excluded_title_term",
            "topic_term_matches": topic_matches,
            "motorsport_context_matches": context_matches,
            "excluded_title_matches": excluded,
        }
    if not topic_matches:
        return {
            "topic_relevance": "OFF_TOPIC",
            "topic_relevance_reason": "missing_topic_term_in_title",
            "topic_term_matches": [],
            "motorsport_context_matches": context_matches,
            "excluded_title_matches": [],
        }
    if not context_matches:
        return {
            "topic_relevance": "OFF_TOPIC",
            "topic_relevance_reason": "missing_motorsport_context_in_title",
            "topic_term_matches": topic_matches,
            "motorsport_context_matches": [],
            "excluded_title_matches": [],
        }
    return {
        "topic_relevance": "ON_TOPIC",
        "topic_relevance_reason": "title_topic_and_motorsport_context",
        "topic_term_matches": topic_matches,
        "motorsport_context_matches": context_matches,
        "excluded_title_matches": [],
    }

def confidence_from_unique_channels(count: int) -> str:
    if count >= 5:
        return "STRONG"
    if count >= 3:
        return "MODERATE"
    if count >= 1:
        return "LOW"
    return "INSUFFICIENT"


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result = []
    for row in rows:
        video_id = str(row.get("video_id", ""))
        if video_id and video_id not in seen:
            seen.add(video_id)
            result.append(row)
    return result


def aggregate_age_matched_velocity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = dedupe_rows([row for row in rows if row.get("topic_relevance") == "ON_TOPIC"])

    cohort_values: dict[str, list[float]] = defaultdict(list)
    for row in eligible:
        if row.get("current_views_per_day") is not None:
            cohort_values[str(row.get("format_candidate", "unknown"))].append(
                float(row["current_views_per_day"])
            )
    cohort_medians = {fmt: median_or_none(values) for fmt, values in cohort_values.items()}

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        for topic in row.get("validated_topics", []):
            grouped[(str(topic), str(row.get("format_candidate", "unknown")))].append(row)

    topics: dict[str, Any] = {}
    for (topic, fmt), group in sorted(grouped.items()):
        group = dedupe_rows(group)
        velocities = [float(r["current_views_per_day"]) for r in group if r.get("current_views_per_day") is not None]
        ages = [float(r["age_days"]) for r in group if r.get("age_days") is not None]
        views = [int(r["views"]) for r in group if r.get("views") is not None]
        trusted = [
            float(r["outlier_ratio"])
            for r in group
            if r.get("outlier_reliability") == "TRUSTED" and r.get("outlier_ratio") is not None
        ]
        unique_channels = len({r.get("channel_id") for r in group if r.get("channel_id")})
        topic_median = median_or_none(velocities)
        cohort_median = cohort_medians.get(fmt)
        index = None
        if topic_median is not None and cohort_median is not None and cohort_median > 0:
            index = round(topic_median / cohort_median, 3)

        topics.setdefault(topic, {"by_format": {}})["by_format"][fmt] = {
            "video_count": len(group),
            "unique_channels": unique_channels,
            "confidence": confidence_from_unique_channels(unique_channels),
            "velocity_sample_count": len(velocities),
            "median_age_days": median_or_none(ages),
            "median_views": median_or_none(views),
            "median_current_views_per_day": topic_median,
            "cohort_median_current_views_per_day": cohort_median,
            "age_matched_velocity_index": index,
            "trusted_outlier_count": len(trusted),
            "median_trusted_outlier_ratio": median_or_none(trusted),
        }

    return {
        "cohort_median_current_views_per_day_by_format": cohort_medians,
        "topics": topics,
    }


def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        raise SystemExit(f"Cannot find {CONFIG_FILE}")
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    required = {
        "target_age_days",
        "age_tolerance_days",
        "minimum_views",
        "search_orders",
        "expansion_search_orders",
        "search_profiles",
        "wide_age_tolerance_days",
        "minimum_unique_channels_per_topic_format",
        "motorsport_context_terms",
        "topics",
    }
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit("Experiment 01.3 config is missing: " + ", ".join(missing))
    return config


def load_api_key() -> str:
    load_env_file(ENV_FILE)
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise SystemExit(f"YOUTUBE_API_KEY not found in {ENV_FILE}")
    return api_key


def discover(
    config: dict[str, Any],
    api_key: str,
    age_window: dict[str, Any],
    max_searches: int,
    region_code: str | None,
    language: str | None,
    *,
    search_orders: list[str] | None = None,
    topic_format_targets: dict[str, set[str]] | None = None,
    search_phase: str = "strict",
    calls_already: int = 0,
) -> tuple[dict[str, set[str]], dict[str, list[dict[str, Any]]], list[dict[str, Any]], int]:
    """Search one age window using format-specific YouTube duration branches."""

    discovered: dict[str, set[str]] = {}
    matches: dict[str, list[dict[str, Any]]] = {}
    audit: list[dict[str, Any]] = []
    calls = 0
    orders = list(search_orders or config["search_orders"])
    search_profiles = config["search_profiles"]

    for topic in config["topics"]:
        topic_name = str(topic["topic"])
        target_formats = (
            sorted(topic_format_targets.get(topic_name, set()))
            if topic_format_targets is not None
            else sorted(search_profiles)
        )
        if not target_formats:
            continue

        for query in topic["queries"]:
            for format_target in target_formats:
                duration_filters = list(search_profiles.get(format_target, []))
                for video_duration in duration_filters:
                    for order in orders:
                        if calls_already + calls >= max_searches:
                            return discovered, matches, audit, calls

                        params: dict[str, Any] = {
                            "part": "snippet",
                            "q": query,
                            "type": "video",
                            "order": order,
                            "maxResults": 50,
                            "publishedAfter": age_window["published_after"],
                            "publishedBefore": age_window["published_before"],
                            "videoDuration": video_duration,
                        }
                        if region_code:
                            params["regionCode"] = region_code
                        if language:
                            params["relevanceLanguage"] = language

                        print(
                            f"  {topic_name}: {query} "
                            f"[{format_target}; duration={video_duration}; order={order}; phase={search_phase}]"
                        )
                        data = api_get("search", api_key, **params)
                        calls += 1

                        ids = []
                        for rank, item in enumerate(data.get("items", []), start=1):
                            video_id = item.get("id", {}).get("videoId")
                            if not video_id:
                                continue
                            ids.append(video_id)
                            discovered.setdefault(video_id, set()).add(topic_name)
                            matches.setdefault(video_id, []).append(
                                {
                                    "target_topic": topic_name,
                                    "query": query,
                                    "search_order": order,
                                    "search_phase": search_phase,
                                    "search_format_target": format_target,
                                    "video_duration_filter": video_duration,
                                    "rank": rank,
                                }
                            )

                        audit.append(
                            {
                                "target_topic": topic_name,
                                "query": query,
                                "search_order": order,
                                "search_phase": search_phase,
                                "search_format_target": format_target,
                                "video_duration_filter": video_duration,
                                "results_returned": len(ids),
                                "video_ids": ids,
                            }
                        )

    return discovered, matches, audit, calls


def merge_discovery(
    base_discovered: dict[str, set[str]],
    base_matches: dict[str, list[dict[str, Any]]],
    base_audit: list[dict[str, Any]],
    extra_discovered: dict[str, set[str]],
    extra_matches: dict[str, list[dict[str, Any]]],
    extra_audit: list[dict[str, Any]],
) -> None:
    for video_id, topics in extra_discovered.items():
        base_discovered.setdefault(video_id, set()).update(topics)
    for video_id, items in extra_matches.items():
        base_matches.setdefault(video_id, []).extend(items)
    base_audit.extend(extra_audit)


def deficient_topic_formats(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, set[str]]:
    minimum_channels = int(config["minimum_unique_channels_per_topic_format"])
    channels: dict[tuple[str, str], set[str]] = defaultdict(set)

    for row in rows:
        channel_id = str(row.get("channel_id", ""))
        if not channel_id:
            continue
        for topic in row.get("validated_topics", []):
            channels[(str(topic), str(row.get("format_candidate", "unknown")))].add(channel_id)

    deficient: dict[str, set[str]] = {}
    for topic in config["topics"]:
        topic_name = str(topic["topic"])
        for format_target in config["search_profiles"]:
            if len(channels.get((topic_name, format_target), set())) < minimum_channels:
                deficient.setdefault(topic_name, set()).add(format_target)

    return deficient


def archive_existing_output() -> Path | None:
    """Archive a prior 01.3 run before intentionally replacing its cohort."""

    if not OUTPUT_DIR.exists():
        return None

    archive_root = OUTPUT_DIR.parent / "archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = archive_root / f"experiment_01_3_{timestamp}"
    suffix = 1
    while destination.exists():
        destination = archive_root / f"experiment_01_3_{timestamp}_{suffix}"
        suffix += 1

    shutil.move(str(OUTPUT_DIR), str(destination))
    return destination

def build_rows(
    discovered: dict[str, set[str]],
    query_matches: dict[str, list[dict[str, Any]]],
    details: dict[str, dict[str, Any]],
    channels: dict[str, dict[str, Any]],
    config: dict[str, Any],
    age_window: dict[str, Any],
    api_key: str,
    *,
    include_baselines: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    topics = {str(t["topic"]): t for t in config["topics"]}
    context_terms = list(config["motorsport_context_terms"])
    exclude_title_terms = list(config.get("exclude_title_terms", []))
    minimum_views = int(config["minimum_views"])
    minimum_age = float(age_window["minimum_age_days"])
    maximum_age = float(age_window["maximum_age_days"])
    history_cache: dict[str, list[dict[str, Any]]] = {}
    eligible, rejected = [], []

    for video_id, searched_set in discovered.items():
        item = details.get(video_id)
        if not item:
            continue

        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})
        title = str(snippet.get("title", ""))
        published_at = str(snippet.get("publishedAt", ""))
        if not published_at:
            continue

        days = age_days(published_at)
        views = int(stats.get("viewCount", 0) or 0)
        duration = parse_duration_seconds(content.get("duration", ""))
        fmt = classify_format_candidate(duration)
        channel_id = str(snippet.get("channelId", ""))
        channel = channels.get(channel_id, {})
        subscribers = int(channel.get("statistics", {}).get("subscriberCount", 0) or 0)

        searched_topics = sorted(searched_set)
        validated_topics = []
        validation = {}

        for topic_name in searched_topics:
            format_matches = [
                match
                for match in query_matches.get(video_id, [])
                if match.get("target_topic") == topic_name
                and match.get("search_format_target") == fmt
            ]
            if not format_matches:
                result = {
                    "topic_relevance": "OFF_TOPIC",
                    "topic_relevance_reason": "format_branch_mismatch",
                    "topic_term_matches": [],
                    "motorsport_context_matches": [],
                    "excluded_title_matches": [],
                }
            else:
                result = classify_topic_relevance(
                    title,
                    list(topics[topic_name].get("match_terms", [])),
                    context_terms,
                    exclude_title_terms,
                )

            validation[topic_name] = result
            if result["topic_relevance"] == "ON_TOPIC":
                validated_topics.append(topic_name)

        reasons = []
        if days < minimum_age or days > maximum_age:
            reasons.append("outside_allowed_age_window")
        if views < minimum_views:
            reasons.append("below_minimum_views")
        if not validated_topics:
            reasons.append("no_validated_topic")

        search_phases = sorted(
            {
                str(match.get("search_phase", ""))
                for match in query_matches.get(video_id, [])
                if match.get("search_phase")
            }
        )
        row: dict[str, Any] = {
            "experiment_id": EXPERIMENT_ID,
            "video_id": video_id,
            "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
            "title": title,
            "channel_id": channel_id,
            "channel_title": snippet.get("channelTitle"),
            "searched_topics": searched_topics,
            "validated_topics": sorted(validated_topics),
            "query_matches": query_matches.get(video_id, []),
            "search_phases": search_phases,
            "cohort_window_source": "strict" if "strict" in search_phases else "expanded",
            "published_at": published_at,
            "age_days": round(days, 2),
            "duration_seconds": duration,
            "format_candidate": fmt,
            "views": views,
            "likes": int(stats["likeCount"]) if stats.get("likeCount") is not None else None,
            "channel_subscribers": subscribers,
            "topic_validation": validation,
        }

        if reasons:
            rejected.append({**row, "rejection_reasons": reasons})
            continue

        if not include_baselines:
            row.update(
                {
                    "topic_relevance": "ON_TOPIC",
                    "topic_relevance_reason": "strict_title_validation",
                    "channel_baseline_median": None,
                    "baseline_sample_size": 0,
                    "baseline_confidence": "not_calculated",
                    "baseline_warning": "",
                    "outlier_ratio": None,
                    "outlier_reliability": "UNAVAILABLE",
                    "outlier_reliability_reason": "preliminary_cohort_check",
                }
            )
            eligible.append(row)
            continue

        if channel_id not in history_cache:
            upload_ids = get_recent_upload_ids(channel, api_key, maximum=25)
            history_cache[channel_id] = list(get_video_details(upload_ids, api_key).values())

        baseline, sample_size = calculate_channel_baseline(row, history_cache[channel_id])
        confidence = baseline_confidence(sample_size)
        warning = baseline_warning(baseline, sample_size)
        ratio = round(views / baseline, 2) if baseline is not None and baseline > 0 else None
        row.update(
            {
                "topic_relevance": "ON_TOPIC",
                "topic_relevance_reason": "strict_title_validation",
                "channel_baseline_median": baseline,
                "baseline_sample_size": sample_size,
                "baseline_confidence": confidence,
                "baseline_warning": warning,
                "outlier_ratio": ratio,
                **classify_outlier_reliability(
                    outlier_ratio=ratio,
                    baseline_confidence=confidence,
                    baseline_warning=warning,
                ),
            }
        )
        eligible.append(row)

    eligible.sort(key=lambda r: (r["format_candidate"], r["validated_topics"], -r["views"]))
    return eligible, rejected

STATIC_KEYS = (
    "experiment_id", "video_id", "youtube_url", "title", "channel_id",
    "channel_title", "searched_topics", "validated_topics", "query_matches",
    "search_phases", "cohort_window_source",
    "published_at", "duration_seconds", "format_candidate",
    "channel_subscribers", "topic_relevance", "topic_relevance_reason",
    "channel_baseline_median", "baseline_sample_size", "baseline_confidence",
    "baseline_warning", "outlier_ratio", "outlier_reliability",
    "outlier_reliability_reason",
)


def static_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in STATIC_KEYS}


def apply_velocity(rows: list[dict[str, Any]], observed_at: str) -> None:
    history = load_snapshot_history(SNAPSHOT_FILE)
    for row in rows:
        row.update(
            calculate_snapshot_velocity(
                video_id=row["video_id"],
                current_views=int(row["views"]),
                observed_at=observed_at,
                history=history,
            )
        )
    append_snapshots(SNAPSHOT_FILE, rows, observed_at)


def refresh_rows(manifest: dict[str, Any], api_key: str) -> tuple[list[dict[str, Any]], list[str]]:
    static_rows = {str(r["video_id"]): r for r in manifest.get("candidates", []) if r.get("video_id")}
    details = get_video_details(list(static_rows), api_key)
    rows, missing = [], []

    for video_id, stored in static_rows.items():
        item = details.get(video_id)
        if not item:
            missing.append(video_id)
            continue
        row = dict(stored)
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        views = int(stats.get("viewCount", 0) or 0)
        row.update(
            {
                "title": snippet.get("title", row.get("title")),
                "channel_title": snippet.get("channelTitle", row.get("channel_title")),
                "views": views,
                "likes": int(stats["likeCount"]) if stats.get("likeCount") is not None else None,
                "age_days": round(age_days(str(snippet.get("publishedAt", row["published_at"]))), 2),
            }
        )
        baseline = row.get("channel_baseline_median")
        if baseline is not None and float(baseline) > 0:
            row["outlier_ratio"] = round(views / float(baseline), 2)
            row.update(
                classify_outlier_reliability(
                    outlier_ratio=row["outlier_ratio"],
                    baseline_confidence=str(row.get("baseline_confidence", "no_baseline")),
                    baseline_warning=str(row.get("baseline_warning", "")),
                )
            )
        rows.append(row)

    return rows, missing


def build_summary(
    mode: str,
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
    missing: list[str],
    topic_velocity: dict[str, Any],
) -> dict[str, Any]:
    format_counts: dict[str, int] = {}
    topic_counts: dict[str, int] = {}
    for row in rows:
        fmt = str(row.get("format_candidate", "unknown"))
        format_counts[fmt] = format_counts.get(fmt, 0) + 1
        for topic in row.get("validated_topics", []):
            topic_counts[str(topic)] = topic_counts.get(str(topic), 0) + 1

    valid = [r for r in rows if r.get("velocity_status") == "VALID"]
    return {
        "experiment": "Stage 2 Experiment 01.3",
        "purpose": "age_matched_velocity_validation",
        "mode": mode,
        "cohort_id": manifest.get("cohort_id"),
        "cohort_created_at": manifest.get("created_at"),
        "target_age_days": manifest.get("target_age_days"),
        "age_tolerance_days": manifest.get("age_tolerance_days"),
        "minimum_age_days": manifest.get("minimum_age_days"),
        "maximum_age_days": manifest.get("maximum_age_days"),
        "published_after": manifest.get("published_after"),
        "published_before": manifest.get("published_before"),
        "fallback_age_tolerance_days": manifest.get("fallback_age_tolerance_days"),
        "fallback_minimum_age_days": manifest.get("fallback_minimum_age_days"),
        "fallback_maximum_age_days": manifest.get("fallback_maximum_age_days"),
        "fallback_published_after": manifest.get("fallback_published_after"),
        "fallback_published_before": manifest.get("fallback_published_before"),
        "adaptive_expansion": manifest.get("adaptive_expansion"),
        "minimum_views": manifest.get("minimum_views"),
        "search_orders": manifest.get("search_orders"),
        "search_calls": manifest.get("search_calls"),
        "frozen_cohort_size": len(manifest.get("video_ids", [])),
        "available_cohort_videos": len(rows),
        "missing_videos": missing,
        "rejected_during_discovery": int(manifest.get("rejected_during_discovery", 0)),
        "format_counts": dict(sorted(format_counts.items())),
        "topic_counts": dict(sorted(topic_counts.items(), key=lambda item: (-item[1], item[0]))),
        "velocity_analysis": {
            "valid_velocity_samples": len(valid),
            "no_prior_snapshot": sum(r.get("velocity_status") == "NO_PRIOR" for r in rows),
            "negative_view_adjustments": sum(
                r.get("velocity_status") == "NEGATIVE_ADJUSTMENT" for r in rows
            ),
            "median_current_views_per_day": median_or_none(
                [float(r["current_views_per_day"]) for r in valid]
            ),
        },
        "topic_velocity": topic_velocity,
        "important_notes": [
            "The cohort is frozen after discovery; refresh mode performs no new search.",
            "Topic and motorsport-context validation use title text only.",
            "Discovery uses separate short/medium/long YouTube duration branches.",
            "The primary 105-135 day window widens to 90-150 only for sparse topic/format cells.",
            "Primary metric: median current views/day within the same age window and format.",
            "Short-form and long-form candidates are benchmarked separately.",
            "Age-matched velocity index = topic median / whole-cohort median for the same format.",
            "1-2 unique channels = LOW confidence; 3-4 = MODERATE; 5+ = STRONG.",
            "Outlier ratio is supporting evidence only; no final opportunity score is calculated.",
        ],
    }


CSV_FIELDS = [
    "experiment_id", "video_id", "youtube_url", "title", "channel_id",
    "channel_title", "searched_topics", "validated_topics", "query_matches",
    "search_phases", "cohort_window_source",
    "published_at", "age_days", "duration_seconds", "format_candidate",
    "views", "likes", "channel_subscribers", "channel_baseline_median",
    "baseline_sample_size", "baseline_confidence", "baseline_warning",
    "outlier_ratio", "outlier_reliability", "outlier_reliability_reason",
    "topic_relevance", "topic_relevance_reason", "velocity_status",
    "velocity_previous_at", "velocity_previous_views", "velocity_interval_hours",
    "view_delta_since_snapshot", "current_views_per_hour", "current_views_per_day",
]


def write_outputs(rows: list[dict[str, Any]], topic_velocity: dict[str, Any], summary: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_FILE.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    TOPIC_FILE.write_text(json.dumps(topic_velocity, indent=2, ensure_ascii=False), encoding="utf-8")
    SUMMARY_FILE.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    with CANDIDATES_FILE.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            flat["searched_topics"] = "|".join(row.get("searched_topics", []))
            flat["validated_topics"] = "|".join(row.get("validated_topics", []))
            flat["query_matches"] = json.dumps(row.get("query_matches", []), ensure_ascii=False)
            flat["search_phases"] = "|".join(row.get("search_phases", []))
            writer.writerow({field: flat.get(field) for field in CSV_FIELDS})


def run_discover(args: argparse.Namespace, config: dict[str, Any], api_key: str) -> None:
    if OUTPUT_DIR.exists():
        if not args.replace_cohort:
            raise SystemExit(
                "01.3 output already exists. Use --mode refresh, or rerun discovery "
                "with --replace-cohort to archive the old cohort and start clean."
            )
        archived = archive_existing_output()
        if archived is not None:
            print(f"Archived previous Experiment 01.3 output to: {archived}")

    observed_dt = datetime.now(timezone.utc)
    observed_at = observed_dt.isoformat()
    target = args.target_age_days or int(config["target_age_days"])
    tolerance = (
        args.age_tolerance_days
        if args.age_tolerance_days is not None
        else int(config["age_tolerance_days"])
    )
    wide_tolerance = int(config["wide_age_tolerance_days"])
    strict_window = calculate_age_window(observed_dt, target, tolerance)
    wide_window = calculate_age_window(observed_dt, target, wide_tolerance)

    print("\nSTAGE 2 — EXPERIMENT 01.3")
    print("=" * 60)
    print("Mode: DISCOVER + FREEZE COHORT")
    print(
        f"Primary age window: "
        f"{strict_window['minimum_age_days']}-{strict_window['maximum_age_days']} days"
    )
    print(
        f"Fallback age window: "
        f"{wide_window['minimum_age_days']}-{wide_window['maximum_age_days']} days"
    )
    print("Validation: title-only topic + motorsport context")
    print("Search: format-separated short / medium / long branches\n")

    discovered, matches, audit, strict_calls = discover(
        config,
        api_key,
        strict_window,
        args.max_searches,
        args.region_code,
        args.language,
        search_phase="strict",
        calls_already=0,
    )

    strict_details = get_video_details(list(discovered), api_key)
    strict_channel_ids = sorted(
        {
            str(item.get("snippet", {}).get("channelId", ""))
            for item in strict_details.values()
            if item.get("snippet", {}).get("channelId")
        }
    )
    strict_channels = get_channel_details(strict_channel_ids, api_key)
    strict_rows, _ = build_rows(
        discovered,
        matches,
        strict_details,
        strict_channels,
        config,
        strict_window,
        api_key,
        include_baselines=False,
    )

    deficient = deficient_topic_formats(strict_rows, config)
    expansion_calls = 0

    if deficient and strict_calls < args.max_searches:
        print("\nSparse topic/format cells detected; widening only those cells:")
        for topic_name, formats in sorted(deficient.items()):
            print(f"  {topic_name}: {', '.join(sorted(formats))}")

        extra_discovered, extra_matches, extra_audit, expansion_calls = discover(
            config,
            api_key,
            wide_window,
            args.max_searches,
            args.region_code,
            args.language,
            search_orders=list(config["expansion_search_orders"]),
            topic_format_targets=deficient,
            search_phase="expanded",
            calls_already=strict_calls,
        )
        merge_discovery(
            discovered,
            matches,
            audit,
            extra_discovered,
            extra_matches,
            extra_audit,
        )

    total_calls = strict_calls + expansion_calls

    print(f"\nUnique search hits: {len(discovered):,}")
    print(f"Search calls used: {total_calls:,}/{args.max_searches:,}")

    details = get_video_details(list(discovered), api_key)
    channel_ids = sorted(
        {
            str(item.get("snippet", {}).get("channelId", ""))
            for item in details.values()
            if item.get("snippet", {}).get("channelId")
        }
    )
    channels = get_channel_details(channel_ids, api_key)
    rows, rejected = build_rows(
        discovered,
        matches,
        details,
        channels,
        config,
        wide_window,
        api_key,
        include_baselines=True,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_FILE.write_text(
        json.dumps(rejected, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if not rows:
        raise SystemExit(
            "No videos passed the age, view, title-topic and motorsport-context filters."
        )

    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "cohort_id": (
            f"day{target}_adaptive_{observed_dt.strftime('%Y%m%dT%H%M%SZ')}"
        ),
        "created_at": observed_at,
        "target_age_days": target,
        "age_tolerance_days": tolerance,
        "minimum_age_days": strict_window["minimum_age_days"],
        "maximum_age_days": strict_window["maximum_age_days"],
        "published_after": strict_window["published_after"],
        "published_before": strict_window["published_before"],
        "fallback_age_tolerance_days": wide_tolerance,
        "fallback_minimum_age_days": wide_window["minimum_age_days"],
        "fallback_maximum_age_days": wide_window["maximum_age_days"],
        "fallback_published_after": wide_window["published_after"],
        "fallback_published_before": wide_window["published_before"],
        "minimum_views": int(config["minimum_views"]),
        "minimum_unique_channels_per_topic_format": int(
            config["minimum_unique_channels_per_topic_format"]
        ),
        "search_orders": config["search_orders"],
        "expansion_search_orders": config["expansion_search_orders"],
        "search_profiles": config["search_profiles"],
        "search_calls": total_calls,
        "strict_search_calls": strict_calls,
        "expansion_search_calls": expansion_calls,
        "search_limit_reached": total_calls >= args.max_searches,
        "adaptive_expansion": {
            topic: sorted(formats)
            for topic, formats in sorted(deficient.items())
        },
        "search_audit": audit,
        "rejected_during_discovery": len(rejected),
        "video_ids": [r["video_id"] for r in rows],
        "candidates": [static_candidate(r) for r in rows],
    }
    MANIFEST_FILE.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    apply_velocity(rows, observed_at)
    topic_velocity = aggregate_age_matched_velocity(rows)
    summary = build_summary("discover", manifest, rows, [], topic_velocity)
    write_outputs(rows, topic_velocity, summary)
    print_completion("discover", summary)

def run_refresh(api_key: str) -> None:
    if not MANIFEST_FILE.exists():
        raise SystemExit("No 01.3 cohort exists. Run --mode discover first.")
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    observed_at = datetime.now(timezone.utc).isoformat()

    print("\nSTAGE 2 — EXPERIMENT 01.3")
    print("=" * 60)
    print("Mode: REFRESH FROZEN COHORT")
    print(f"Cohort: {manifest.get('cohort_id')}")
    print(f"Frozen videos: {len(manifest.get('video_ids', [])):,}\n")

    rows, missing = refresh_rows(manifest, api_key)
    apply_velocity(rows, observed_at)
    topic_velocity = aggregate_age_matched_velocity(rows)
    summary = build_summary("refresh", manifest, rows, missing, topic_velocity)
    write_outputs(rows, topic_velocity, summary)
    print_completion("refresh", summary)


def print_completion(mode: str, summary: dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("EXPERIMENT 01.3 COMPLETE")
    print("=" * 60)
    print(f"Mode:                  {mode}")
    print(f"Frozen cohort size:    {summary['frozen_cohort_size']:,}")
    print(f"Available videos:      {summary['available_cohort_videos']:,}")
    print(
        "Valid velocity samples: "
        f"{summary['velocity_analysis']['valid_velocity_samples']:,}"
    )
    print("\nResults:")
    for path in (
        MANIFEST_FILE, CANDIDATES_FILE, RAW_FILE, REJECTED_FILE,
        TOPIC_FILE, SUMMARY_FILE, SNAPSHOT_FILE,
    ):
        print(f"  {path}")
    if mode == "discover":
        print("\nCohort frozen. Run refresh after at least one hour.")
    else:
        print("\nRefresh used the same frozen IDs; no discovery search was performed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2 Experiment 01.3 age-matched velocity validation")
    parser.add_argument("--mode", choices=("discover", "refresh"), required=True)
    parser.add_argument("--max-searches", type=int, default=80)
    parser.add_argument("--target-age-days", type=int, default=None)
    parser.add_argument("--age-tolerance-days", type=int, default=None)
    parser.add_argument("--region-code", default=None)
    parser.add_argument("--language", default=None)
    parser.add_argument("--replace-cohort", action="store_true")
    args = parser.parse_args()

    config = load_config()
    api_key = load_api_key()
    if args.mode == "discover":
        run_discover(args, config, api_key)
    else:
        run_refresh(api_key)


if __name__ == "__main__":
    main()
