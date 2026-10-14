"""Experiment 02 analysis-model runner.

Runs prepared Experiment 02 analysis requests through a provider adapter.
The first adapter is FAIR, executed in FAIR's own Python environment through
a small subprocess bridge. Model responses are scope-restricted and passed
through the deterministic Experiment 02 apply gate before acceptance.

This module uses only the Python standard library plus local project modules.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from experiment_02_analysis.analysis_execute import merge_analysis_response
from core.hashing import sha256_file
from experiment_02_analysis.experiment_02 import load_config as load_experiment_config
from experiment_02_analysis.experiment_02 import safe_filename
from core.jsonio import load_json_or_exit as load_json

from core.pipeline_integrity import (
    atomic_write_json,
    atomic_write_text,
    batch_status,
    exit_code_for_status,
)
from core.model_bridge import (
    bridge_payload,
    call_fair_bridge,
    confirmed_free_providers,
    inference_cost_authorized,
    load_runner_config,
    parse_model_json,
    resolve_fair_paths,
    safe_attempts,
)

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent

OUTPUT_DIR = HERE / "output"
MODEL_RUNS_DIR = OUTPUT_DIR / "model_runs"
MODEL_RESPONSES_DIR = OUTPUT_DIR / "model_responses"
RAW_OUTPUTS_DIR = OUTPUT_DIR / "raw_model_outputs"
ANALYZED_DIR = OUTPUT_DIR / "profiles_analyzed"
BATCH_SUMMARY_FILE = OUTPUT_DIR / "model_runner_batch_summary.json"

def response_schema(request: dict[str, Any]) -> dict[str, Any]:
    mechanism_ids = sorted(request.get("mechanism_taxonomy", {}))
    dimensions = sorted(request.get("dimensions", {}))

    finding_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["finding", "mechanism_ids", "evidence_refs", "confidence"],
        "properties": {
            "finding": {"type": "string", "minLength": 1},
            "mechanism_ids": {
                "type": "array",
                "items": {"type": "string", "enum": mechanism_ids},
                "uniqueItems": True,
            },
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "minItems": 1,
                "uniqueItems": True,
            },
            "confidence": {
                "type": "string",
                "enum": ["LOW", "MODERATE", "HIGH"],
            },
        },
    }

    dimension_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["findings", "notes"],
        "properties": {
            "findings": {"type": "array", "items": finding_schema},
            "notes": {"type": "string"},
        },
    }

    transferable_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["description", "mechanism_ids", "evidence_refs", "confidence"],
        "properties": {
            "description": {"type": "string", "minLength": 1},
            "mechanism_ids": {
                "type": "array",
                "items": {"type": "string", "enum": mechanism_ids},
                "minItems": 1,
                "uniqueItems": True,
            },
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "minItems": 1,
                "uniqueItems": True,
            },
            "confidence": {
                "type": "string",
                "enum": ["LOW", "MODERATE", "HIGH"],
            },
        },
    }

    specific_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["element", "evidence_refs", "confidence"],
        "properties": {
            "element": {"type": "string", "minLength": 1},
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "minItems": 1,
                "uniqueItems": True,
            },
            "confidence": {
                "type": "string",
                "enum": ["LOW", "MODERATE", "HIGH"],
            },
        },
    }

    transformation_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "mechanism_id",
            "new_direction",
            "evidence_refs",
            "source_dependency_test",
        ],
        "properties": {
            "mechanism_id": {"type": "string", "enum": mechanism_ids},
            "new_direction": {"type": "string", "minLength": 1},
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "minItems": 1,
                "uniqueItems": True,
            },
            "source_dependency_test": {
                "type": "object",
                "additionalProperties": False,
                "required": ["passes", "rationale"],
                "properties": {
                    "passes": {"type": "boolean"},
                    "rationale": {"type": "string", "minLength": 1},
                },
            },
        },
    }

    hypothesis_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["hypothesis", "limitation"],
        "properties": {
            "hypothesis": {"type": "string", "minLength": 1},
            "limitation": {"type": "string", "minLength": 1},
            "dimension": {"type": "string"},
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "uniqueItems": True,
            },
        },
    }

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["video_id", "analysis", "working_hypotheses", "transfer"],
        "properties": {
            "video_id": {
                "type": "string",
                "const": str(request.get("video_id", "")),
            },
            "analysis": {
                "type": "object",
                "additionalProperties": False,
                "required": dimensions,
                "properties": {dimension: dimension_schema for dimension in dimensions},
            },
            "working_hypotheses": {
                "type": "array",
                "items": hypothesis_schema,
            },
            "transfer": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "transferable_mechanisms",
                    "source_specific_elements",
                    "transformation_opportunities",
                ],
                "properties": {
                    "transferable_mechanisms": {
                        "type": "array",
                        "items": transferable_schema,
                    },
                    "source_specific_elements": {
                        "type": "array",
                        "items": specific_schema,
                    },
                    "transformation_opportunities": {
                        "type": "array",
                        "items": transformation_schema,
                    },
                },
            },
        },
    }


def build_model_prompt(
    request: dict[str, Any],
    *,
    maximum_chars: int,
) -> str:
    prompt = (
        "You are performing a first-pass evidence analysis for a YouTube "
        "research pipeline. Return JSON only. Do not wrap the JSON in prose.\n\n"
        "Rules:\n"
        "1. Use only evidence supplied in evidence_library.\n"
        "2. For each dimension, use only evidence IDs listed in that "
        "dimension's evidence_refs.\n"
        "3. If evidence is insufficient, return an empty findings array and "
        "briefly explain the limitation in notes.\n"
        "4. Findings must be observational and evidence-backed. Do not claim "
        "a mechanism caused views, virality, recommendation exposure, or "
        "retention.\n"
        "5. Do not reproduce long transcript passages. Paraphrase observations "
        "and cite evidence IDs.\n"
        "6. Use only mechanism IDs from mechanism_taxonomy.\n"
        "7. Put interpretations that are plausible but not directly supported "
        "into working_hypotheses with an explicit limitation.\n"
        "8. Separate transferable mechanisms from source-specific expression.\n"
        "9. A transformation opportunity must remain valuable without copying "
        "the source creator's wording, footage, story, personality, or exact "
        "execution. Set source_dependency_test.passes accordingly.\n\n"
        "ANALYSIS REQUEST:\n"
        + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt) > maximum_chars:
        raise ValueError(
            f"Model prompt is {len(prompt):,} characters; configured maximum "
            f"is {maximum_chars:,}. Reduce the prepared evidence packet before running."
        )
    return prompt


def restrict_response_to_request(
    response: dict[str, Any],
    request: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Remove evidence refs the model was not shown before deterministic apply."""

    allowed = set(request.get("evidence_library", {}))
    result = deepcopy(response)
    removals: list[dict[str, Any]] = []

    def restrict(item: dict[str, Any], path: str) -> None:
        refs = item.get("evidence_refs")
        if not isinstance(refs, list):
            return
        kept = [str(ref) for ref in refs if str(ref) in allowed]
        removed = [str(ref) for ref in refs if str(ref) not in allowed]
        item["evidence_refs"] = kept
        if removed:
            removals.append({"path": path, "removed_refs": removed})

    for dimension, payload in result.get("analysis", {}).items():
        for index, item in enumerate(payload.get("findings", []) or []):
            restrict(item, f"analysis.{dimension}.findings[{index}]")

    for key in ("transferable_mechanisms", "source_specific_elements"):
        for index, item in enumerate(result.get("transfer", {}).get(key, []) or []):
            restrict(item, f"transfer.{key}[{index}]")

    for index, item in enumerate(
        result.get("transfer", {}).get("transformation_opportunities", []) or []
    ):
        restrict(item, f"transfer.transformation_opportunities[{index}]")

    for index, item in enumerate(result.get("working_hypotheses", []) or []):
        restrict(item, f"working_hypotheses[{index}]")

    return result, removals


