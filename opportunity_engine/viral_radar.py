"""Viral / Breakout Radar (spec v2.1 slices O6-O9).

O6 discovery  - a channel watchlist (seeded competitors plus every channel the
                system has already seen) is crawled through each channel's
                uploads playlist (1 API unit per channel, no search quota);
                yt-dlp "This week" bucket searches only widen the watchlist.
O7 baseline   - each channel's mature uploads (15+ days old, same format;
                Shorts only after the March 2025 view-count change) give the
                median views and median lifetime views/hour.
O8 tracking   - promising videos get append-only snapshots on an age-based
                cadence, reusing the D-021 snapshot store and velocity maths.
O9 classifier - four separate axes (strength, trajectory, breadth, historical
                alignment); every ratio states its basis (R4). Breadth stays
                UNASSESSED until theme clustering (O10).

Fifteen days is the maximum tracking window, never a wait: a video is
classified on the first run that sees it. Failures are named, never read as
"nothing found". Thresholds are hypotheses; day-15 outcomes are recorded (R7).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess  # nosec B404 - fixed argument list, no shell
import sys
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import atomic_write_json  # noqa: E402

from experiment_01_discovery.market_intelligence import (  # noqa: E402
    VELOCITY_VALID,
    calculate_snapshot_velocity,
    load_snapshot_history,
)
from opportunity_engine import (  # noqa: E402
    channel_scope,
    historical_adapter,
    models,
    radar_lane,
    radar_learning,
    viral_cluster,
)
from opportunity_engine.human_video_intake import (  # noqa: E402
    VIDEO_ID_PATTERN,
    _iso8601_seconds,
    _load_api_key,
    watch_url,
)
from opportunity_engine.packet_schema import build_packet, evidence, validate_packet  # noqa: E402
from opportunity_engine.provenance import opportunity_id  # noqa: E402

HERE = Path(__file__).resolve().parent
RADAR_DIR = HERE / "output" / "viral"
STATE_FILE = RADAR_DIR / "radar_state.json"
SUMMARY_FILE = RADAR_DIR / "last_run.json"
SNAPSHOT_FILE = RADAR_DIR / "snapshots.jsonl"
CLUSTERS_FILE = RADAR_DIR / "clusters.json"
PACKETS_DIR = HERE / "output" / "opportunities" / "viral"
GENERATOR = "opportunity_engine.viral_radar"
SCHEMA_VERSION = 1

STATUS_COMPLETE = "COMPLETE"
STATUS_PARTIAL = "PARTIAL"
API_UNAVAILABLE = "API_VALIDATION_UNAVAILABLE"
YT_DLP_FAILED = "YT_DLP_DISCOVERY_FAILED"
THROTTLED = "DISCOVERY_THROTTLED"
THROTTLE_MARKERS = ("429", "too many requests", "sign in to confirm", "rate-limit", "rate limit")


class RadarError(RuntimeError):
    """A named radar failure (see spec section 31)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


Api = Callable[..., "dict[str, Any]"]
Searcher = Callable[[str, int, int], "list[dict[str, Any]]"]


def radar_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    return (config or channel_scope.load_config())["viral_radar"]


def _parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _median(values: list[float]) -> float | None:
    return round(float(statistics.median(values)), 2) if values else None


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------


def empty_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "watchlist": {},
        "resolved_handles": {},
        "seen_video_ids": {},
        "tracked": {},
        "completed": {},
        "bucket_cursor": 0,
        "throttled_until": None,
        "last_discovery_run": None,
    }


def load_state() -> dict[str, Any]:
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_state()
    if not isinstance(state, dict) or state.get("schema_version") != SCHEMA_VERSION:
        return empty_state()
    base = empty_state()
    base.update({k: v for k, v in state.items() if k in base})
    return base


def save_state(state: dict[str, Any]) -> None:
    atomic_write_json(STATE_FILE, state)


# --------------------------------------------------------------------------
# External access (injected in tests)
# --------------------------------------------------------------------------


def default_api() -> Api:
    """YouTube Data API through the project's retrying client."""
    api_key = _load_api_key()
    if not api_key:
        raise RadarError(API_UNAVAILABLE, "YOUTUBE_API_KEY is not configured")
    from experiment_01_discovery.youtube_discovery import api_get

    def call(resource: str, **params: Any) -> dict[str, Any]:
        try:
            return api_get(resource, api_key, **params)
        except (SystemExit, urllib.error.URLError, OSError, RuntimeError, ValueError) as exc:
            raise RadarError(API_UNAVAILABLE, f"YouTube API request failed: {exc}") from exc

    return call


