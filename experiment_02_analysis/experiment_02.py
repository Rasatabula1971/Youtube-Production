"""Experiment 02 — Why Did It Work? evidence framework.

This module is deliberately offline. It prepares analysis packets from the
Experiment 01.5 study set, validates evidence-backed analysis profiles, and
aggregates repeated mechanisms across independent source videos/channels.

It does not download videos, fetch transcripts, call an LLM, or spend YouTube
API quota.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
CONFIG_FILE = HERE / "experiment_02_config.json"
TEMPLATE_FILE = HERE / "profile_template.json"

SOURCE_STUDY_SET = (
    PROJECT_ROOT
    / "experiment_01_discovery"
    / "output"
    / "experiment_01_5"
    / "study_set.json"
)

OUTPUT_DIR = HERE / "output"
WORK_PACKETS_FILE = OUTPUT_DIR / "work_packets.json"
PREPARED_PROFILES_DIR = OUTPUT_DIR / "profiles_to_complete"
VALIDATION_DIR = OUTPUT_DIR / "validation_reports"
PATTERNS_FILE = OUTPUT_DIR / "cross_video_patterns.json"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"

EXPERIMENT_ID = "02"
SCHEMA_VERSION = "2.0"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_FILE)
    required = {
        "required_dimensions",
        "allowed_confidence",
        "evidence_types",
        "dimension_evidence_types",
        "mechanism_taxonomy",
        "minimum_replication_videos",
        "minimum_replication_channels",
        "causal_warning_phrases",
    }
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit("Experiment 02 config is missing: " + ", ".join(missing))
    return config


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "unknown"


def empty_analysis(config: dict[str, Any]) -> dict[str, Any]:
    return {
        dimension: {
            "findings": [],
            "notes": "",
        }
        for dimension in config["required_dimensions"]
    }


def build_profile_from_study_item(
    study_item: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    video_id = str(study_item.get("video_id", ""))
    title = str(study_item.get("title", ""))

    evidence = [
        {
            "evidence_id": "metadata.title",
            "type": "metadata",
            "locator": "video title",
            "observation": title,
        },
        {
            "evidence_id": "opportunity.01_5",
            "type": "opportunity_evidence",
            "locator": "Experiment 01.5 handoff packet",
            "observation": (
                "Upstream demand evidence is context only; it does not prove "
                "a creative mechanism caused performance."
            ),
        },
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "study_id": str(study_item.get("handoff_id") or video_id),
        "video_id": video_id,
        "youtube_url": study_item.get("youtube_url"),
        "source": {
            "title": title,
            "channel_id": study_item.get("channel_id"),
            "channel_title": study_item.get("channel_title"),
            "format_candidate": study_item.get("format_candidate"),
            "topic": study_item.get("topic"),
            "views_at_handoff": study_item.get("views"),
            "age_matched_velocity_index": (
                study_item.get("primary_metric", {}).get("value")
            ),
            "replicated_families": study_item.get("replicated_families", []),
        },
        "source_inputs": {
            "transcript": {"status": "NOT_PROVIDED", "source": None},
            "thumbnail": {"status": "NOT_PROVIDED", "source": None},
            "opening_frame": {"status": "NOT_PROVIDED", "source": None},
            "visual_notes": {"status": "NOT_PROVIDED", "source": None},
            "timing_notes": {"status": "NOT_PROVIDED", "source": None},
            "audio_notes": {"status": "NOT_PROVIDED", "source": None},
        },
        "evidence": evidence,
        "analysis": empty_analysis(config),
        "working_hypotheses": [],
        "transfer": {
            "transferable_mechanisms": [],
            "source_specific_elements": [],
            "transformation_opportunities": [],
        },
        "review": {
            "analyst": None,
            "completed": False,
            "notes": "",
        },
    }


def prepare_work_packets(
    study_set: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    packets = []
    for item in study_set:
        profile = build_profile_from_study_item(item, config)
        packets.append(
            {
                "study_id": profile["study_id"],
                "video_id": profile["video_id"],
                "youtube_url": profile["youtube_url"],
                "title": profile["source"]["title"],
                "channel_title": profile["source"]["channel_title"],
                "topic": profile["source"]["topic"],
                "format_candidate": profile["source"]["format_candidate"],
                "required_source_inputs": list(profile["source_inputs"]),
                "profile_filename": safe_filename(profile["video_id"]) + ".json",
            }
        )
    return packets


def evidence_index(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in profile.get("evidence", []):
        evidence_id = str(item.get("evidence_id", "")).strip()
        if evidence_id:
            index[evidence_id] = item
    return index


def finding_evidence_types(
    refs: list[str],
    evidence: dict[str, dict[str, Any]],
) -> set[str]:
    return {
        str(evidence[ref].get("type"))
        for ref in refs
        if ref in evidence
    }


def causal_warnings(statement: str, config: dict[str, Any]) -> list[str]:
    lowered = statement.casefold()
    return [
        phrase
        for phrase in config["causal_warning_phrases"]
        if str(phrase).casefold() in lowered
    ]


def validate_supported_item(
    item: dict[str, Any],
    *,
    path: str,
    evidence: dict[str, dict[str, Any]],
    allowed_evidence_types: set[str] | None,
    config: dict[str, Any],
    require_mechanism_ids: bool = False,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    statement = str(
        item.get("finding")
        or item.get("description")
        or item.get("element")
        or item.get("opportunity")
        or ""
    ).strip()
    if not statement:
        errors.append(f"{path}: missing supported statement")

    refs = item.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        errors.append(f"{path}: evidence_refs must contain at least one evidence id")
        refs = []

    unknown = [str(ref) for ref in refs if str(ref) not in evidence]
    if unknown:
        errors.append(f"{path}: unknown evidence refs: {', '.join(unknown)}")

    if allowed_evidence_types and refs:
        observed_types = finding_evidence_types(
            [str(ref) for ref in refs],
            evidence,
        )
        if not observed_types.intersection(allowed_evidence_types):
            errors.append(
                f"{path}: evidence types {sorted(observed_types)} do not support "
                f"this dimension; expected one of {sorted(allowed_evidence_types)}"
            )

    confidence = item.get("confidence")
    if confidence is not None and confidence not in config["allowed_confidence"]:
        errors.append(f"{path}: invalid confidence {confidence!r}")

    mechanism_ids = item.get("mechanism_ids", [])
    if require_mechanism_ids and not mechanism_ids:
        errors.append(f"{path}: at least one mechanism_id is required")

    unknown_mechanisms = [
        mechanism
        for mechanism in mechanism_ids
        if mechanism not in config["mechanism_taxonomy"]
    ]
    if unknown_mechanisms:
        errors.append(
            f"{path}: unknown mechanism ids: {', '.join(unknown_mechanisms)}"
        )

    for phrase in causal_warnings(statement, config):
        warnings.append(
            f"{path}: causal wording '{phrase}' is not established by public "
            "observational evidence"
        )

    return errors, warnings


def validate_profile(
    profile: dict[str, Any],
    config: dict[str, Any],
    *,
    allowed_video_ids: set[str] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if profile.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {SCHEMA_VERSION}; "
            f"received {profile.get('schema_version')!r}"
        )

    video_id = str(profile.get("video_id", ""))
    if not video_id:
        errors.append("video_id is required")
    elif allowed_video_ids is not None and video_id not in allowed_video_ids:
        errors.append("video_id is not present in the Experiment 01.5 study set")

    evidence = evidence_index(profile)
    if not evidence:
        errors.append("evidence list is empty")

    duplicate_count = len(profile.get("evidence", [])) - len(evidence)
    if duplicate_count > 0:
        errors.append("evidence_id values must be unique")

    analysis = profile.get("analysis", {})
    for dimension in config["required_dimensions"]:
        if dimension not in analysis:
            errors.append(f"analysis.{dimension} is required")
            continue
        findings = analysis[dimension].get("findings", [])
        if not isinstance(findings, list):
            errors.append(f"analysis.{dimension}.findings must be a list")
            continue

        allowed_types = set(
            config["dimension_evidence_types"].get(dimension, [])
        )
        for index, finding in enumerate(findings):
            item_errors, item_warnings = validate_supported_item(
                finding,
                path=f"analysis.{dimension}.findings[{index}]",
                evidence=evidence,
                allowed_evidence_types=allowed_types,
                config=config,
                require_mechanism_ids=False,
            )
            errors.extend(item_errors)
            warnings.extend(item_warnings)

    for index, item in enumerate(
        profile.get("transfer", {}).get("transferable_mechanisms", [])
    ):
        item_errors, item_warnings = validate_supported_item(
            item,
            path=f"transfer.transferable_mechanisms[{index}]",
            evidence=evidence,
            allowed_evidence_types={
                evidence_type
                for evidence_type in config["evidence_types"]
                if evidence_type != "opportunity_evidence"
            },
            config=config,
            require_mechanism_ids=True,
        )
        errors.extend(item_errors)
        warnings.extend(item_warnings)

    for index, item in enumerate(
        profile.get("transfer", {}).get("source_specific_elements", [])
    ):
        item_errors, item_warnings = validate_supported_item(
            item,
            path=f"transfer.source_specific_elements[{index}]",
            evidence=evidence,
            allowed_evidence_types={
                evidence_type
                for evidence_type in config["evidence_types"]
                if evidence_type != "opportunity_evidence"
            },
            config=config,
        )
        errors.extend(item_errors)
        warnings.extend(item_warnings)

    for index, item in enumerate(
        profile.get("transfer", {}).get("transformation_opportunities", [])
    ):
        path = f"transfer.transformation_opportunities[{index}]"
        mechanism_id = item.get("mechanism_id")
        if mechanism_id not in config["mechanism_taxonomy"]:
            errors.append(f"{path}: valid mechanism_id is required")

        new_direction = str(item.get("new_direction", "")).strip()
        if not new_direction:
            errors.append(f"{path}: new_direction is required")

        dependency = item.get("source_dependency_test", {})
        if not isinstance(dependency.get("passes"), bool):
            errors.append(f"{path}: source_dependency_test.passes must be boolean")
        if not str(dependency.get("rationale", "")).strip():
            errors.append(f"{path}: source_dependency_test.rationale is required")

        refs = item.get("evidence_refs", [])
        if not isinstance(refs, list) or not refs:
            errors.append(f"{path}: evidence_refs are required")
        else:
            unknown = [str(ref) for ref in refs if str(ref) not in evidence]
            if unknown:
                errors.append(
                    f"{path}: unknown evidence refs: {', '.join(unknown)}"
                )

    for index, hypothesis in enumerate(profile.get("working_hypotheses", [])):
        if not str(hypothesis.get("hypothesis", "")).strip():
            errors.append(f"working_hypotheses[{index}]: hypothesis is required")
        if not str(hypothesis.get("limitation", "")).strip():
            errors.append(f"working_hypotheses[{index}]: limitation is required")

    return {
        "video_id": video_id,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "evidence_count": len(evidence),
    }


def iter_mechanism_occurrences(
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    occurrences: list[dict[str, Any]] = []

    for dimension, payload in profile.get("analysis", {}).items():
        for finding in payload.get("findings", []):
            for mechanism_id in finding.get("mechanism_ids", []):
                occurrences.append(
                    {
                        "mechanism_id": mechanism_id,
                        "dimension": dimension,
                        "evidence_refs": finding.get("evidence_refs", []),
                    }
                )

    for item in profile.get("transfer", {}).get("transferable_mechanisms", []):
        for mechanism_id in item.get("mechanism_ids", []):
            occurrences.append(
                {
                    "mechanism_id": mechanism_id,
                    "dimension": "transferable_mechanism",
                    "evidence_refs": item.get("evidence_refs", []),
                }
            )

    return occurrences


def aggregate_profiles(
    profiles: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    allowed_video_ids: set[str] | None = None,
) -> dict[str, Any]:
    valid_profiles: list[dict[str, Any]] = []
    validation_reports: list[dict[str, Any]] = []

    for profile in profiles:
        report = validate_profile(
            profile,
            config,
            allowed_video_ids=allowed_video_ids,
        )
        validation_reports.append(report)
        if report["valid"]:
            valid_profiles.append(profile)

    mechanism_rows: dict[str, dict[str, Any]] = {}

    for profile in valid_profiles:
        video_id = str(profile.get("video_id", ""))
        channel_id = str(profile.get("source", {}).get("channel_id", ""))
        for occurrence in iter_mechanism_occurrences(profile):
            mechanism_id = str(occurrence["mechanism_id"])
            row = mechanism_rows.setdefault(
                mechanism_id,
                {
                    "mechanism_id": mechanism_id,
                    "video_ids": set(),
                    "channel_ids": set(),
                    "dimensions": set(),
                    "evidence_occurrences": 0,
                },
            )
            row["video_ids"].add(video_id)
            if channel_id:
                row["channel_ids"].add(channel_id)
            row["dimensions"].add(str(occurrence["dimension"]))
            row["evidence_occurrences"] += len(occurrence.get("evidence_refs", []))

    patterns = []
    for mechanism_id in sorted(mechanism_rows):
        row = mechanism_rows[mechanism_id]
        video_count = len(row["video_ids"])
        channel_count = len(row["channel_ids"])
        replicated = (
            video_count >= int(config["minimum_replication_videos"])
            and channel_count >= int(config["minimum_replication_channels"])
        )
        patterns.append(
            {
                "mechanism_id": mechanism_id,
                "label": config["mechanism_taxonomy"][mechanism_id],
                "status": (
                    "REPLICATED_PATTERN"
                    if replicated
                    else "SINGLE_SOURCE_OBSERVATION"
                ),
                "video_count": video_count,
                "unique_channels": channel_count,
                "video_ids": sorted(row["video_ids"]),
                "channel_ids": sorted(row["channel_ids"]),
                "dimensions": sorted(row["dimensions"]),
                "evidence_occurrences": row["evidence_occurrences"],
            }
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "schema_version": SCHEMA_VERSION,
        "valid_profile_count": len(valid_profiles),
        "invalid_profile_count": len(profiles) - len(valid_profiles),
        "validation_reports": validation_reports,
        "patterns": patterns,
        "notes": [
            "Repeated occurrence is observational evidence, not causal proof.",
            "Only profiles passing evidence validation contribute to pattern aggregation.",
            "Replication requires independent videos and independent channels.",
        ],
    }


def load_study_set_video_ids() -> set[str]:
    if not SOURCE_STUDY_SET.exists():
        return set()
    study_set = load_json(SOURCE_STUDY_SET)
    return {
        str(item.get("video_id"))
        for item in study_set
        if item.get("video_id")
    }


def run_prepare() -> None:
    config = load_config()
    if not SOURCE_STUDY_SET.exists():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        summary = {
            "experiment": "Experiment 02 — Why Did It Work?",
            "status": "WAITING_FOR_01_5_STUDY_SET",
            "source": str(SOURCE_STUDY_SET),
            "api_calls": 0,
        }
        SUMMARY_FILE.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print("\nEXPERIMENT 02")
        print("=" * 60)
        print("Status: WAITING_FOR_01_5_STUDY_SET")
        print(f"Expected input: {SOURCE_STUDY_SET}")
        return

    study_set = load_json(SOURCE_STUDY_SET)
    packets = prepare_work_packets(study_set, config)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PREPARED_PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    WORK_PACKETS_FILE.write_text(
        json.dumps(packets, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    for item in study_set:
        profile = build_profile_from_study_item(item, config)
        filename = safe_filename(str(profile["video_id"])) + ".json"
        (PREPARED_PROFILES_DIR / filename).write_text(
            json.dumps(profile, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    summary = {
        "experiment": "Experiment 02 — Why Did It Work?",
        "status": "PREPARED",
        "study_video_count": len(study_set),
        "profile_count": len(packets),
        "api_calls": 0,
        "outputs": {
            "work_packets": str(WORK_PACKETS_FILE),
            "profiles_to_complete": str(PREPARED_PROFILES_DIR),
        },
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nEXPERIMENT 02")
    print("=" * 60)
    print("Mode: PREPARE (zero API calls)")
    print(f"Study videos: {len(study_set):,}")
    print(f"Profiles:     {PREPARED_PROFILES_DIR}")


def run_validate(profile_path: Path) -> None:
    config = load_config()
    profile = load_json(profile_path)
    allowed_ids = load_study_set_video_ids() or None
    report = validate_profile(
        profile,
        config,
        allowed_video_ids=allowed_ids,
    )

    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    output = VALIDATION_DIR / (safe_filename(profile_path.stem) + ".validation.json")
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nEXPERIMENT 02 PROFILE VALIDATION")
    print("=" * 60)
    print(f"Video:    {report['video_id']}")
    print(f"Valid:    {report['valid']}")
    print(f"Errors:   {len(report['errors'])}")
    print(f"Warnings: {len(report['warnings'])}")
    print(f"Report:   {output}")


def run_aggregate(profiles_dir: Path) -> None:
    config = load_config()
    if not profiles_dir.exists():
        raise SystemExit(f"Profiles directory not found: {profiles_dir}")

    profile_paths = sorted(profiles_dir.glob("*.json"))
    profiles = [load_json(path) for path in profile_paths]
    allowed_ids = load_study_set_video_ids() or None

    result = aggregate_profiles(
        profiles,
        config,
        allowed_video_ids=allowed_ids,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PATTERNS_FILE.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nEXPERIMENT 02 CROSS-VIDEO AGGREGATION")
    print("=" * 60)
    print(f"Profiles read:  {len(profiles):,}")
    print(f"Valid profiles: {result['valid_profile_count']:,}")
    print(f"Patterns:       {len(result['patterns']):,}")
    print(f"Output:         {PATTERNS_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Experiment 02 why-it-worked evidence framework"
    )
    parser.add_argument(
        "--mode",
        choices=("prepare", "validate", "aggregate"),
        required=True,
    )
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--profiles-dir", type=Path, default=None)
    args = parser.parse_args()

    if args.mode == "prepare":
        run_prepare()
    elif args.mode == "validate":
        if args.profile is None:
            raise SystemExit("--profile is required for validate mode")
        run_validate(args.profile)
    else:
        if args.profiles_dir is None:
            raise SystemExit("--profiles-dir is required for aggregate mode")
        run_aggregate(args.profiles_dir)


if __name__ == "__main__":
    main()
