"""Explore My Topic: a topic or question becomes an Opportunity Packet (slice O4).

The seed does not need to exist in niches.json. It is normalised, expanded into
a few deterministic search variants, searched on YouTube with yt-dlp (one flat
search request per variant: no quota, nothing downloaded), and the results are
measured with the YouTube Data API (1 quota unit per 50 videos; the flat search
metadata is the fallback). Only relevant, non-excluded results count as
evidence, and every evidence level names the written rule that set it.

Search results are a sample, not the age-matched 01.3 engine: the packet says
so, and a topic may stay valid without crossing historical thresholds.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess  # nosec B404 - fixed argument list, no shell
import sys
import time
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from opportunity_engine import channel_scope, models  # noqa: E402
from opportunity_engine.human_video_intake import (  # noqa: E402
    IntakeError,
    SHORT_MAX_SECONDS,
    VIDEO_ID_PATTERN,
    _iso8601_seconds,
    _load_api_key,
    watch_url,
)
from opportunity_engine.packet_schema import build_packet, evidence, validate_packet  # noqa: E402
from opportunity_engine.provenance import opportunity_id  # noqa: E402

HERE = Path(__file__).resolve().parent
PACKETS_DIR = HERE / "output" / "opportunities" / "human_topic"
GENERATOR = "opportunity_engine.human_topic_search"
TOPIC_KEY_PATTERN = re.compile(r"^[a-z0-9_]{1,120}$")

QUESTION_WORDS = {
    "why", "how", "what", "when", "where", "which", "who", "does", "do", "did",
    "can", "could", "is", "are", "was", "were", "will", "would", "should",
}
STOPWORDS = QUESTION_WORDS | {
    "the", "and", "for", "with", "that", "this", "from", "into", "your", "you",
    "its", "it's", "they", "them", "their", "than", "then", "there", "about",
    "over", "under", "just", "really", "actually", "explained", "science",
    "suddenly", "work", "works", "happen", "happens", "make", "makes", "get",
    "gets", "a", "an", "of", "in", "on", "to", "at", "by", "or", "so",
}


def topic_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    return (config or channel_scope.load_config())["human_topic"]


# --------------------------------------------------------------------------
# Seed
# --------------------------------------------------------------------------


def normalize_seed(raw: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = topic_config(config)
    text = re.sub(r"\s+", " ", str(raw or "")).strip()
    if not text:
        raise IntakeError("Type a topic or a viewer question.")
    if len(text) > int(settings["max_seed_chars"]):
        raise IntakeError(f"Keep it under {settings['max_seed_chars']} characters.")
    if re.search(r"https?://|www\.|youtu\.?be", text, re.IGNORECASE):
        raise IntakeError("That looks like a link. Use Analyze a video for links.")
    words = text.rstrip("?").split()
    first = words[0].lower() if words else ""
    kind = "QUESTION" if text.endswith("?") or first in QUESTION_WORDS else "TOPIC"
    core_words = list(words)
    while kind == "QUESTION" and core_words and core_words[0].lower() in QUESTION_WORDS:
        core_words.pop(0)
    while len(core_words) > 1 and core_words[0].lower() in {"a", "an", "the"}:
        core_words.pop(0)
    core = " ".join(core_words) or text.rstrip("?")
    keywords = []
    for word in re.findall(r"[a-z0-9]+", core.lower()):
        has_digit = any(ch.isdigit() for ch in word)
        if (len(word) >= 3 or has_digit) and word not in STOPWORDS and word not in keywords:
            keywords.append(word)
    if not keywords:
        raise IntakeError("Add a more specific word or two so the search has something to match.")
    return {
        "text": text,
        "kind": kind,
        "question": text if kind == "QUESTION" else None,
        "core": core,
        "keywords": keywords,
        "topic_key": re.sub(r"[^a-z0-9]+", "_", core.lower()).strip("_")[:120] or "topic",
    }


def search_variants(seed: dict[str, Any], config: dict[str, Any] | None = None) -> list[str]:
    settings = topic_config(config)
    templates = settings["variant_templates"][seed["kind"]]
    variants: list[str] = []
    for template in templates:
        query = template.format(core=seed["core"], question=seed["text"]).strip()
        query = re.sub(r"\s+", " ", query)
        if query and query.lower() not in {v.lower() for v in variants}:
            variants.append(query)
    return variants[: int(settings["max_variants"])]


def _keyword_hit(keyword: str, title_words: list[str]) -> bool:
    prefix = keyword if len(keyword) <= 4 else keyword[: max(4, len(keyword) - 2)]
    return any(word == keyword or word.startswith(prefix) for word in title_words)


def relevance(title: str, keywords: list[str]) -> dict[str, Any]:
    title_words = re.findall(r"[a-z0-9]+", str(title or "").lower())
    hits = [k for k in keywords if _keyword_hit(k, title_words)]
    needed = min(2, len(keywords))
    return {"relevant": len(hits) >= needed, "hits": hits, "needed": needed}


# --------------------------------------------------------------------------
# Search and measurement
# --------------------------------------------------------------------------


def search_flat(query: str, limit: int, timeout_seconds: int) -> list[dict[str, Any]]:
    """One yt-dlp flat search request. Raises IntakeError on failure."""
    binary = shutil.which("yt-dlp")
    if not binary:
        raise IntakeError("yt-dlp is not installed")
    command = [
        binary,
        "--flat-playlist",
        "--dump-single-json",
        "--no-warnings",
        "--",
        f"ytsearch{int(limit)}:{query}",
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
        raise IntakeError(f"search timed out after {timeout_seconds}s") from exc
    except OSError as exc:
        raise IntakeError(f"yt-dlp failed to start: {exc}") from exc
    if completed.returncode != 0:
        message = (completed.stderr or "").strip().splitlines() or ["no output"]
        raise IntakeError("yt-dlp search failed: " + message[-1][:300])
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise IntakeError("yt-dlp returned unreadable search results") from exc
    results = []
    for entry in (payload or {}).get("entries") or []:
        if not isinstance(entry, dict):
            continue
        video_id = str(entry.get("id") or "")
        if not VIDEO_ID_PATTERN.fullmatch(video_id):
            continue
        results.append(
            {
                "video_id": video_id,
                "title": entry.get("title"),
                "channel_id": entry.get("channel_id"),
                "channel_title": entry.get("channel") or entry.get("uploader"),
                "duration_seconds": entry.get("duration"),
                "views": entry.get("view_count"),
            }
        )
    return results


def measure_via_api(video_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Batch videos.list (1 unit per 50 ids). Raises IntakeError on failure."""
    api_key = _load_api_key()
    if not api_key:
        raise IntakeError("YOUTUBE_API_KEY is not configured")
    from experiment_01_discovery.youtube_discovery import api_get

    measured: dict[str, dict[str, Any]] = {}
    for start in range(0, len(video_ids), 50):
        batch = video_ids[start : start + 50]
        try:
            data = api_get(
                "videos",
                api_key,
                part="snippet,statistics,contentDetails,status",
                id=",".join(batch),
                maxResults=50,
            )
        except (SystemExit, urllib.error.URLError, OSError, RuntimeError, ValueError) as exc:
            raise IntakeError(f"YouTube API request failed: {exc}") from exc
        for item in data.get("items") or []:
            snippet = item.get("snippet") or {}
            stats = item.get("statistics") or {}
            measured[str(item.get("id"))] = {
                "title": snippet.get("title"),
                "channel_id": snippet.get("channelId"),
                "channel_title": snippet.get("channelTitle"),
                "published_at": snippet.get("publishedAt"),
                "duration_seconds": _iso8601_seconds(
                    str((item.get("contentDetails") or {}).get("duration") or "")
                ),
                "views": int(stats["viewCount"]) if str(stats.get("viewCount", "")).isdigit() else None,
                "likes": int(stats["likeCount"]) if str(stats.get("likeCount", "")).isdigit() else None,
                "made_for_kids": (item.get("status") or {}).get("madeForKids"),
            }
    return measured


