"""FAIR-backed Story / Script model runner."""

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

from story_script_engine import (
    DRAFTS_DIR,
    OUTPUT_DIR,
    REQUESTS_DIR,
    RESPONSES_DIR,
    load_json,
    safe_slug,
    sha256_file,
    validate_script_response,
    validation_contract_sha256,
)

MODEL_RUNS_DIR = OUTPUT_DIR / "script_model_runs"
RAW_OUTPUTS_DIR = OUTPUT_DIR / "raw_script_outputs"
BATCH_SUMMARY_FILE = OUTPUT_DIR / "script_model_batch_summary.json"


def response_schema(request: dict[str, Any]) -> dict[str, Any]:
    allowed = list(request.get("accepted_claim_ids", []))
    approved_title = str(request.get("package", {}).get("title") or "")
    story_plan = request.get("story_plan", {})
    beats = (
        story_plan.get("beats", [])
        if isinstance(story_plan, dict)
        else []
    )
    beat_ids = [
        str(beat.get("beat_id", ""))
        for beat in beats
        if isinstance(beat, dict) and str(beat.get("beat_id", "")).strip()
    ]
    opening_psychology = (
        story_plan.get("opening_psychology", {})
        if isinstance(story_plan, dict)
        else {}
    )
    planned_hook_mechanism = str(
        opening_psychology.get("mechanism", "")
        if isinstance(opening_psychology, dict)
        else ""
    )
    psychology_contract = request.get("psychology_contract", {})
    beat_mechanisms = list(
        psychology_contract.get("beat_mechanisms", [])
        if isinstance(psychology_contract, dict)
        else []
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "concept_id",
            "title",
            "opening_hook",
            "opening_hook_mechanism",
            "sections",
            "closing",
        ],
        "properties": {
            "concept_id": {
                "type": "string",
                "const": str(request.get("concept_id", "")),
            },
            "title": {"type": "string", "const": approved_title},
            "opening_hook": {"type": "string", "minLength": 1},
            "opening_hook_mechanism": {
                "type": "string",
                "const": planned_hook_mechanism,
            },
            "sections": {
                "type": "array",
                "minItems": len(beat_ids) if beat_ids else 1,
                **({"maxItems": len(beat_ids)} if beat_ids else {}),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "section_id",
                        "story_beat_id",
                        "purpose",
                        "psychology_mechanism",
                        "narration",
                        "claim_ids",
                    ],
                    "properties": {
                        "section_id": {"type": "string", "minLength": 1},
                        "story_beat_id": {
                            "type": "string",
                            "enum": beat_ids,
                        },
                        "purpose": {"type": "string", "minLength": 1},
                        "psychology_mechanism": {
                            "type": "string",
                            "enum": beat_mechanisms,
                        },
                        "narration": {"type": "string", "minLength": 1},
                        "claim_ids": {
                            "type": "array",
                            "items": {"type": "string", "enum": allowed},
                            "uniqueItems": True,
                        },
                    },
                },
            },
            "closing": {"type": "string", "minLength": 1},
        },
    }


