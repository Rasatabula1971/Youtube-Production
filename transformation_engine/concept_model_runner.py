"""FAIR-backed Transformation Engine concept runner.

Prepared concept requests are sent through the existing FAIR subprocess bridge.
The runner is free-only, validates model output through transformation_engine,
and writes only request-bound responses for the deterministic merge step.
"""

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
from evidence_ingest import sha256_file

from transformation_engine import (
    OUTPUT_DIR,
    REQUESTS_DIR,
    RESPONSES_DIR,
    load_config,
    load_json,
    run_apply,
    safe_slug,
    validate_response,
)

MODEL_RUNS_DIR = OUTPUT_DIR / "concept_model_runs"
RAW_OUTPUTS_DIR = OUTPUT_DIR / "raw_concept_outputs"
BATCH_SUMMARY_FILE = OUTPUT_DIR / "concept_model_batch_summary.json"


def response_schema(request: dict[str, Any]) -> dict[str, Any]:
    mechanism_id = str(request.get("mechanism_id", ""))
    allowed_formats = list(request.get("allowed_format_intents", []))

    concept_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "concept_id",
            "working_title",
            "premise",
            "audience_promise",
            "viewer_problem",
            "viewer_moment",
            "desired_outcome",
            "content_gap",
            "channel_fit",
            "title_clarity_test",
            "format_intent",
            "mechanism_application",
            "transformation_method",
            "research_questions",
            "source_specific_elements_used",
            "source_dependency_test",
        ],
        "properties": {
            "concept_id": {"type": "string", "minLength": 1},
            "working_title": {"type": "string", "minLength": 1},
            "premise": {"type": "string", "minLength": 1},
            "audience_promise": {"type": "string", "minLength": 1},
            "viewer_problem": {"type": "string", "minLength": 1},
            "viewer_moment": {"type": "string", "minLength": 1},
            "desired_outcome": {"type": "string", "minLength": 1},
            "content_gap": {
                "type": "object",
                "additionalProperties": False,
                "required": ["hypothesis", "evidence_status", "evidence_basis"],
                "properties": {
                    "hypothesis": {"type": "string", "minLength": 1},
                    "evidence_status": {
                        "type": "string",
                        "enum": ["SUPPORTED", "HYPOTHESIS", "UNASSESSED"],
                    },
                    "evidence_basis": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            "channel_fit": {
                "type": "object",
                "additionalProperties": False,
                "required": ["status", "rationale"],
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["FIT", "REVIEW", "UNASSESSED"],
                    },
                    "rationale": {"type": "string", "minLength": 1},
                },
            },
            "title_clarity_test": {
                "type": "object",
                "additionalProperties": False,
                "required": ["options", "result", "rationale"],
                "properties": {
                    "options": {
                        "type": "array",
                        "minItems": 3,
                        "items": {"type": "string", "minLength": 1},
                    },
                    "result": {
                        "type": "string",
                        "enum": ["PASS", "REFRAME"],
                    },
                    "rationale": {"type": "string", "minLength": 1},
                },
            },
            "format_intent": {
                "type": "string",
                "enum": allowed_formats,
            },
            "mechanism_application": {"type": "string", "minLength": 1},
            "transformation_method": {"type": "string", "minLength": 1},
            "research_questions": {
                "type": "array",
                "minItems": 2,
                "items": {"type": "string", "minLength": 1},
            },
            "source_specific_elements_used": {
                "type": "array",
                "maxItems": 0,
                "items": {"type": "string"},
            },
            "source_dependency_test": {
                "type": "object",
                "additionalProperties": False,
                "required": ["passes", "source_assets_required", "rationale"],
                "properties": {
                    "passes": {"const": True},
                    "source_assets_required": {"const": False},
                    "rationale": {"type": "string", "minLength": 1},
                },
            },
        },
    }

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["mechanism_id", "concepts"],
        "properties": {
            "mechanism_id": {
                "type": "string",
                "const": mechanism_id,
            },
            "concepts": {
                "type": "array",
                "minItems": 1,
                "maxItems": int(request.get("concept_count_requested", 5)),
                "items": concept_schema,
            },
        },
    }


