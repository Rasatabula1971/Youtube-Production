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
import sys
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
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from source_acquisition.agent_reach_adapter import (
    AcquisitionError,
    search_youtube,
    youtube_health,
)

ENV_FILE = PROJECT_ROOT / ".env"
CONFIG_FILE = HERE / "experiment_01_3_config.json"
OUTPUT_ROOT = HERE / "output"
OUTPUT_DIR = OUTPUT_ROOT / "experiment_01_3"
CHECKPOINT_FILE = OUTPUT_ROOT / "experiment_01_3_discovery_checkpoint.json"
MANIFEST_FILE = OUTPUT_DIR / "cohort_manifest.json"
SNAPSHOT_FILE = OUTPUT_DIR / "video_snapshots.jsonl"
PERSISTENT_SNAPSHOT_FILE = OUTPUT_ROOT / "experiment_01_3_snapshot_history.jsonl"
CANDIDATES_FILE = OUTPUT_DIR / "candidates.csv"
RAW_FILE = OUTPUT_DIR / "raw_results.json"
REJECTED_FILE = OUTPUT_DIR / "rejected_candidates.json"
TOPIC_FILE = OUTPUT_DIR / "topic_velocity.json"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"
REFRESH_LOCK_FILE = OUTPUT_ROOT / "experiment_01_3_refresh.lock"
EXPERIMENT_ID = "01.3"


def acquire_refresh_lock(
    path: Path = REFRESH_LOCK_FILE,
    *,
    stale_minutes: int = 30,
) -> bool:
    """Prevent manual and scheduled refreshes from overlapping."""
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)

    if path.exists():
        try:
            modified = datetime.fromtimestamp(
                path.stat().st_mtime,
                tz=timezone.utc,
            )
            age_minutes = (now - modified).total_seconds() / 60
        except OSError:
            age_minutes = 0
        if age_minutes >= stale_minutes:
            try:
                path.unlink()
            except OSError:
                return False
        else:
            return False

    try:
        fd = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )
    except FileExistsError:
        return False

    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "created_at": now.isoformat(),
                }
            )
        )
    return True


def release_refresh_lock(
    path: Path = REFRESH_LOCK_FILE,
) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


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

def topic_channel_confidence(count: int) -> str:
    """Describe topic evidence breadth from independent source channels."""
    if count >= 5:
        return "STRONG"
    if count >= 3:
        return "MODERATE"
    if count >= 1:
        return "LOW"
    return "INSUFFICIENT"


def confidence_from_unique_channels(count: int) -> str:
    """Backward-compatible alias for older callers/tests."""
    return topic_channel_confidence(count)


def topic_niche_map(config: dict[str, Any]) -> dict[str, str]:
    """Return the configured niche for every globally unique topic ID."""
    mapping: dict[str, str] = {}
    for item in config.get("topics", []):
        topic = str(item.get("topic") or "").strip()
        niche = str(item.get("niche") or "").strip()
        if not topic:
            raise ValueError("Experiment 01.3 topic is missing its topic ID.")
        if not niche:
            raise ValueError(
                f"Experiment 01.3 topic '{topic}' is missing required niche."
            )
        existing = mapping.get(topic)
        if existing is not None and existing != niche:
            raise ValueError(
                f"Experiment 01.3 topic '{topic}' is assigned to multiple niches."
            )
        mapping[topic] = niche
    return mapping


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result = []
    for row in rows:
        video_id = str(row.get("video_id", ""))
        if video_id and video_id not in seen:
            seen.add(video_id)
            result.append(row)
    return result


