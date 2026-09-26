"""Stage 2 Experiment 01.4 — Depth-First Topic Expansion.

Consumes final Experiment 01.3 age-matched evidence and expands only topic /
format cells that have enough replicated evidence to justify deeper discovery.

PLAN mode is offline and spends zero YouTube search quota.
EXECUTE mode runs the frozen query plan with checkpoint/resume protection.
No composite opportunity score is calculated.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from experiment_01_3 import classify_topic_relevance
from youtube_discovery import (
    age_days,
    api_get,
    classify_format_candidate,
    get_video_details,
    load_env_file,
    parse_duration_seconds,
)

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
ENV_FILE = PROJECT_ROOT / ".env"
CONFIG_FILE = HERE / "experiment_01_4_config.json"
EXPERIMENT_01_3_DIR = HERE / "output" / "experiment_01_3"
TOPIC_VELOCITY_01_3 = EXPERIMENT_01_3_DIR / "topic_velocity.json"
SUMMARY_01_3 = EXPERIMENT_01_3_DIR / "summary.json"

OUTPUT_DIR = HERE / "output" / "experiment_01_4"
PLAN_FILE = OUTPUT_DIR / "expansion_plan.json"
CHECKPOINT_FILE = OUTPUT_DIR / "search_checkpoint.json"
RAW_FILE = OUTPUT_DIR / "raw_results.json"
CANDIDATES_FILE = OUTPUT_DIR / "candidates.csv"
EVIDENCE_FILE = OUTPUT_DIR / "expansion_evidence.json"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"

EXPERIMENT_ID = "01.4"


def median_or_none(values: list[float | int]) -> float | None:
    return round(float(statistics.median(values)), 2) if values else None


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Required file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_FILE)
    required = {
        "minimum_unique_channels",
        "minimum_velocity_samples",
        "maximum_plan_searches",
        "search_order",
        "lookback_days",
        "motorsport_context_terms",
        "exclude_title_terms",
        "topic_definitions",
        "query_families",
        "duration_filters",
    }
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit("Experiment 01.4 config is missing: " + ", ".join(missing))
    return config


def confidence_rank(value: str) -> int:
    return {
        "INSUFFICIENT": 0,
        "LOW": 1,
        "MODERATE": 2,
        "STRONG": 3,
    }.get(str(value).upper(), 0)


def extract_topic_cells(topic_velocity: dict[str, Any]) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for topic, payload in topic_velocity.get("topics", {}).items():
        for fmt, evidence in payload.get("by_format", {}).items():
            row = dict(evidence)
            row["topic"] = str(topic)
            row["format_candidate"] = str(fmt)
            cells.append(row)
    return cells


def classify_depth_readiness(
    cell: dict[str, Any],
    *,
    minimum_unique_channels: int,
    minimum_velocity_samples: int,
) -> dict[str, Any]:
    unique_channels = int(cell.get("unique_channels") or 0)
    velocity_samples = int(cell.get("velocity_sample_count") or 0)
    velocity_index = cell.get("age_matched_velocity_index")

    reasons: list[str] = []
    if unique_channels < minimum_unique_channels:
        reasons.append("insufficient_unique_channels")
    if velocity_samples < minimum_velocity_samples:
        reasons.append("insufficient_velocity_samples")
    if velocity_index is None:
        reasons.append("missing_age_matched_velocity_index")

    return {
        **cell,
        "depth_ready": not reasons,
        "readiness_reasons": reasons,
    }


def topic_priority_key(cell: dict[str, Any]) -> tuple[float, int, int, str, str]:
    """Scheduling order only; this is not a composite opportunity score."""

    index = cell.get("age_matched_velocity_index")
    index_value = float(index) if index is not None else float("-inf")
    return (
        -index_value,
        -int(cell.get("unique_channels") or 0),
        -int(cell.get("velocity_sample_count") or 0),
        str(cell.get("topic", "")),
        str(cell.get("format_candidate", "")),
    )


def make_task_id(
    topic: str,
    fmt: str,
    family: str,
    duration_filter: str,
    query: str,
) -> str:
    safe = "|".join([topic, fmt, family, duration_filter, query]).casefold()
    return safe


def build_tasks_for_cell(
    cell: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    topic = str(cell["topic"])
    fmt = str(cell["format_candidate"])
    topic_def = config["topic_definitions"].get(topic)
    if not topic_def:
        return []

    root = str(topic_def["query_root"])
    duration_filters = list(config["duration_filters"].get(fmt, []))
    tasks: list[dict[str, Any]] = []

    for family in config["query_families"]:
        family_name = str(family["family"])
        template = str(family["template"])
        query = template.format(root=root).strip()

        for duration_filter in duration_filters:
            task = {
                "topic": topic,
                "format_candidate": fmt,
                "family": family_name,
                "query": query,
                "video_duration_filter": duration_filter,
                "search_order": str(config["search_order"]),
                "source_age_matched_velocity_index": cell.get("age_matched_velocity_index"),
                "source_unique_channels": int(cell.get("unique_channels") or 0),
                "source_velocity_samples": int(cell.get("velocity_sample_count") or 0),
            }
            task["task_id"] = make_task_id(
                topic,
                fmt,
                family_name,
                duration_filter,
                query,
            )
            tasks.append(task)

    return tasks


def allocate_search_budget(
    ready_cells: list[dict[str, Any]],
    config: dict[str, Any],
    maximum_searches: int,
) -> list[dict[str, Any]]:
    """Round-robin cells so one long-form topic cannot consume the whole budget."""

    ordered_cells = sorted(ready_cells, key=topic_priority_key)
    queues = [deque(build_tasks_for_cell(cell, config)) for cell in ordered_cells]
    selected: list[dict[str, Any]] = []

    while queues and len(selected) < maximum_searches:
        next_round = []
        for queue in queues:
            if queue and len(selected) < maximum_searches:
                selected.append(queue.popleft())
            if queue:
                next_round.append(queue)
        queues = next_round

    for sequence, task in enumerate(selected, start=1):
        task["sequence"] = sequence

    return selected


def build_plan(
    topic_velocity: dict[str, Any],
    summary_01_3: dict[str, Any],
    config: dict[str, Any],
    *,
    maximum_searches: int | None = None,
) -> dict[str, Any]:
    minimum_channels = int(config["minimum_unique_channels"])
    minimum_velocity = int(config["minimum_velocity_samples"])
    budget = int(maximum_searches or config["maximum_plan_searches"])

    cells = [
        classify_depth_readiness(
            cell,
            minimum_unique_channels=minimum_channels,
            minimum_velocity_samples=minimum_velocity,
        )
        for cell in extract_topic_cells(topic_velocity)
    ]
    ready = [cell for cell in cells if cell["depth_ready"]]
    tasks = allocate_search_budget(ready, config, budget) if ready else []

    created_at = datetime.now(timezone.utc)
    lookback_days = int(config["lookback_days"])
    published_after = (
        created_at - timedelta(days=lookback_days)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    status = "READY" if tasks else "WAITING_FOR_01_3_EVIDENCE"
    return {
        "experiment_id": EXPERIMENT_ID,
        "purpose": "depth_first_topic_expansion",
        "status": status,
        "created_at": created_at.isoformat(),
        "source_experiment": "01.3",
        "source_cohort_id": summary_01_3.get("cohort_id"),
        "source_mode": summary_01_3.get("mode"),
        "minimum_unique_channels": minimum_channels,
        "minimum_velocity_samples": minimum_velocity,
        "search_budget": budget,
        "search_order": config["search_order"],
        "lookback_days": lookback_days,
        "published_after": published_after,
        "cells": cells,
        "ready_cells": [
            {
                "topic": cell["topic"],
                "format_candidate": cell["format_candidate"],
                "unique_channels": cell.get("unique_channels"),
                "velocity_sample_count": cell.get("velocity_sample_count"),
                "confidence": cell.get("confidence"),
                "age_matched_velocity_index": cell.get("age_matched_velocity_index"),
                "median_current_views_per_day": cell.get("median_current_views_per_day"),
            }
            for cell in sorted(ready, key=topic_priority_key)
        ],
        "search_tasks": tasks,
        "notes": [
            "Planning spends zero YouTube search calls.",
            "Depth-ready requires replicated current-velocity evidence and independent channels.",
            "Task scheduling uses the primary age-matched velocity metric only; no composite opportunity score is created.",
            "Search tasks are frozen before execution for reproducibility and quota control.",
        ],
    }


def load_api_key() -> str:
    load_env_file(ENV_FILE)
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise SystemExit(f"YOUTUBE_API_KEY not found in {ENV_FILE}")
    return api_key


def save_checkpoint(
    plan: dict[str, Any],
    completed_task_ids: set[str],
    search_results: list[dict[str, Any]],
    status: str,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "plan_created_at": plan.get("created_at"),
        "status": status,
        "completed_task_ids": sorted(completed_task_ids),
        "search_results": search_results,
    }
    CHECKPOINT_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_checkpoint(plan: dict[str, Any]) -> tuple[set[str], list[dict[str, Any]]]:
    if not CHECKPOINT_FILE.exists():
        return set(), []
    checkpoint = load_json(CHECKPOINT_FILE)
    if checkpoint.get("plan_created_at") != plan.get("created_at"):
        raise SystemExit(
            "01.4 checkpoint belongs to a different expansion plan. "
            "Delete output/experiment_01_4/search_checkpoint.json or rebuild the plan."
        )
    return (
        set(checkpoint.get("completed_task_ids", [])),
        list(checkpoint.get("search_results", [])),
    )


def execute_plan(
    plan: dict[str, Any],
    api_key: str,
    *,
    max_searches: int,
    region_code: str | None,
    language: str | None,
) -> tuple[list[dict[str, Any]], str, int]:
    completed, search_results = load_checkpoint(plan)
    calls = 0

    for task in plan.get("search_tasks", []):
        task_id = str(task["task_id"])
        if task_id in completed:
            continue
        if calls >= max_searches:
            save_checkpoint(plan, completed, search_results, "SEARCH_BUDGET_REACHED")
            return search_results, "SEARCH_BUDGET_REACHED", calls

        params: dict[str, Any] = {
            "part": "snippet",
            "q": task["query"],
            "type": "video",
            "order": task["search_order"],
            "maxResults": 50,
            "videoDuration": task["video_duration_filter"],
            "publishedAfter": plan["published_after"],
        }
        if region_code:
            params["regionCode"] = region_code
        if language:
            params["relevanceLanguage"] = language

        print(
            f"  [{task['sequence']:02d}] {task['topic']} / {task['format_candidate']} / "
            f"{task['family']} / {task['video_duration_filter']}: {task['query']}"
        )

        try:
            data = api_get("search", api_key, **params)
        except SystemExit:
            save_checkpoint(plan, completed, search_results, "QUOTA_EXHAUSTED")
            return search_results, "QUOTA_EXHAUSTED", calls

        calls += 1
        video_ids = [
            item.get("id", {}).get("videoId")
            for item in data.get("items", [])
            if item.get("id", {}).get("videoId")
        ]
        search_results.append(
            {
                **task,
                "results_returned": len(video_ids),
                "video_ids": video_ids,
            }
        )
        completed.add(task_id)
        save_checkpoint(plan, completed, search_results, "IN_PROGRESS")

    save_checkpoint(plan, completed, search_results, "COMPLETE")
    return search_results, "COMPLETE", calls


def build_candidates(
    plan: dict[str, Any],
    search_results: list[dict[str, Any]],
    config: dict[str, Any],
    api_key: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    video_provenance: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in search_results:
        for rank, video_id in enumerate(result.get("video_ids", []), start=1):
            video_provenance[str(video_id)].append(
                {
                    "topic": result["topic"],
                    "format_candidate": result["format_candidate"],
                    "family": result["family"],
                    "query": result["query"],
                    "video_duration_filter": result["video_duration_filter"],
                    "rank": rank,
                }
            )

    details = get_video_details(sorted(video_provenance), api_key)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for video_id, provenance in video_provenance.items():
        item = details.get(video_id)
        if not item:
            continue

        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        content = item.get("contentDetails", {})
        title = str(snippet.get("title", ""))
        duration_seconds = parse_duration_seconds(content.get("duration", ""))
        fmt = classify_format_candidate(duration_seconds)
        views = int(statistics.get("viewCount", 0) or 0)
        published_at = str(snippet.get("publishedAt", ""))

        valid_topics = []
        topic_validation = {}
        valid_provenance = []
        for match in provenance:
            topic = str(match["topic"])
            if match["format_candidate"] != fmt:
                continue
            topic_def = config["topic_definitions"].get(topic, {})
            result = classify_topic_relevance(
                title,
                list(topic_def.get("match_terms", [])),
                list(config["motorsport_context_terms"]),
                list(config["exclude_title_terms"]),
            )
            topic_validation[topic] = result
            if result["topic_relevance"] == "ON_TOPIC":
                valid_topics.append(topic)
                valid_provenance.append(match)

        row = {
            "experiment_id": EXPERIMENT_ID,
            "video_id": video_id,
            "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
            "title": title,
            "channel_id": snippet.get("channelId"),
            "channel_title": snippet.get("channelTitle"),
            "published_at": published_at,
            "age_days": round(age_days(published_at), 2) if published_at else None,
            "duration_seconds": duration_seconds,
            "format_candidate": fmt,
            "views": views,
            "likes": int(statistics["likeCount"]) if statistics.get("likeCount") is not None else None,
            "validated_topics": sorted(set(valid_topics)),
            "matched_families": sorted({m["family"] for m in valid_provenance}),
            "query_provenance": valid_provenance,
            "topic_validation": topic_validation,
        }

        reasons = []
        if not valid_topics:
            reasons.append("no_validated_topic_after_title_filter")
        if not valid_provenance:
            reasons.append("format_or_query_branch_mismatch")

        if reasons:
            rejected.append({**row, "rejection_reasons": sorted(set(reasons))})
        else:
            accepted.append(row)

    accepted.sort(key=lambda row: (-int(row["views"]), str(row["title"])))
    return accepted, rejected


def aggregate_expansion_evidence(
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for row in candidates:
        for provenance in row.get("query_provenance", []):
            key = (
                str(provenance["topic"]),
                str(row["format_candidate"]),
                str(provenance["family"]),
            )
            groups[key].append(row)

    output: dict[str, Any] = {}
    for (topic, fmt, family), rows in sorted(groups.items()):
        deduped = {row["video_id"]: row for row in rows}
        values = list(deduped.values())
        views = [int(row["views"]) for row in values]
        ages = [
            float(row["age_days"])
            for row in values
            if row.get("age_days") is not None
        ]
        unique_channels = len(
            {
                row.get("channel_id")
                for row in values
                if row.get("channel_id")
            }
        )
        output.setdefault(topic, {}).setdefault(fmt, {})[family] = {
            "video_count": len(values),
            "unique_channels": unique_channels,
            "median_views": median_or_none(views),
            "maximum_views": max(views) if views else None,
            "median_age_days": median_or_none(ages),
        }

    return {
        "experiment_id": EXPERIMENT_ID,
        "purpose": "depth_expansion_evidence",
        "topics": output,
        "notes": [
            "Expansion evidence describes observed search-result patterns only.",
            "No age-matched velocity is calculated in Experiment 01.4.",
            "No final opportunity score is calculated.",
        ],
    }


CSV_FIELDS = [
    "experiment_id",
    "video_id",
    "youtube_url",
    "title",
    "channel_id",
    "channel_title",
    "published_at",
    "age_days",
    "duration_seconds",
    "format_candidate",
    "views",
    "likes",
    "validated_topics",
    "matched_families",
    "query_provenance",
]


def write_candidate_outputs(
    candidates: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    evidence: dict[str, Any],
    plan: dict[str, Any],
    execution_status: str,
    calls_this_run: int,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_FILE.write_text(
        json.dumps(
            {"accepted": candidates, "rejected": rejected},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    EVIDENCE_FILE.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    with CANDIDATES_FILE.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in candidates:
            flat = dict(row)
            flat["validated_topics"] = "|".join(row.get("validated_topics", []))
            flat["matched_families"] = "|".join(row.get("matched_families", []))
            flat["query_provenance"] = json.dumps(
                row.get("query_provenance", []),
                ensure_ascii=False,
            )
            writer.writerow({field: flat.get(field) for field in CSV_FIELDS})

    summary = {
        "experiment": "Stage 2 Experiment 01.4",
        "purpose": "depth_first_topic_expansion",
        "plan_status": plan.get("status"),
        "execution_status": execution_status,
        "source_cohort_id": plan.get("source_cohort_id"),
        "ready_cell_count": len(plan.get("ready_cells", [])),
        "planned_search_calls": len(plan.get("search_tasks", [])),
        "search_calls_this_run": calls_this_run,
        "accepted_candidates": len(candidates),
        "rejected_candidates": len(rejected),
        "notes": [
            "01.4 expands only evidence-ready topic/format cells from 01.3.",
            "Query families are deterministic and auditable.",
            "Search execution is checkpointed and quota-bounded.",
            "No composite opportunity score is calculated.",
        ],
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def run_plan(args: argparse.Namespace) -> None:
    config = load_config()
    topic_velocity = load_json(TOPIC_VELOCITY_01_3)
    summary_01_3 = load_json(SUMMARY_01_3)

    plan = build_plan(
        topic_velocity,
        summary_01_3,
        config,
        maximum_searches=args.plan_searches,
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
    PLAN_FILE.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nSTAGE 2 — EXPERIMENT 01.4")
    print("=" * 60)
    print("Mode: PLAN (zero YouTube search calls)")
    print(f"Status:                {plan['status']}")
    print(f"01.3 source cohort:    {plan.get('source_cohort_id')}")
    print(f"Evidence-ready cells:  {len(plan['ready_cells'])}")
    print(f"Planned search calls:  {len(plan['search_tasks'])}/{plan['search_budget']}")
    print(f"Plan:                  {PLAN_FILE}")

    if plan["status"] != "READY":
        print("\n01.4 is built and waiting for final 01.3 velocity evidence.")


def run_execute(args: argparse.Namespace) -> None:
    config = load_config()
    plan = load_json(PLAN_FILE)
    if plan.get("status") != "READY":
        raise SystemExit(
            "The current 01.4 plan is not READY. Complete 01.3 refresh evidence "
            "and rebuild the plan first."
        )

    api_key = load_api_key()
    search_results, status, calls = execute_plan(
        plan,
        api_key,
        max_searches=args.max_searches,
        region_code=args.region_code,
        language=args.language,
    )

    if status != "COMPLETE":
        print("\nExperiment 01.4 execution paused safely.")
        print(f"Reason:     {status}")
        print(f"Checkpoint: {CHECKPOINT_FILE}")
        print("Rerun the same execute command to resume.")
        return

    candidates, rejected = build_candidates(plan, search_results, config, api_key)
    evidence = aggregate_expansion_evidence(candidates)
    write_candidate_outputs(
        candidates,
        rejected,
        evidence,
        plan,
        status,
        calls,
    )

    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()

    print("\nEXPERIMENT 01.4 COMPLETE")
    print("=" * 60)
    print(f"Accepted candidates:   {len(candidates):,}")
    print(f"Rejected candidates:   {len(rejected):,}")
    print(f"Search calls this run: {calls:,}")
    print(f"Candidates:            {CANDIDATES_FILE}")
    print(f"Evidence:              {EVIDENCE_FILE}")
    print(f"Summary:               {SUMMARY_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage 2 Experiment 01.4 depth-first topic expansion"
    )
    parser.add_argument("--mode", choices=("plan", "execute"), required=True)
    parser.add_argument("--plan-searches", type=int, default=None)
    parser.add_argument("--max-searches", type=int, default=30)
    parser.add_argument("--region-code", default=None)
    parser.add_argument("--language", default=None)
    args = parser.parse_args()

    if args.mode == "plan":
        run_plan(args)
    else:
        run_execute(args)


if __name__ == "__main__":
    main()