def build_prompt(request: dict[str, Any], *, maximum_chars: int) -> str:
    prompt = (
        "You are generating original YouTube concept candidates from a validated "
        "transferable mechanism. Return JSON only.\n\n"
        "Rules:\n"
        "1. Generate new premises, not rewrites of the source videos.\n"
        "2. Do not reuse source titles, scripts, footage, story sequences, exact "
        "examples, personalities, or source video IDs.\n"
        "3. Treat observed examples as evidence about a mechanism, not material to copy.\n"
        "4. Every concept must identify a specific viewer problem, viewer moment, "
        "desired outcome, and an honest content-gap evidence state.\n"
        "5. Do not invent evidence for a content gap. If not proven, use HYPOTHESIS "
        "or UNASSESSED.\n"
        "6. Do not predict views, virality, CTR, retention, or recommendation.\n"
        "7. Channel fit may be REVIEW or UNASSESSED when it cannot be defended.\n"
        "8. Provide at least three clear working-title options as an idea clarity test.\n"
        "9. Include at least two independent research questions before scripting.\n"
        "10. The Source Dependency Test must pass: the concept must keep its main "
        "value without source wording, footage, story, personality, or exact execution.\n"
        "11. Do not rank or score concepts.\n\n"
        "CONCEPT REQUEST:\n"
        + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt) > maximum_chars:
        raise ValueError(
            f"Concept prompt is {len(prompt):,} characters; configured maximum "
            f"is {maximum_chars:,}."
        )
    return prompt


def run_one(
    request_path: Path,
    *,
    force: bool,
    runner_config: dict[str, Any],
) -> dict[str, Any]:
    request_path = request_path.resolve()
    request = load_json(request_path)
    mechanism_id = str(request.get("mechanism_id", "")).strip()
    if not mechanism_id:
        raise ValueError("Concept request requires mechanism_id")

    request_hash = sha256_file(request_path)
    slug = safe_slug(mechanism_id)
    report_path = MODEL_RUNS_DIR / f"{slug}.model_run.json"
    response_path = RESPONSES_DIR / f"{slug}.json"

    if report_path.exists() and response_path.exists() and not force:
        existing = load_json(report_path)
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
                "mechanism_id": mechanism_id,
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
            f"Generated concept schema is {schema_chars:,} characters; "
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
    payload["settings"]["client_id"] = "youtube-transformation-concepts"

    MODEL_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)

    try:
        bridge_result = call_fair_bridge(
            payload,
            python_executable=paths["python"],
            timeout_seconds=float(
                runner_config["runner"].get(
                    "subprocess_timeout_seconds",
                    300,
                )
            ),
        )
    except Exception as exc:
        report = {
            "mechanism_id": mechanism_id,
            "status": "RUNNER_ERROR",
            "error_type": type(exc).__name__,
            "request_source": str(request_path),
            "request_sha256": request_hash,
        }
        atomic_write_json(report_path, report)
        return report

    if bridge_result.get("paid_inference_executed") is not False:
        report = {
            "mechanism_id": mechanism_id,
            "status": "COST_POLICY_VIOLATION",
            "request_source": str(request_path),
            "request_sha256": request_hash,
            "fair_status": bridge_result.get("status"),
        }
        atomic_write_json(report_path, report)
        return report

    base_report = {
        "mechanism_id": mechanism_id,
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
        validation = validate_response(
            response,
            request,
            load_config(),
        )
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

    report = {
        **base_report,
        "status": "VALIDATED",
        "model_response": str(response_path),
        "raw_output": str(raw_path),
        "structurally_accepted": len(validation["accepted"]),
        "structurally_rejected": len(validation["rejected"]),
    }
    atomic_write_json(report_path, report)
    return report


def run_batch(
    requests_dir: Path,
    *,
    force: bool,
    maximum_requests: int | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    paths = sorted(requests_dir.glob("*.concept_request.json"))
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
            force=force,
            runner_config=config,
        )
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
    parser = argparse.ArgumentParser(
        description="FAIR-backed Transformation Engine concept runner"
    )
    parser.add_argument(
        "--mode",
        choices=("run", "batch"),
        required=True,
    )
    parser.add_argument("--request", type=Path, default=None)
    parser.add_argument("--requests-dir", type=Path, default=REQUESTS_DIR)
    parser.add_argument("--max-requests", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    config = load_runner_config()

    if args.mode == "run":
        if args.request is None:
            raise SystemExit("--request is required for run mode")
        result = run_one(
            args.request,
            force=args.force,
            runner_config=config,
        )
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