def build_prompt(request: dict[str, Any], maximum_chars: int) -> str:
    prompt = (
        "You are writing the narration for an original YouTube video from an "
        "approved Story Plan and human-verified research. Return JSON only.\n\n"
        "Rules:\n"
        "1. Return the approved Packaging title EXACTLY. Do not rewrite, optimize, or replace it.\n"
        "2. Follow the supplied Story Plan in order. Do not invent a new story structure.\n"
        "3. The opening_hook is the FIRST SPOKEN LINE. It must be high-impact and use exactly the planned opening_psychology mechanism.\n"
        "4. High-impact means immediate contradiction, surprise, stakes, expectation violation, specific curiosity, or a bold specific promise as planned. Never manufacture drama or overstate the verified research.\n"
        "5. The narration immediately after the hook must justify, contextualize, or begin proving it. Avoid generic introductions and throat-clearing.\n"
        "6. Create exactly one script section for each Story Plan beat and map it with story_beat_id.\n"
        "7. Each section must carry exactly the claim_ids assigned to its Story Plan beat.\n"
        "8. Each section must report and preserve the beat's primary psychology_mechanism.\n"
        "9. Use only accepted_claims for factual assertions. Never invent a factual detail.\n"
        "10. Use the beat cognitive_load_instruction: explain one primary new idea at a time when complexity is high, and connect it to what the viewer now understands.\n"
        "11. Preserve OPEN, ADVANCE and PAYOFF behavior for planned open loops. Do not add fake unresolved loops.\n"
        "12. Original connective narration is allowed only when it does not add factual claims.\n"
        "13. Do not copy source-video wording, story sequence, personality, or exact execution.\n"
        "14. Do not mention claim IDs, psychology labels, or story beat IDs in spoken narration.\n"
        "15. Do not use arbitrary fixed hook-second or pattern-interrupt timing rules.\n"
        "16. Deliver the planned payoff and end concisely after the promise is satisfied.\n\n"
        "SCRIPT REQUEST:\n"
        + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt) > maximum_chars:
        raise ValueError("Script prompt exceeds configured maximum")
    return prompt


def run_one(
    path: Path,
    force: bool,
    config: dict[str, Any],
) -> dict[str, Any]:
    path = path.resolve()
    request = load_json(path)
    concept_id = str(request.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Script request requires concept_id")

    slug = safe_slug(concept_id)
    request_hash = sha256_file(path)
    validation_contract = validation_contract_sha256()
    report_path = MODEL_RUNS_DIR / f"{slug}.model_run.json"
    response_path = RESPONSES_DIR / f"{slug}.json"
    draft_path = DRAFTS_DIR / f"{slug}.script_draft.json"

    if report_path.exists() and draft_path.exists() and not force:
        existing = tolerant_load_json(report_path) or {}
        draft = tolerant_load_json(draft_path) or {}
        provenance = draft.get("draft_provenance", {})
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
    payload["settings"]["client_id"] = "youtube-story-script"

    for directory in (
        MODEL_RUNS_DIR,
        RAW_OUTPUTS_DIR,
        RESPONSES_DIR,
        DRAFTS_DIR,
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
        validation = validate_script_response(response, request)
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
        "validation_contract_sha256": validation_contract,
        "provider_id": result.get("provider_id"),
        "model_id": result.get("model_id"),
    }
    atomic_write_json(response_path, response)

    draft = {
        **response,
        "accepted_claims": request.get("accepted_claims", []),
        "package": request.get("package", {}),
        "story_plan": request.get("story_plan", {}),
        "psychology_contract": request.get("psychology_contract", {}),
        "validation": validation,
        "draft_provenance": response["response_provenance"],
    }
    atomic_write_json(draft_path, draft)

    report = {
        **base,
        "status": "VALIDATED",
        "script_draft": str(draft_path),
        "claim_usage": validation["claim_usage"],
        "unused_accepted_claim_ids": validation["unused_accepted_claim_ids"],
    }
    atomic_write_json(report_path, report)
    return report


def run_batch(
    requests_dir: Path, force: bool, maximum: int | None, config: dict[str, Any]
) -> dict[str, Any]:
    paths = sorted(requests_dir.glob("*.script_request.json"))
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
    p = argparse.ArgumentParser(description="FAIR-backed Story / Script runner")
    p.add_argument("--mode", choices=("run", "batch"), required=True)
    p.add_argument("--request", type=Path)
    p.add_argument("--requests-dir", type=Path, default=REQUESTS_DIR)
    p.add_argument("--max-requests", type=int)
    p.add_argument("--force", action="store_true")
    a = p.parse_args()
    config = load_runner_config()
    result = (
        run_one(a.request, a.force, config)
        if a.mode == "run" and a.request
        else run_batch(a.requests_dir.resolve(), a.force, a.max_requests, config)
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if a.mode == "batch":
        if result["status"] == "BATCH_PROGRESS":
            raise SystemExit(0)
        raise SystemExit(exit_code_for_status(result["status"]))


if __name__ == "__main__":
    main()