def aggregate_age_matched_velocity(
    rows: list[dict[str, Any]],
    topic_niches: dict[str, str],
) -> dict[str, Any]:
    """Aggregate velocity against a niche-and-format matched cohort baseline."""

    eligible = dedupe_rows(
        [
            row
            for row in rows
            if row.get("topic_relevance") == "ON_TOPIC"
        ]
    )

    cohort_values: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in eligible:
        velocity = row.get("current_views_per_day")
        if velocity is None:
            continue
        fmt = str(row.get("format_candidate", "unknown"))
        row_niches = {
            topic_niches.get(str(topic), "unknown")
            for topic in row.get("validated_topics", [])
        }
        for niche in row_niches:
            cohort_values[(niche, fmt)].append(float(velocity))

    cohort_medians = {
        key: median_or_none(values)
        for key, values in cohort_values.items()
    }
    cohort_medians_nested: dict[str, dict[str, float | None]] = {}
    for (niche, fmt), value in sorted(cohort_medians.items()):
        cohort_medians_nested.setdefault(niche, {})[fmt] = value

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        fmt = str(row.get("format_candidate", "unknown"))
        for topic in row.get("validated_topics", []):
            topic_name = str(topic)
            niche = topic_niches.get(topic_name, "unknown")
            grouped[(niche, topic_name, fmt)].append(row)

    topics: dict[str, Any] = {}
    for (niche, topic, fmt), group in sorted(grouped.items()):
        group = dedupe_rows(group)
        velocities = [
            float(r["current_views_per_day"])
            for r in group
            if r.get("current_views_per_day") is not None
        ]
        ages = [
            float(r["age_days"])
            for r in group
            if r.get("age_days") is not None
        ]
        views = [
            int(r["views"])
            for r in group
            if r.get("views") is not None
        ]
        trusted = [
            float(r["outlier_ratio"])
            for r in group
            if r.get("outlier_reliability") == "TRUSTED"
            and r.get("outlier_ratio") is not None
        ]
        unique_channels = len(
            {
                r.get("channel_id")
                for r in group
                if r.get("channel_id")
            }
        )
        topic_median = median_or_none(velocities)
        cohort_median = cohort_medians.get((niche, fmt))
        index = None
        if (
            topic_median is not None
            and cohort_median is not None
            and cohort_median > 0
        ):
            index = round(topic_median / cohort_median, 3)

        topic_payload = topics.setdefault(
            topic,
            {
                "niche": niche,
                "by_format": {},
            },
        )
        topic_payload["niche"] = niche
        topic_payload["by_format"][fmt] = {
            "niche": niche,
            "video_count": len(group),
            "unique_channels": unique_channels,
            "topic_channel_confidence": topic_channel_confidence(
                unique_channels
            ),
            "velocity_sample_count": len(velocities),
            "median_age_days": median_or_none(ages),
            "median_views": median_or_none(views),
            "median_current_views_per_day": topic_median,
            "cohort_median_current_views_per_day": cohort_median,
            "age_matched_velocity_index": index,
            "trusted_outlier_count": len(trusted),
            "median_trusted_outlier_ratio": median_or_none(trusted),
        }

    legacy_by_format: dict[str, float | None] = {}
    if len(cohort_medians_nested) == 1:
        legacy_by_format = dict(
            next(iter(cohort_medians_nested.values()))
        )

    return {
        "cohort_median_current_views_per_day_by_niche_format":
            cohort_medians_nested,
        # Transitional single-niche alias for older consumers. It is empty
        # once more than one niche is present so cross-niche pooling cannot
        # silently reappear.
        "cohort_median_current_views_per_day_by_format":
            legacy_by_format,
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
    try:
        topic_niche_map(config)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    return config


def load_api_key() -> str:
    load_env_file(ENV_FILE)
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise SystemExit(f"YOUTUBE_API_KEY not found in {ENV_FILE}")
    return api_key


def load_discovery_checkpoint() -> dict[str, Any] | None:
    if not CHECKPOINT_FILE.exists():
        return None
    try:
        return json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_discovery_checkpoint(
    *,
    observed_at: str,
    target_age_days: int,
    age_tolerance_days: int,
    wide_age_tolerance_days: int,
    strict_window: dict[str, Any],
    wide_window: dict[str, Any],
    discovered: dict[str, set[str]],
    matches: dict[str, list[dict[str, Any]]],
    audit: list[dict[str, Any]],
    completed_jobs: set[str],
    status: str,
) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "status": status,
        "observed_at": observed_at,
        "target_age_days": target_age_days,
        "age_tolerance_days": age_tolerance_days,
        "wide_age_tolerance_days": wide_age_tolerance_days,
        "strict_window": strict_window,
        "wide_window": wide_window,
        "completed_search_jobs": sorted(completed_jobs),
        "discovered": {
            video_id: sorted(topics)
            for video_id, topics in discovered.items()
        },
        "matches": matches,
        "audit": audit,
    }
    CHECKPOINT_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def restore_checkpoint_state(
    checkpoint: dict[str, Any],
) -> tuple[
    dict[str, set[str]],
    dict[str, list[dict[str, Any]]],
    list[dict[str, Any]],
    set[str],
]:
    discovered = {
        str(video_id): set(topics)
        for video_id, topics in checkpoint.get("discovered", {}).items()
    }
    matches = {
        str(video_id): [dict(item) for item in items]
        for video_id, items in checkpoint.get("matches", {}).items()
    }
    audit = [
        dict(item)
        for item in checkpoint.get("audit", [])
    ]

    # Checkpoints created before automatic backend routing could only have
    # come from YouTube Data API v3 search. Backfill provenance so a resumed
    # mixed-backend cohort remains auditable.
    for items in matches.values():
        for item in items:
            item.setdefault(
                "discovery_backend",
                "youtube_api_v3",
            )
            item.setdefault(
                "backend_search_strategy",
                item.get("search_order"),
            )
    for item in audit:
        item.setdefault(
            "discovery_backend",
            "youtube_api_v3",
        )
        item.setdefault(
            "backend_search_strategy",
            item.get("search_order"),
        )

    completed_jobs = set(checkpoint.get("completed_search_jobs", []))
    return discovered, matches, audit, completed_jobs


def search_job_key(
    *,
    search_phase: str,
    topic_name: str,
    query: str,
    format_target: str,
    video_duration: str,
    order: str,
    age_window: dict[str, Any],
) -> str:
    return "|".join(
        [
            search_phase,
            topic_name,
            query,
            format_target,
            video_duration,
            order,
            str(age_window["published_after"]),
            str(age_window["published_before"]),
        ]
    )




