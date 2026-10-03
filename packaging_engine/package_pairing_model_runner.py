"""FAIR-backed Slice 26 package pairing evaluator."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_EXP2 = _ROOT / "experiment_02_analysis"
if str(_EXP2) not in sys.path:
    sys.path.insert(0, str(_EXP2))

from pipeline_integrity import (
    atomic_write_json,
    atomic_write_text,
    batch_status,
    exit_code_for_status,
    tolerant_load_json,
)
from analysis_model_runner import (
    bridge_payload,
    call_fair_bridge,
    inference_cost_authorized,
    load_runner_config,
    parse_model_json,
    resolve_fair_paths,
    safe_attempts,
)
from package_pairing import (
    PACKAGE_VALIDATION_FILE,
    PROMPT_VERSION,
    REQUESTS_DIR,
    RESPONSES_DIR,
    SCHEMA_VERSION,
    load_json,
    request_is_current,
    run_apply,
    safe_slug,
    sha256_file,
    validate_response,
)

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"
MODEL_RUNS_DIR = OUTPUT_DIR / "package_pairing_model_runs"
RAW_OUTPUTS_DIR = OUTPUT_DIR / "raw_package_pairing_outputs"
BATCH_SUMMARY_FILE = OUTPUT_DIR / "package_pairing_model_batch_summary.json"


def response_schema(request: dict[str, Any]) -> dict[str, Any]:
    package_ids = [
        str(item.get("package_id"))
        for item in request.get("pair_candidates", [])
        if isinstance(item, dict) and str(item.get("package_id") or "").strip()
    ]
    refs = [
        str(item.get("claim_id"))
        for item in request.get("approved_claims", [])
        if isinstance(item, dict) and str(item.get("claim_id") or "").strip()
    ]
    hard_codes = [str(x) for x in request.get("hard_reject_codes", [])]
    rework_codes = [str(x) for x in request.get("rework_codes", [])]
    diagnostics = [str(x) for x in request.get("diagnostic_dimensions", [])]

    finding = lambda codes: {
        "type": "object",
        "additionalProperties": False,
        "required": ["code", "reason", "evidence_refs"],
        "properties": {
            "code": {"type": "string", "enum": codes},
            "reason": {"type": "string", "minLength": 1},
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string", "enum": refs},
                "uniqueItems": True,
            },
        },
    }
    claim_validation = {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "reason", "evidence_refs"],
        "properties": {
            "status": {
                "type": "string",
                "enum": [
                    "VERIFIED",
                    "SUPPORTED_WITH_QUALIFICATION",
                    "UNSUPPORTED",
                    "CONFLICTING",
                ],
            },
            "reason": {"type": "string", "minLength": 1},
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string", "enum": refs},
                "uniqueItems": True,
            },
        },
    }
    diagnostic_properties = {
        key: {"type": "integer", "minimum": 0, "maximum": 5}
        for key in diagnostics
    }
    evaluation = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "package_id",
            "semantic_redundancy",
            "semantic_redundancy_reason",
            "visual_text_redundancy",
            "psychological_complementarity",
            "information_gain",
            "promise_consistency",
            "promise_alignment_reason",
            "hook_alignment_status",
            "hook_alignment_reason",
            "title_claim_validation",
            "thumbnail_claim_validation",
            "hard_validation_findings",
            "rework_findings",
            "diagnostics",
        ],
        "properties": {
            "package_id": {"type": "string", "enum": package_ids},
            "semantic_redundancy": {
                "type": "string",
                "enum": ["NONE", "LOW", "MODERATE", "HIGH"],
            },
            "semantic_redundancy_reason": {
                "type": "string",
                "minLength": 1,
            },
            "visual_text_redundancy": {
                "type": "string",
                "enum": ["NONE", "LOW", "MODERATE", "HIGH"],
            },
            "psychological_complementarity": {
                "type": "integer",
                "minimum": 0,
                "maximum": 5,
            },
            "information_gain": {
                "type": "integer",
                "minimum": 0,
                "maximum": 5,
            },
            "promise_consistency": {
                "type": "string",
                "enum": [
                    "PASS",
                    "UNDERPROMISE",
                    "OVERPROMISE",
                    "WRONG_PROMISE",
                    "DELAYED_ACKNOWLEDGEMENT",
                    "MISSING_PAYOFF",
                ],
            },
            "promise_alignment_reason": {
                "type": "string",
                "minLength": 1,
            },
            "hook_alignment_status": {
                "type": "string",
                "enum": ["PASS", "REWORK", "FAIL"],
            },
            "hook_alignment_reason": {
                "type": "string",
                "minLength": 1,
            },
            "title_claim_validation": claim_validation,
            "thumbnail_claim_validation": claim_validation,
            "hard_validation_findings": {
                "type": "array",
                "items": finding(hard_codes),
            },
            "rework_findings": {
                "type": "array",
                "items": finding(rework_codes),
            },
            "diagnostics": {
                "type": "object",
                "additionalProperties": False,
                "required": diagnostics,
                "properties": diagnostic_properties,
            },
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["video_id", "thumbnail_id", "evaluations"],
        "properties": {
            "video_id": {
                "type": "string",
                "const": str(request.get("video_id") or ""),
            },
            "thumbnail_id": {
                "type": "string",
                "const": str(request.get("thumbnail_id") or ""),
            },
            "evaluations": {
                "type": "array",
                "minItems": len(package_ids),
                "maxItems": len(package_ids),
                "items": evaluation,
            },
        },
    }


def build_prompt(request: dict[str, Any], maximum_chars: int) -> str:
    prompt = (
        "You are evaluating TITLE + THUMBNAIL + OPENING HOOK + VIEWER PROMISE "
        "as one YouTube packaging unit. Return JSON only.\n\n"
        "Rules:\n"
        "1. Evaluate every supplied pair independently. Do not rank them and do not select a winner.\n"
        "2. Do not create new title wording, new thumbnail concepts, new hook wording or new facts.\n"
        "3. semantic_redundancy asks whether title and thumbnail communicate substantially the same idea, not whether they share an unavoidable word.\n"
        "4. visual_text_redundancy asks whether thumbnail text unnecessarily repeats information already carried by title or visual concept.\n"
        "5. psychological_complementarity measures whether title and thumbnail contribute different but compatible psychological information.\n"
        "6. information_gain measures whether combining title and thumbnail gives more useful unresolved information than either alone.\n"
        "7. Promise Alignment compares title + thumbnail against viewer_promise_contract and video_payoff. Overpromise/wrong promise/missing payoff must be identified.\n"
        "8. Hook Alignment asks whether the approved opening immediately acknowledges why this viewer clicked while preserving the open loop. Do not require the opening to reveal the final answer.\n"
        "9. Claim validation must use only approved evidence refs already attached to the paired title/thumbnail component. Never invent an evidence ref.\n"
        "10. hard_validation_findings are only for the supplied hard reject codes. rework_findings are only for supplied rework codes.\n"
        "11. Diagnostic scores are 0-5 decision support only. They are not virality, CTR, view, retention, or recommendation predictions.\n"
        "12. A title outside 45-60 characters is not automatically bad; title length is a soft design guideline.\n"
        "13. SEARCH packages prioritize semantic clarity and subject/problem/payoff. BROWSE packages prioritize attention, curiosity, stakes and consequence. HYBRID balances both.\n"
        "14. Shorts require essentially immediate package-promise confirmation. Long-form may allow slightly deeper setup but still must acknowledge the click reason quickly.\n"
        "15. Be conservative with factual claims. Excellent psychological appeal cannot override unsupported or misleading claims.\n\n"
        "REQUEST:\n"
        + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt) > maximum_chars:
        raise ValueError("Package pairing prompt exceeds configured maximum")
    return prompt


def run_one(
    request_path: Path,
    *,
    force: bool,
    runner_config: dict[str, Any],
) -> dict[str, Any]:
    request_path = request_path.resolve()
    request = request_is_current(request_path)
    if request is None:
        raise ValueError("STALE_PACKAGE_PAIRING_REQUEST")
    video_id = str(request.get("video_id") or "").strip()
    thumbnail_id = str(request.get("thumbnail_id") or "").strip()
    if not video_id or not thumbnail_id:
        raise ValueError("Package pairing request requires video_id and thumbnail_id")

    request_hash = sha256_file(request_path)
    slug = safe_slug(f"{video_id}--{thumbnail_id}")
    report_path = MODEL_RUNS_DIR / f"{slug}.package_pairing_model_run.json"
    response_path = RESPONSES_DIR / f"{slug}.package_pairing_response.json"

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
                "video_id": video_id,
                "thumbnail_id": thumbnail_id,
            }

    schema = response_schema(request)
    prompt = build_prompt(
        request,
        int(runner_config["runner"].get("max_prompt_chars", 95000)),
    )
    paths = resolve_fair_paths(runner_config)
    payload = bridge_payload(
        action="solve",
        prompt=prompt,
        schema=schema,
        config=runner_config,
        paths=paths,
    )
    payload["settings"]["client_id"] = "youtube-package-pairing"

    MODEL_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)

    try:
        bridge_result = call_fair_bridge(
            payload,
            python_executable=paths["python"],
            timeout_seconds=float(
                runner_config["runner"].get(
                    "subprocess_timeout_seconds", 300
                )
            ),
        )
    except Exception as exc:
        report = {
            "video_id": video_id,
            "thumbnail_id": thumbnail_id,
            "status": "RUNNER_ERROR",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "request_sha256": request_hash,
        }
        atomic_write_json(report_path, report)
        return report

    base = {
        "video_id": video_id,
        "thumbnail_id": thumbnail_id,
        "request_source": str(request_path),
        "request_sha256": request_hash,
        "fair_request_id": bridge_result.get("request_id"),
        "fair_status": bridge_result.get("status"),
        "provider_id": bridge_result.get("provider_id"),
        "model_id": bridge_result.get("model_id"),
        "paid_inference_executed": bridge_result.get(
            "paid_inference_executed"
        ),
        "direct_backup_used": bridge_result.get("direct_backup_used", False),
        "attempts": safe_attempts(bridge_result),
    }
    if not inference_cost_authorized(bridge_result):
        report = {**base, "status": "COST_POLICY_VIOLATION"}
        atomic_write_json(report_path, report)
        return report
    if bridge_result.get("status") != "ACCEPTED":
        report = {**base, "status": "MODEL_FAILED"}
        atomic_write_json(report_path, report)
        return report

    raw = str(bridge_result.get("output") or "")
    atomic_write_text(RAW_OUTPUTS_DIR / f"{slug}.txt", raw)
    try:
        parsed = parse_model_json(raw)
        validate_response(parsed, request)
    except Exception as exc:
        report = {
            **base,
            "status": "MODEL_OUTPUT_VALIDATION_ERROR",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        atomic_write_json(report_path, report)
        return report

    response = {
        **parsed,
        "response_provenance": {
            "request_source": str(request_path),
            "request_sha256": request_hash,
            "provider": bridge_result.get("provider_id"),
            "model": bridge_result.get("model_id"),
            "prompt_version": PROMPT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    atomic_write_json(response_path, response)
    report = {
        **base,
        "status": "VALIDATED",
        "response": str(response_path),
    }
    atomic_write_json(report_path, report)
    return report


def run_batch(force: bool = False) -> dict[str, Any]:
    config = load_runner_config()
    requests = (
        sorted(REQUESTS_DIR.glob("*.package_pairing_request.json"))
        if REQUESTS_DIR.exists()
        else []
    )
    results = [
        run_one(path, force=force, runner_config=config)
        for path in requests
    ]
    run_apply()
    status = batch_status(
        results,
        expected_count=len(requests),
        processed_count=len(results),
    )
    summary = {
        "status": status,
        "requests": len(requests),
        "results": results,
        "package_validation_file": str(PACKAGE_VALIDATION_FILE),
    }
    atomic_write_json(BATCH_SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate Slice 26 title-thumbnail pairs"
    )
    parser.add_argument("--mode", choices=("batch",), required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run_batch(force=args.force)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(
        exit_code_for_status(str(result.get("status") or ""))
    )


if __name__ == "__main__":
    main()
