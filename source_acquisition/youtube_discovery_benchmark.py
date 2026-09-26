"""Benchmark Agent Reach / yt-dlp YouTube discovery against 01.3 search audit.

This is intentionally an evaluation layer. It does not modify Experiment 01.3
cohorts or replace YouTube Data API measurement.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_reach_adapter import (
    AcquisitionError,
    doctor,
    render_console_json,
    search_youtube,
    youtube_health,
)

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
EXP13_CONFIG = (
    PROJECT_ROOT
    / "experiment_01_discovery"
    / "experiment_01_3_config.json"
)
DEFAULT_API_REFERENCE = (
    PROJECT_ROOT
    / "experiment_01_discovery"
    / "output"
    / "experiment_01_3_discovery_checkpoint.json"
)

OUTPUT_DIR = (
    HERE
    / "output"
    / "youtube_discovery_benchmark"
)
RESULTS_FILE = OUTPUT_DIR / "agent_reach_results.json"
COMPARISON_FILE = OUTPUT_DIR / "comparison.json"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def query_plan(config: dict[str, Any]) -> list[dict[str, str]]:
    items = []
    for topic in config.get("topics", []):
        topic_name = str(topic.get("topic", "")).strip()
        for query in topic.get("queries", []):
            text = str(query).strip()
            if topic_name and text:
                items.append(
                    {
                        "topic": topic_name,
                        "query": text,
                    }
                )
    return items


def collect(
    *,
    limit: int,
    strategy: str,
) -> dict[str, Any]:
    config = load_json(EXP13_CONFIG)
    plan = query_plan(config)
    strategies = (
        ["relevance", "date"]
        if strategy == "both"
        else [strategy]
    )

    health_payload = doctor()
    health = youtube_health(health_payload)
    if not health["ready"]:
        return {
            "status": "AGENT_REACH_YOUTUBE_NOT_READY",
            "doctor_status": health_payload.get(
                "status"
            ),
            "youtube_health": health,
            "query_count": len(plan),
            "searches_completed": 0,
        }

    searches = []
    failures = []

    for item in plan:
        for current_strategy in strategies:
            try:
                result = search_youtube(
                    item["query"],
                    limit=limit,
                    strategy=current_strategy,
                    require_agent_reach_health=False,
                )
            except (
                AcquisitionError,
                ValueError,
            ) as exc:
                failures.append(
                    {
                        **item,
                        "strategy": current_strategy,
                        "error": str(exc),
                    }
                )
                continue

            searches.append(
                {
                    **item,
                    "strategy": current_strategy,
                    "status": result["status"],
                    "result_count": result[
                        "result_count"
                    ],
                    "results": result["results"],
                }
            )

    return {
        "status": (
            "COMPLETE"
            if not failures
            else "PARTIAL"
        ),
        "collected_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "source": "agent_reach",
        "active_backend": health.get(
            "active_backend"
        ),
        "limit_per_search": limit,
        "strategy": strategy,
        "query_count": len(plan),
        "searches_completed": len(searches),
        "failures": failures,
        "searches": searches,
    }


def _reference_map(
    checkpoint: dict[str, Any],
) -> dict[tuple[str, str], set[str]]:
    result: dict[
        tuple[str, str],
        set[str],
    ] = defaultdict(set)

    for audit in checkpoint.get("audit", []):
        topic = str(
            audit.get("target_topic", "")
        ).strip()
        query = str(
            audit.get("query", "")
        ).strip()
        if not topic or not query:
            continue
        for video_id in audit.get(
            "video_ids", []
        ):
            value = str(video_id).strip()
            if value:
                result[
                    (topic, query)
                ].add(value)
    return result


def _agent_map(
    results: dict[str, Any],
) -> dict[tuple[str, str], set[str]]:
    output: dict[
        tuple[str, str],
        set[str],
    ] = defaultdict(set)

    for search in results.get(
        "searches", []
    ):
        key = (
            str(search.get("topic", "")),
            str(search.get("query", "")),
        )
        for item in search.get(
            "results", []
        ):
            video_id = str(
                item.get("video_id", "")
            ).strip()
            if video_id:
                output[key].add(video_id)
    return output


def ratio(
    numerator: int,
    denominator: int,
) -> float | None:
    if denominator <= 0:
        return None
    return round(
        numerator / denominator,
        4,
    )


def compare(
    results: dict[str, Any],
    checkpoint: dict[str, Any],
) -> dict[str, Any]:
    api_map = _reference_map(checkpoint)
    agent_map = _agent_map(results)

    keys = sorted(
        set(api_map) | set(agent_map)
    )
    rows = []

    api_union: set[str] = set()
    agent_union: set[str] = set()

    for topic, query in keys:
        api_ids = api_map.get(
            (topic, query), set()
        )
        agent_ids = agent_map.get(
            (topic, query), set()
        )
        overlap = (
            api_ids & agent_ids
        )

        api_union.update(api_ids)
        agent_union.update(agent_ids)

        rows.append(
            {
                "topic": topic,
                "query": query,
                "youtube_api_unique_ids": len(
                    api_ids
                ),
                "agent_reach_unique_ids": len(
                    agent_ids
                ),
                "overlap_count": len(
                    overlap
                ),
                "api_reference_recall": ratio(
                    len(overlap),
                    len(api_ids),
                ),
                "agent_overlap_rate": ratio(
                    len(overlap),
                    len(agent_ids),
                ),
                "overlap_video_ids": sorted(
                    overlap
                ),
                "only_agent_reach_video_ids": sorted(
                    agent_ids - api_ids
                ),
                "only_youtube_api_video_ids": sorted(
                    api_ids - agent_ids
                ),
            }
        )

    overall_overlap = (
        api_union & agent_union
    )

    return {
        "status": "COMPARISON_READY",
        "reference_experiment": checkpoint.get(
            "experiment_id"
        ),
        "reference_status": checkpoint.get(
            "status"
        ),
        "reference_observed_at": checkpoint.get(
            "observed_at"
        ),
        "queries_compared": len(rows),
        "overall": {
            "youtube_api_unique_ids": len(
                api_union
            ),
            "agent_reach_unique_ids": len(
                agent_union
            ),
            "overlap_count": len(
                overall_overlap
            ),
            "api_reference_recall": ratio(
                len(overall_overlap),
                len(api_union),
            ),
            "agent_overlap_rate": ratio(
                len(overall_overlap),
                len(agent_union),
            ),
        },
        "by_query": rows,
        "notes": [
            "This compares discovery result IDs only.",
            "The YouTube API reference used publication-window, duration and ordering filters that yt-dlp search does not reproduce identically.",
            "Low overlap is therefore evidence that direct substitution is unsafe, not proof that either source is wrong.",
            "No Experiment 01.3 cohort or measurement file is modified by this benchmark.",
        ],
    }


def write_summary(
    collection: dict[str, Any],
    comparison: dict[str, Any] | None,
) -> dict[str, Any]:
    if collection.get("status") == (
        "AGENT_REACH_YOUTUBE_NOT_READY"
    ):
        status = collection["status"]
    elif comparison is not None:
        status = "BENCHMARK_COMPARISON_READY"
    else:
        status = "BENCHMARK_COLLECTED_NO_API_REFERENCE"

    summary = {
        "status": status,
        "agent_reach_collection_status": collection.get(
            "status"
        ),
        "searches_completed": collection.get(
            "searches_completed", 0
        ),
        "comparison_available": (
            comparison is not None
        ),
        "results_file": str(
            RESULTS_FILE
        ),
        "comparison_file": (
            str(COMPARISON_FILE)
            if comparison is not None
            else None
        ),
        "youtube_api_calls": 0,
        "experiment_01_3_modified": False,
    }
    SUMMARY_FILE.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return summary


def run_collect(
    *,
    limit: int,
    strategy: str,
    api_reference: Path,
) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    collection = collect(
        limit=limit,
        strategy=strategy,
    )
    RESULTS_FILE.write_text(
        json.dumps(
            collection,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    comparison = None
    if (
        collection.get("status")
        in {"COMPLETE", "PARTIAL"}
        and api_reference.exists()
    ):
        checkpoint = load_json(
            api_reference
        )
        comparison = compare(
            collection,
            checkpoint,
        )
        COMPARISON_FILE.write_text(
            json.dumps(
                comparison,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    return write_summary(
        collection,
        comparison,
    )


def run_compare(
    *,
    results_path: Path,
    api_reference: Path,
) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    results = load_json(
        results_path
    )
    checkpoint = load_json(
        api_reference
    )
    comparison = compare(
        results,
        checkpoint,
    )
    COMPARISON_FILE.write_text(
        json.dumps(
            comparison,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return write_summary(
        results,
        comparison,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark Agent Reach / yt-dlp "
            "YouTube discovery against Experiment 01.3"
        )
    )
    parser.add_argument(
        "--mode",
        choices=("collect", "compare"),
        required=True,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--strategy",
        choices=(
            "relevance",
            "date",
            "both",
        ),
        default="relevance",
    )
    parser.add_argument(
        "--api-reference",
        type=Path,
        default=DEFAULT_API_REFERENCE,
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=RESULTS_FILE,
    )
    args = parser.parse_args()

    if args.mode == "collect":
        result = run_collect(
            limit=args.limit,
            strategy=args.strategy,
            api_reference=args.api_reference.resolve(),
        )
    else:
        result = run_compare(
            results_path=args.results.resolve(),
            api_reference=args.api_reference.resolve(),
        )

    print(render_console_json(result))


if __name__ == "__main__":
    main()
