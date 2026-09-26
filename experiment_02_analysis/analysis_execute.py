"""Experiment 02 analysis execution helper.

Two-phase, offline workflow:

1. PREPARE: build compact dimension-specific evidence packets and objective
   metrics from an enriched Experiment 02 profile.
2. APPLY: merge a human/LLM analysis response back into the profile only when
   findings are directly supported by valid evidence references.

Unsupported or causal interpretations are diverted into working_hypotheses
instead of being stored as factual findings.
"""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from experiment_02 import (
    OUTPUT_DIR,
    evidence_index,
    load_config,
    load_json,
    safe_filename,
    validate_profile,
    validate_supported_item,
)

REQUESTS_DIR = OUTPUT_DIR / "analysis_requests"
ANALYZED_DIR = OUTPUT_DIR / "profiles_analyzed"
APPLY_REPORTS_DIR = OUTPUT_DIR / "analysis_apply_reports"

TIME_RANGE_RE = re.compile(
    r"^(?P<start>\d{2}:\d{2}:\d{2}\.\d{3})-(?P<end>\d{2}:\d{2}:\d{2}\.\d{3})$"
)
TIME_POINT_RE = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}$")


def timecode_to_seconds(value: str) -> float:
    hours, minutes, seconds_ms = value.split(":")
    seconds, milliseconds = seconds_ms.split(".")
    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int(milliseconds) / 1000.0
    )


def evidence_time_bounds(item: dict[str, Any]) -> tuple[float | None, float | None]:
    locator = str(item.get("locator", "")).strip()
    match = TIME_RANGE_RE.match(locator)
    if match:
        return (
            timecode_to_seconds(match.group("start")),
            timecode_to_seconds(match.group("end")),
        )
    if TIME_POINT_RE.match(locator):
        value = timecode_to_seconds(locator)
        return value, value
    return None, None


def compact_evidence_item(
    item: dict[str, Any],
    *,
    max_observation_chars: int,
) -> dict[str, Any]:
    observation = str(item.get("observation", ""))
    truncated = False
    if len(observation) > max_observation_chars:
        observation = observation[: max_observation_chars - 1].rstrip() + "…"
        truncated = True

    return {
        "evidence_id": item.get("evidence_id"),
        "type": item.get("type"),
        "locator": item.get("locator"),
        "observation": observation,
        "observation_truncated": truncated,
    }


def objective_metrics(
    profile: dict[str, Any],
    *,
    opening_window_seconds: float,
) -> dict[str, Any]:
    evidence = profile.get("evidence", [])
    counts: dict[str, int] = {}
    transcript_word_count = 0
    transcript_segments = 0
    transcript_starts: list[float] = []
    transcript_ends: list[float] = []
    opening_refs: list[str] = []

    for item in evidence:
        evidence_type = str(item.get("type", "unknown"))
        counts[evidence_type] = counts.get(evidence_type, 0) + 1

        start, end = evidence_time_bounds(item)
        if start is not None and start <= opening_window_seconds:
            if evidence_type in {
                "transcript",
                "opening_frame",
                "visual_note",
                "timing_note",
                "audio_note",
            }:
                evidence_id = str(item.get("evidence_id", "")).strip()
                if evidence_id:
                    opening_refs.append(evidence_id)

        if evidence_type == "transcript":
            transcript_segments += 1
            transcript_word_count += len(
                re.findall(r"\b\w+\b", str(item.get("observation", "")))
            )
            if start is not None:
                transcript_starts.append(start)
            if end is not None:
                transcript_ends.append(end)

    transcript_span = None
    transcript_segments_per_minute = None
    if transcript_starts and transcript_ends:
        start = min(transcript_starts)
        end = max(transcript_ends)
        transcript_span = max(0.0, end - start)
        if transcript_span > 0:
            transcript_segments_per_minute = round(
                transcript_segments / (transcript_span / 60.0),
                2,
            )

    return {
        "evidence_counts_by_type": dict(sorted(counts.items())),
        "total_evidence_items": len(evidence),
        "transcript_segment_count": transcript_segments,
        "transcript_word_count": transcript_word_count,
        "timestamped_transcript_span_seconds": (
            round(transcript_span, 3) if transcript_span is not None else None
        ),
        "transcript_segments_per_minute": transcript_segments_per_minute,
        "opening_window_seconds": opening_window_seconds,
        "opening_window_evidence_refs": sorted(set(opening_refs)),
    }