def discovery_backend_counts(audit: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in audit:
        backend = str(
            item.get("discovery_backend", "unknown")
        )
        counts[backend] = counts.get(backend, 0) + 1
    return dict(sorted(counts.items()))


YT_DLP_RELEVANCE_POOL = 100


def _parse_yt_dlp_datetime(item: dict[str, Any]) -> datetime | None:
    timestamp = item.get("timestamp")
    if timestamp is not None:
        try:
            return datetime.fromtimestamp(
                float(timestamp),
                tz=timezone.utc,
            )
        except (TypeError, ValueError, OSError):
            pass

    upload_date = str(item.get("upload_date") or "").strip()
    if len(upload_date) == 8 and upload_date.isdigit():
        try:
            return datetime.strptime(
                upload_date,
                "%Y%m%d",
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _yt_dlp_query_variants(
    query: str,
    age_window: dict[str, Any],
) -> list[str]:
    after = datetime.fromisoformat(
        str(age_window["published_after"]).replace("Z", "+00:00")
    )
    before = datetime.fromisoformat(
        str(age_window["published_before"]).replace("Z", "+00:00")
    )

    variants = [str(query).strip()]
    for year in range(after.year, before.year + 1):
        variants.append(f"{str(query).strip()} {year}")

    return list(
        dict.fromkeys(
            value
            for value in variants
            if value
        )
    )


def _topic_queries(
    topic: dict[str, Any],
    *,
    search_phase: str,
    format_target: str,
) -> list[str]:
    """Return auditable query families without weakening acceptance gates."""

    if search_phase == "expanded":
        keys = ["expansion_queries"]
        if format_target == "short_candidate":
            keys.append("short_expansion_queries")
        elif format_target == "long_form_candidate":
            keys.append("long_expansion_queries")
    else:
        keys = ["queries"]
        if format_target == "short_candidate":
            keys.append("short_queries")
        elif format_target == "long_form_candidate":
            keys.append("long_queries")

    queries: list[str] = []
    for key in keys:
        values = topic.get(key, [])
        if not isinstance(values, list):
            continue
        for value in values:
            query = str(value).strip()
            if query and query not in queries:
                queries.append(query)

    if not queries:
        for value in topic.get("queries", []):
            query = str(value).strip()
            if query and query not in queries:
                queries.append(query)

    return queries


def _yt_dlp_pool(
    query: str,
    age_window: dict[str, Any],
    cache: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    variants = _yt_dlp_query_variants(
        query,
        age_window,
    )
    cache_key = "||".join(variants)
    if cache_key in cache:
        return [
            dict(item)
            for item in cache[cache_key]
        ]

    merged: dict[str, dict[str, Any]] = {}

    for variant in variants:
        result = search_youtube(
            variant,
            limit=YT_DLP_RELEVANCE_POOL,
            strategy="relevance",
            require_agent_reach_health=False,
        )
        for raw in result.get("results", []):
            video_id = str(
                raw.get("video_id", "")
            ).strip()
            if not video_id:
                continue

            if video_id not in merged:
                item = dict(raw)
                item["discovery_queries"] = [variant]
                merged[video_id] = item
                continue

            existing = merged[video_id]
            queries = list(
                existing.get(
                    "discovery_queries",
                    [],
                )
            )
            if variant not in queries:
                queries.append(variant)
            existing["discovery_queries"] = queries

            for key, value in raw.items():
                if (
                    existing.get(key) in (None, "")
                    and value not in (None, "")
                ):
                    existing[key] = value

    cache[cache_key] = list(merged.values())
    return [
        dict(item)
        for item in cache[cache_key]
    ]


def _yt_dlp_ids(
    query: str,
    age_window: dict[str, Any],
    format_target: str,
    video_duration_filter: str,
    minimum_views: int,
    cache: dict[str, list[dict[str, Any]]],
) -> list[str]:
    if video_duration_filter not in {"short", "medium", "long"}:
        raise ValueError(
            "video_duration_filter must be short, medium, or long"
        )
    pool = _yt_dlp_pool(
        query,
        age_window,
        cache,
    )

    after = datetime.fromisoformat(
        str(age_window["published_after"]).replace("Z", "+00:00")
    ).date()
    before = datetime.fromisoformat(
        str(age_window["published_before"]).replace("Z", "+00:00")
    ).date()

    ids: list[str] = []
    for item in pool:
        observed = _parse_yt_dlp_datetime(item)
        if observed is not None:
            observed_date = observed.date()
            if observed_date < after or observed_date > before:
                continue

        duration_raw = item.get("duration_seconds")
        if duration_raw is not None:
            try:
                duration = float(duration_raw)
            except (TypeError, ValueError):
                duration = 0.0
            if duration > 0:
                # Keep the fallback's branches distinct. The project uses
                # <=180 seconds as the short-candidate boundary, then splits
                # long-form discovery at 20 minutes so "medium" and "long"
                # jobs do not recycle the same videos.
                if video_duration_filter == "short" and duration > 180:
                    continue
                if (
                    video_duration_filter == "medium"
                    and not (180 < duration <= 1200)
                ):
                    continue
                if video_duration_filter == "long" and duration <= 1200:
                    continue

        views_raw = item.get("view_count")
        if views_raw is not None:
            try:
                if int(views_raw) < int(minimum_views):
                    continue
            except (TypeError, ValueError):
                pass

        video_id = str(item.get("video_id", "")).strip()
        if video_id:
            ids.append(video_id)

    return ids

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
    discovered: dict[str, set[str]] | None = None,
    matches: dict[str, list[dict[str, Any]]] | None = None,
    audit: list[dict[str, Any]] | None = None,
    completed_jobs: set[str] | None = None,
    discovery_backend: str = "auto",
    yt_dlp_cache: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[
    dict[str, set[str]],
    dict[str, list[dict[str, Any]]],
    list[dict[str, Any]],
    set[str],
    int,
    str,
]:
    """Search one age window and preserve completed work across quota failures."""

    discovered = discovered if discovered is not None else {}
    matches = matches if matches is not None else {}
    audit = audit if audit is not None else []
    completed_jobs = completed_jobs if completed_jobs is not None else set()
    calls = 0
    orders = list(search_orders or config["search_orders"])
    search_profiles = config["search_profiles"]
    api_search_available = discovery_backend != "yt_dlp"
    fallback_health_checked = False
    fallback_ready = False
    api_fallback_reason: str | None = None
    fallback_cache = yt_dlp_cache if yt_dlp_cache is not None else {}

    for topic in config["topics"]:
        topic_name = str(topic["topic"])
        topic_niche = str(topic.get("niche") or "unknown")
        target_formats = (
            sorted(topic_format_targets.get(topic_name, set()))
            if topic_format_targets is not None
            else sorted(search_profiles)
        )
        if not target_formats:
            continue

        for format_target in target_formats:
            topic_queries = _topic_queries(
                topic,
                search_phase=search_phase,
                format_target=format_target,
            )
            for query in topic_queries:
                duration_filters = list(search_profiles.get(format_target, []))
                for video_duration in duration_filters:
                    for order in orders:
                        job_key = search_job_key(
                            search_phase=search_phase,
                            topic_name=topic_name,
                            query=query,
                            format_target=format_target,
                            video_duration=video_duration,
                            order=order,
                            age_window=age_window,
                        )
                        if job_key in completed_jobs:
                            continue

                        if (
                            api_search_available
                            and calls_already + calls >= max_searches
                        ):
                            if discovery_backend == "auto":
                                api_search_available = False
                                api_fallback_reason = (
                                    "YOUTUBE_API_SEARCH_BUDGET_REACHED"
                                )
                                print(
                                    "  YouTube API search budget reached; "
                                    "switching remaining discovery jobs to Agent Reach / yt-dlp."
                                )
                            else:
                                return (
                                    discovered,
                                    matches,
                                    audit,
                                    completed_jobs,
                                    calls,
                                    "SEARCH_BUDGET_REACHED",
                                )

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
                            f"[{format_target}; duration={video_duration}; "
                            f"order={order}; phase={search_phase}]"
                        )

                        ids: list[str] = []
                        backend_used = ""
                        backend_strategy = order

                        if api_search_available:
                            try:
                                data = api_get("search", api_key, **params)
                                calls += 1
                                for item in data.get("items", []):
                                    video_id = item.get("id", {}).get("videoId")
                                    if video_id:
                                        ids.append(str(video_id))
                                backend_used = "youtube_api_v3"
                            except SystemExit as exc:
                                api_fallback_reason = str(exc)
                                if discovery_backend == "youtube_api":
                                    return (
                                        discovered,
                                        matches,
                                        audit,
                                        completed_jobs,
                                        calls,
                                        "YOUTUBE_API_UNAVAILABLE",
                                    )
                                api_search_available = False
                                print(
                                    "  YouTube search API unavailable; "
                                    "switching remaining discovery jobs to Agent Reach / yt-dlp."
                                )
                                print(
                                    "    API fallback reason: "
                                    f"{api_fallback_reason}"
                                )

                        if not backend_used:
                            if not fallback_health_checked:
                                health = youtube_health()
                                fallback_health_checked = True
                                fallback_ready = bool(health.get("ready"))
                                if fallback_ready:
                                    print(
                                        "  Agent Reach fallback ready: "
                                        f"{health.get('active_backend')}"
                                    )
                                else:
                                    print(
                                        "  Agent Reach fallback unavailable: "
                                        f"{health.get('message') or health.get('channel_status')}"
                                    )

                            if not fallback_ready:
                                return (
                                    discovered,
                                    matches,
                                    audit,
                                    completed_jobs,
                                    calls,
                                    "SEARCH_BACKENDS_UNAVAILABLE",
                                )

                            try:
                                ids = _yt_dlp_ids(
                                    query,
                                    age_window,
                                    format_target,
                                    video_duration,
                                    int(config["minimum_views"]),
                                    fallback_cache,
                                )
                            except AcquisitionError as exc:
                                print(
                                    "  Agent Reach / yt-dlp search failed: "
                                    f"{exc}"
                                )
                                return (
                                    discovered,
                                    matches,
                                    audit,
                                    completed_jobs,
                                    calls,
                                    "SEARCH_BACKENDS_UNAVAILABLE",
                                )

                            backend_used = "agent_reach_yt_dlp"
                            backend_strategy = "ytsearch_relevance+year_hint"
                            print(
                                "    yt-dlp age/format/view filtered candidates: "
                                f"{len(ids)}"
                            )

                        for rank, video_id in enumerate(ids, start=1):
                            discovered.setdefault(video_id, set()).add(topic_name)
                            matches.setdefault(video_id, []).append(
                                {
                                    "target_topic": topic_name,
                                    "target_niche": topic_niche,
                                    "query": query,
                                    "search_order": order,
                                    "search_phase": search_phase,
                                    "search_format_target": format_target,
                                    "video_duration_filter": video_duration,
                                    "rank": rank,
                                    "discovery_backend": backend_used,
                                    "backend_search_strategy": backend_strategy,
                                }
                            )

                        audit.append(
                            {
                                "target_topic": topic_name,
                                "target_niche": topic_niche,
                                "query": query,
                                "search_order": order,
                                "search_phase": search_phase,
                                "search_format_target": format_target,
                                "video_duration_filter": video_duration,
                                "discovery_backend": backend_used,
                                "backend_search_strategy": backend_strategy,
                                "api_fallback_reason": (
                                    api_fallback_reason
                                    if backend_used == "agent_reach_yt_dlp"
                                    else None
                                ),
                                "results_returned": len(ids),
                                "video_ids": ids,
                            }
                        )
                        completed_jobs.add(job_key)

    return discovered, matches, audit, completed_jobs, calls, "COMPLETE"

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


def cohort_discovery_readiness(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    required = int(
        config["minimum_unique_channels_per_topic_format"]
    )
    channels: dict[tuple[str, str], set[str]] = defaultdict(set)

    for row in rows:
        channel_id = str(row.get("channel_id") or "").strip()
        fmt = str(row.get("format_candidate") or "").strip()
        if not channel_id or not fmt:
            continue
        for topic in row.get("validated_topics", []):
            channels[(str(topic), fmt)].add(channel_id)

    topic_niches = topic_niche_map(config)
    cells = []
    for (topic, fmt), channel_ids in sorted(channels.items()):
        cells.append(
            {
                "topic": topic,
                "niche": topic_niches.get(topic, "unknown"),
                "format_candidate": fmt,
                "unique_channels": len(channel_ids),
                "refresh_worthy": len(channel_ids) >= required,
            }
        )

    ready = [
        cell
        for cell in cells
        if cell["refresh_worthy"]
    ]
    return {
        "required_unique_channels_per_topic_format": required,
        "refresh_worthy": bool(ready),
        "refresh_worthy_cell_count": len(ready),
        "maximum_unique_channels_in_any_cell": max(
            (
                int(cell["unique_channels"])
                for cell in cells
            ),
            default=0,
        ),
        "cells": cells,
    }


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
    topic_niches = topic_niche_map(config)
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
        searched_niches = sorted(
            {
                topic_niches[topic_name]
                for topic_name in searched_topics
                if topic_name in topic_niches
            }
        )
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
            "searched_niches": searched_niches,
            "validated_topics": sorted(validated_topics),
            "validated_niches": sorted(
                {
                    topic_niches[topic_name]
                    for topic_name in validated_topics
                    if topic_name in topic_niches
                }
            ),
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
    "channel_title", "searched_topics", "searched_niches", "validated_topics",
    "validated_niches", "query_matches",
    "search_phases", "cohort_window_source",
    "published_at", "duration_seconds", "format_candidate",
    "channel_subscribers", "topic_relevance", "topic_relevance_reason",
    "channel_baseline_median", "baseline_sample_size", "baseline_confidence",
    "baseline_warning", "outlier_ratio", "outlier_reliability",
    "outlier_reliability_reason",
)


def static_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in STATIC_KEYS}


def load_velocity_history() -> dict[str, list[dict[str, Any]]]:
    merged: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, str, int]] = set()

    def add_snapshot(
        video_id: str,
        observed_at: str,
        views: int,
    ) -> None:
        key = (str(video_id), str(observed_at), int(views))
        if key in seen:
            return
        try:
            datetime.fromisoformat(
                str(observed_at).replace("Z", "+00:00")
            )
        except ValueError:
            return
        seen.add(key)
        merged[str(video_id)].append(
            {
                "video_id": str(video_id),
                "observed_at": str(observed_at),
                "views": int(views),
            }
        )

    paths = [
        PERSISTENT_SNAPSHOT_FILE,
        SNAPSHOT_FILE,
    ]
    archive_root = OUTPUT_ROOT / "archive"
    archive_dirs: list[Path] = []
    if archive_root.exists():
        archive_dirs = sorted(
            archive_root.glob("experiment_01_3_*")
        )
        paths.extend(
            archive_dir / "video_snapshots.jsonl"
            for archive_dir in archive_dirs
        )

    for path in paths:
        for video_id, snapshots in load_snapshot_history(path).items():
            for snapshot in snapshots:
                add_snapshot(
                    str(video_id),
                    str(snapshot["observed_at"]),
                    int(snapshot["views"]),
                )

    # Older discovery runs fetched official YouTube metadata for many
    # candidates that were later rejected. Reuse those API observations as
    # history too, so a rebuilt cohort does not needlessly restart the clock
    # when one of those videos becomes eligible later.
    for archive_dir in archive_dirs:
        summary_path = archive_dir / "summary.json"
        try:
            summary = json.loads(
                summary_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            continue

        observed_at = str(
            summary.get("cohort_created_at") or ""
        ).strip()
        if not observed_at:
            continue

        for name in (
            "raw_results.json",
            "rejected_candidates.json",
        ):
            path = archive_dir / name
            try:
                rows = json.loads(
                    path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(rows, list):
                continue

            for row in rows:
                if not isinstance(row, dict):
                    continue
                video_id = str(row.get("video_id") or "").strip()
                views = row.get("views")
                if not video_id or views is None:
                    continue
                try:
                    add_snapshot(
                        video_id,
                        observed_at,
                        int(views),
                    )
                except (TypeError, ValueError):
                    continue

    for snapshots in merged.values():
        snapshots.sort(
            key=lambda item: datetime.fromisoformat(
                str(item["observed_at"]).replace("Z", "+00:00")
            )
        )

    return dict(merged)


def append_candidate_detail_snapshots(
    details: dict[str, dict[str, Any]],
    observed_at: str,
) -> None:
    rows = []
    for video_id, item in details.items():
        stats = item.get("statistics", {})
        views = stats.get("viewCount")
        if views is None:
            continue
        try:
            view_count = int(views)
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "video_id": str(video_id),
                "views": view_count,
            }
        )

    if rows:
        append_snapshots(
            PERSISTENT_SNAPSHOT_FILE,
            rows,
            observed_at,
        )