Searcher = Callable[[str, int, int], "list[dict[str, Any]]"]
Measurer = Callable[["list[str]"], "dict[str, dict[str, Any]]"]


def run_searches(
    variants: list[str],
    *,
    settings: dict[str, Any],
    searcher: Searcher | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Search every variant; dedupe by video id; record each variant's outcome."""
    searcher = searcher or search_flat
    found: dict[str, dict[str, Any]] = {}
    log: list[dict[str, Any]] = []
    for query in variants:
        started = time.monotonic()
        try:
            results = searcher(
                query, int(settings["results_per_variant"]), int(settings["search_timeout_seconds"])
            )
        except IntakeError as exc:
            log.append({"query": query, "status": "FAILED", "error": str(exc)})
            continue
        new = 0
        for result in results:
            if result["video_id"] not in found:
                found[result["video_id"]] = {**result, "matched_queries": [query]}
                new += 1
            else:
                found[result["video_id"]]["matched_queries"].append(query)
        log.append(
            {
                "query": query,
                "status": "COMPLETE",
                "result_count": len(results),
                "new_video_count": new,
                "seconds": round(time.monotonic() - started, 1),
            }
        )
    return list(found.values()), log


# --------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------


def _channels_at(videos: list[dict[str, Any]], minimum_views: int) -> set[str]:
    return {
        str(v.get("channel_id") or v.get("channel_title"))
        for v in videos
        if (v.get("channel_id") or v.get("channel_title"))
        and int(v.get("views") or 0) >= minimum_views
    }


def _apply_rules(rules: list[dict[str, Any]], videos: list[dict[str, Any]], what: str) -> dict[str, Any]:
    for rule in rules:
        channels = _channels_at(videos, int(rule["minimum_views"]))
        if len(channels) >= int(rule["minimum_channels"]):
            return evidence(
                rule["level"],
                rule["rule_id"],
                [
                    f"{len(channels)} independent channel(s) with a relevant video at "
                    f"{int(rule['minimum_views']):,}+ views ({what}; search sample)"
                ],
            )
    return evidence("UNASSESSED")


def topic_evidence(videos: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rules = config["evidence_rules"]
    state = {
        "cross_channel_replication": _apply_rules(
            rules["human_topic_replication"], videos, "replication"
        ),
    }
    if videos:
        state["historical_demand"] = _apply_rules(rules["human_topic_demand"], videos, "demand")
    return state


# --------------------------------------------------------------------------
# Packets
# --------------------------------------------------------------------------


def packet_path(topic_key: str) -> Path:
    return PACKETS_DIR / f"{topic_key}.json"


def _age_days(published_at: Any, now: datetime) -> float | None:
    try:
        published = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    return round(max((now - published).total_seconds() / 86400, 1 / 24), 2)


def explore(
    raw: str,
    *,
    note: str = "",
    searcher: Searcher | None = None,
    measurer: Measurer | None = None,
    config: dict[str, Any] | None = None,
    now: datetime | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """Search a topic and build its packet; ``save=False`` only returns it (D-174)."""
    config = config or channel_scope.load_config()
    settings = topic_config(config)
    now = now or datetime.now(timezone.utc)
    seed = normalize_seed(raw, config)
    seed_route = channel_scope.route(seed["text"], niche="everyday_science", config=config)
    variants = search_variants(seed, config)
    found, search_log = run_searches(variants, settings=settings, searcher=searcher)
    if not any(entry["status"] == "COMPLETE" for entry in search_log):
        details = "; ".join(f"{e['query']}: {e.get('error')}" for e in search_log)
        raise IntakeError(f"YouTube search failed for every variant ({details}). Nothing was saved.")

    measurement = {"source": "YT_DLP_FLAT_SEARCH", "error": None}
    measured: dict[str, dict[str, Any]] = {}
    if found:
        try:
            measured = (measurer or measure_via_api)([v["video_id"] for v in found])
            if measured:
                measurement["source"] = "YOUTUBE_DATA_API"
        except IntakeError as exc:
            measurement["error"] = str(exc)

    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    irrelevant = 0
    for result in found:
        video = {**result, **{k: v for k, v in measured.get(result["video_id"], {}).items() if v is not None}}
        match = relevance(video.get("title") or "", seed["keywords"])
        if not match["relevant"]:
            irrelevant += 1
            continue
        route = channel_scope.route(
            str(video.get("title") or ""),
            niche="everyday_science",
            made_for_kids=bool(video.get("made_for_kids")),
            config=config,
        )
        duration = int(video.get("duration_seconds") or 0)
        entry = {
            "video_id": video["video_id"],
            "youtube_url": watch_url(video["video_id"]),
            "title": video.get("title"),
            "channel_id": video.get("channel_id"),
            "channel_title": video.get("channel_title"),
            "format": "short" if 0 < duration <= SHORT_MAX_SECONDS else "long_form",
            "published_at": video.get("published_at"),
            "age_days": _age_days(video.get("published_at"), now) if video.get("published_at") else None,
            "duration_seconds": duration,
            "views": video.get("views"),
            "likes": video.get("likes"),
            "measurement_source": measurement["source"] if video["video_id"] in measured else "YT_DLP_FLAT_SEARCH",
            "matched_queries": video.get("matched_queries", []),
            "keyword_hits": match["hits"],
            "route": route["route"],
            "route_rule_id": route.get("rule_id"),
        }
        (excluded if route["route"] == models.ROUTE_EXCLUDED else candidates).append(entry)

    candidates.sort(key=lambda v: int(v.get("views") or 0), reverse=True)
    candidates = candidates[: int(settings["max_candidate_videos"])]
    formats = sorted({v["format"] for v in candidates}) or ["long_form"]
    packet = build_packet(
        opportunity_id=opportunity_id(models.SOURCE_HUMAN_TOPIC, seed["topic_key"]),
        source_type=models.SOURCE_HUMAN_TOPIC,
        title=seed["text"],
        summary=(
            f"{len(candidates)} relevant video(s) from "
            f"{len(_channels_at(candidates, 0))} channel(s) across {len(variants)} searches. "
            "Search results are a sample, not the age-matched historical engine."
        ),
        channel=seed_route,
        topic=seed["core"],
        niche="everyday_science",
        formats=formats,
        seed={"topic": seed["core"], "question": seed["question"]},
        evidence_state=topic_evidence(candidates, config),
        candidate_videos=candidates,
        generator=GENERATOR,
        created_at=now.isoformat(),
    )
    packet["human_notes"] = [note.strip()] if note.strip() else []
    packet["intake"] = {
        "topic_key": seed["topic_key"],
        "seed_kind": seed["kind"],
        "keywords": seed["keywords"],
        "variants": variants,
        "search_log": search_log,
        "measurement": measurement,
        "found_count": len(found),
        "irrelevant_count": irrelevant,
        "excluded_videos": [
            {"video_id": v["video_id"], "title": v["title"], "rule_id": v["route_rule_id"]}
            for v in excluded
        ],
    }
    if save:
        save_packet(packet)
    return packet


def save_packet(packet: dict[str, Any]) -> Path:
    errors = validate_packet(packet)
    if errors:
        raise ValueError("Invalid HUMAN_TOPIC packet: " + "; ".join(errors))
    path = packet_path(packet["intake"]["topic_key"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_packet(topic_key: str) -> dict[str, Any] | None:
    if not TOPIC_KEY_PATTERN.fullmatch(str(topic_key or "")):
        return None
    path = packet_path(topic_key)
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return packet if isinstance(packet, dict) else None


def list_packets() -> list[dict[str, Any]]:
    if not PACKETS_DIR.is_dir():
        return []
    packets = [p for p in (load_packet(path.stem) for path in PACKETS_DIR.glob("*.json")) if p]
    return sorted(packets, key=lambda p: str(p.get("created_at") or ""), reverse=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("topic", help="A topic or viewer question, e.g. 'Why are aircraft windows round?'")
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    try:
        packet = explore(args.topic, note=args.note)
    except IntakeError as exc:
        raise SystemExit(f"Not saved: {exc}") from exc
    state = packet["evidence_state"]
    print(f"Saved {packet['opportunity_id']}  ({packet['channel']['route']})")
    print(f"  {packet['summary']}")
    print(f"  Demand: {state['historical_demand']['level']}  Replication: {state['cross_channel_replication']['level']}")
    for video in packet["candidate_videos"][:5]:
        print(f"  - {video['views']} views  {video['title']}  [{video['channel_title']}]")


if __name__ == "__main__":
    main()