def dimension_packet(
    profile: dict[str, Any],
    dimension: str,
    config: dict[str, Any],
    *,
    max_evidence_items: int,
    max_observation_chars: int,
) -> dict[str, Any]:
    allowed_types = set(
        config["dimension_evidence_types"].get(dimension, [])
    )
    matching = [
        item
        for item in profile.get("evidence", [])
        if item.get("type") in allowed_types
        and item.get("type") != "opportunity_evidence"
    ]

    selected = matching[:max_evidence_items]
    return {
        "dimension": dimension,
        "allowed_evidence_types": sorted(allowed_types),
        "evidence_available": bool(matching),
        "evidence_item_count": len(matching),
        "evidence_items_in_packet": len(selected),
        "evidence_truncated": len(matching) > len(selected),
        "evidence": [
            compact_evidence_item(
                item,
                max_observation_chars=max_observation_chars,
            )
            for item in selected
        ],
        "response_schema": {
            "findings": [
                {
                    "finding": "Observed, evidence-backed statement",
                    "mechanism_ids": ["mechanism_id_if_applicable"],
                    "evidence_refs": ["evidence.id"],
                    "confidence": "LOW|MODERATE|HIGH",
                }
            ],
            "notes": "Optional analyst notes",
        },
    }


def build_analysis_request(
    profile: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    execution = config.get("analysis_execution", {})
    opening_window_seconds = float(
        execution.get("opening_window_seconds", 30)
    )
    max_evidence_items = int(
        execution.get("max_evidence_items_per_dimension", 60)
    )
    max_observation_chars = int(
        execution.get("max_observation_chars", 1200)
    )

    dimensions = {
        dimension: dimension_packet(
            profile,
            dimension,
            config,
            max_evidence_items=max_evidence_items,
            max_observation_chars=max_observation_chars,
        )
        for dimension in config["required_dimensions"]
    }

    return {
        "experiment_id": "02",
        "request_type": "why_it_worked_analysis",
        "video_id": profile.get("video_id"),
        "study_id": profile.get("study_id"),
        "source": profile.get("source", {}),
        "objective_metrics": objective_metrics(
            profile,
            opening_window_seconds=opening_window_seconds,
        ),
        "mechanism_taxonomy": config["mechanism_taxonomy"],
        "dimensions": dimensions,
        "transfer_response_schema": {
            "transferable_mechanisms": [
                {
                    "description": "General mechanism supported by source evidence",
                    "mechanism_ids": ["mechanism_id"],
                    "evidence_refs": ["evidence.id"],
                    "confidence": "LOW|MODERATE|HIGH",
                }
            ],
            "source_specific_elements": [
                {
                    "element": "Source-specific wording, footage, personality, or execution",
                    "evidence_refs": ["evidence.id"],
                    "confidence": "LOW|MODERATE|HIGH",
                }
            ],
            "transformation_opportunities": [
                {
                    "mechanism_id": "mechanism_id",
                    "new_direction": "A genuinely new concept direction",
                    "evidence_refs": ["evidence.id"],
                    "source_dependency_test": {
                        "passes": true,
                        "rationale": "Why the new concept keeps its value without the source expression"
                    }
                }
            ],
        },
        "working_hypothesis_schema": {
            "hypothesis": "Interpretation not established as a supported finding",
            "limitation": "Why the evidence is insufficient",
            "dimension": "optional_dimension",
            "evidence_refs": ["optional.evidence.id"],
        },
        "instructions": [
            "Use only the evidence supplied in this request.",
            "Do not infer thumbnail, visual, audio, pacing, hook, story, or payoff details that are not evidenced.",
            "Every factual finding must cite one or more evidence_refs.",
            "Use only mechanism_ids from the supplied mechanism_taxonomy.",
            "Do not claim a mechanism caused views, virality, recommendation, or retention.",
            "Place unsupported interpretations in working_hypotheses with an explicit limitation.",
            "Keep transferable mechanisms separate from source-specific expression.",
            "Transformation opportunities must pass the Source Dependency Test.",
        ],
    }


def supported_finding_or_hypothesis(
    finding: dict[str, Any],
    *,
    dimension: str,
    evidence: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
    allowed_types = set(
        config["dimension_evidence_types"].get(dimension, [])
    )
    errors, warnings = validate_supported_item(
        finding,
        path=f"analysis.{dimension}",
        evidence=evidence,
        allowed_evidence_types=allowed_types,
        config=config,
    )

    if not errors and not warnings:
        return finding, None, {
            "status": "ACCEPTED_FINDING",
            "errors": [],
            "warnings": [],
        }

    statement = str(finding.get("finding", "")).strip()
    valid_refs = [
        str(ref)
        for ref in finding.get("evidence_refs", [])
        if str(ref) in evidence
    ]
    reasons = errors + warnings
    hypothesis = {
        "hypothesis": statement or "Unsupported analysis statement",
        "limitation": "Not accepted as a factual finding: " + "; ".join(reasons),
        "dimension": dimension,
        "evidence_refs": valid_refs,
        "routed_from": "analysis_response.finding",
    }
    return None, hypothesis, {
        "status": "ROUTED_TO_HYPOTHESIS",
        "errors": errors,
        "warnings": warnings,
    }


def supported_transfer_or_hypothesis(
    item: dict[str, Any],
    *,
    path: str,
    statement_key: str,
    evidence: dict[str, dict[str, Any]],
    config: dict[str, Any],
    require_mechanism_ids: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
    non_opportunity_types = {
        evidence_type
        for evidence_type in config["evidence_types"]
        if evidence_type != "opportunity_evidence"
    }
    normalized = dict(item)
    if statement_key != "finding":
        normalized["finding"] = item.get(statement_key)

    errors, warnings = validate_supported_item(
        normalized,
        path=path,
        evidence=evidence,
        allowed_evidence_types=non_opportunity_types,
        config=config,
        require_mechanism_ids=require_mechanism_ids,
    )

    if not errors and not warnings:
        return item, None, {
            "status": "ACCEPTED",
            "errors": [],
            "warnings": [],
        }

    statement = str(item.get(statement_key, "")).strip()
    valid_refs = [
        str(ref)
        for ref in item.get("evidence_refs", [])
        if str(ref) in evidence
    ]
    hypothesis = {
        "hypothesis": statement or "Unsupported transfer interpretation",
        "limitation": "Not accepted into transfer analysis: "
        + "; ".join(errors + warnings),
        "dimension": "transfer",
        "evidence_refs": valid_refs,
        "routed_from": path,
    }
    return None, hypothesis, {
        "status": "ROUTED_TO_HYPOTHESIS",
        "errors": errors,
        "warnings": warnings,
    }


def validate_transformation_opportunity(
    item: dict[str, Any],
    *,
    evidence: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    mechanism_id = item.get("mechanism_id")
    if mechanism_id not in config["mechanism_taxonomy"]:
        errors.append("valid mechanism_id is required")

    new_direction = str(item.get("new_direction", "")).strip()
    if not new_direction:
        errors.append("new_direction is required")

    refs = item.get("evidence_refs", [])
    if not isinstance(refs, list) or not refs:
        errors.append("evidence_refs are required")
    else:
        unknown = [str(ref) for ref in refs if str(ref) not in evidence]
        if unknown:
            errors.append("unknown evidence refs: " + ", ".join(unknown))
        if refs:
            evidence_types = {
                str(evidence[str(ref)].get("type"))
                for ref in refs
                if str(ref) in evidence
            }
            if evidence_types == {"opportunity_evidence"}:
                errors.append(
                    "opportunity_evidence alone cannot support transformation"
                )

    dependency = item.get("source_dependency_test", {})
    if not isinstance(dependency.get("passes"), bool):
        errors.append("source_dependency_test.passes must be boolean")
    elif dependency.get("passes") is not True:
        errors.append("source_dependency_test does not pass")

    if not str(dependency.get("rationale", "")).strip():
        errors.append("source_dependency_test.rationale is required")

    lowered = new_direction.casefold()
    for phrase in config["causal_warning_phrases"]:
        if str(phrase).casefold() in lowered:
            warnings.append(
                f"causal wording '{phrase}' is not established by the evidence"
            )

    return errors, warnings


def merge_analysis_response(
    profile: dict[str, Any],
    response: dict[str, Any],
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    profile_video_id = str(profile.get("video_id", ""))
    response_video_id = str(response.get("video_id", ""))
    if response_video_id != profile_video_id:
        raise ValueError(
            f"Response video_id {response_video_id!r} does not match profile "
            f"video_id {profile_video_id!r}"
        )

    result = deepcopy(profile)
    evidence = evidence_index(result)
    routed_hypotheses: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []

    response_analysis = response.get("analysis", {})
    for dimension in config["required_dimensions"]:
        payload = response_analysis.get(dimension, {})
        findings = payload.get("findings", [])
        if findings is None:
            findings = []
        if not isinstance(findings, list):
            raise ValueError(f"analysis.{dimension}.findings must be a list")

        accepted: list[dict[str, Any]] = []
        for ordinal, finding in enumerate(findings):
            accepted_finding, hypothesis, decision = supported_finding_or_hypothesis(
                finding,
                dimension=dimension,
                evidence=evidence,
                config=config,
            )
            decision.update(
                {
                    "path": f"analysis.{dimension}.findings[{ordinal}]",
                    "statement": finding.get("finding"),
                }
            )
            decisions.append(decision)
            if accepted_finding is not None:
                accepted.append(accepted_finding)
            if hypothesis is not None:
                routed_hypotheses.append(hypothesis)

        result.setdefault("analysis", {}).setdefault(
            dimension,
            {"findings": [], "notes": ""},
        )
        result["analysis"][dimension]["findings"] = accepted
        if "notes" in payload:
            result["analysis"][dimension]["notes"] = str(payload.get("notes") or "")

    transfer_response = response.get("transfer", {})
    transfer_result = result.setdefault(
        "transfer",
        {
            "transferable_mechanisms": [],
            "source_specific_elements": [],
            "transformation_opportunities": [],
        },
    )

    for key, statement_key, require_mechanisms in (
        ("transferable_mechanisms", "description", True),
        ("source_specific_elements", "element", False),
    ):
        accepted_items: list[dict[str, Any]] = []
        items = transfer_response.get(key, []) or []
        if not isinstance(items, list):
            raise ValueError(f"transfer.{key} must be a list")

        for ordinal, item in enumerate(items):
            accepted_item, hypothesis, decision = supported_transfer_or_hypothesis(
                item,
                path=f"transfer.{key}[{ordinal}]",
                statement_key=statement_key,
                evidence=evidence,
                config=config,
                require_mechanism_ids=require_mechanisms,
            )
            decision.update(
                {
                    "path": f"transfer.{key}[{ordinal}]",
                    "statement": item.get(statement_key),
                }
            )
            decisions.append(decision)
            if accepted_item is not None:
                accepted_items.append(accepted_item)
            if hypothesis is not None:
                routed_hypotheses.append(hypothesis)

        transfer_result[key] = accepted_items

    accepted_transformations: list[dict[str, Any]] = []
    transformations = transfer_response.get("transformation_opportunities", []) or []
    if not isinstance(transformations, list):
        raise ValueError("transfer.transformation_opportunities must be a list")

    for ordinal, item in enumerate(transformations):
        errors, warnings = validate_transformation_opportunity(
            item,
            evidence=evidence,
            config=config,
        )
        path = f"transfer.transformation_opportunities[{ordinal}]"
        if not errors and not warnings:
            accepted_transformations.append(item)
            decisions.append(
                {
                    "path": path,
                    "statement": item.get("new_direction"),
                    "status": "ACCEPTED",
                    "errors": [],
                    "warnings": [],
                }
            )
        else:
            valid_refs = [
                str(ref)
                for ref in item.get("evidence_refs", [])
                if str(ref) in evidence
            ]
            routed_hypotheses.append(
                {
                    "hypothesis": str(item.get("new_direction", "")).strip()
                    or "Unsupported transformation opportunity",
                    "limitation": "Not accepted as a transformation opportunity: "
                    + "; ".join(errors + warnings),
                    "dimension": "transformation",
                    "evidence_refs": valid_refs,
                    "routed_from": path,
                }
            )
            decisions.append(
                {
                    "path": path,
                    "statement": item.get("new_direction"),
                    "status": "ROUTED_TO_HYPOTHESIS",
                    "errors": errors,
                    "warnings": warnings,
                }
            )

    transfer_result["transformation_opportunities"] = accepted_transformations

    explicit_hypotheses = response.get("working_hypotheses", []) or []
    if not isinstance(explicit_hypotheses, list):
        raise ValueError("working_hypotheses must be a list")

    accepted_explicit_hypotheses: list[dict[str, Any]] = []
    for ordinal, hypothesis in enumerate(explicit_hypotheses):
        statement = str(hypothesis.get("hypothesis", "")).strip()
        limitation = str(hypothesis.get("limitation", "")).strip()
        if not statement or not limitation:
            decisions.append(
                {
                    "path": f"working_hypotheses[{ordinal}]",
                    "statement": statement,
                    "status": "REJECTED_MALFORMED_HYPOTHESIS",
                    "errors": [
                        "hypothesis and limitation are both required"
                    ],
                    "warnings": [],
                }
            )
            continue

        normalized = dict(hypothesis)
        refs = normalized.get("evidence_refs", [])
        if refs is not None:
            normalized["evidence_refs"] = [
                str(ref) for ref in refs if str(ref) in evidence
            ]
        accepted_explicit_hypotheses.append(normalized)

    result["working_hypotheses"] = (
        accepted_explicit_hypotheses + routed_hypotheses
    )

    result["analysis_execution"] = {
        "response_video_id": response_video_id,
        "accepted_findings": sum(
            decision["status"] == "ACCEPTED_FINDING"
            for decision in decisions
        ),
        "accepted_transfer_items": sum(
            decision["status"] == "ACCEPTED"
            for decision in decisions
        ),
        "routed_to_hypotheses": sum(
            decision["status"] == "ROUTED_TO_HYPOTHESIS"
            for decision in decisions
        ),
        "decisions": decisions,
    }

    validation = validate_profile(result, config)
    report = {
        "video_id": profile_video_id,
        "final_profile_valid": validation["valid"],
        "final_validation_errors": validation["errors"],
        "final_validation_warnings": validation["warnings"],
        "accepted_findings": result["analysis_execution"]["accepted_findings"],
        "accepted_transfer_items": result["analysis_execution"][
            "accepted_transfer_items"
        ],
        "routed_to_hypotheses": result["analysis_execution"][
            "routed_to_hypotheses"
        ],
        "decisions": decisions,
    }
    return result, report


def run_prepare(profile_path: Path, output_path: Path | None) -> None:
    profile = load_json(profile_path)
    config = load_config()
    request = build_analysis_request(profile, config)

    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    video_id = safe_filename(str(profile.get("video_id", "unknown")))
    destination = (
        output_path.resolve()
        if output_path is not None
        else (REQUESTS_DIR / f"{video_id}.analysis_request.json").resolve()
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(request, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nEXPERIMENT 02 ANALYSIS EXECUTION")
    print("=" * 60)
    print("Mode: PREPARE")
    print(f"Video:   {profile.get('video_id')}")
    print(f"Request: {destination}")
    print("No model or network call was made.")


def run_apply(
    profile_path: Path,
    response_path: Path,
    output_path: Path | None,
) -> None:
    profile = load_json(profile_path)
    response = load_json(response_path)
    config = load_config()

    merged, report = merge_analysis_response(profile, response, config)

    ANALYZED_DIR.mkdir(parents=True, exist_ok=True)
    APPLY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    video_id = safe_filename(str(profile.get("video_id", "unknown")))
    destination = (
        output_path.resolve()
        if output_path is not None
        else (ANALYZED_DIR / f"{video_id}.json").resolve()
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    report["output_profile"] = str(destination)
    report_path = APPLY_REPORTS_DIR / f"{video_id}.analysis_apply.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nEXPERIMENT 02 ANALYSIS EXECUTION")
    print("=" * 60)
    print("Mode: APPLY")
    print(f"Video:                  {profile.get('video_id')}")
    print(f"Accepted findings:      {report['accepted_findings']}")
    print(f"Accepted transfer items:{report['accepted_transfer_items']}")
    print(f"Routed to hypotheses:   {report['routed_to_hypotheses']}")
    print(f"Final profile valid:    {report['final_profile_valid']}")
    print(f"Output profile:         {destination}")
    print(f"Apply report:           {report_path}")


def run_batch_prepare(
    profiles_dir: Path,
) -> None:
    if not profiles_dir.exists():
        raise SystemExit(f"Profiles directory not found: {profiles_dir}")

    config = load_config()
    paths = sorted(profiles_dir.glob("*.json"))
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)

    created = 0
    for profile_path in paths:
        profile = load_json(profile_path)
        request = build_analysis_request(profile, config)
        video_id = safe_filename(str(profile.get("video_id", profile_path.stem)))
        destination = REQUESTS_DIR / f"{video_id}.analysis_request.json"
        destination.write_text(
            json.dumps(request, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        created += 1

    print("\nEXPERIMENT 02 ANALYSIS EXECUTION")
    print("=" * 60)
    print("Mode: BATCH PREPARE")
    print(f"Profiles read:    {len(paths)}")
    print(f"Requests created: {created}")
    print(f"Output directory: {REQUESTS_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Experiment 02 evidence-linked analysis execution helper"
    )
    parser.add_argument(
        "--mode",
        choices=("prepare", "apply", "batch-prepare"),
        required=True,
    )
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--response", type=Path, default=None)
    parser.add_argument("--profiles-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if args.mode == "prepare":
        if args.profile is None:
            raise SystemExit("--profile is required for prepare mode")
        run_prepare(args.profile.resolve(), args.output)
    elif args.mode == "apply":
        if args.profile is None or args.response is None:
            raise SystemExit(
                "--profile and --response are required for apply mode"
            )
        run_apply(
            args.profile.resolve(),
            args.response.resolve(),
            args.output,
        )
    else:
        if args.profiles_dir is None:
            raise SystemExit("--profiles-dir is required for batch-prepare mode")
        run_batch_prepare(args.profiles_dir.resolve())


if __name__ == "__main__":
    main()
