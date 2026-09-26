"""Stage 2 Experiment 01.5 — Opportunity Handoff Gate.

Combines Experiment 01.3 age-matched topic evidence with Experiment 01.4
depth-expansion evidence and produces auditable candidate packets for
Experiment 02.

This stage is offline: it spends zero YouTube API quota and creates no
composite opportunity score.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "experiment_01_5_config.json"

OUTPUT_ROOT = HERE / "output"
EXPERIMENT_01_3_DIR = OUTPUT_ROOT / "experiment_01_3"
EXPERIMENT_01_4_DIR = OUTPUT_ROOT / "experiment_01_4"
OUTPUT_DIR = OUTPUT_ROOT / "experiment_01_5"

TOPIC_VELOCITY_01_3 = EXPERIMENT_01_3_DIR / "topic_velocity.json"
SUMMARY_01_3 = EXPERIMENT_01_3_DIR / "summary.json"
RAW_01_4 = EXPERIMENT_01_4_DIR / "raw_results.json"
EVIDENCE_01_4 = EXPERIMENT_01_4_DIR / "expansion_evidence.json"
SUMMARY_01_4 = EXPERIMENT_01_4_DIR / "summary.json"

PACKETS_FILE = OUTPUT_DIR / "handoff_packets.json"
STUDY_SET_FILE = OUTPUT_DIR / "study_set.json"
CSV_FILE = OUTPUT_DIR / "handoff_candidates.csv"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"

EXPERIMENT_ID = "01.5"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_FILE)
    required = {
        "minimum_topic_unique_channels",
        "minimum_topic_velocity_samples",
        "minimum_family_unique_channels",
        "minimum_family_video_count",
        "candidate_view_reference",
        "max_study_candidates",
        "max_per_topic_format",
        "max_per_channel",
    }
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit("Experiment 01.5 config is missing: " + ", ".join(missing))
    return config


def topic_cell(
    topic_velocity: dict[str, Any],
    topic: str,
    fmt: str,
) -> dict[str, Any] | None:
    return (
        topic_velocity.get("topics", {})
        .get(topic, {})
        .get("by_format", {})
        .get(fmt)
    )


def family_cell(
    expansion_evidence: dict[str, Any],
    topic: str,
    fmt: str,
    family: str,
) -> dict[str, Any] | None:
    return (
        expansion_evidence.get("topics", {})
        .get(topic, {})
        .get(fmt, {})
        .get(family)
    )


def candidate_topic_families(candidate: dict[str, Any], topic: str) -> list[str]:
    families = {
        str(item.get("family"))
        for item in candidate.get("query_provenance", [])
        if item.get("topic") == topic and item.get("family")
    }
    return sorted(families)


def evaluate_topic_evidence(
    cell: dict[str, Any] | None,
    config: dict[str, Any],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not cell:
        return False, ["missing_topic_evidence"]

    if int(cell.get("unique_channels") or 0) < int(config["minimum_topic_unique_channels"]):
        reasons.append("insufficient_topic_unique_channels")
    if int(cell.get("velocity_sample_count") or 0) < int(config["minimum_topic_velocity_samples"]):
        reasons.append("insufficient_topic_velocity_samples")
    if cell.get("age_matched_velocity_index") is None:
        reasons.append("missing_age_matched_velocity_index")

    return not reasons, reasons


def replicated_families(
    expansion_evidence: dict[str, Any],
    topic: str,
    fmt: str,
    families: list[str],
    config: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    replicated: list[str] = []
    evidence: dict[str, Any] = {}

    for family in families:
        cell = family_cell(expansion_evidence, topic, fmt, family)
        if cell is None:
            continue
        evidence[family] = cell
        if (
            int(cell.get("unique_channels") or 0) >= int(config["minimum_family_unique_channels"])
            and int(cell.get("video_count") or 0) >= int(config["minimum_family_video_count"])
        ):
            replicated.append(family)

    return sorted(replicated), evidence


def build_handoff_packets(
    candidates: list[dict[str, Any]],
    topic_velocity: dict[str, Any],
    expansion_evidence: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    view_reference = int(config["candidate_view_reference"])

    for candidate in candidates:
        fmt = str(candidate.get("format_candidate", "unknown"))
        for topic in sorted(candidate.get("validated_topics", [])):
            topic_evidence = topic_cell(topic_velocity, topic, fmt)
            topic_ready, topic_reasons = evaluate_topic_evidence(topic_evidence, config)

            families = candidate_topic_families(candidate, topic)
            replicated, family_evidence = replicated_families(
                expansion_evidence,
                topic,
                fmt,
                families,
                config,
            )

            views = int(candidate.get("views") or 0)
            demand_reference_met = views >= view_reference

            reasons = list(topic_reasons)
            if not families:
                reasons.append("no_depth_query_family_provenance")
            elif not replicated:
                reasons.append("no_replicated_depth_family")
            if not demand_reference_met:
                reasons.append("below_candidate_view_reference")

            if topic_ready and replicated and demand_reference_met:
                status = "PASS"
            elif topic_ready:
                status = "REVIEW"
            else:
                status = "HOLD"

            packets.append(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "handoff_id": f"{candidate.get('video_id')}:{topic}:{fmt}",
                    "gate_status": status,
                    "gate_reasons": reasons,
                    "video_id": candidate.get("video_id"),
                    "youtube_url": candidate.get("youtube_url"),
                    "title": candidate.get("title"),
                    "channel_id": candidate.get("channel_id"),
                    "channel_title": candidate.get("channel_title"),
                    "published_at": candidate.get("published_at"),
                    "age_days": candidate.get("age_days"),
                    "duration_seconds": candidate.get("duration_seconds"),
                    "format_candidate": fmt,
                    "views": views,
                    "likes": candidate.get("likes"),
                    "topic": topic,
                    "matched_families": families,
                    "replicated_families": replicated,
                    "candidate_view_reference": view_reference,
                    "candidate_view_reference_met": demand_reference_met,
                    "topic_evidence": topic_evidence,
                    "family_evidence": family_evidence,
                    "primary_metric": {
                        "name": "age_matched_velocity_index",
                        "value": (
                            topic_evidence.get("age_matched_velocity_index")
                            if topic_evidence
                            else None
                        ),
                    },
                }
            )

    return packets


def study_priority(packet: dict[str, Any]) -> tuple[float, int, str, str]:
    metric = packet.get("primary_metric", {}).get("value")
    metric_value = float(metric) if metric is not None else float("-inf")
    return (
        -metric_value,
        -int(packet.get("views") or 0),
        str(packet.get("topic", "")),
        str(packet.get("video_id", "")),
    )


def build_study_set(
    packets: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Coverage-constrained handoff set; no composite score is used."""

    eligible = sorted(
        [packet for packet in packets if packet.get("gate_status") == "PASS"],
        key=study_priority,
    )
    maximum = int(config["max_study_candidates"])
    max_per_cell = int(config["max_per_topic_format"])
    max_per_channel = int(config["max_per_channel"])

    topic_format_counts: dict[tuple[str, str], int] = defaultdict(int)
    channel_counts: dict[str, int] = defaultdict(int)
    used_video_ids: set[str] = set()
    selected: list[dict[str, Any]] = []

    for packet in eligible:
        if len(selected) >= maximum:
            break

        video_id = str(packet.get("video_id", ""))
        channel_id = str(packet.get("channel_id", ""))
        key = (str(packet.get("topic", "")), str(packet.get("format_candidate", "")))

        if not video_id or video_id in used_video_ids:
            continue
        if topic_format_counts[key] >= max_per_cell:
            continue
        if channel_id and channel_counts[channel_id] >= max_per_channel:
            continue

        selected.append(
            {
                **packet,
                "study_set_sequence": len(selected) + 1,
                "selection_basis": [
                    "PASS handoff gate",
                    "ordered by age_matched_velocity_index",
                    "absolute views used only as tie-breaker",
                    "topic/format and channel diversity caps applied",
                ],
            }
        )
        used_video_ids.add(video_id)
        topic_format_counts[key] += 1
        if channel_id:
            channel_counts[channel_id] += 1

    return selected


