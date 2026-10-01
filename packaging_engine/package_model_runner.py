"""FAIR-backed Packaging Engine package runner.

Prepared package requests are sent through the existing FAIR subprocess bridge.
The runner is free-only, validates model output through packaging_engine, and
writes request-bound responses for the deterministic merge step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_INTEGRITY_ROOT = Path(__file__).resolve().parent.parent
if str(_INTEGRITY_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEGRITY_ROOT))

from typing import Any

from pipeline_integrity import (
    atomic_write_json,
    atomic_write_text,
    batch_status,
    exit_code_for_status,
    tolerant_load_json,
)

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
EXP2_DIR = PROJECT_ROOT / "experiment_02_analysis"
if str(EXP2_DIR) not in sys.path:
    sys.path.insert(0, str(EXP2_DIR))

from analysis_model_runner import (
    bridge_payload,
    call_fair_bridge,
    inference_cost_authorized,
    load_runner_config,
    parse_model_json,
    resolve_fair_paths,
    safe_attempts,
)

from packaging_engine import (
    OUTPUT_DIR,
    REQUESTS_DIR,
    RESPONSES_DIR,
    load_config,
    load_json,
    run_apply,
    safe_slug,
    validate_response,
)

MODEL_RUNS_DIR = OUTPUT_DIR / "package_model_runs"
RAW_OUTPUTS_DIR = OUTPUT_DIR / "raw_package_outputs"
BATCH_SUMMARY_FILE = OUTPUT_DIR / "package_model_batch_summary.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def response_schema(request: dict[str, Any]) -> dict[str, Any]:
    concept_id = str(request.get("concept_id", ""))
    allowed_formats = list(request.get("allowed_format_intents", []))
    package_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "package_id",
            "title",
            "thumbnail",
            "opening_frame",
            "expected_viewer",
            "awareness_level",
            "viewer_problem",
            "viewer_moment",
            "desired_outcome",
            "one_sentence_promise",
            "gap_positioning",
            "channel_fit_alignment",
            "core_promise",
            "curiosity_gap",
            "expected_payoff",
            "format_intent",
            "title_thumbnail_relationship",
            "research_dependencies",
        ],
        "properties": {
            "package_id": {"type": "string", "minLength": 1},
            "title": {"type": "string", "minLength": 1},
            "thumbnail": {
                "type": "object",
                "additionalProperties": False,
                "required": ["message", "visual_concept", "text_overlay"],
                "properties": {
                    "message": {"type": "string", "minLength": 1},
                    "visual_concept": {"type": "string", "minLength": 1},
                    "text_overlay": {"type": "string"},
                },
            },
            "opening_frame": {
                "type": "object",
                "additionalProperties": False,
                "required": ["purpose", "visual_concept"],
                "properties": {
                    "purpose": {"type": "string", "minLength": 1},
                    "visual_concept": {"type": "string", "minLength": 1},
                },
            },
            "expected_viewer": {"type": "string", "minLength": 1},
            "awareness_level": {"type": "string", "minLength": 1},
            "viewer_problem": {"type": "string", "minLength": 1},
            "viewer_moment": {"type": "string", "minLength": 1},
            "desired_outcome": {"type": "string", "minLength": 1},
            "one_sentence_promise": {"type": "string", "minLength": 1},
            "gap_positioning": {"type": "string", "minLength": 1},
            "channel_fit_alignment": {"type": "string", "minLength": 1},
            "core_promise": {"type": "string", "minLength": 1},
            "curiosity_gap": {"type": "string", "minLength": 1},
            "expected_payoff": {"type": "string", "minLength": 1},
            "format_intent": {"type": "string", "enum": allowed_formats},
            "title_thumbnail_relationship": {"type": "string", "minLength": 1},
            "research_dependencies": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
            },
        },
    }
    rework_package_id = str(request.get("human_rework_package_id") or "").strip()
    rework_mode = bool(request.get("human_rework_note") and rework_package_id)
    if rework_mode:
        package_schema["properties"]["package_id"] = {
            "type": "string",
            "const": rework_package_id,
        }

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["concept_id", "packages"],
        "properties": {
            "concept_id": {"type": "string", "const": concept_id},
            "packages": {
                "type": "array",
                "minItems": 1,
                "maxItems": (
                    1
                    if rework_mode
                    else int(request.get("package_count_requested", 5))
                ),
                "items": package_schema,
            },
        },
    }


def build_prompt(request: dict[str, Any], *, maximum_chars: int) -> str:
    prompt = (
        "You are generating original YouTube packaging candidates for a human-accepted "
        "concept. Return JSON only.\n\n"
        "Rules:\n"
        "1. Preserve the accepted concept, viewer problem, viewer moment, and desired outcome.\n"
        "2. Treat title and thumbnail as one communication unit; they should complement, not repeat.\n"
        "3. Every package must make one honest promise and define the payoff the video must deliver.\n"
        "4. Do not invent facts, evidence, urgency, controversy, or certainty.\n"
        "5. Do not upgrade HYPOTHESIS or UNASSESSED content-gap evidence into a proven fact.\n"
        "6. Preserve channel fit; do not chase unrelated clicks.\n"
        "7. Do not predict CTR, views, virality, retention, or recommendation performance.\n"
        "8. List any factual or evidentiary dependency that Research must verify before scripting.\n"
        "9. Do not rank or score package options.\n"
        "10. The future script must be capable of fully delivering the package promise.\n"
        "11. If human_rework_note is present, it is an AUTHORITATIVE human directive, not a suggestion. Apply it literally unless it conflicts with factual or safety constraints. Do not silently substitute a narrower, broader, or different audience than the human requested.\n"
        "12. In human rework mode, return exactly one revised package and keep its package_id exactly equal to human_rework_package_id. The runner will preserve all other package options unchanged.\n"
        "13. Use human_rework_original_package as the before-version. Criteria listed in human_rework_keep_criteria should stay aligned; criteria listed in human_rework_change_criteria must be corrected.\n\n"
        "PACKAGE REQUEST:\n"
        + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt) > maximum_chars:
        raise ValueError(
            f"Packaging prompt is {len(prompt):,} characters; configured maximum "
            f"is {maximum_chars:,}."
        )
    return prompt


def _merge_human_rework_response(
    request: dict[str, Any],
    response: dict[str, Any],
) -> dict[str, Any]:
    note = str(request.get("human_rework_note") or "").strip()
    target = str(request.get("human_rework_package_id") or "").strip()
    if not note or not target:
        return response

    generated = response.get("packages")
    if not isinstance(generated, list) or len(generated) != 1:
        raise ValueError("Human rework must return exactly one revised package")
    replacement = generated[0]
    if (
        not isinstance(replacement, dict)
        or str(replacement.get("package_id") or "") != target
    ):
        raise ValueError("Human rework package_id must match the reviewed package")

    originals = request.get("human_rework_original_packages")
    if not isinstance(originals, list) or not originals:
        raise ValueError("Human rework is missing the original package set")

    merged: list[dict[str, Any]] = []
    replaced = False
    for item in originals:
        if not isinstance(item, dict):
            continue
        if str(item.get("package_id") or "") == target:
            merged.append(replacement)
            replaced = True
        else:
            merged.append(item)

    if not replaced:
        raise ValueError("Human rework target is absent from original package set")
    return {
        "concept_id": str(response.get("concept_id") or request.get("concept_id") or ""),
        "packages": merged,
    }


def run_one(
    request_path: Path,
    *,
    force: bool,
    runner_config: dict[str, Any],
) -> dict[str, Any]:
    request_path = request_path.resolve()
    request = load_json(request_path)
    concept_id = str(request.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Package request requires concept_id")

    request_hash = sha256_file(request_path)
    slug = safe_slug(concept_id)
    report_path = MODEL_RUNS_DIR / f"{slug}.model_run.json"
    response_path = RESPONSES_DIR / f"{slug}.json"

    if report_path.exists() and response_path.exists() and not force:
        existing = tolerant_load_json(report_path) or {}
        response = load_json(response_path)
        provenance = response.get("response_provenance", {})
        if (
            existing.get("status") == "VALIDATED"
            and existing.get("request_sha256") == request_hash
            and isinstance(provenance, dict)
            and provenance.get("request_sha256") == request_hash
        ):
            return {
                "status": "SKIPPED_ALREADY_VALIDATED",
                "concept_id": concept_id,
                "report": str(report_path),
            }

    prompt = build_prompt(
        request,
        maximum_chars=int(runner_config["runner"].get("max_prompt_chars", 95000)),
    )
    schema = response_schema(request)
    schema_chars = len(json.dumps(schema, separators=(",", ":")))
    if schema_chars > 19000:
        raise ValueError(
            f"Generated package schema is {schema_chars:,} characters; "
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
    payload["settings"]["client_id"] = "youtube-packaging"

    MODEL_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)

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
            "concept_id": concept_id,
            "status": "RUNNER_ERROR",
            "error_type": type(exc).__name__,
            "request_source": str(request_path),
            "request_sha256": request_hash,
        }
        atomic_write_json(report_path, report)
        return report

    if not inference_cost_authorized(bridge_result):
        report = {
            "concept_id": concept_id,
            "status": "COST_POLICY_VIOLATION",
            "request_source": str(request_path),
            "request_sha256": request_hash,
            "fair_status": bridge_result.get("status"),
        }
        atomic_write_json(report_path, report)
        return report

    base_report = {
        "concept_id": concept_id,
        "request_source": str(request_path),
        "request_sha256": request_hash,
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
    raw_path = RAW_OUTPUTS_DIR / f"{slug}.txt"
    atomic_write_text(raw_path, raw_output)

    try:
        response = parse_model_json(raw_output)
        config = load_config()
        validation = validate_response(response, request, config)
        if request.get("human_rework_note"):
            if not validation["accepted"]:
                raise ValueError("Human rework produced no structurally accepted package")
            response = _merge_human_rework_response(request, response)
            validation = validate_response(response, request, config)
    except Exception as exc:
        report = {
            **base_report,
            "status": "MODEL_OUTPUT_VALIDATION_ERROR",
            "error_type": type(exc).__name__,
            "raw_output": str(raw_path),
        }
        atomic_write_json(report_path, report)
        return report

    response["response_provenance"] = {
        "request_source": str(request_path),
        "request_sha256": request_hash,
        "provider_id": bridge_result.get("provider_id"),
        "model_id": bridge_result.get("model_id"),
    }
    atomic_write_json(response_path, response)

    validated_report: dict[str, Any] = {
        **base_report,
        "status": "VALIDATED",
        "model_response": str(response_path),
        "raw_output": str(raw_path),
        "structurally_accepted": len(validation["accepted"]),
        "structurally_rejected": len(validation["rejected"]),
    }
    atomic_write_json(report_path, validated_report)
    return validated_report


def run_batch(
    requests_dir: Path,
    *,
    force: bool,
    maximum_requests: int | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    paths = sorted(requests_dir.glob("*.package_request.json"))
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
        result = run_one(request_path, force=force, runner_config=config)
        results.append(result)
        if result.get("status") != "SKIPPED_ALREADY_VALIDATED":
            invoked += 1
        if result.get("status") in {
            "COST_POLICY_VIOLATION",
            "RUNNER_ERROR",
            "MODEL_FAILED",
        }:
            break

    merge_summary = run_apply()
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
        "merge": merge_summary,
    }
    atomic_write_json(BATCH_SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="FAIR-backed Packaging Engine runner")
    parser.add_argument("--mode", choices=("run", "batch"), required=True)
    parser.add_argument("--request", type=Path, default=None)
    parser.add_argument("--requests-dir", type=Path, default=REQUESTS_DIR)
    parser.add_argument("--max-requests", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    config = load_runner_config()
    if args.mode == "run":
        if args.request is None:
            raise SystemExit("--request is required for run mode")
        result = run_one(args.request, force=args.force, runner_config=config)
    else:
        result = run_batch(
            args.requests_dir.resolve(),
            force=args.force,
            maximum_requests=args.max_requests,
            config=config,
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.mode == "batch":
        raise SystemExit(exit_code_for_status(result["status"]))


if __name__ == "__main__":
    main()