def resolve_profile_path(
    request: dict[str, Any],
    explicit_profile: Path | None,
) -> Path:
    if explicit_profile is not None:
        return explicit_profile.resolve()

    source = request.get("request_provenance", {}).get("profile_source")
    if not source:
        raise ValueError(
            "Analysis request has no request_provenance.profile_source; "
            "pass --profile explicitly."
        )
    return Path(str(source)).expanduser().resolve()


def run_one(
    request_path: Path,
    *,
    profile_path: Path | None,
    force: bool,
    runner_config: dict[str, Any],
) -> dict[str, Any]:
    request_path = request_path.resolve()
    request = load_json(request_path)
    profile_path = resolve_profile_path(request, profile_path)
    profile = load_json(profile_path)

    request_video_id = str(request.get("video_id", ""))
    profile_video_id = str(profile.get("video_id", ""))
    if request_video_id != profile_video_id:
        raise ValueError(
            f"Request video_id {request_video_id!r} does not match profile "
            f"video_id {profile_video_id!r}"
        )

    request_hash = sha256_file(request_path)
    video_slug = safe_filename(request_video_id or request_path.stem)
    report_path = MODEL_RUNS_DIR / f"{video_slug}.model_run.json"

    if report_path.exists() and not force:
        existing = load_json(report_path)
        if (
            existing.get("request_sha256") == request_hash
            and existing.get("status") == "APPLIED"
        ):
            return {
                "status": "SKIPPED_ALREADY_APPLIED",
                "video_id": request_video_id,
                "report": str(report_path),
            }

    maximum_prompt_chars = int(runner_config["runner"].get("max_prompt_chars", 95000))
    prompt = build_model_prompt(request, maximum_chars=maximum_prompt_chars)
    schema = response_schema(request)
    schema_chars = len(json.dumps(schema, separators=(",", ":")))
    if schema_chars > 19000:
        raise ValueError(
            f"Generated response schema is {schema_chars:,} characters; "
            "FAIR supports schemas below 20,000 characters."
        )

    paths = resolve_fair_paths(runner_config)
    payload = bridge_payload(
        action="solve",
        prompt=prompt,
        schema=schema,
        config=runner_config,
        paths=paths,
    )

    MODEL_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    RAW_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    ANALYZED_DIR.mkdir(parents=True, exist_ok=True)

    try:
        bridge_result = call_fair_bridge(
            payload,
            python_executable=paths["python"],
            timeout_seconds=float(
                runner_config["runner"].get("subprocess_timeout_seconds", 300)
            ),
        )
    except Exception as exc:
        report = {
            "video_id": request_video_id,
            "status": "RUNNER_ERROR",
            "error_type": type(exc).__name__,
            "request_source": str(request_path),
            "request_sha256": request_hash,
            "profile_source": str(profile_path),
            "adapter": runner_config["adapter"],
        }
        atomic_write_json(report_path, report)
        return report

    if not inference_cost_authorized(bridge_result):
        report = {
            "video_id": request_video_id,
            "status": "COST_POLICY_VIOLATION",
            "request_source": str(request_path),
            "request_sha256": request_hash,
            "adapter": runner_config["adapter"],
            "bridge_status": bridge_result.get("status"),
        }
        atomic_write_json(report_path, report)
        return report

    base_report = {
        "video_id": request_video_id,
        "request_source": str(request_path),
        "request_sha256": request_hash,
        "profile_source": str(profile_path),
        "profile_sha256": sha256_file(profile_path),
        "adapter": runner_config["adapter"],
        "fair_request_id": bridge_result.get("request_id"),
        "fair_status": bridge_result.get("status"),
        "fair_reason_code": bridge_result.get("reason_code"),
        "provider_id": bridge_result.get("provider_id"),
        "model_id": bridge_result.get("model_id"),
        "best_quality_score": bridge_result.get("best_quality_score"),
        "verification_state": bridge_result.get("verification_state"),
        "paid_inference_executed": bridge_result.get("paid_inference_executed"),
        "direct_backup_used": bridge_result.get("direct_backup_used", False),
        "direct_backup_may_bill": bridge_result.get("direct_backup_may_bill", False),
        "billing_authorization": bridge_result.get("billing_authorization"),
        "bridge_error_type": bridge_result.get("error_type"),
        "bridge_error_detail": bridge_result.get("error_detail"),
        "compatibility": bridge_result.get("compatibility"),
        "attempts": safe_attempts(bridge_result),
    }

    if bridge_result.get("status") != "ACCEPTED":
        report = {
            **base_report,
            "status": (
                "MODEL_ESCALATION_REQUIRED"
                if bridge_result.get("status") == "ESCALATION_REQUIRED"
                else "MODEL_FAILED"
            ),
        }
        atomic_write_json(report_path, report)
        return report

    raw_output = str(bridge_result.get("output") or "")
    raw_path = RAW_OUTPUTS_DIR / f"{video_slug}.txt"
    atomic_write_text(raw_path, raw_output)

    try:
        response = parse_model_json(raw_output)
    except Exception as exc:
        report = {
            **base_report,
            "status": "MODEL_OUTPUT_PARSE_ERROR",
            "error_type": type(exc).__name__,
            "raw_output": str(raw_path),
        }
        atomic_write_json(report_path, report)
        return report

    restricted_response, scope_removals = restrict_response_to_request(
        response,
        request,
    )
    response_path = MODEL_RESPONSES_DIR / f"{video_slug}.json"
    atomic_write_json(response_path, restricted_response)

    experiment_config = load_experiment_config()
    try:
        analyzed_profile, apply_report = merge_analysis_response(
            profile,
            restricted_response,
            experiment_config,
        )
    except Exception as exc:
        report = {
            **base_report,
            "status": "APPLY_ERROR",
            "error_type": type(exc).__name__,
            "model_response": str(response_path),
            "scope_removals": scope_removals,
        }
        atomic_write_json(report_path, report)
        return report

    if not apply_report.get("final_profile_valid"):
        report = {
            **base_report,
            "status": "APPLY_VALIDATION_FAILED",
            "model_response": str(response_path),
            "scope_removals": scope_removals,
            "apply": {
                "accepted_findings": apply_report.get("accepted_findings"),
                "accepted_transfer_items": apply_report.get("accepted_transfer_items"),
                "routed_to_hypotheses": apply_report.get("routed_to_hypotheses"),
                "final_validation_errors": apply_report.get("final_validation_errors"),
                "final_validation_warnings": apply_report.get(
                    "final_validation_warnings"
                ),
            },
        }
        atomic_write_json(report_path, report)
        return report

    analyzed_path = ANALYZED_DIR / f"{video_slug}.json"
    atomic_write_json(analyzed_path, analyzed_profile)

    report = {
        **base_report,
        "status": "APPLIED",
        "model_response": str(response_path),
        "raw_output": str(raw_path),
        "analyzed_profile": str(analyzed_path),
        "scope_removals": scope_removals,
        "apply": {
            "final_profile_valid": apply_report.get("final_profile_valid"),
            "accepted_findings": apply_report.get("accepted_findings"),
            "accepted_transfer_items": apply_report.get("accepted_transfer_items"),
            "routed_to_hypotheses": apply_report.get("routed_to_hypotheses"),
            "final_validation_errors": apply_report.get("final_validation_errors"),
            "final_validation_warnings": apply_report.get("final_validation_warnings"),
        },
    }
    atomic_write_json(report_path, report)
    return report