CSV_FIELDS = [
    "gate_status",
    "handoff_id",
    "video_id",
    "youtube_url",
    "title",
    "channel_id",
    "channel_title",
    "format_candidate",
    "views",
    "likes",
    "topic",
    "matched_families",
    "replicated_families",
    "candidate_view_reference_met",
    "age_matched_velocity_index",
    "topic_unique_channels",
    "topic_velocity_sample_count",
    "gate_reasons",
]


def write_outputs(
    packets: list[dict[str, Any]],
    study_set: list[dict[str, Any]],
    summary_01_3: dict[str, Any],
    summary_01_4: dict[str, Any],
    config: dict[str, Any],
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    PACKETS_FILE.write_text(
        json.dumps(packets, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    STUDY_SET_FILE.write_text(
        json.dumps(study_set, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    with CSV_FILE.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for packet in packets:
            topic_evidence = packet.get("topic_evidence") or {}
            writer.writerow(
                {
                    "gate_status": packet.get("gate_status"),
                    "handoff_id": packet.get("handoff_id"),
                    "video_id": packet.get("video_id"),
                    "youtube_url": packet.get("youtube_url"),
                    "title": packet.get("title"),
                    "channel_id": packet.get("channel_id"),
                    "channel_title": packet.get("channel_title"),
                    "format_candidate": packet.get("format_candidate"),
                    "views": packet.get("views"),
                    "likes": packet.get("likes"),
                    "topic": packet.get("topic"),
                    "matched_families": "|".join(packet.get("matched_families", [])),
                    "replicated_families": "|".join(packet.get("replicated_families", [])),
                    "candidate_view_reference_met": packet.get("candidate_view_reference_met"),
                    "age_matched_velocity_index": topic_evidence.get("age_matched_velocity_index"),
                    "topic_unique_channels": topic_evidence.get("unique_channels"),
                    "topic_velocity_sample_count": topic_evidence.get("velocity_sample_count"),
                    "gate_reasons": "|".join(packet.get("gate_reasons", [])),
                }
            )

    counts: dict[str, int] = defaultdict(int)
    for packet in packets:
        counts[str(packet.get("gate_status", "UNKNOWN"))] += 1

    summary = {
        "experiment": "Stage 2 Experiment 01.5",
        "purpose": "opportunity_handoff_gate",
        "status": "READY_FOR_EXPERIMENT_02" if study_set else "NO_PASSING_STUDY_SET",
        "source_01_3_cohort_id": summary_01_3.get("cohort_id"),
        "source_01_3_mode": summary_01_3.get("mode"),
        "source_01_4_execution_status": summary_01_4.get("execution_status"),
        "packet_count": len(packets),
        "gate_counts": dict(sorted(counts.items())),
        "study_set_count": len(study_set),
        "configuration": config,
        "outputs": {
            "packets": str(PACKETS_FILE),
            "study_set": str(STUDY_SET_FILE),
            "csv": str(CSV_FILE),
        },
        "notes": [
            "01.5 spends zero YouTube API quota.",
            "PASS / REVIEW / HOLD are explicit evidence gates, not scores.",
            "The study set uses age-matched velocity as the primary ordering metric.",
            "Absolute views are a tie-breaker only.",
            "Topic/format and channel caps preserve diversity.",
            "No composite opportunity score is calculated.",
        ],
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_waiting_summary(reason: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_FILE.write_text(
        json.dumps(
            {
                "experiment": "Stage 2 Experiment 01.5",
                "purpose": "opportunity_handoff_gate",
                "status": "WAITING",
                "reason": reason,
                "notes": [
                    "01.5 is offline and ready, but does not fabricate missing upstream evidence."
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def run_build() -> None:
    config = load_config()

    required = [
        TOPIC_VELOCITY_01_3,
        SUMMARY_01_3,
        RAW_01_4,
        EVIDENCE_01_4,
        SUMMARY_01_4,
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        reason = "missing_upstream_files: " + ", ".join(str(path) for path in missing)
        write_waiting_summary(reason)
        print("\nSTAGE 2 — EXPERIMENT 01.5")
        print("=" * 60)
        print("Status: WAITING")
        print(reason)
        return

    topic_velocity = load_json(TOPIC_VELOCITY_01_3)
    summary_01_3 = load_json(SUMMARY_01_3)
    raw_01_4 = load_json(RAW_01_4)
    expansion_evidence = load_json(EVIDENCE_01_4)
    summary_01_4 = load_json(SUMMARY_01_4)

    if summary_01_4.get("execution_status") != "COMPLETE":
        reason = (
            "Experiment 01.4 execution is not COMPLETE: "
            f"{summary_01_4.get('execution_status')}"
        )
        write_waiting_summary(reason)
        print("\nSTAGE 2 — EXPERIMENT 01.5")
        print("=" * 60)
        print("Status: WAITING")
        print(reason)
        return

    candidates = list(raw_01_4.get("accepted", []))
    packets = build_handoff_packets(
        candidates,
        topic_velocity,
        expansion_evidence,
        config,
    )
    study_set = build_study_set(packets, config)
    write_outputs(
        packets,
        study_set,
        summary_01_3,
        summary_01_4,
        config,
    )

    print("\nSTAGE 2 — EXPERIMENT 01.5")
    print("=" * 60)
    print("Mode: BUILD HANDOFF (zero API calls)")
    print(f"Packets:               {len(packets):,}")
    print(f"PASS:                  {sum(p.get('gate_status') == 'PASS' for p in packets):,}")
    print(f"REVIEW:                {sum(p.get('gate_status') == 'REVIEW' for p in packets):,}")
    print(f"HOLD:                  {sum(p.get('gate_status') == 'HOLD' for p in packets):,}")
    print(f"Experiment 02 study set: {len(study_set):,}")
    print(f"Study set:             {STUDY_SET_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage 2 Experiment 01.5 opportunity handoff gate"
    )
    parser.add_argument("--mode", choices=("build",), default="build")
    parser.parse_args()
    run_build()


if __name__ == "__main__":
    main()
