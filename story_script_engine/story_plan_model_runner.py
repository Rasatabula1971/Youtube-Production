"""FAIR-backed Story Plan model runner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_INTEGRITY_ROOT = Path(__file__).resolve().parent.parent
if str(_INTEGRITY_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEGRITY_ROOT))

from pipeline_integrity import (
    SUCCESS_STATUSES,
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
from story_plan_engine import (
    STORY_PLAN_REQUESTS_DIR,
    STORY_PLAN_RESPONSES_DIR,
    STORY_PLANS_DIR,
    validate_story_plan_response,
    validation_contract_sha256,
)
from story_script_engine import (
    OUTPUT_DIR,
    load_json,
    safe_slug,
    sha256_file,
)

MODEL_RUNS_DIR = OUTPUT_DIR / "story_plan_model_runs"
RAW_OUTPUTS_DIR = OUTPUT_DIR / "raw_story_plan_outputs"
BATCH_SUMMARY_FILE = OUTPUT_DIR / "story_plan_model_batch_summary.json"


def response_schema(request: dict[str, Any]) -> dict[str, Any]:
    allowed_claims = list(request.get("accepted_claim_ids", []))
    approved_title = str(request.get("package", {}).get("title") or "")
    psychology_contract = request.get("psychology_contract", {})
    opening_line = (
        psychology_contract.get("opening_line", {})
        if isinstance(psychology_contract, dict)
        else {}
    )
    hook_mechanisms = list(opening_line.get("allowed_mechanisms", []))
    beat_mechanisms = list(
        psychology_contract.get("beat_mechanisms", [])
        if isinstance(psychology_contract, dict)
        else []
    )
    loop_actions = list(
        psychology_contract.get("loop_actions", [])
        if isinstance(psychology_contract, dict)
        else []
    )
    tension_levels = list(
        psychology_contract.get("tension_levels", [])
        if isinstance(psychology_contract, dict)
        else []
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "concept_id",
            "title",
            "story_question",
            "opening_hook_intent",
            "viewer_state",
            "opening_psychology",
            "beats",
            "payoff_intent",
            "closing_intent",
        ],
        "properties": {
            "concept_id": {
                "type": "string",
                "const": str(request.get("concept_id", "")),
            },
            "title": {"type": "string", "const": approved_title},
            "story_question": {"type": "string", "minLength": 1},
            "opening_hook_intent": {"type": "string", "minLength": 1},
            "viewer_state": {
                "type": "object",
                "additionalProperties": False,
                "required": ["awareness", "expectation", "desired_resolution"],
                "properties": {
                    "awareness": {"type": "string", "minLength": 1},
                    "expectation": {"type": "string", "minLength": 1},
                    "desired_resolution": {"type": "string", "minLength": 1},
                },
            },
            "opening_psychology": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "mechanism",
                    "impact_intent",
                    "justification_intent",
                    "claim_ids",
                ],
                "properties": {
                    "mechanism": {"type": "string", "enum": hook_mechanisms},
                    "impact_intent": {"type": "string", "minLength": 1},
                    "justification_intent": {"type": "string", "minLength": 1},
                    "claim_ids": {
                        "type": "array",
                        "items": {"type": "string", "enum": allowed_claims},
                        "uniqueItems": True,
                    },
                },
            },
            "beats": {
                "type": "array",
                "minItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "beat_id",
                        "role",
                        "purpose",
                        "viewer_progress",
                        "claim_ids",
                        "transition_intent",
                        "psychology",
                    ],
                    "properties": {
                        "beat_id": {"type": "string", "minLength": 1},
                        "role": {
                            "type": "string",
                            "enum": [
                                "SETUP",
                                "ESCALATION",
                                "EXPLANATION",
                                "REVEAL",
                                "PAYOFF",
                            ],
                        },
                        "purpose": {"type": "string", "minLength": 1},
                        "viewer_progress": {"type": "string", "minLength": 1},
                        "claim_ids": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": allowed_claims,
                            },
                            "uniqueItems": True,
                        },
                        "transition_intent": {
                            "type": "string",
                            "minLength": 1,
                        },
                        "psychology": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "primary_mechanism",
                                "viewer_expectation",
                                "cognitive_load_instruction",
                                "tension_level",
                                "open_loop_id",
                                "loop_action",
                            ],
                            "properties": {
                                "primary_mechanism": {
                                    "type": "string",
                                    "enum": beat_mechanisms,
                                },
                                "viewer_expectation": {
                                    "type": "string",
                                    "minLength": 1,
                                },
                                "cognitive_load_instruction": {
                                    "type": "string",
                                    "minLength": 1,
                                },
                                "tension_level": {
                                    "type": "string",
                                    "enum": tension_levels,
                                },
                                "open_loop_id": {
                                    "type": ["string", "null"],
                                },
                                "loop_action": {
                                    "type": "string",
                                    "enum": loop_actions,
                                },
                            },
                        },
                    },
                },
            },
            "payoff_intent": {"type": "string", "minLength": 1},
            "closing_intent": {"type": "string", "minLength": 1},
        },
    }


def build_prompt(request: dict[str, Any], maximum_chars: int) -> str:
    prompt = (
        "You are planning the story structure for an original YouTube video. "
        "Do NOT write the final narration. Return JSON only.\n\n"
        "Rules:\n"
        "1. The approved Packaging title is immutable. Return it exactly.\n"
        "2. Decide the viewer journey before wording: high-impact hook, setup, escalation/explanation, reveal, payoff, close.\n"
        "3. Model the viewer state explicitly: what they already know, what they expect, and what they want resolved.\n"
        "4. Plan a high-impact FIRST SPOKEN LINE using one allowed opening mechanism. Bold is good; unsupported drama is not.\n"
        "5. The material immediately after the hook must justify, contextualize, or begin proving the hook.\n"
        "6. Assign one primary audience-psychology mechanism to every beat and make each beat change the viewer's state.\n"
        "7. Manage cognitive load deliberately. Prefer one primary new idea per beat when the explanation is complex.\n"
        "8. Track open loops with open_loop_id and loop_action. Every OPEN must later receive a PAYOFF; never create a fake unresolved hook.\n"
        "9. Use tension, novelty and expectation violation only when they serve the verified story and approved promise.\n"
        "10. Use only accepted_claim_ids for factual beats and factual opening claims.\n"
        "11. Do not invent facts or copy source-video wording, sequence, personality, or exact execution.\n"
        "12. At least one beat must be PAYOFF.\n"
        "13. Keep this as a structural plan: no polished narration paragraphs and no arbitrary fixed timing rules.\n\n"
        "STORY PLAN REQUEST:\n"
        + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt) > maximum_chars:
        raise ValueError("Story Plan prompt exceeds configured maximum")
    return prompt


def run_one(path: Path, force: bool, config: dict[str, Any]) -> dict[str, Any]:
    path = path.resolve()
    request = load_json(path)
    concept_id = str(request.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Story Plan request requires concept_id")

    slug = safe_slug(concept_id)
    request_hash = sha256_file(path)
    validation_contract = validation_contract_sha256()
    report_path = MODEL_RUNS_DIR / f"{slug}.model_run.json"
    response_path = STORY_PLAN_RESPONSES_DIR / f"{slug}.json"
    plan_path = STORY_PLANS_DIR / f"{slug}.story_plan.json"

    if report_path.exists() and plan_path.exists() and not force:
        existing = tolerant_load_json(report_path) or {}
        plan = tolerant_load_json(plan_path) or {}
        provenance = plan.get("plan_provenance", {})
        if (
            existing.get("status") == "VALIDATED"
            and existing.get("validation_contract_sha256")
            == validation_contract
            and isinstance(provenance, dict)
            and provenance.get("request_sha256") == request_hash
            and provenance.get("validation_contract_sha256")
            == validation_contract
        ):
            return {
                "status": "SKIPPED_ALREADY_VALIDATED",
                "concept_id": concept_id,
                "report": str(report_path),
            }

    prompt = build_prompt(
        request,
        int(config["runner"].get("max_prompt_chars", 95000)),
    )
    schema = response_schema(request)
    paths = resolve_fair_paths(config)
    payload = bridge_payload(
        action="solve",
        prompt=prompt,
        schema=schema,
        config=config,
        paths=paths,
    )
    payload["settings"]["client_id"] = "youtube-story-plan"

    for directory in (
        MODEL_RUNS_DIR,
        RAW_OUTPUTS_DIR,
        STORY_PLAN_RESPONSES_DIR,
        STORY_PLANS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    try:
        result = call_fair_bridge(
            payload,
            python_executable=paths["python"],
            timeout_seconds=float(
                config["runner"].get("subprocess_timeout_seconds", 300)
            ),
        )
    except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
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
        "validation_contract_sha256": validation_contract,
        "fair_request_id": result.get("request_id"),
        "fair_status": result.get("status"),
        "fair_reason_code": result.get("reason_code"),
        "provider_id": result.get("provider_id"),
        "model_id": result.get("model_id"),
        "best_quality_score": result.get("best_quality_score"),
        "verification_state": result.get("verification_state"),
        "paid_inference_executed": result.get("paid_inference_executed"),
        "direct_backup_used": result.get("direct_backup_used", False),
        "direct_backup_may_bill": result.get("direct_backup_may_bill", False),
        "billing_authorization": result.get("billing_authorization"),
        "attempts": safe_attempts(result),
    }

    if not inference_cost_authorized(result):
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
        validation = validate_story_plan_response(response, request)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
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
        "validation_contract_sha256": validation_contract,
        "provider_id": result.get("provider_id"),
        "model_id": result.get("model_id"),
    }
    atomic_write_json(response_path, response)

    plan = {
        "artifact": "story_plan",
        "status": "STORY_PLAN_READY",
        **response,
        "package": request.get("package", {}),
        "concept": request.get("concept", {}),
        "accepted_claims": request.get("accepted_claims", []),
        "accepted_claim_ids": request.get("accepted_claim_ids", []),
        "validation": validation,
        "plan_provenance": response["response_provenance"],
    }
    atomic_write_json(plan_path, plan)

    report = {
        **base,
        "status": "VALIDATED",
        "story_plan": str(plan_path),
        "claim_usage": validation["claim_usage"],
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
    paths = sorted(requests_dir.glob("*.story_plan_request.json"))
    limit = int(
        maximum
        if maximum is not None
        else config["runner"].get("max_requests_per_batch", 4)
    )
    results: list[dict[str, Any]] = []
    invoked = 0
    for path in paths:
        if invoked >= limit:
            break
        try:
            item = run_one(path, force, config)
        except (OSError, RuntimeError, ValueError, TypeError, TimeoutError) as exc:
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
        results,
        expected_count=len(paths),
        processed_count=len(results),
    )
    if (
        len(results) < len(paths)
        and invoked >= limit
        and results
        and all(str(item.get("status") or "") in SUCCESS_STATUSES for item in results)
    ):
        status = "BATCH_PROGRESS"
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
    parser = argparse.ArgumentParser(description="FAIR-backed Story Plan runner")
    parser.add_argument("--mode", choices=("run", "batch"), required=True)
    parser.add_argument("--request", type=Path)
    parser.add_argument(
        "--requests-dir",
        type=Path,
        default=STORY_PLAN_REQUESTS_DIR,
    )
    parser.add_argument("--max-requests", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    config = load_runner_config()
    result = (
        run_one(args.request, args.force, config)
        if args.mode == "run" and args.request
        else run_batch(
            args.requests_dir.resolve(),
            args.force,
            args.max_requests,
            config,
        )
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.mode == "batch":
        if result["status"] == "BATCH_PROGRESS":
            raise SystemExit(0)
        raise SystemExit(exit_code_for_status(result["status"]))


if __name__ == "__main__":
    main()