def run_doctor(config: dict[str, Any]) -> dict[str, Any]:
    paths = resolve_fair_paths(config)
    payload = bridge_payload(
        action="doctor",
        prompt=None,
        schema=None,
        config=config,
        paths=paths,
    )
    try:
        result = call_fair_bridge(
            payload,
            python_executable=paths["python"],
            timeout_seconds=float(
                config["runner"].get("subprocess_timeout_seconds", 300)
            ),
        )
    except Exception as exc:
        return {
            "status": "DOCTOR_ERROR",
            "error_type": type(exc).__name__,
            "fair_repo": str(paths["repo"]),
            "fair_python": str(paths["python"]),
            "fair_env_file": str(paths["env_file"]),
        }

    return {
        "status": result.get("status"),
        "error_type": result.get("error_type"),
        "error_detail": result.get("error_detail"),
        "fair_repo": str(paths["repo"]),
        "fair_python": str(paths["python"]),
        "fair_env_file": str(paths["env_file"]),
        "confirmed_free_providers": confirmed_free_providers(
            config,
            paths["env_file"],
        ),
        "providers": result.get("providers", []),
        "skipped": result.get("skipped", {}),
        "compatibility": result.get("compatibility", {}),
    }


def run_batch(
    requests_dir: Path,
    *,
    force: bool,
    maximum_requests: int | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    paths = sorted(requests_dir.glob("*.analysis_request.json"))
    limit = int(
        maximum_requests
        if maximum_requests is not None
        else config["runner"].get("max_requests_per_batch", 4)
    )

    results: list[dict[str, Any]] = []
    invoked = 0
    for request_path in paths:
        if invoked >= limit:
            break

        result = run_one(
            request_path,
            profile_path=None,
            force=force,
            runner_config=config,
        )
        results.append(result)
        if result.get("status") != "SKIPPED_ALREADY_APPLIED":
            invoked += 1

        if result.get("status") in {
            "COST_POLICY_VIOLATION",
            "RUNNER_ERROR",
            "MODEL_FAILED",
        }:
            break

    summary = {
        "status": batch_status(
            results,
            expected_count=len(paths),
            processed_count=len(results),
        ),
        "requests_found": len(paths),
        "model_runs_invoked": invoked,
        "batch_limit": limit,
        "results": results,
    }
    atomic_write_json(BATCH_SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Experiment 02 FAIR-backed analysis model runner"
    )
    parser.add_argument(
        "--mode",
        choices=("doctor", "run", "batch"),
        required=True,
    )
    parser.add_argument("--request", type=Path, default=None)
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--requests-dir", type=Path, default=None)
    parser.add_argument("--max-requests", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    config = load_runner_config()

    if args.mode == "doctor":
        result = run_doctor(config)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.mode == "run":
        if args.request is None:
            raise SystemExit("--request is required for run mode")
        result = run_one(
            args.request,
            profile_path=args.profile,
            force=args.force,
            runner_config=config,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.requests_dir is None:
        raise SystemExit("--requests-dir is required for batch mode")
    summary = run_batch(
        args.requests_dir.resolve(),
        force=args.force,
        maximum_requests=args.max_requests,
        config=config,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    raise SystemExit(exit_code_for_status(summary["status"]))


if __name__ == "__main__":
    main()
