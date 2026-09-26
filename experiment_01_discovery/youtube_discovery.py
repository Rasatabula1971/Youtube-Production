"""Stage 2 Experiment 01.2 — Relevance & Evidence Quality.

Purpose:
Discover proven YouTube content and collect independent signals for:

1. Demand
2. Breakout performance
3. Momentum proxy
4. Channel-baseline quality
5. Format candidate
6. Search provenance
7. Relevance quality
8. Outlier reliability
9. Content themes

IMPORTANT:
This is research tooling.

The program deliberately DOES NOT calculate a final score yet.
We first collect data across the niches, inspect the distribution,
and then decide what scoring thresholds are justified.

No third-party Python packages required.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evidence_quality import (
    RELEVANCE_ADJACENT,
    RELEVANCE_OFF_INTENT,
    RELEVANCE_ON_INTENT,
    RELIABILITY_CAUTION,
    RELIABILITY_TRUSTED,
    RELIABILITY_UNAVAILABLE,
    annotate_evidence_quality,
)


# ============================================================
# PATHS
# ============================================================

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent

ENV_FILE = PROJECT_ROOT / ".env"
NICHE_FILE = HERE / "niches.json"
OUTPUT_DIR = HERE / "output"


# ============================================================
# RESEARCH COLLECTION FLOOR
# ============================================================

# Keep videos at or above this level for Stage 2 analysis.
# This is NOT the final selection threshold.

ANALYSIS_MIN_VIEWS = 500_000


# ============================================================
# ORIGINAL PROVEN-DEMAND REFERENCE THRESHOLDS
#
# These are retained as reference measurements only.
# They do NOT produce a final recommendation.
# ============================================================

LONG_FORM_REFERENCE_VIEWS = 1_000_000
SHORT_CANDIDATE_REFERENCE_VIEWS = 5_000_000


# ============================================================
# YOUTUBE API
# ============================================================

YOUTUBE_API = "https://www.googleapis.com/youtube/v3"


# ============================================================
# ENVIRONMENT
# ============================================================

def load_env_file(path: Path) -> None:
    """Load KEY=VALUE entries from the project .env file."""

    if not path.exists():
        print(f"WARNING: .env file not found: {path}")
        return

    for raw_line in path.read_text(
        encoding="utf-8"
    ).splitlines():

        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)

        key = key.strip()

        value = (
            value
            .strip()
            .strip('"')
            .strip("'")
        )

        if key and key not in os.environ:
            os.environ[key] = value


# ============================================================
# API ERROR DISPLAY
# ============================================================

def display_http_error(
    exc: urllib.error.HTTPError,
) -> None:

    try:
        body = exc.read().decode(
            "utf-8",
            errors="replace",
        )
    except Exception:
        body = "<Could not read response body>"

    print()
    print("=" * 60)
    print("YOUTUBE API ERROR")
    print("=" * 60)

    print(f"HTTP status: {exc.code}")
    print(f"Reason:      {exc.reason}")

    print()
    print("Google response:")
    print("-" * 60)

    try:
        parsed = json.loads(body)

        print(
            json.dumps(
                parsed,
                indent=2,
                ensure_ascii=False,
            )
        )

    except json.JSONDecodeError:
        print(body)

    print("-" * 60)
    print()


# ============================================================
# API REQUEST
# ============================================================

def api_get(
    resource: str,
    api_key: str,
    **params: Any,
) -> dict[str, Any]:

    params["key"] = api_key

    query_string = urllib.parse.urlencode(
        params
    )

    url = (
        f"{YOUTUBE_API}/{resource}"
        f"?{query_string}"
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "YouTube-Production-Stage2-Research/1.1"
        },
    )

    for attempt in range(4):

        try:

            with urllib.request.urlopen(
                request,
                timeout=30,
            ) as response:

                raw = response.read().decode(
                    "utf-8"
                )

                return json.loads(raw)

        except urllib.error.HTTPError as exc:

            display_http_error(exc)

            if 400 <= exc.code < 500:

                raise SystemExit(
                    "YouTube rejected the request. "
                    "Read the API error above."
                )

            if attempt == 3:
                raise

        except urllib.error.URLError as exc:

            if attempt == 3:
                raise

            wait_seconds = 2 ** attempt

            print(
                f"Network error: {exc}"
            )

            print(
                f"Retrying in {wait_seconds}s..."
            )

            time.sleep(wait_seconds)

        except Exception:

            if attempt == 3:
                raise

            wait_seconds = 2 ** attempt

            print(
                "Unexpected API error. "
                f"Retrying in {wait_seconds}s..."
            )

            time.sleep(wait_seconds)

    raise RuntimeError(
        "API request failed after retries."
    )


# ============================================================
# HELPERS
# ============================================================

def parse_duration_seconds(
    duration: str,
) -> int:

    match = re.fullmatch(
        r"PT(?:(\d+)H)?"
        r"(?:(\d+)M)?"
        r"(?:(\d+)S)?",
        duration or "",
    )

    if not match:
        return 0

    hours, minutes, seconds = (
        int(value or 0)
        for value in match.groups()
    )

    return (
        hours * 3600
        + minutes * 60
        + seconds
    )


def parse_time(
    value: str,
) -> datetime:

    return datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )


def age_days(
    published_at: str,
) -> float:

    delta = (
        datetime.now(timezone.utc)
        - parse_time(published_at)
    )

    return max(
        delta.total_seconds() / 86400,
        1 / 24,
    )


def chunks(
    values: list[str],
    size: int = 50,
):

    for index in range(
        0,
        len(values),
        size,
    ):

        yield values[
            index:index + size
        ]


# ============================================================
# FORMAT CANDIDATE
# ============================================================

def classify_format_candidate(
    duration_seconds: int,
) -> str:
    """
    Research heuristic ONLY.

    <=180 seconds is called short_candidate.

    This does NOT claim YouTube actually classified
    the video as a Short.
    """

    if (
        duration_seconds > 0
        and duration_seconds <= 180
    ):
        return "short_candidate"

    return "long_form_candidate"


# ============================================================
# BASELINE QUALITY
# ============================================================

def baseline_confidence(
    sample_size: int,
) -> str:
    """
    Describe how much comparison data was available.

    This is not a judgment about the video's quality.
    """

    if sample_size >= 8:
        return "strong_sample"

    if sample_size >= 5:
        return "moderate_sample"

    if sample_size >= 3:
        return "weak_sample"

    if sample_size >= 1:
        return "very_weak_sample"

    return "no_baseline"


def baseline_warning(
    baseline: float | None,
    sample_size: int,
) -> str:
    """
    Flag situations where an outlier ratio can become misleading.
    """

    warnings: list[str] = []

    if sample_size < 5:
        warnings.append(
            "small_baseline_sample"
        )

    if baseline is not None:

        if baseline < 1_000:
            warnings.append(
                "extremely_small_channel_baseline"
            )

        elif baseline < 5_000:
            warnings.append(
                "small_channel_baseline"
            )

    if not warnings:
        return ""

    return "|".join(warnings)


# ============================================================
# VIDEO DETAILS
# ============================================================

def get_video_details(
    video_ids: list[str],
    api_key: str,
) -> dict[str, dict[str, Any]]:

    results: dict[
        str,
        dict[str, Any]
    ] = {}

    unique_ids = list(
        dict.fromkeys(video_ids)
    )

    for batch in chunks(
        unique_ids
    ):

        data = api_get(
            "videos",
            api_key,
            part=(
                "snippet,"
                "statistics,"
                "contentDetails"
            ),
            id=",".join(batch),
            maxResults=50,
        )

        for item in data.get(
            "items",
            [],
        ):

            results[
                item["id"]
            ] = item

    return results


# ============================================================
# CHANNEL DETAILS
# ============================================================

def get_channel_details(
    channel_ids: list[str],
    api_key: str,
) -> dict[str, dict[str, Any]]:

    results: dict[
        str,
        dict[str, Any]
    ] = {}

    unique_ids = list(
        dict.fromkeys(channel_ids)
    )

    for batch in chunks(
        unique_ids
    ):

        data = api_get(
            "channels",
            api_key,
            part=(
                "snippet,"
                "statistics,"
                "contentDetails"
            ),
            id=",".join(batch),
            maxResults=50,
        )

        for item in data.get(
            "items",
            [],
        ):

            results[
                item["id"]
            ] = item

    return results


# ============================================================
# RECENT CHANNEL UPLOADS
# ============================================================

def get_recent_upload_ids(
    channel: dict[str, Any],
    api_key: str,
    maximum: int = 25,
) -> list[str]:

    uploads_playlist = (
        channel
        .get(
            "contentDetails",
            {},
        )
        .get(
            "relatedPlaylists",
            {},
        )
        .get("uploads")
    )

    if not uploads_playlist:
        return []

    data = api_get(
        "playlistItems",
        api_key,
        part="contentDetails",
        playlistId=uploads_playlist,
        maxResults=min(
            maximum,
            50,
        ),
    )

    results: list[str] = []

    for item in data.get(
        "items",
        [],
    ):

        video_id = (
            item
            .get(
                "contentDetails",
                {},
            )
            .get("videoId")
        )

        if video_id:
            results.append(
                video_id
            )

    return results


# ============================================================
# CHANNEL BASELINE
# ============================================================

def calculate_channel_baseline(
    candidate: dict[str, Any],
    history: list[dict[str, Any]],
) -> tuple[
    float | None,
    int,
]:

    candidate_id = (
        candidate["video_id"]
    )

    candidate_format = (
        candidate["format_candidate"]
    )

    comparable_views: list[int] = []

    for video in history:

        if video["id"] == candidate_id:
            continue

        duration = (
            parse_duration_seconds(
                video
                .get(
                    "contentDetails",
                    {},
                )
                .get(
                    "duration",
                    "",
                )
            )
        )

        video_format = (
            classify_format_candidate(
                duration
            )
        )

        if (
            video_format
            != candidate_format
        ):
            continue

        views = int(
            video
            .get(
                "statistics",
                {},
            )
            .get(
                "viewCount",
                0,
            )
        )

        comparable_views.append(
            views
        )

        if (
            len(comparable_views)
            >= 10
        ):
            break

    if not comparable_views:
        return None, 0

    baseline = float(
        statistics.median(
            comparable_views
        )
    )

    return (
        baseline,
        len(comparable_views),
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Stage 2 Experiment 01.1 — "
            "collect independent YouTube "
            "opportunity signals."
        )
    )

    parser.add_argument(
        "--max-searches",
        type=int,
        default=30,
        help=(
            "Maximum number of "
            "YouTube search.list requests."
        ),
    )

    parser.add_argument(
        "--published-after",
        default=None,
        help=(
            "Optional RFC3339 date. "
            "Example: "
            "2025-01-01T00:00:00Z"
        ),
    )

    parser.add_argument(
        "--region-code",
        default=None,
    )

    parser.add_argument(
        "--language",
        default=None,
    )

    args = parser.parse_args()

    # ========================================================
    # LOAD ENVIRONMENT
    # ========================================================

    print()
    print(
        "Loading environment from:"
    )

    print(
        f"  {ENV_FILE}"
    )

    load_env_file(
        ENV_FILE
    )

    api_key = os.getenv(
        "YOUTUBE_API_KEY"
    )

    if not api_key:

        raise SystemExit(
            "\nERROR: YOUTUBE_API_KEY "
            "was not found.\n\n"
            f"Expected file:\n"
            f"{ENV_FILE}\n"
        )

    print(
        "YouTube API key found."
    )

    # ========================================================
    # LOAD NICHES
    # ========================================================

    if not NICHE_FILE.exists():

        raise SystemExit(
            f"Cannot find {NICHE_FILE}"
        )

    try:

        config = json.loads(
            NICHE_FILE.read_text(
                encoding="utf-8"
            )
        )

    except json.JSONDecodeError as exc:

        raise SystemExit(
            f"Invalid niches.json: {exc}"
        )

    if "niches" not in config:

        raise SystemExit(
            "niches.json must contain "
            "a 'niches' array."
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ========================================================
    # DISCOVERY
    # ========================================================

    discovered: dict[
        str,
        set[str],
    ] = {}

    query_matches: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    search_calls = 0

    print()
    print(
        "STAGE 2 — EXPERIMENT 01.2"
    )

    print(
        "=" * 60
    )

    print(
        "Collecting Demand + Breakout + "
        "Momentum signals..."
    )

    print()

    for niche in config["niches"]:

        niche_name = niche["name"]

        print(
            f"Niche: {niche_name}"
        )

        for query in niche[
            "queries"
        ]:

            if (
                search_calls
                >= args.max_searches
            ):
                break

            print(
                f"  Searching: {query}"
            )

            params: dict[
                str,
                Any,
            ] = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "order": "viewCount",
                "maxResults": 50,
            }

            if args.published_after:

                params[
                    "publishedAfter"
                ] = args.published_after

            if args.region_code:

                params[
                    "regionCode"
                ] = args.region_code

            if args.language:

                params[
                    "relevanceLanguage"
                ] = args.language

            data = api_get(
                "search",
                api_key,
                **params,
            )

            search_calls += 1

            for rank, item in enumerate(
                data.get(
                    "items",
                    [],
                ),
                start=1,
            ):

                video_id = (
                    item
                    .get(
                        "id",
                        {},
                    )
                    .get(
                        "videoId"
                    )
                )

                if video_id:

                    discovered.setdefault(
                        video_id,
                        set(),
                    ).add(
                        niche_name
                    )

                    query_matches.setdefault(
                        video_id,
                        [],
                    ).append(
                        {
                            "niche": niche_name,
                            "query": query,
                            "rank": rank,
                        }
                    )

        if (
            search_calls
            >= args.max_searches
        ):
            break

    print()

    print(
        "Unique videos discovered: "
        f"{len(discovered):,}"
    )

    # ========================================================
    # VIDEO DETAILS
    # ========================================================

    print(
        "Downloading video statistics..."
    )

    details = get_video_details(
        list(discovered),
        api_key,
    )

    channel_ids = list(
        {
            video[
                "snippet"
            ][
                "channelId"
            ]
            for video
            in details.values()
        }
    )

    print(
        "Channels discovered: "
        f"{len(channel_ids):,}"
    )

    channels = (
        get_channel_details(
            channel_ids,
            api_key,
        )
    )

    # ========================================================
    # BUILD DATASET
    # ========================================================

    rows: list[
        dict[str, Any]
    ] = []

    for (
        video_id,
        item,
    ) in details.items():

        stats = item.get(
            "statistics",
            {},
        )

        snippet = item.get(
            "snippet",
            {},
        )

        views = int(
            stats.get(
                "viewCount",
                0,
            )
        )

        # Keep >=500K for research.
        if views < ANALYSIS_MIN_VIEWS:
            continue

        duration_seconds = (
            parse_duration_seconds(
                item
                .get(
                    "contentDetails",
                    {},
                )
                .get(
                    "duration",
                    "",
                )
            )
        )

        format_candidate = (
            classify_format_candidate(
                duration_seconds
            )
        )

        published_at = (
            snippet.get(
                "publishedAt",
                "",
            )
        )

        days = age_days(
            published_at
        )

        average_views_per_day = (
            views / days
        )

        if "likeCount" in stats:

            likes: int | None = int(
                stats["likeCount"]
            )

        else:
            likes = None

        channel_id = (
            snippet.get(
                "channelId",
                "",
            )
        )

        channel = channels.get(
            channel_id,
            {},
        )

        channel_stats = channel.get(
            "statistics",
            {},
        )

        subscriber_count = int(
            channel_stats.get(
                "subscriberCount",
                0,
            )
            or 0
        )

        # ----------------------------------------------------
        # Reference threshold only.
        #
        # This does NOT mean selected/rejected.
        # ----------------------------------------------------

        if (
            format_candidate
            == "short_candidate"
        ):

            meets_original_reference = (
                views
                >= SHORT_CANDIDATE_REFERENCE_VIEWS
            )

        else:

            meets_original_reference = (
                views
                >= LONG_FORM_REFERENCE_VIEWS
            )

        rows.append(
            {
                # --------------------------------------------
                # Identity
                # --------------------------------------------

                "video_id":
                    video_id,

                "youtube_url":
                    (
                        "https://www.youtube.com/"
                        "watch?v="
                        + video_id
                    ),

                "title":
                    snippet.get(
                        "title",
                        "",
                    ),

                "channel_id":
                    channel_id,

                "channel_title":
                    snippet.get(
                        "channelTitle",
                        "",
                    ),

                "niches":
                    sorted(
                        discovered.get(
                            video_id,
                            set(),
                        )
                    ),

                "matched_queries":
                    sorted(
                        {
                            match["query"]
                            for match
                            in query_matches.get(
                                video_id,
                                [],
                            )
                        }
                    ),

                "best_search_rank":
                    min(
                        (
                            match["rank"]
                            for match
                            in query_matches.get(
                                video_id,
                                [],
                            )
                        ),
                        default=None,
                    ),

                "query_matches":
                    query_matches.get(
                        video_id,
                        [],
                    ),

                # --------------------------------------------
                # Format signal
                # --------------------------------------------

                "duration_seconds":
                    duration_seconds,

                "format_candidate":
                    format_candidate,

                # --------------------------------------------
                # Demand signal
                # --------------------------------------------

                "views":
                    views,

                "meets_original_reference":
                    meets_original_reference,

                # --------------------------------------------
                # Momentum proxy
                # --------------------------------------------

                "published_at":
                    published_at,

                "age_days":
                    round(
                        days,
                        2,
                    ),

                "average_views_per_day":
                    round(
                        average_views_per_day,
                        2,
                    ),

                # --------------------------------------------
                # Engagement context
                # --------------------------------------------

                "likes":
                    likes,

                "like_rate":
                    (
                        round(
                            likes / views,
                            6,
                        )
                        if (
                            likes is not None
                            and views
                        )
                        else None
                    ),

                # --------------------------------------------
                # Channel context
                # --------------------------------------------

                "channel_subscribers":
                    subscriber_count,

                # --------------------------------------------
                # Breakout signal
                # --------------------------------------------

                "channel_baseline_median":
                    None,

                "baseline_sample_size":
                    0,

                "baseline_confidence":
                    "no_baseline",

                "baseline_warning":
                    "",

                "outlier_ratio":
                    None,
            }
        )

    print(
        "Videos with >=500K views: "
        f"{len(rows):,}"
    )

    # ========================================================
    # BASELINE / BREAKOUT ANALYSIS
    # ========================================================

    print()
    print(
        "Calculating channel-relative "
        "breakout signals..."
    )

    history_cache: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for row in rows:

        channel_id = (
            row["channel_id"]
        )

        channel = channels.get(
            channel_id
        )

        if not channel:
            continue

        if (
            channel_id
            not in history_cache
        ):

            upload_ids = (
                get_recent_upload_ids(
                    channel,
                    api_key,
                    maximum=25,
                )
            )

            history_cache[
                channel_id
            ] = list(
                get_video_details(
                    upload_ids,
                    api_key,
                ).values()
            )

        baseline, sample_size = (
            calculate_channel_baseline(
                row,
                history_cache[
                    channel_id
                ],
            )
        )

        row[
            "channel_baseline_median"
        ] = baseline

        row[
            "baseline_sample_size"
        ] = sample_size

        row[
            "baseline_confidence"
        ] = baseline_confidence(
            sample_size
        )

        row[
            "baseline_warning"
        ] = baseline_warning(
            baseline,
            sample_size,
        )

        if (
            baseline is not None
            and baseline > 0
        ):

            row[
                "outlier_ratio"
            ] = round(
                row["views"]
                / baseline,
                2,
            )

    # ========================================================
    # EXPERIMENT 01.2 — RELEVANCE / EVIDENCE QUALITY
    # ========================================================

    niche_lookup = {
        niche["name"]: niche
        for niche in config["niches"]
    }

    for row in rows:
        row.update(
            annotate_evidence_quality(
                row,
                niche_lookup,
            )
        )

    # ========================================================
    # SORT
    #
    # Sorting is for inspection only.
    # It is NOT a final opportunity score.
    # ========================================================

    rows.sort(
        key=lambda row: (
            row[
                "average_views_per_day"
            ],
            row["views"],
        ),
        reverse=True,
    )

    # ========================================================
    # RAW JSON
    # ========================================================

    raw_file = (
        OUTPUT_DIR
        / "raw_results.json"
    )

    raw_file.write_text(
        json.dumps(
            rows,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # ========================================================
    # CSV
    # ========================================================

    csv_file = (
        OUTPUT_DIR
        / "candidates.csv"
    )

    fields = [
        "video_id",
        "youtube_url",
        "title",
        "channel_id",
        "channel_title",
        "niches",
        "matched_queries",
        "best_search_rank",
        "query_matches",

        "duration_seconds",
        "format_candidate",

        "views",
        "meets_original_reference",

        "published_at",
        "age_days",
        "average_views_per_day",

        "likes",
        "like_rate",

        "channel_subscribers",

        "channel_baseline_median",
        "baseline_sample_size",
        "baseline_confidence",
        "baseline_warning",
        "outlier_ratio",
        "outlier_reliability",
        "outlier_reliability_reason",

        "relevance",
        "relevance_reason",
        "relevance_matches",
        "themes",
    ]

    with csv_file.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file_handle:

        writer = csv.DictWriter(
            file_handle,
            fieldnames=fields,
        )

        writer.writeheader()

        for row in rows:

            flat_row = dict(
                row
            )

            flat_row[
                "niches"
            ] = "|".join(
                row["niches"]
            )

            flat_row[
                "matched_queries"
            ] = "|".join(
                row["matched_queries"]
            )

            flat_row[
                "query_matches"
            ] = json.dumps(
                row["query_matches"],
                ensure_ascii=False,
            )

            flat_row[
                "relevance_matches"
            ] = "|".join(
                row["relevance_matches"]
            )

            flat_row[
                "themes"
            ] = "|".join(
                row["themes"]
            )

            writer.writerow(
                {
                    key:
                        flat_row.get(
                            key
                        )
                    for key
                    in fields
                }
            )

    # ========================================================
    # SUMMARY STATISTICS
    # ========================================================

    reference_count = sum(
        bool(
            row[
                "meets_original_reference"
            ]
        )
        for row in rows
    )

    with_baseline = [
        row
        for row in rows
        if row[
            "channel_baseline_median"
        ] is not None
    ]

    strong_baselines = sum(
        row[
            "baseline_confidence"
        ] == "strong_sample"
        for row in rows
    )

    warned_baselines = sum(
        bool(
            row[
                "baseline_warning"
            ]
        )
        for row in rows
    )

    short_candidates = sum(
        row[
            "format_candidate"
        ] == "short_candidate"
        for row in rows
    )

    long_candidates = sum(
        row[
            "format_candidate"
        ] == "long_form_candidate"
        for row in rows
    )

    relevance_counts = {
        label: sum(
            row.get("relevance") == label
            for row in rows
        )
        for label in (
            RELEVANCE_ON_INTENT,
            RELEVANCE_ADJACENT,
            RELEVANCE_OFF_INTENT,
        )
    }

    reliability_counts = {
        label: sum(
            row.get("outlier_reliability") == label
            for row in rows
        )
        for label in (
            RELIABILITY_TRUSTED,
            RELIABILITY_CAUTION,
            RELIABILITY_UNAVAILABLE,
        )
    }

    theme_counts: dict[str, int] = {}
    for row in rows:
        for theme in row.get("themes", []):
            theme_counts[theme] = (
                theme_counts.get(theme, 0)
                + 1
            )

    # ========================================================
    # DISTRIBUTION DATA
    #
    # Useful later for choosing evidence-based thresholds.
    # ========================================================

    view_values = sorted(
        row["views"]
        for row in rows
    )

    avg_rate_values = sorted(
        row[
            "average_views_per_day"
        ]
        for row in rows
    )

    outlier_values = sorted(
        row[
            "outlier_ratio"
        ]
        for row in rows
        if row[
            "outlier_ratio"
        ] is not None
    )

    def median_or_none(
        values: list[float],
    ) -> float | None:

        if not values:
            return None

        return round(
            float(
                statistics.median(
                    values
                )
            ),
            2,
        )

    summary = {
        "experiment":
            "Stage 2 Experiment 01.2",

        "search_calls":
            search_calls,

        "unique_search_hits":
            len(discovered),

        "videos_at_least_500k":
            len(rows),

        "format_candidates": {
            "long_form_candidate":
                long_candidates,

            "short_candidate":
                short_candidates,
        },

        "original_reference_threshold": {
            "count_meeting_reference":
                reference_count,

            "long_form_reference_views":
                LONG_FORM_REFERENCE_VIEWS,

            "short_candidate_reference_views":
                SHORT_CANDIDATE_REFERENCE_VIEWS,
        },

        "baseline_analysis": {
            "videos_with_baseline":
                len(with_baseline),

            "strong_baseline_samples":
                strong_baselines,

            "videos_with_baseline_warning":
                warned_baselines,
        },

        "relevance_analysis":
            relevance_counts,

        "outlier_reliability_analysis":
            reliability_counts,

        "theme_counts":
            dict(
                sorted(
                    theme_counts.items(),
                    key=lambda item: (
                        -item[1],
                        item[0],
                    ),
                )
            ),

        "distribution": {
            "median_views":
                median_or_none(
                    view_values
                ),

            "median_average_views_per_day":
                median_or_none(
                    avg_rate_values
                ),

            "median_outlier_ratio":
                median_or_none(
                    outlier_values
                ),
        },

        "important_notes": [
            (
                "No final opportunity score "
                "is calculated in Experiment 01.2."
            ),
            (
                "Views measure absolute demand."
            ),
            (
                "Outlier ratio measures performance "
                "relative to recent comparable uploads "
                "from the same channel."
            ),
            (
                "average_views_per_day is lifetime "
                "average view accumulation, not true "
                "current velocity."
            ),
            (
                "True current velocity requires "
                "another observation of the same "
                "video at a later time."
            ),
            (
                "format_candidate is a heuristic. "
                "Duration <=180 seconds does not prove "
                "YouTube classified the video as a Short."
            ),
            (
                "Transformability will be evaluated "
                "separately rather than inferred from "
                "popularity."
            ),
            (
                "Experiment 01.2 relevance labels are "
                "deterministic research annotations, "
                "not a final opportunity score."
            ),
            (
                "OFF_INTENT rows remain in raw outputs "
                "so search contamination stays auditable."
            ),
            (
                "Outlier reliability never changes the "
                "raw outlier ratio; it only flags caution."
            ),
        ],
    }

    summary_file = (
        OUTPUT_DIR
        / "summary.json"
    )

    summary_file.write_text(
        json.dumps(
            summary,
            indent=2,
        ),
        encoding="utf-8",
    )

    # ========================================================
    # CONSOLE OUTPUT
    # ========================================================

    print()
    print(
        "=" * 60
    )

    print(
        "EXPERIMENT 01.2 COMPLETE"
    )

    print(
        "=" * 60
    )

    print(
        f"Search calls:             "
        f"{search_calls}"
    )

    print(
        f"Unique search hits:       "
        f"{len(discovered):,}"
    )

    print(
        f"Videos >=500K:            "
        f"{len(rows):,}"
    )

    print(
        f"Long-form candidates:     "
        f"{long_candidates:,}"
    )

    print(
        f"Short candidates:         "
        f"{short_candidates:,}"
    )

    print(
        f"Meet old reference:       "
        f"{reference_count:,}"
    )

    print(
        f"Videos with baseline:     "
        f"{len(with_baseline):,}"
    )

    print(
        f"Strong baseline samples:  "
        f"{strong_baselines:,}"
    )

    print(
        f"Baseline warnings:        "
        f"{warned_baselines:,}"
    )

    print(
        f"ON_INTENT:                "
        f"{relevance_counts[RELEVANCE_ON_INTENT]:,}"
    )

    print(
        f"ADJACENT:                 "
        f"{relevance_counts[RELEVANCE_ADJACENT]:,}"
    )

    print(
        f"OFF_INTENT:               "
        f"{relevance_counts[RELEVANCE_OFF_INTENT]:,}"
    )

    print(
        f"Trusted outliers:         "
        f"{reliability_counts[RELIABILITY_TRUSTED]:,}"
    )

    print(
        f"Caution outliers:         "
        f"{reliability_counts[RELIABILITY_CAUTION]:,}"
    )

    print()
    print(
        "No final score has been assigned."
    )

    print(
        "Demand, breakout and momentum "
        "are being measured independently."
    )

    print()
    print(
        "Results:"
    )

    print(
        f"  {raw_file}"
    )

    print(
        f"  {csv_file}"
    )

    print(
        f"  {summary_file}"
    )


if __name__ == "__main__":
    main()