def search_url_flat(url: str, limit: int, timeout_seconds: int) -> list[dict[str, Any]]:
    """One yt-dlp flat read of a YouTube search URL (metadata only)."""
    binary = shutil.which("yt-dlp")
    if not binary:
        raise RadarError(YT_DLP_FAILED, "yt-dlp is not installed")
    command = [
        binary,
        "--flat-playlist",
        "--dump-single-json",
        "--no-warnings",
        "--playlist-end",
        str(int(limit)),
        "--",
        url,
    ]
    try:
        completed = subprocess.run(  # nosec B603 - fixed argument list, no shell
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RadarError(YT_DLP_FAILED, f"yt-dlp timed out after {timeout_seconds}s") from exc
    except OSError as exc:
        raise RadarError(YT_DLP_FAILED, f"yt-dlp failed to start: {exc}") from exc
    if completed.returncode != 0:
        message = (completed.stderr or "").strip()
        code = THROTTLED if any(m in message.lower() for m in THROTTLE_MARKERS) else YT_DLP_FAILED
        raise RadarError(code, (message.splitlines() or ["yt-dlp failed"])[-1][:300])
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RadarError(YT_DLP_FAILED, "yt-dlp returned unreadable results") from exc
    results = []
    for entry in (payload or {}).get("entries") or []:
        if isinstance(entry, dict) and VIDEO_ID_PATTERN.fullmatch(str(entry.get("id") or "")):
            results.append(
                {
                    "video_id": entry["id"],
                    "title": entry.get("title"),
                    "channel_id": entry.get("channel_id"),
                    "channel_title": entry.get("channel") or entry.get("uploader"),
                }
            )
    return results


# --------------------------------------------------------------------------
# O6 discovery: watchlist
# --------------------------------------------------------------------------


def _add_channel(
    state: dict[str, Any], channel_id: Any, source: str, settings: dict[str, Any], now: datetime
) -> bool:
    channel_id = str(channel_id or "")
    if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", channel_id) or channel_id in state["watchlist"]:
        return False
    if len(state["watchlist"]) >= int(settings["max_watchlist_channels"]):
        return False
    state["watchlist"][channel_id] = {"source": source, "added_at": now.isoformat()}
    return True


def seed_watchlist_from_system(state: dict[str, Any], settings: dict[str, Any], now: datetime) -> int:
    """Every channel the system has already seen joins the watchlist."""
    from opportunity_engine import human_topic_search, human_video_intake

    added = 0
    for packet in (*human_video_intake.list_packets(), *human_topic_search.list_packets()):
        for video in packet.get("candidate_videos") or []:
            added += _add_channel(state, video.get("channel_id"), str(packet.get("source_type")), settings, now)
    try:
        historical = historical_adapter.build()
    except (OSError, ValueError):
        historical = {"packets": []}
    for packet in historical.get("packets") or []:
        for video in packet.get("candidate_videos") or []:
            added += _add_channel(state, video.get("channel_id"), "HISTORICAL", settings, now)
    return added


def resolve_handles(state: dict[str, Any], api: Api, settings: dict[str, Any], now: datetime) -> list[str]:
    errors = []
    for handle in settings.get("watchlist_handles") or []:
        if handle in state["resolved_handles"]:
            continue
        # An API failure here is the same failure as anywhere else in the run:
        # it propagates so the run is not reported as complete.
        data = api("channels", part="id", forHandle=handle, maxResults=1)
        items = data.get("items") or []
        channel_id = items[0].get("id") if items else None
        state["resolved_handles"][handle] = channel_id
        if channel_id:
            _add_channel(state, channel_id, f"seed:{handle}", settings, now)
        else:
            errors.append(f"{handle}: no channel found")
    return errors


def bucket_discovery(
    state: dict[str, Any], searcher: Searcher, settings: dict[str, Any], now: datetime
) -> dict[str, Any]:
    """Rotate through bucket queries; new channels widen the watchlist."""
    throttled_until = _parse_time(state.get("throttled_until"))
    if throttled_until and throttled_until > now:
        return {"status": THROTTLED, "skipped_until": state["throttled_until"], "queries": []}
    queries = list(settings.get("bucket_queries") or [])
    count = min(int(settings["bucket_queries_per_run"]), len(queries))
    cursor = int(state.get("bucket_cursor") or 0)
    log: list[dict[str, Any]] = []
    status = STATUS_COMPLETE
    for offset in range(count):
        query = queries[(cursor + offset) % len(queries)]
        url = (
            "https://www.youtube.com/results?search_query="
            + query.replace(" ", "+")
            + "&sp="
            + str(settings["bucket_search_sp"])
        )
        try:
            results = searcher(url, int(settings["bucket_results_per_query"]), int(settings["search_timeout_seconds"]))
        except RadarError as exc:
            log.append({"query": query, "status": exc.code, "error": str(exc)})
            status = exc.code
            if exc.code == THROTTLED:
                state["throttled_until"] = (now + timedelta(hours=float(settings["throttle_backoff_hours"]))).isoformat()
                break  # back off: never retry aggressively
            continue
        added = sum(_add_channel(state, r.get("channel_id"), f"bucket:{query}", settings, now) for r in results)
        log.append({"query": query, "status": STATUS_COMPLETE, "results": len(results), "new_channels": added})
    state["bucket_cursor"] = (cursor + count) % max(len(queries), 1)
    return {"status": status, "queries": log}


# --------------------------------------------------------------------------
# Crawl and measurement
# --------------------------------------------------------------------------


def refresh_channels(state: dict[str, Any], api: Api) -> None:
    """Uploads playlist id, title and follower count for watchlist channels (1 unit per 50)."""
    ids = list(state["watchlist"])
    for start in range(0, len(ids), 50):
        batch = ids[start : start + 50]
        data = api("channels", part="snippet,contentDetails,statistics", id=",".join(batch), maxResults=50)
        for item in data.get("items") or []:
            entry = state["watchlist"].get(item.get("id"))
            if entry is None:
                continue
            stats = item.get("statistics") or {}
            entry["title"] = (item.get("snippet") or {}).get("title")
            entry["uploads_playlist"] = ((item.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
            entry["follower_count"] = (
                None if stats.get("hiddenSubscriberCount") else _int(stats.get("subscriberCount"))
            )


def _int(value: Any) -> int | None:
    return int(value) if str(value or "").isdigit() else None


def crawl_uploads(state: dict[str, Any], api: Api, settings: dict[str, Any]) -> dict[str, list[str]]:
    """Recent upload ids per channel from each uploads playlist (1 unit per channel)."""
    uploads: dict[str, list[str]] = {}
    for channel_id, entry in state["watchlist"].items():
        playlist = entry.get("uploads_playlist")
        if not playlist:
            continue
        data = api(
            "playlistItems",
            part="contentDetails",
            playlistId=playlist,
            maxResults=min(int(settings["uploads_per_channel"]), 50),
        )
        uploads[channel_id] = [
            str((item.get("contentDetails") or {}).get("videoId"))
            for item in data.get("items") or []
            if (item.get("contentDetails") or {}).get("videoId")
        ]
    return uploads


def measure_videos(video_ids: list[str], api: Api) -> dict[str, dict[str, Any]]:
    measured: dict[str, dict[str, Any]] = {}
    unique = list(dict.fromkeys(video_ids))
    for start in range(0, len(unique), 50):
        data = api(
            "videos",
            part="snippet,statistics,contentDetails,status",
            id=",".join(unique[start : start + 50]),
            maxResults=50,
        )
        for item in data.get("items") or []:
            snippet = item.get("snippet") or {}
            stats = item.get("statistics") or {}
            measured[str(item.get("id"))] = {
                "video_id": str(item.get("id")),
                "title": snippet.get("title"),
                "channel_id": snippet.get("channelId"),
                "channel_title": snippet.get("channelTitle"),
                "published_at": snippet.get("publishedAt"),
                "live": snippet.get("liveBroadcastContent") not in (None, "none"),
                "duration_seconds": _iso8601_seconds(str((item.get("contentDetails") or {}).get("duration") or "")),
                "views": _int(stats.get("viewCount")),
                "likes": _int(stats.get("likeCount")),
                "comments": _int(stats.get("commentCount")),
                "made_for_kids": (item.get("status") or {}).get("madeForKids"),
            }
    return measured


# --------------------------------------------------------------------------
# O7 baseline
# --------------------------------------------------------------------------


def video_format(video: dict[str, Any], settings: dict[str, Any]) -> str:
    duration = int(video.get("duration_seconds") or 0)
    return "short" if 0 < duration <= int(settings["short_max_seconds"]) else "long_form"


def age_hours(video: dict[str, Any], now: datetime) -> float | None:
    published = _parse_time(video.get("published_at"))
    if published is None:
        return None
    return max((now - published).total_seconds() / 3600, 1 / 60)


def channel_baseline(
    channel_videos: list[dict[str, Any]], fmt: str, settings: dict[str, Any], now: datetime
) -> dict[str, Any]:
    """Median of the channel's mature uploads in the same format."""
    min_age = float(settings["baseline_min_age_days"]) * 24
    shorts_after = _parse_time(settings.get("shorts_baseline_after"))
    views, vph, ages = [], [], []
    for video in channel_videos:
        hours = age_hours(video, now)
        if video.get("live") or video.get("views") is None or hours is None or hours < min_age:
            continue
        if video_format(video, settings) != fmt:
            continue
        if fmt == "short" and shorts_after and (_parse_time(video.get("published_at")) or now) < shorts_after:
            continue
        views.append(int(video["views"]))
        vph.append(int(video["views"]) / hours)
        ages.append(round(hours / 24, 1))
        if len(views) >= int(settings["baseline_max_sample"]):
            break
    return {
        "format": fmt,
        "sample_size": len(views),
        "median_views": _median([float(v) for v in views]),
        "median_lifetime_vph": _median(vph),
        "sample_age_days": {"min": min(ages), "max": max(ages)} if ages else None,
        "rule": f"same-format uploads at least {settings['baseline_min_age_days']} days old",
        "sufficient": len(views) >= int(settings["baseline_min_sample"]),
    }


# --------------------------------------------------------------------------
# O9 classification
# --------------------------------------------------------------------------


def ratios(video: dict[str, Any], baseline: dict[str, Any], follower_count: int | None, now: datetime) -> dict[str, Any]:
    hours = age_hours(video, now) or 0.0
    views = int(video.get("views") or 0)
    lifetime_vph = views / hours if hours else None
    result: dict[str, Any] = {
        "age_hours": round(hours, 2),
        "views": views,
        "lifetime_vph": round(lifetime_vph, 2) if lifetime_vph is not None else None,
        "lifetime_ratio": None,
        "vph_ratio": None,
        "ratio_basis": [],
        "views_per_follower": round(views / follower_count, 3) if follower_count else None,
        "subscriber_outlier": "AVAILABLE" if follower_count else "UNAVAILABLE",
        "likes_per_view": round(int(video["likes"]) / views, 4) if views and video.get("likes") is not None else None,
        "comments_per_view": round(int(video["comments"]) / views, 5) if views and video.get("comments") is not None else None,
    }
    if baseline.get("sufficient") and baseline.get("median_views"):
        result["lifetime_ratio"] = round(views / float(baseline["median_views"]), 2)
        result["ratio_basis"].append("lifetime_vs_lifetime")
    if baseline.get("sufficient") and baseline.get("median_lifetime_vph") and lifetime_vph is not None:
        result["vph_ratio"] = round(lifetime_vph / float(baseline["median_lifetime_vph"]), 2)
        result["ratio_basis"].append("vph_vs_lifetime_vph")
    return result


def classify_strength(metrics: dict[str, Any], settings: dict[str, Any]) -> tuple[str, str | None]:
    if metrics.get("lifetime_ratio") is None or metrics.get("vph_ratio") is None:
        return "INSUFFICIENT_EVIDENCE", None
    hours = float(metrics["age_hours"])
    for rule in settings["strength_rules"]:
        if hours < float(rule.get("min_age_hours", 0)):
            continue
        if "max_age_hours" in rule and hours > float(rule["max_age_hours"]):
            continue
        if metrics["lifetime_ratio"] < float(rule.get("min_lifetime_ratio", 0)):
            continue
        if metrics["vph_ratio"] < float(rule.get("min_vph_ratio", 0)):
            continue
        return str(rule["strength"]), str(rule["rule_id"])
    return "NORMAL", None


def snapshot_intervals(video_id: str, history: dict[str, list[dict[str, Any]]], min_hours: float) -> list[dict[str, Any]]:
    """Views/hour between consecutive stored snapshots (D-021 rules)."""
    snapshots = history.get(video_id, [])
    intervals = []
    for index in range(1, len(snapshots)):
        current = snapshots[index]
        velocity = calculate_snapshot_velocity(
            video_id=video_id,
            current_views=current["views"],
            observed_at=current["observed_at"],
            history={video_id: snapshots[:index]},
            minimum_interval_hours=min_hours,
        )
        if velocity["velocity_status"] == VELOCITY_VALID:
            intervals.append(
                {
                    "from": velocity["velocity_previous_at"],
                    "to": current["observed_at"],
                    "vph": velocity["current_views_per_hour"],
                }
            )
    return intervals


def classify_trajectory(
    intervals: list[dict[str, Any]], baseline: dict[str, Any], settings: dict[str, Any]
) -> str:
    if len(intervals) < 2:
        return "INSUFFICIENT_SNAPSHOTS"
    rules = settings["trajectory"]
    previous, latest = float(intervals[-2]["vph"]), float(intervals[-1]["vph"])
    if previous > 0 and latest / previous >= float(rules["accelerating_ratio"]):
        return "ACCELERATING"
    if previous > 0 and latest / previous <= float(rules["decelerating_ratio"]):
        return "DECELERATING"
    median_vph = baseline.get("median_lifetime_vph")
    if median_vph and latest >= float(median_vph) * float(rules["stable_high_vph_multiple"]):
        return "STABLE_HIGH"
    return "FLAT"


def historical_topics() -> list[dict[str, Any]]:
    try:
        packets = historical_adapter.build().get("packets") or []
    except (OSError, ValueError):
        return []
    topics = []
    for packet in packets:
        words = [w for w in re.findall(r"[a-z0-9]+", str(packet.get("topic") or "").lower()) if len(w) >= 4]
        if words:
            topics.append({"topic": packet.get("topic"), "words": words})
    return topics


def classify_history(title: str, topics: list[dict[str, Any]]) -> tuple[str, str | None]:
    if not topics:
        return "UNASSESSED", None
    title_words = set(re.findall(r"[a-z0-9]+", str(title or "").lower()))
    for topic in topics:
        if any(word in title_words or word.rstrip("s") in title_words for word in topic["words"]):
            return "ESTABLISHED_DEMAND", str(topic["topic"])
    return "NO_HISTORY", None


# --------------------------------------------------------------------------
# O8 tracking
# --------------------------------------------------------------------------


def snapshot_due(record: dict[str, Any] | None, hours: float, settings: dict[str, Any], now: datetime) -> bool:
    if not record or not record.get("last_snapshot_at"):
        return True
    last = _parse_time(record["last_snapshot_at"])
    if last is None:
        return True
    return (now - last).total_seconds() / 3600 >= cadence_hours(hours, settings)


def cadence_hours(age: float, settings: dict[str, Any]) -> float:
    for max_age, every in settings["snapshot_cadence_hours"]:
        if age <= float(max_age):
            return float(every)
    return float(settings["snapshot_cadence_hours"][-1][1])


def next_snapshot_due(state: dict[str, Any], settings: dict[str, Any], now: datetime) -> datetime | None:
    """When the earliest tracked video next needs a snapshot (None if none tracked)."""
    due: list[datetime] = []
    for record in state["tracked"].values():
        last = _parse_time(record.get("last_snapshot_at"))
        hours = age_hours(record.get("video") or {}, now)
        if last is None or hours is None:
            due.append(now)
            continue
        due.append(last + timedelta(hours=cadence_hours(hours, settings)))
    return min(due) if due else None


def append_snapshot(video: dict[str, Any], hours: float, observed_at: str) -> None:
    """Append-only; extra fields are ignored by the shared D-021 loader."""
    SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "video_id": video["video_id"],
        "observed_at": observed_at,
        "views": int(video["views"]),
        "likes": video.get("likes"),
        "comments": video.get("comments"),
        "video_age_hours": round(hours, 2),
        "measurement_source": "YOUTUBE_DATA_API",
    }
    with SNAPSHOT_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _milestones(classifications: list[dict[str, Any]]) -> dict[str, Any]:
    """The classification closest to (and not after) 24h, 72h and 168h (R7)."""
    marks: dict[str, Any] = {}
    for label, limit in (("24h", 24), ("3d", 72), ("7d", 168)):
        earlier = [c for c in classifications if float(c["age_hours"]) <= limit]
        marks[label] = earlier[-1] if earlier else None
    return marks


# --------------------------------------------------------------------------
# Packets
# --------------------------------------------------------------------------


def packet_path(video_id: str) -> Path:
    return PACKETS_DIR / f"{video_id}.json"


def load_packet(video_id: str) -> dict[str, Any] | None:
    if not VIDEO_ID_PATTERN.fullmatch(str(video_id or "")):
        return None
    try:
        packet = json.loads(packet_path(video_id).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return packet if isinstance(packet, dict) else None


def list_packets() -> list[dict[str, Any]]:
    if not PACKETS_DIR.is_dir():
        return []
    packets = [p for p in (load_packet(path.stem) for path in PACKETS_DIR.glob("*.json")) if p]
    return sorted(packets, key=lambda p: str(p.get("created_at") or ""), reverse=True)


def build_viral_packet(record: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    settings = radar_config(config)
    video = record["video"]
    strength = record["strength"]
    level = settings["breakout_evidence"].get(strength)
    state = {}
    if level:
        state["current_breakout"] = evidence(
            level,
            record.get("strength_rule_id"),
            [
                f"{record['metrics'].get('lifetime_ratio')}x channel median views "
                f"(basis: {', '.join(record['metrics'].get('ratio_basis') or [])})",
                f"{record['metrics'].get('vph_ratio')}x channel median lifetime views/hour",
            ],
        )
    cluster_info = record.get("cluster") or {}
    rule_id = cluster_info.get("replication_rule_id")
    if rule_id:
        rules = {r["rule_id"]: r for r in config["evidence_rules"]["viral_replication"]}
        state["cross_channel_replication"] = evidence(
            rules[rule_id]["level"],
            rule_id,
            [
                f"{cluster_info.get('independent_channel_count')} independent channel(s) breaking out on "
                f"'{cluster_info.get('label')}' ({cluster_info.get('kind')})"
            ],
        )
    if record["historical_alignment"] == "ESTABLISHED_DEMAND":
        state["historical_demand"] = evidence(
            "STRONG", "HA-STUDY-SET-TOPIC", [f"title matches historical topic {record.get('historical_topic')}"]
        )
    channel = channel_scope.route(
        str(video.get("title") or ""),
        niche="everyday_science",
        made_for_kids=bool(video.get("made_for_kids")),
        config=config,
    )
    packet = build_packet(
        opportunity_id=opportunity_id(models.SOURCE_VIRAL_RADAR, video["video_id"]),
        source_type=models.SOURCE_VIRAL_RADAR,
        title=str(video.get("title") or video["video_id"]),
        summary=(
            f"{strength.replace('_', ' ').title()} on {video.get('channel_title') or 'a channel'}: "
            f"{record['metrics'].get('views'):,} views at {round(record['metrics']['age_hours'] / 24, 1)} days, "
            f"{record['metrics'].get('lifetime_ratio')}x the channel's normal."
        ),
        channel=channel,
        niche="everyday_science",
        formats=[record["format"]],
        evidence_state=state,
        viral_evidence={
            "strength": strength,
            "trajectory": record["trajectory"],
            "breadth": record.get("breadth") or "UNASSESSED",
            "historical_alignment": record["historical_alignment"],
            "trajectory_history_available": len(record.get("snapshots_taken") or []) >= 2,
            "strength_rule_id": record.get("strength_rule_id"),
            "metrics": record["metrics"],
            "baseline": record["baseline"],
            "intervals": record.get("intervals") or [],
            "classification_history": (record.get("classifications") or [])[-10:],
            "tracking_status": record.get("tracking_status", "TRACKING"),
            "outcome": record.get("outcome"),
            "candidate_video_ids": [video["video_id"]],
            "tracked_video_ids": [video["video_id"]],
            "topic_cluster_id": cluster_info.get("cluster_id"),
            "cluster": cluster_info or None,
            "not_publicly_observable": ["CTR", "average view duration", "retention", "viewed vs swiped away"],
        },
        candidate_videos=[
            {
                "video_id": video["video_id"],
                "youtube_url": watch_url(video["video_id"]),
                "title": video.get("title"),
                "channel_id": video.get("channel_id"),
                "channel_title": video.get("channel_title"),
                "format": record["format"],
                "published_at": video.get("published_at"),
                "age_days": round(record["metrics"]["age_hours"] / 24, 2),
                "duration_seconds": video.get("duration_seconds"),
                "views": video.get("views"),
                "likes": video.get("likes"),
                "measurement_source": "YOUTUBE_DATA_API",
            }
        ],
        generator=GENERATOR,
        created_at=record["first_seen_at"],
    )
    return packet


def save_packet(packet: dict[str, Any]) -> None:
    errors = validate_packet(packet)
    if errors:
        raise ValueError("Invalid VIRAL_RADAR packet: " + "; ".join(errors))
    video_id = packet["candidate_videos"][0]["video_id"]
    path = packet_path(video_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------


MODE_FULL = "full"
MODE_SNAPSHOTS = "snapshots"


def run(
    *,
    api: Api | None = None,
    searcher: Searcher | None = None,
    config: dict[str, Any] | None = None,
    now: datetime | None = None,
    mode: str = MODE_FULL,
) -> dict[str, Any]:
    """One radar pass.

    ``full`` discovers (watchlist crawl and bucket searches) and measures;
    ``snapshots`` (O13) only re-measures already-tracked videos, which costs
    one API unit per 50 videos and never searches.
    """
    if mode not in (MODE_FULL, MODE_SNAPSHOTS):
        raise ValueError(f"Unknown radar mode: {mode}")
    config = config or channel_scope.load_config()
    settings = radar_config(config)
    now = now or datetime.now(timezone.utc)
    observed_at = now.isoformat()
    state = load_state()
    summary: dict[str, Any] = {
        "run_at": observed_at,
        "mode": mode,
        "status": STATUS_COMPLETE,
        "errors": [],
        "api_calls": 0,
        "watchlist_size": 0,
        "new_channels": 0,
        "recent_videos": 0,
        "classified": {},
        "tracked": 0,
        "completed_tracking": 0,
        "excluded_candidates": 0,
        "packets_written": 0,
    }

    try:
        api_call = api or default_api()
    except RadarError as exc:
        summary.update(status=exc.code, errors=[str(exc)])
        _write_summary(summary)
        return summary

    def counted(resource: str, **params: Any) -> dict[str, Any]:
        summary["api_calls"] += 1
        return api_call(resource, **params)

    before = len(state["watchlist"])
    if mode == MODE_FULL:
        seed_watchlist_from_system(state, settings, now)
        discovery = bucket_discovery(state, searcher or search_url_flat, settings, now)
        summary["bucket_discovery"] = discovery
        if discovery["status"] in (THROTTLED, YT_DLP_FAILED):
            summary["status"] = STATUS_PARTIAL
            summary["errors"].append(f"bucket discovery: {discovery['status']}")
        state["last_discovery_run"] = observed_at

    try:
        uploads: dict[str, list[str]] = {}
        if mode == MODE_FULL:
            summary["errors"].extend(resolve_handles(state, counted, settings, now))
            refresh_channels(state, counted)
            uploads = crawl_uploads(state, counted, settings)
        tracked_ids = list(state["tracked"])
        measured = measure_videos([v for ids in uploads.values() for v in ids] + tracked_ids, counted)
    except RadarError as exc:
        summary.update(status=exc.code)
        summary["errors"].append(str(exc))
        save_state(state)
        _write_summary(summary)
        return summary

    summary["watchlist_size"] = len(state["watchlist"])
    summary["new_channels"] = len(state["watchlist"]) - before
    if mode == MODE_FULL and not state["watchlist"]:
        summary["status"] = STATUS_PARTIAL
        summary["errors"].append(
            "The watchlist is empty: no seed handle resolved and no channel has been seen yet."
        )
    window_hours = float(settings["active_window_days"]) * 24
    by_channel: dict[str, list[dict[str, Any]]] = {}
    for video in measured.values():
        by_channel.setdefault(str(video.get("channel_id")), []).append(video)
    for videos in by_channel.values():
        videos.sort(key=lambda v: str(v.get("published_at") or ""), reverse=True)

    topics = historical_topics()
    history_before = load_snapshot_history(SNAPSHOT_FILE)
    min_interval = float(settings["minimum_snapshot_interval_hours"])

    for video in measured.values():
        video_id = video["video_id"]
        hours = age_hours(video, now)
        record = state["tracked"].get(video_id)
        if hours is None or video.get("live") or video.get("views") is None:
            continue
        if hours > window_hours:
            if record:
                _complete(state, video_id, record, video, hours, observed_at)
                summary["completed_tracking"] += 1
            continue
        summary["recent_videos"] += 1
        state["seen_video_ids"].setdefault(video_id, observed_at)
        fmt = video_format(video, settings)
        follower_count = (state["watchlist"].get(str(video.get("channel_id"))) or {}).get("follower_count")
        baseline = channel_baseline(by_channel.get(str(video.get("channel_id")), []), fmt, settings, now)
        if not baseline["sufficient"] and record:
            baseline = record.get("baseline") or baseline  # keep the last good baseline
        metrics = ratios(video, baseline, follower_count, now)
        strength, rule_id = classify_strength(metrics, settings)
        summary["classified"][strength] = summary["classified"].get(strength, 0) + 1
        if strength not in settings["track_strengths"] and not record:
            continue
        record = record or {"first_seen_at": observed_at, "snapshots_taken": [], "classifications": []}
        if snapshot_due(record, hours, settings, now):
            append_snapshot(video, hours, observed_at)
            record["last_snapshot_at"] = observed_at
            record["snapshots_taken"] = (record.get("snapshots_taken") or []) + [observed_at]
        own_history = history_before.get(video_id, []) + (
            [{"video_id": video_id, "observed_at": observed_at, "views": int(video["views"])}]
            if record.get("last_snapshot_at") == observed_at
            else []
        )
        intervals = snapshot_intervals(video_id, {video_id: own_history}, min_interval)
        trajectory = classify_trajectory(intervals, baseline, settings)
        alignment, topic = classify_history(str(video.get("title") or ""), topics)
        record.update(
            video=video,
            format=fmt,
            baseline=baseline,
            metrics=metrics,
            strength=strength,
            strength_rule_id=rule_id,
            trajectory=trajectory,
            intervals=intervals[-6:],
            historical_alignment=alignment,
            historical_topic=topic,
            tracking_status="TRACKING",
        )
        record["classifications"] = (record.get("classifications") or []) + [
            {"at": observed_at, "age_hours": metrics["age_hours"], "strength": strength, "trajectory": trajectory}
        ]
        record["classifications"] = record["classifications"][-60:]
        state["tracked"][video_id] = record
        summary["tracked"] += 1

    # Tracked videos that disappeared (deleted or private) stop being tracked.
    for video_id in [v for v in state["tracked"] if v not in measured]:
        record = state["tracked"].pop(video_id)
        record["tracking_status"] = "UNAVAILABLE"
        state["completed"][video_id] = {"at": observed_at, "reason": "video unavailable", "last": record.get("metrics")}

    # O10: themes across independent channels, then one packet per breakout.
    clusters = viral_cluster.cluster(state["tracked"], config["viral_clustering"])
    by_video = {m["video_id"]: c for c in clusters for m in c["members"]}
    for video_id, record in state["tracked"].items():
        found = by_video.get(video_id)
        record["breadth"] = found["breadth"] if found else "UNASSESSED"
        record["cluster"] = (
            {k: v for k, v in found.items() if k != "members"} if found else None
        )
        packet = build_viral_packet(record, config)
        if packet["channel"]["route"] == models.ROUTE_EXCLUDED:
            summary["excluded_candidates"] += 1
            continue
        save_packet(packet)
        summary["packets_written"] += 1
    atomic_write_json(CLUSTERS_FILE, {"generated_at": observed_at, "clusters": clusters})
    summary["clusters"] = {
        "count": len(clusters),
        "replicated": sum(1 for c in clusters if c["breadth"] == "REPLICATED"),
    }

    # The seen-id cache only needs to cover the active window (plus margin).
    cutoff = now - timedelta(days=float(settings["active_window_days"]) * 2)
    state["seen_video_ids"] = {
        vid: seen
        for vid, seen in state["seen_video_ids"].items()
        if (_parse_time(seen) or now) >= cutoff
    }

    save_state(state)
    _write_summary(summary)
    return summary


def _complete(
    state: dict[str, Any], video_id: str, record: dict[str, Any], video: dict[str, Any], hours: float, at: str
) -> None:
    """Leave the active radar after the window; keep the outcome (R7)."""
    record["outcome"] = {
        "final_views": video.get("views"),
        "final_age_hours": round(hours, 2),
        "classified_at": _milestones(record.get("classifications") or []),
    }
    record["tracking_status"] = "TRACKING_COMPLETE"
    state["completed"][video_id] = {"at": at, "reason": "15-day window ended", "outcome": record["outcome"]}
    state["tracked"].pop(video_id, None)
    if load_packet(video_id) is not None and record.get("metrics"):
        record["video"] = {**record.get("video", {}), **{k: v for k, v in video.items() if v is not None}}
        try:
            save_packet(build_viral_packet(record, channel_scope.load_config()))
        except ValueError:
            pass


def _write_summary(summary: dict[str, Any]) -> None:
    atomic_write_json(SUMMARY_FILE, summary)


def snapshots_for(video_id: str) -> list[dict[str, Any]]:
    """The stored snapshots of one video, oldest first, for the trajectory chart (O14)."""
    if not VIDEO_ID_PATTERN.fullmatch(str(video_id or "")):
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = SNAPSHOT_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("video_id") == video_id and row.get("views") is not None:
            rows.append(
                {
                    "observed_at": row.get("observed_at"),
                    "views": int(row["views"]),
                    "video_age_hours": row.get("video_age_hours"),
                    "likes": row.get("likes"),
                    "comments": row.get("comments"),
                }
            )
    rows.sort(key=lambda r: str(r.get("observed_at") or ""))
    return rows


def load_clusters() -> list[dict[str, Any]]:
    try:
        payload = json.loads(CLUSTERS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    clusters = payload.get("clusters") if isinstance(payload, dict) else None
    return clusters if isinstance(clusters, list) else []


def load_cluster(cluster_id: str) -> dict[str, Any] | None:
    return next((c for c in load_clusters() if c.get("cluster_id") == cluster_id), None)


SPARKLINE_MAX_POINTS = 24


def _snapshot_series(video_ids: set[str]) -> dict[str, list[list[float]]]:
    """[age_hours, views] per video from the append-only snapshot log, one pass."""
    series: dict[str, list[list[float]]] = {video_id: [] for video_id in video_ids}
    if not video_ids:
        return series
    try:
        lines = SNAPSHOT_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return series
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or row.get("video_id") not in series:
            continue
        try:
            point = [float(row["video_age_hours"]), float(row["views"])]
        except (KeyError, TypeError, ValueError):
            continue
        series[str(row["video_id"])].append(point)
    for points in series.values():
        points.sort(key=lambda point: point[0])
        if len(points) > SPARKLINE_MAX_POINTS:
            step = (len(points) - 1) / (SPARKLINE_MAX_POINTS - 1)
            kept = [points[round(i * step)] for i in range(SPARKLINE_MAX_POINTS)]
            points[:] = kept
    return series


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def radar_overview(now: datetime | None = None) -> dict[str, Any]:
    """Everything the Viral Radar page shows, read from the radar's own files (UI-04).

    Themes come from the last clustering pass; tracked videos from the radar
    state; sparkline points from the snapshot log. Nothing is re-measured.
    """
    now = now or datetime.now(timezone.utc)
    settings = radar_config()
    window_days = int(settings.get("active_window_days") or 15)
    state = load_state()
    tracked: dict[str, dict[str, Any]] = state.get("tracked") or {}
    clusters = load_clusters()
    ids = set(tracked) | {
        str(member.get("video_id"))
        for cluster in clusters
        for member in cluster.get("members") or []
        if member.get("video_id")
    }
    series = _snapshot_series(ids)
    taste = taste_model()

    def video_row(video_id: str, record: dict[str, Any]) -> dict[str, Any]:
        video = record.get("video") or {}
        metrics = record.get("metrics") or {}
        published = _parse_time(video.get("published_at"))
        age = (now - published).total_seconds() / 3600 if published else _float(metrics.get("age_hours"))
        lane = radar_lane.classify(video.get("title"), video.get("channel_title"))
        score = taste.score(video.get("title"), video.get("channel_id"))
        return {
            "video_id": video_id,
            "lane": lane["lane"],
            "lane_hits": lane["hits"],
            "taste": score,
            "taste_label": radar_learning.taste_label(score),
            "opportunity_id": opportunity_id(models.SOURCE_VIRAL_RADAR, video_id),
            "title": video.get("title"),
            "channel_title": video.get("channel_title"),
            "format": record.get("format"),
            "strength": record.get("strength"),
            "trajectory": record.get("trajectory"),
            "breadth": record.get("breadth"),
            "historical_alignment": record.get("historical_alignment"),
            "lifetime_ratio": _float(metrics.get("lifetime_ratio")),
            "views": metrics.get("views", video.get("views")),
            "age_hours": round(age, 1) if age is not None else None,
            "day": min(window_days, int(age // 24) + 1) if age is not None and age >= 0 else None,
            "window_days": window_days,
            "first_seen_at": record.get("first_seen_at"),
            "cluster_id": (record.get("cluster") or {}).get("cluster_id"),
            "series": series.get(video_id, []),
        }

    videos = [video_row(video_id, record) for video_id, record in tracked.items() if isinstance(record, dict)]
    videos.sort(key=lambda row: -(row["lifetime_ratio"] or 0))
    by_id = {row["video_id"]: row for row in videos}

    themes = []
    for cluster in clusters:
        members = [m for m in cluster.get("members") or [] if isinstance(m, dict)]
        rows = [by_id[str(m.get("video_id"))] for m in members if str(m.get("video_id")) in by_id]
        ratios_ = sorted(
            r for r in (_float(m.get("lifetime_ratio")) for m in members) if r is not None
        )
        top = max(rows, key=lambda row: row["lifetime_ratio"] or 0) if rows else None
        seen = [str(row.get("first_seen_at")) for row in rows if row.get("first_seen_at")]
        themes.append(
            {
                "cluster_id": cluster.get("cluster_id"),
                "label": cluster.get("label"),
                "kind": cluster.get("kind"),
                "breadth": cluster.get("breadth"),
                "replication_rule_id": cluster.get("replication_rule_id"),
                "independent_channel_count": cluster.get("independent_channel_count"),
                "member_count": cluster.get("member_count", len(members)),
                "lane": radar_lane.theme_lane([row["lane"] for row in rows]),
                "taste": max((r["taste"] for r in rows if r.get("taste") is not None), default=None),
                "strongest_ratio": ratios_[-1] if ratios_ else None,
                "median_ratio": _median(ratios_),
                "direction": top.get("trajectory") if top else None,
                "historical_alignment": top.get("historical_alignment") if top else None,
                "first_detected_at": min(seen) if seen else None,
                "top_video_id": top.get("video_id") if top else None,
                "top_opportunity_id": top.get("opportunity_id") if top else None,
                "momentum": top.get("series") if top else [],
                "videos": [
                    {k: row[k] for k in ("video_id", "opportunity_id", "title", "channel_title", "lifetime_ratio", "trajectory", "lane", "day", "taste", "taste_label")}
                    for row in sorted(rows, key=lambda row: -(row["lifetime_ratio"] or 0))
                ],
            }
        )
    themes.sort(
        key=lambda theme: (
            theme["breadth"] != "REPLICATED",
            -(theme["strongest_ratio"] or 0),
        )
    )
    return {
        "generated_at": now.isoformat(),
        "window_days": window_days,
        "themes": themes,
        "tracked": videos,
        "learning": taste.status(),
        "status": status_snapshot(),
    }


def taste_model() -> radar_learning.TasteModel:
    """What the operator picks, learned from inbox decisions on radar packets (D-165)."""
    from opportunity_engine import inbox  # the inbox imports this module

    try:
        items = inbox.load_state().get("items") or {}
    except (OSError, ValueError, AttributeError):
        items = {}
    return radar_learning.TasteModel(radar_learning.examples(items, list_packets()))


def status_snapshot() -> dict[str, Any]:
    state = load_state()
    try:
        last = json.loads(SUMMARY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        last = None
    return {
        "last_run": last,
        "watchlist_size": len(state["watchlist"]),
        "tracked_count": len(state["tracked"]),
        "completed_count": len(state["completed"]),
        "throttled_until": state.get("throttled_until"),
        "replicated_themes": sum(1 for c in load_clusters() if c.get("breadth") == "REPLICATED"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["run", "snapshots", "status"])
    args = parser.parse_args()
    if args.mode == "status":
        print(json.dumps(status_snapshot(), indent=2))
        return
    summary = run(mode=MODE_SNAPSHOTS if args.mode == "snapshots" else MODE_FULL)
    print(f"Viral radar: {summary['status']}  ({summary['api_calls']} API calls)")
    print(f"  Watchlist {summary['watchlist_size']} channels (+{summary['new_channels']} new)")
    print(f"  Recent uploads checked {summary['recent_videos']}: {summary['classified']}")
    print(f"  Tracked {summary['tracked']}, packets written {summary['packets_written']}, finished tracking {summary['completed_tracking']}")
    for error in summary["errors"]:
        print(f"  ! {error}")
    if summary["status"] not in (STATUS_COMPLETE, STATUS_PARTIAL):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