def apply_velocity(rows: list[dict[str, Any]], observed_at: str) -> None:
    history = load_velocity_history()
    for row in rows:
        row.update(
            calculate_snapshot_velocity(
                video_id=row["video_id"],
                current_views=int(row["views"]),
                observed_at=observed_at,
                history=history,
            )
        )

    # Keep a run-local snapshot file for auditability and a persistent
    # cross-cohort ledger so rebuilding discovery does not reset velocity
    # history for videos already observed.
    append_snapshots(SNAPSHOT_FILE, rows, observed_at)
    append_snapshots(PERSISTENT_SNAPSHOT_FILE, rows, observed_at)


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
    niche_counts: dict[str, int] = {}
    for row in rows:
        fmt = str(row.get("format_candidate", "unknown"))
        format_counts[fmt] = format_counts.get(fmt, 0) + 1
        for topic in row.get("validated_topics", []):
            topic_counts[str(topic)] = topic_counts.get(str(topic), 0) + 1
        for niche in row.get("validated_niches", []):
            niche_counts[str(niche)] = niche_counts.get(str(niche), 0) + 1

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
        "search_calls_this_run": manifest.get("search_calls_this_run"),
        "discovery_backend_mode": manifest.get("discovery_backend_mode"),
        "discovery_backend_counts": manifest.get("discovery_backend_counts", {}),
        "completed_search_jobs_total": manifest.get("completed_search_jobs_total"),
        "frozen_cohort_size": len(manifest.get("video_ids", [])),
        "available_cohort_videos": len(rows),
        "missing_videos": missing,
        "rejected_during_discovery": int(manifest.get("rejected_during_discovery", 0)),
        "format_counts": dict(sorted(format_counts.items())),
        "niche_counts": dict(
            sorted(
                niche_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),
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
        "cohort_readiness": manifest.get("cohort_readiness", {}),
        "topic_velocity": topic_velocity,
        "important_notes": [
            "The cohort is frozen after discovery; refresh mode performs no new search.",
            "Topic and motorsport-context validation use title text only.",
            "Discovery uses separate short/medium/long YouTube duration branches.",
            "The primary 105-135 day window widens to 90-150 only for sparse topic/format cells.",
            "Primary metric: median current views/day within the same age window, niche and format.",
            "Short-form and long-form candidates are benchmarked separately.",
            "Age-matched velocity index = topic median / niche-and-format cohort median.",
            "Topic channel confidence: 1-2 = LOW; 3-4 = MODERATE; 5+ = STRONG.",
            "Outlier ratio is supporting evidence only; no final opportunity score is calculated.",
        ],
    }


