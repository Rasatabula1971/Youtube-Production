"""Experiment 02 cross-video synthesis and transformation handoff.

Consumes analyzed Experiment 02 profiles, validates them, builds a mechanism
library, distinguishes replicated patterns from single-source observations,
tracks human-review coverage, and creates a deterministic handoff for the
Transformation Engine.

No network calls, model calls, or YouTube API calls are made here.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from experiment_02 import load_config, load_json, validate_profile

HERE = Path(__file__).resolve().parent
SYNTHESIS_CONFIG_FILE = HERE / "synthesis_config.json"

OUTPUT_DIR = HERE / "output"
ANALYZED_PROFILES_DIR = OUTPUT_DIR / "profiles_analyzed"
REVIEWED_PROFILES_DIR = OUTPUT_DIR / "profiles_reviewed"
SYNTHESIS_DIR = OUTPUT_DIR / "synthesis"
MECHANISM_LIBRARY_FILE = SYNTHESIS_DIR / "mechanism_library.json"
HANDOFF_FILE = SYNTHESIS_DIR / "transformation_handoff.json"
SUMMARY_FILE = SYNTHESIS_DIR / "synthesis_summary.json"


def load_synthesis_config() -> dict[str, Any]:
    config = load_json(SYNTHESIS_CONFIG_FILE)
    required = {
        "max_observed_examples_per_mechanism",
        "max_transfer_descriptions_per_mechanism",
        "max_transformation_directions_per_mechanism",
        "require_human_review_for_ready",
    }
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit(
            "Experiment 02 synthesis config is missing: " + ", ".join(missing)
        )
    return config


def profile_reviewed(profile: dict[str, Any]) -> bool:
    return bool(profile.get("review", {}).get("completed") is True)


def supported_profile_metadata(profile: dict[str, Any]) -> dict[str, Any]:
    source = profile.get("source", {})
    return {
        "video_id": str(profile.get("video_id", "")),
        "channel_id": str(source.get("channel_id", "")),
        "channel_title": source.get("channel_title"),
        "topic": source.get("topic"),
        "format_candidate": source.get("format_candidate"),
        "review_completed": profile_reviewed(profile),
    }


def collect_occurrences(profile: dict[str, Any]) -> list[dict[str, Any]]:
    meta = supported_profile_metadata(profile)
    occurrences: list[dict[str, Any]] = []

    for dimension, payload in profile.get("analysis", {}).items():
        for finding in payload.get("findings", []):
            for mechanism_id in finding.get("mechanism_ids", []):
                occurrences.append(
                    {
                        **meta,
                        "mechanism_id": mechanism_id,
                        "source_kind": "analysis_finding",
                        "dimension": dimension,
                        "statement": finding.get("finding"),
                        "confidence": finding.get("confidence"),
                        "evidence_refs": list(finding.get("evidence_refs", [])),
                    }
                )

    for item in profile.get("transfer", {}).get("transferable_mechanisms", []):
        for mechanism_id in item.get("mechanism_ids", []):
            occurrences.append(
                {
                    **meta,
                    "mechanism_id": mechanism_id,
                    "source_kind": "transferable_mechanism",
                    "dimension": "transferable_mechanism",
                    "statement": item.get("description"),
                    "confidence": item.get("confidence"),
                    "evidence_refs": list(item.get("evidence_refs", [])),
                }
            )

    return occurrences


def collect_source_specific_elements(
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    meta = supported_profile_metadata(profile)
    return [
        {
            **meta,
            "element": item.get("element"),
            "confidence": item.get("confidence"),
            "evidence_refs": list(item.get("evidence_refs", [])),
        }
        for item in profile.get("transfer", {}).get(
            "source_specific_elements", []
        )
    ]


def collect_transformation_directions(
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    meta = supported_profile_metadata(profile)
    items: list[dict[str, Any]] = []

    for item in profile.get("transfer", {}).get(
        "transformation_opportunities", []
    ):
        dependency = item.get("source_dependency_test", {})
        if dependency.get("passes") is not True:
            continue

        mechanism_id = str(item.get("mechanism_id", "")).strip()
        if not mechanism_id:
            continue

        items.append(
            {
                **meta,
                "mechanism_id": mechanism_id,
                "new_direction": item.get("new_direction"),
                "evidence_refs": list(item.get("evidence_refs", [])),
                "source_dependency_test": {
                    "passes": True,
                    "rationale": dependency.get("rationale"),
                },
            }
        )

    return items


def unique_nonempty(values: list[Any]) -> list[str]:
    return sorted(
        {
            str(value)
            for value in values
            if value is not None and str(value).strip()
        }
    )


def replication_scope(values: list[str], *, cross_label: str) -> str:
    unique = unique_nonempty(values)
    if not unique:
        return "UNKNOWN"
    if len(unique) == 1:
        return "SINGLE"
    return cross_label


def mechanism_state(
    *,
    video_count: int,
    channel_count: int,
    reviewed_video_count: int,
    reviewed_channel_count: int,
    minimum_videos: int,
    minimum_channels: int,
) -> str:
    replicated = (
        video_count >= minimum_videos
        and channel_count >= minimum_channels
    )
    if not replicated:
        return "SINGLE_SOURCE_OBSERVATION"

    reviewed_replicated = (
        reviewed_video_count >= minimum_videos
        and reviewed_channel_count >= minimum_channels
    )
    if reviewed_replicated:
        return "HUMAN_CONFIRMED_PATTERN"

    return "MODEL_SYNTHESIS_DRAFT"


def build_mechanism_library(
    profiles: list[dict[str, Any]],
    experiment_config: dict[str, Any],
    synthesis_config: dict[str, Any],
) -> dict[str, Any]:
    validation_reports = []
    valid_profiles: list[dict[str, Any]] = []

    for profile in profiles:
        report = validate_profile(profile, experiment_config)
        validation_reports.append(report)
        if report["valid"]:
            valid_profiles.append(profile)

    occurrence_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    direction_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_specific_by_video: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for profile in valid_profiles:
        for occurrence in collect_occurrences(profile):
            mechanism_id = str(occurrence["mechanism_id"])
            if mechanism_id in experiment_config["mechanism_taxonomy"]:
                occurrence_map[mechanism_id].append(occurrence)

        for direction in collect_transformation_directions(profile):
            mechanism_id = str(direction["mechanism_id"])
            if mechanism_id in experiment_config["mechanism_taxonomy"]:
                direction_map[mechanism_id].append(direction)

        for item in collect_source_specific_elements(profile):
            source_specific_by_video[str(item["video_id"])].append(item)

    minimum_videos = int(experiment_config["minimum_replication_videos"])
    minimum_channels = int(experiment_config["minimum_replication_channels"])
    max_examples = int(
        synthesis_config["max_observed_examples_per_mechanism"]
    )
    max_transfer = int(
        synthesis_config["max_transfer_descriptions_per_mechanism"]
    )
    max_directions = int(
        synthesis_config["max_transformation_directions_per_mechanism"]
    )

    mechanisms: list[dict[str, Any]] = []

    for mechanism_id in sorted(occurrence_map):
        occurrences = occurrence_map[mechanism_id]
        video_ids = unique_nonempty(
            [item.get("video_id") for item in occurrences]
        )
        channel_ids = unique_nonempty(
            [item.get("channel_id") for item in occurrences]
        )
        reviewed_video_ids = unique_nonempty(
            [
                item.get("video_id")
                for item in occurrences
                if item.get("review_completed")
            ]
        )
        reviewed_channel_ids = unique_nonempty(
            [
                item.get("channel_id")
                for item in occurrences
                if item.get("review_completed")
            ]
        )

        topics = unique_nonempty([item.get("topic") for item in occurrences])
        formats = unique_nonempty(
            [item.get("format_candidate") for item in occurrences]
        )
        dimensions = unique_nonempty(
            [item.get("dimension") for item in occurrences]
        )

        state = mechanism_state(
            video_count=len(video_ids),
            channel_count=len(channel_ids),
            reviewed_video_count=len(reviewed_video_ids),
            reviewed_channel_count=len(reviewed_channel_ids),
            minimum_videos=minimum_videos,
            minimum_channels=minimum_channels,
        )

        observed_examples = [
            {
                "video_id": item.get("video_id"),
                "channel_id": item.get("channel_id"),
                "topic": item.get("topic"),
                "format_candidate": item.get("format_candidate"),
                "dimension": item.get("dimension"),
                "statement": item.get("statement"),
                "confidence": item.get("confidence"),
                "evidence_refs": item.get("evidence_refs", []),
                "review_completed": item.get("review_completed"),
            }
            for item in occurrences
            if item.get("source_kind") == "analysis_finding"
        ][:max_examples]

        transferable_descriptions = [
            {
                "video_id": item.get("video_id"),
                "channel_id": item.get("channel_id"),
                "description": item.get("statement"),
                "confidence": item.get("confidence"),
                "evidence_refs": item.get("evidence_refs", []),
                "review_completed": item.get("review_completed"),
            }
            for item in occurrences
            if item.get("source_kind") == "transferable_mechanism"
        ][:max_transfer]

        source_specific = []
        for video_id in video_ids:
            for item in source_specific_by_video.get(video_id, []):
                source_specific.append(
                    {
                        "video_id": item.get("video_id"),
                        "channel_id": item.get("channel_id"),
                        "element": item.get("element"),
                        "confidence": item.get("confidence"),
                        "evidence_refs": item.get("evidence_refs", []),
                    }
                )

        directions = direction_map.get(mechanism_id, [])[:max_directions]

        mechanisms.append(
            {
                "mechanism_id": mechanism_id,
                "label": experiment_config["mechanism_taxonomy"][mechanism_id],
                "state": state,
                "replication": {
                    "video_count": len(video_ids),
                    "unique_channels": len(channel_ids),
                    "reviewed_video_count": len(reviewed_video_ids),
                    "reviewed_unique_channels": len(reviewed_channel_ids),
                    "minimum_videos": minimum_videos,
                    "minimum_channels": minimum_channels,
                    "video_ids": video_ids,
                    "channel_ids": channel_ids,
                    "reviewed_video_ids": reviewed_video_ids,
                    "reviewed_channel_ids": reviewed_channel_ids,
                },
                "scope": {
                    "topics": topics,
                    "topic_scope": replication_scope(
                        topics, cross_label="CROSS_TOPIC"
                    ),
                    "formats": formats,
                    "format_scope": replication_scope(
                        formats, cross_label="CROSS_FORMAT"
                    ),
                    "dimensions": dimensions,
                },
                "occurrence_count": len(occurrences),
                "observed_examples": observed_examples,
                "transferable_descriptions": transferable_descriptions,
                "source_specific_elements_to_avoid": source_specific,
                "accepted_transformation_directions": directions,
                "notes": [
                    "Replication is observational evidence, not causal proof.",
                    "State reflects breadth and human-review coverage, not importance or ranking.",
                ],
            }
        )

    return {
        "experiment_id": "02",
        "artifact": "mechanism_library",
        "valid_profile_count": len(valid_profiles),
        "invalid_profile_count": len(profiles) - len(valid_profiles),
        "validation_reports": validation_reports,
        "mechanisms": mechanisms,
        "notes": [
            "No composite mechanism score is calculated.",
            "Mechanisms are not ranked as best or worst.",
            "Only evidence-valid profiles contribute.",
            "Human-confirmed status requires replicated support among human-reviewed profiles.",
        ],
    }


def build_transformation_handoff(
    library: dict[str, Any],
    synthesis_config: dict[str, Any],
) -> dict[str, Any]:
    require_review = bool(
        synthesis_config["require_human_review_for_ready"]
    )

    entries: list[dict[str, Any]] = []

    for mechanism in library.get("mechanisms", []):
        state = mechanism.get("state")
        if state == "SINGLE_SOURCE_OBSERVATION":
            continue

        if require_review and state != "HUMAN_CONFIRMED_PATTERN":
            handoff_status = "REQUIRES_HUMAN_REVIEW"
        else:
            handoff_status = "READY_FOR_TRANSFORMATION_ENGINE"

        entries.append(
            {
                "mechanism_id": mechanism["mechanism_id"],
                "label": mechanism["label"],
                "pattern_state": state,
                "handoff_status": handoff_status,
                "replication": mechanism["replication"],
                "scope": mechanism["scope"],
                "observed_examples": mechanism["observed_examples"],
                "transferable_descriptions": mechanism[
                    "transferable_descriptions"
                ],
                "source_specific_elements_to_avoid": mechanism[
                    "source_specific_elements_to_avoid"
                ],
                "existing_transformation_directions": mechanism[
                    "accepted_transformation_directions"
                ],
                "source_dependency_rule": (
                    "New concepts must retain their main value without the "
                    "source creator's wording, footage, story, personality, "
                    "or exact execution."
                ),
            }
        )

    ready = [
        item
        for item in entries
        if item["handoff_status"] == "READY_FOR_TRANSFORMATION_ENGINE"
    ]
    waiting = [
        item
        for item in entries
        if item["handoff_status"] == "REQUIRES_HUMAN_REVIEW"
    ]

    if ready:
        status = "READY_FOR_TRANSFORMATION_ENGINE"
    elif waiting:
        status = "DRAFT_REQUIRES_HUMAN_REVIEW"
    else:
        status = "NO_REPLICATED_PATTERNS"

    return {
        "experiment_id": "02",
        "artifact": "transformation_handoff",
        "status": status,
        "ready_count": len(ready),
        "requires_review_count": len(waiting),
        "entries": entries,
        "notes": [
            "The handoff contains replicated mechanisms only.",
            "A handoff entry is not a generated content concept.",
            "No mechanism ranking or opportunity score is calculated.",
        ],
    }


def build_summary(
    library: dict[str, Any],
    handoff: dict[str, Any],
    profiles_dir: Path,
) -> dict[str, Any]:
    states: dict[str, int] = defaultdict(int)
    for mechanism in library.get("mechanisms", []):
        states[str(mechanism.get("state"))] += 1

    return {
        "experiment": "Experiment 02 synthesis/handoff",
        "status": handoff.get("status"),
        "profiles_dir": str(profiles_dir),
        "valid_profiles": library.get("valid_profile_count", 0),
        "invalid_profiles": library.get("invalid_profile_count", 0),
        "mechanism_count": len(library.get("mechanisms", [])),
        "mechanism_states": dict(sorted(states.items())),
        "handoff_entries": len(handoff.get("entries", [])),
        "ready_for_transformation": handoff.get("ready_count", 0),
        "requires_human_review": handoff.get("requires_review_count", 0),
        "outputs": {
            "mechanism_library": str(MECHANISM_LIBRARY_FILE),
            "transformation_handoff": str(HANDOFF_FILE),
        },
        "api_calls": 0,
        "model_calls": 0,
    }


def preferred_profiles_dir() -> Path:
    if REVIEWED_PROFILES_DIR.exists() and any(
        REVIEWED_PROFILES_DIR.glob("*.json")
    ):
        return REVIEWED_PROFILES_DIR
    return ANALYZED_PROFILES_DIR


def load_profiles(profiles_dir: Path) -> list[dict[str, Any]]:
    if not profiles_dir.exists():
        return []
    return [load_json(path) for path in sorted(profiles_dir.glob("*.json"))]


def run_build(profiles_dir: Path) -> dict[str, Any]:
    experiment_config = load_config()
    synthesis_config = load_synthesis_config()
    profiles = load_profiles(profiles_dir)

    SYNTHESIS_DIR.mkdir(parents=True, exist_ok=True)

    if not profiles:
        summary = {
            "experiment": "Experiment 02 synthesis/handoff",
            "status": "WAITING_FOR_ANALYZED_PROFILES",
            "profiles_dir": str(profiles_dir),
            "valid_profiles": 0,
            "invalid_profiles": 0,
            "mechanism_count": 0,
            "api_calls": 0,
            "model_calls": 0,
        }
        SUMMARY_FILE.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return summary

    library = build_mechanism_library(
        profiles, experiment_config, synthesis_config
    )
    handoff = build_transformation_handoff(
        library, synthesis_config
    )
    summary = build_summary(library, handoff, profiles_dir)

    MECHANISM_LIBRARY_FILE.write_text(
        json.dumps(library, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    HANDOFF_FILE.write_text(
        json.dumps(handoff, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Experiment 02 synthesis and Transformation Engine handoff"
    )
    parser.add_argument(
        "--mode",
        choices=("build",),
        default="build",
    )
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=None,
    )
    args = parser.parse_args()

    profiles_dir = (
        args.profiles_dir.resolve()
        if args.profiles_dir is not None
        else preferred_profiles_dir().resolve()
    )
    summary = run_build(profiles_dir)

    print("\nEXPERIMENT 02 SYNTHESIS / HANDOFF")
    print("=" * 60)
    print(f"Status:                  {summary['status']}")
    print(f"Valid profiles:          {summary.get('valid_profiles', 0)}")
    print(f"Mechanisms:              {summary.get('mechanism_count', 0)}")
    print(
        "Ready for transformation: "
        f"{summary.get('ready_for_transformation', 0)}"
    )
    print(
        "Requires human review:    "
        f"{summary.get('requires_human_review', 0)}"
    )
    if summary["status"] != "WAITING_FOR_ANALYZED_PROFILES":
        print(f"Mechanism library:       {MECHANISM_LIBRARY_FILE}")
        print(f"Transformation handoff: {HANDOFF_FILE}")


if __name__ == "__main__":
    main()
