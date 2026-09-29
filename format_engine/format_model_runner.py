"""FAIR-backed Format Engine model runner."""

from __future__ import annotations

import argparse
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
    load_runner_config,
    parse_model_json,
    resolve_fair_paths,
    safe_attempts,
)

from format_engine import (
    OUTPUT_DIR,
    PLANS_DIR,
    REQUESTS_DIR,
    RESPONSES_DIR,
    load_json,
    safe_slug,
    sha256_file,
    validate_format_response,
)

MODEL_RUNS_DIR = OUTPUT_DIR / "format_model_runs"
RAW_OUTPUTS_DIR = OUTPUT_DIR / "raw_format_outputs"
BATCH_SUMMARY_FILE = OUTPUT_DIR / "format_model_batch_summary.json"


def response_schema(request: dict[str, Any]) -> dict[str, Any]:
    allowed_claims = list(request.get("accepted_claim_ids", []))
    allowed_sections = list(request.get("script_section_ids", []))
    branches = list(request.get("required_branches", []))
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["concept_id", "branches"],
        "properties": {
            "concept_id": {
                "type": "string",
                "const": str(request.get("concept_id", "")),
            },
            "branches": {
                "type": "array",
                "minItems": len(branches) or 1,
                "maxItems": len(branches) or 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "format",
                        "duration_intent_seconds",
                        "promise_delivery",
                        "payoff",
                        "beats",
                    ],
                    "properties": {
                        "format": {"type": "string", "enum": branches},
                        "duration_intent_seconds": {"type": "integer", "minimum": 1},
                        "promise_delivery": {"type": "string", "minLength": 1},
                        "payoff": {"type": "string", "minLength": 1},
                        "beats": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": [
                                    "beat_id",
                                    "purpose",
                                    "treatment",
                                    "claim_ids",
                                    "source_section_ids",
                                ],
                                "properties": {
                                    "beat_id": {"type": "string", "minLength": 1},
                                    "purpose": {"type": "string", "minLength": 1},
                                    "treatment": {"type": "string", "minLength": 1},
                                    "claim_ids": {
                                        "type": "array",
                                        "items": {
                                            "type": "string",
                                            "enum": allowed_claims,
                                        },
                                        "uniqueItems": True,
                                    },
                                    "source_section_ids": {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {
                                            "type": "string",
                                            "enum": allowed_sections,
                                        },
                                        "uniqueItems": True,
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    }


def build_prompt(request: dict[str, Any], maximum_chars: int) -> str:
    branches = ", ".join(request.get("required_branches", []))
    prompt = (
        "You are planning production branches for an approved YouTube script. "
        "Return JSON only.\n\n"
        f"Required branches: {branches}\n\n"
        "Rules:\n"
        "1. Plan every required branch, and only the required branches.\n"
        "2. Branches share research and accepted facts but are separate "
        "productions. Never submit one timeline re-cut or truncated.\n"
        "3. Each branch delivers the approved package promise in its own shape.\n"
        "4. Attach accepted claim_ids to every beat carrying factual material.\n"
        "5. Never introduce facts outside accepted_claims.\n"
        "6. Trace every beat to the approved script sections it is built from.\n"
        "7. Respect each branch's duration and beat-count constraints.\n"
        "8. Do not copy source-video wording, footage, story beats or execution.\n"
        "9. Do not mention claim IDs in on-screen or spoken text.\n\n"
        "FORMAT REQUEST:\n"
        + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt) > maximum_chars:
        raise ValueError("Format prompt exceeds configured maximum")
    return prompt


def run_one(path: Path, force: bool, config: dict[str, Any]) -> dict[str, Any]:
    path = path.resolve()
    request = load_json(path)
    concept_id = str(request.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Format request requires concept_id")

    slug = safe_slug(concept_id)
    request_hash = sha256_file(path)
    report_path = MODEL_RUNS_DIR / f"{slug}.model_run.json"
    response_path = RESPONSES_DIR / f"{slug}.json"
    plan_path = PLANS_DIR / f"{slug}.format_plan.json"

    if report_path.exists() and plan_path.exists() and not force:
        existing = tolerant_load_json(report_path) or {}
        plan = tolerant_load_json(plan_path) or {}
        provenance = plan.get("plan_provenance", {})
        if (
            existing.get("status") == "VALIDATED"
            and isinstance(provenance, dict)
            and provenance.get("request_sha256") == request_hash
            and plan.get("master_story_package") == request.get("master_story_package")
            and plan.get("script_section_ids") == request.get("script_section_ids")
        ):
            return {
                "status": "SKIPPED_ALREADY_VALIDATED",
                "concept_id": concept_id,
                "report": str(report_path),
            }

    prompt = build_prompt(request, int(config["runner"].get("max_prompt_chars", 95000)))
    schema = response_schema(request)
    paths = resolve_fair_paths(config)
    payload = bridge_payload(
        action="solve",
        prompt=prompt,
        schema=schema,
        config=config,
        paths=paths,
    )
    payload["settings"]["client_id"] = "youtube-format"

    for directory in (MODEL_RUNS_DIR, RAW_OUTPUTS_DIR, RESPONSES_DIR, PLANS_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    try:
        result = call_fair_bridge(
            payload,
            python_executable=paths["python"],
            timeout_seconds=float(
                config["runner"].get("subprocess_timeout_seconds", 300)
            ),
        )
    except Exception as exc:
        report = {
            "concept_id": concept_id,
            "request_source": str(path),
            "request_sha256": request_hash,
            "status": "RUNNER_ERROR",
            "error_type": type(exc).__name__,
        }
        atomic_write_json(report_path, report)
        return report

    base = {
        "concept_id": concept_id,
        "request_source": str(path),
        "request_sha256": request_hash,
        "fair_request_id": result.get("request_id"),
        "fair_status": result.get("status"),
        "fair_reason_code": result.get("reason_code"),
        "provider_id": result.get("provider_id"),
        "model_id": result.get("model_id"),
        "best_quality_score": result.get("best_quality_score"),
        "verification_state": result.get("verification_state"),
        "paid_inference_executed": result.get("paid_inference_executed"),
        "attempts": safe_attempts(result),
    }

    if result.get("paid_inference_executed") is not False:
        report = {**base, "status": "COST_POLICY_VIOLATION"}
        atomic_write_json(report_path, report)
        return report

    if result.get("status") != "ACCEPTED":
        report = {
            **base,
            "status": (
                "MODEL_ESCALATION_REQUIRED"
                if result.get("status") == "ESCALATION_REQUIRED"
                else "MODEL_FAILED"
            ),
        }
        atomic_write_json(report_path, report)
        return report

    raw = str(result.get("output") or "")
    raw_path = RAW_OUTPUTS_DIR / f"{slug}.txt"
    atomic_write_text(raw_path, raw)

    try:
        response = parse_model_json(raw)
        validation = validate_format_response(response, request)
    except Exception as exc:
        report = {
            **base,
            "status": "MODEL_OUTPUT_VALIDATION_ERROR",
            "error_type": type(exc).__name__,
            "message": str(exc)[:1000],
            "raw_output": str(raw_path),
        }
        atomic_write_json(report_path, report)
        return report

    if not validation["valid"]:
        report = {
            **base,
            "status": "MODEL_OUTPUT_VALIDATION_ERROR",
            "errors": validation["errors"],
            "raw_output": str(raw_path),
        }
        atomic_write_json(report_path, report)
        return report

    response["response_provenance"] = {
        "request_source": str(path),
        "request_sha256": request_hash,
        "provider_id": result.get("provider_id"),
        "model_id": result.get("model_id"),
    }
    atomic_write_json(response_path, response)

    plan = {
        **response,
        "format_intent": request.get("format_intent"),
        "required_branches": request.get("required_branches", []),
        "branch_constraints": request.get("branch_constraints", {}),
        "package": request.get("package", {}),
        "master_story_package": request.get("master_story_package", {}),
        "script_section_ids": request.get("script_section_ids", []),
        "accepted_claims": request.get("accepted_claims", []),
        "validation": validation,
        "plan_provenance": response["response_provenance"],
    }
    atomic_write_json(plan_path, plan)

    report = {
        **base,
        "status": "VALIDATED",
        "format_plan": str(plan_path),
        "claim_usage_by_branch": validation["claim_usage_by_branch"],
        "unused_accepted_claim_ids": validation["unused_accepted_claim_ids"],
    }
    atomic_write_json(report_path, report)
    return report


def run_batch(
    requests_dir: Path,
    force: bool,
    maximum: int | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    paths = sorted(requests_dir.glob("*.format_request.json"))
    limit = int(
        maximum
        if maximum is not None
        else config["runner"].get("max_requests_per_batch", 4)
    )
    results = []
    invoked = 0
    for path in paths:
        if invoked >= limit:
            break
        try:
            item = run_one(path, force, config)
        except Exception as exc:
            item = {
                "status": "RUNNER_ERROR",
                "error_type": type(exc).__name__,
                "request_source": str(path),
            }
        results.append(item)
        if item.get("status") != "SKIPPED_ALREADY_VALIDATED":
            invoked += 1
        if item.get("status") in {
            "COST_POLICY_VIOLATION",
            "MODEL_FAILED",
            "RUNNER_ERROR",
        }:
            break
    status = batch_status(
        results, expected_count=len(paths), processed_count=len(results)
    )
    summary = {
        "status": status,
        "requests_found": len(paths),
        "model_runs_invoked": invoked,
        "batch_limit": limit,
        "results": results,
    }
    atomic_write_json(BATCH_SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="FAIR-backed Format Engine runner")
    parser.add_argument("--mode", choices=("run", "batch"), required=True)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--requests-dir", type=Path, default=REQUESTS_DIR)
    parser.add_argument("--max-requests", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    config = load_runner_config()
    result = (
        run_one(args.request, args.force, config)
        if args.mode == "run" and args.request
        else run_batch(
            args.requests_dir.resolve(), args.force, args.max_requests, config
        )
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.mode == "batch":
        raise SystemExit(exit_code_for_status(result["status"]))


if __name__ == "__main__":
    main()