CSV_FIELDS = [
    "experiment_id", "video_id", "youtube_url", "title", "channel_id",
    "channel_title", "searched_topics", "searched_niches", "validated_topics",
    "validated_niches", "query_matches",
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
            flat["searched_niches"] = "|".join(row.get("searched_niches", []))
            flat["validated_topics"] = "|".join(row.get("validated_topics", []))
            flat["validated_niches"] = "|".join(row.get("validated_niches", []))
            flat["query_matches"] = json.dumps(row.get("query_matches", []), ensure_ascii=False)
            flat["search_phases"] = "|".join(row.get("search_phases", []))
            writer.writerow({field: flat.get(field) for field in CSV_FIELDS})


def run_discover(args: argparse.Namespace, config: dict[str, Any], api_key: str) -> None:
    checkpoint = None if args.restart_discovery else load_discovery_checkpoint()

    if checkpoint is not None:
        observed_at = str(checkpoint["observed_at"])
        observed_dt = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        target = int(checkpoint["target_age_days"])
        tolerance = int(checkpoint["age_tolerance_days"])
        wide_tolerance = int(checkpoint["wide_age_tolerance_days"])
        strict_window = dict(checkpoint["strict_window"])
        wide_window = dict(checkpoint["wide_window"])
        discovered, matches, audit, completed_jobs = restore_checkpoint_state(checkpoint)
        print(f"Resuming saved Experiment 01.3 discovery checkpoint: {CHECKPOINT_FILE}")
        print(f"Completed search jobs already saved: {len(completed_jobs):,}")
    else:
        if args.restart_discovery and CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()

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
        discovered, matches, audit, completed_jobs = {}, {}, [], set()

        save_discovery_checkpoint(
            observed_at=observed_at,
            target_age_days=target,
            age_tolerance_days=tolerance,
            wide_age_tolerance_days=wide_tolerance,
            strict_window=strict_window,
            wide_window=wide_window,
            discovered=discovered,
            matches=matches,
            audit=audit,
            completed_jobs=completed_jobs,
            status="STARTED",
        )

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
    print("Search: format-separated short / medium / long branches")
    print(f"Discovery backend: {args.discovery_backend}")
    print(f"Per-run YouTube API search budget: {args.max_searches}\n")

    yt_dlp_cache: dict[str, list[dict[str, Any]]] = {}

    (
        discovered,
        matches,
        audit,
        completed_jobs,
        strict_calls,
        strict_status,
    ) = discover(
        config,
        api_key,
        strict_window,
        args.max_searches,
        args.region_code,
        args.language,
        search_phase="strict",
        calls_already=0,
        discovered=discovered,
        matches=matches,
        audit=audit,
        completed_jobs=completed_jobs,
        discovery_backend=args.discovery_backend,
        yt_dlp_cache=yt_dlp_cache,
    )

    save_discovery_checkpoint(
        observed_at=observed_at,
        target_age_days=target,
        age_tolerance_days=tolerance,
        wide_age_tolerance_days=wide_tolerance,
        strict_window=strict_window,
        wide_window=wide_window,
        discovered=discovered,
        matches=matches,
        audit=audit,
        completed_jobs=completed_jobs,
        status=strict_status,
    )

    if strict_status != "COMPLETE":
        print("\nExperiment 01.3 discovery paused safely.")
        print(f"Reason: {strict_status}")
        print(f"Checkpoint: {CHECKPOINT_FILE}")
        print("Rerun the same discover command; completed searches will be skipped.")
        return

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
    expansion_status = "COMPLETE"
    expansion_backend = args.discovery_backend
    if (
        args.discovery_backend == "auto"
        and any(
            item.get("discovery_backend") == "agent_reach_yt_dlp"
            for item in audit
        )
    ):
        expansion_backend = "yt_dlp"

    if deficient and strict_calls < args.max_searches:
        print("\nSparse topic/format cells detected; widening only those cells:")
        for topic_name, formats in sorted(deficient.items()):
            print(f"  {topic_name}: {', '.join(sorted(formats))}")

        (
            discovered,
            matches,
            audit,
            completed_jobs,
            expansion_calls,
            expansion_status,
        ) = discover(
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
            discovered=discovered,
            matches=matches,
            audit=audit,
            completed_jobs=completed_jobs,
            discovery_backend=expansion_backend,
            yt_dlp_cache=yt_dlp_cache,
        )

        save_discovery_checkpoint(
            observed_at=observed_at,
            target_age_days=target,
            age_tolerance_days=tolerance,
            wide_age_tolerance_days=wide_tolerance,
            strict_window=strict_window,
            wide_window=wide_window,
            discovered=discovered,
            matches=matches,
            audit=audit,
            completed_jobs=completed_jobs,
            status=expansion_status,
        )

        if expansion_status != "COMPLETE":
            print("\nExperiment 01.3 discovery paused safely.")
            print(f"Reason: {expansion_status}")
            print(f"Checkpoint: {CHECKPOINT_FILE}")
            print("Rerun the same discover command; completed searches will be skipped.")
            return

    calls_this_run = strict_calls + expansion_calls

    print(f"\nUnique search hits: {len(discovered):,}")
    print(f"Search calls this run: {calls_this_run:,}/{args.max_searches:,}")
    print(f"Completed search jobs total: {len(completed_jobs):,}")

    details = get_video_details(list(discovered), api_key)
    measurement_observed_at = datetime.now(timezone.utc).isoformat()
    append_candidate_detail_snapshots(
        details,
        measurement_observed_at,
    )
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
        "topic_niches": topic_niche_map(config),
        "minimum_unique_channels_per_topic_format": int(
            config["minimum_unique_channels_per_topic_format"]
        ),
        "search_orders": config["search_orders"],
        "expansion_search_orders": config["expansion_search_orders"],
        "search_profiles": config["search_profiles"],
        "search_calls_this_run": calls_this_run,
        "discovery_backend_mode": args.discovery_backend,
        "discovery_backend_counts": discovery_backend_counts(audit),
        "completed_search_jobs_total": len(completed_jobs),
        "adaptive_expansion": {
            topic: sorted(formats)
            for topic, formats in sorted(deficient.items())
        },
        "search_audit": audit,
        "rejected_during_discovery": len(rejected),
        "cohort_readiness": cohort_discovery_readiness(
            rows,
            config,
        ),
        "video_ids": [r["video_id"] for r in rows],
        "candidates": [static_candidate(r) for r in rows],
    }
    MANIFEST_FILE.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    apply_velocity(rows, measurement_observed_at)
    topic_velocity = aggregate_age_matched_velocity(
        rows,
        topic_niche_map(config),
    )
    summary = build_summary("discover", manifest, rows, [], topic_velocity)
    write_outputs(rows, topic_velocity, summary)

    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()

    print_completion("discover", summary)

def run_refresh(config: dict[str, Any], api_key: str) -> None:
    if not acquire_refresh_lock():
        raise SystemExit(
            "Another Experiment 01.3 refresh is already running."
        )

    try:
        if not MANIFEST_FILE.exists():
            raise SystemExit(
                "No 01.3 cohort exists. Run --mode discover first."
            )
        manifest = json.loads(
            MANIFEST_FILE.read_text(encoding="utf-8")
        )
        observed_at = datetime.now(timezone.utc).isoformat()

        print("\nSTAGE 2 — EXPERIMENT 01.3")
        print("=" * 60)
        print("Mode: REFRESH FROZEN COHORT")
        print(f"Cohort: {manifest.get('cohort_id')}")
        print(
            f"Frozen videos: "
            f"{len(manifest.get('video_ids', [])):,}\n"
        )

        rows, missing = refresh_rows(manifest, api_key)
        apply_velocity(rows, observed_at)
        manifest_topic_niches = manifest.get("topic_niches")
        topic_niches = (
            {
                str(topic): str(niche)
                for topic, niche in manifest_topic_niches.items()
            }
            if isinstance(manifest_topic_niches, dict)
            else topic_niche_map(config)
        )
        topic_velocity = aggregate_age_matched_velocity(
            rows,
            topic_niches,
        )
        summary = build_summary(
            "refresh",
            manifest,
            rows,
            missing,
            topic_velocity,
        )
        write_outputs(rows, topic_velocity, summary)
        print_completion("refresh", summary)
    finally:
        release_refresh_lock()


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
        TOPIC_FILE, SUMMARY_FILE, SNAPSHOT_FILE, PERSISTENT_SNAPSHOT_FILE,
    ):
        print(f"  {path}")
    if mode == "discover":
        readiness = summary.get("cohort_readiness", {})
        if not readiness.get("refresh_worthy"):
            print(
                "\nINSUFFICIENT COHORT: no topic/format cell has enough "
                "independent channels for useful velocity measurement."
            )
            print(
                "Rerun discovery with the improved acquisition path. "
                "Do not wait for a velocity refresh."
            )
        elif summary["velocity_analysis"]["valid_velocity_samples"] > 0:
            print(
                "\nCohort frozen and prior snapshot history produced "
                "measured velocity immediately."
            )
        else:
            print(
                "\nCohort frozen and suitable for velocity measurement. "
                "Refresh may reuse persistent snapshot history from earlier runs."
            )
    else:
        print("\nRefresh used the same frozen IDs; no discovery search was performed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2 Experiment 01.3 age-matched velocity validation")
    parser.add_argument("--mode", choices=("discover", "refresh"), required=True)
    parser.add_argument("--max-searches", type=int, default=60)
    parser.add_argument("--target-age-days", type=int, default=None)
    parser.add_argument("--age-tolerance-days", type=int, default=None)
    parser.add_argument("--region-code", default=None)
    parser.add_argument("--language", default=None)
    parser.add_argument("--replace-cohort", action="store_true")
    parser.add_argument(
        "--discovery-backend",
        choices=("auto", "youtube_api", "yt_dlp"),
        default="auto",
        help=(
            "Discovery backend. auto tries YouTube Data API v3 first and "
            "falls back to Agent Reach / yt-dlp when search is unavailable."
        ),
    )
    parser.add_argument(
        "--restart-discovery",
        action="store_true",
        help="Discard a saved 01.3 discovery checkpoint and start discovery over.",
    )
    args = parser.parse_args()

    config = load_config()
    api_key = load_api_key()
    if args.mode == "discover":
        run_discover(args, config, api_key)
    else:
        run_refresh(config, api_key)


if __name__ == "__main__":
    main()
