"""FAIR-backed Slice 25 runner for psychological packaging angles."""

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
from psychological_angles import (
    ANGLES_FILE,
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
MODEL_RUNS_DIR = OUTPUT_DIR / "psychological_angle_model_runs"
RAW_OUTPUTS_DIR = OUTPUT_DIR / "raw_psychological_angle_outputs"
BATCH_SUMMARY_FILE = OUTPUT_DIR / "psychological_angle_model_batch_summary.json"


def response_schema(request: dict[str, Any]) -> dict[str, Any]:
    drivers = [str(x) for x in request.get("allowed_primary_drivers", [])]
    refs = [str(x) for x in request.get("allowed_evidence_refs", [])]
    count = int(request.get("angle_count") or 0)
    item = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "angle_id",
            "primary_driver",
            "secondary_driver",
            "viewer_question",
            "emotional_trigger",
            "stakes",
            "information_given",
            "information_withheld",
            "expected_click_reason",
            "evidence_refs",
            "selected_title_direction_alignment",
        ],
        "properties": {
            "angle_id": {"type": "string", "minLength": 1},
            "primary_driver": {"type": "string", "enum": drivers},
            "secondary_driver": {"type": "string", "enum": drivers},
            "viewer_question": {"type": "string", "minLength": 1},
            "emotional_trigger": {"type": "string", "minLength": 1},
            "stakes": {"type": "string", "minLength": 1},
            "information_given": {"type": "string", "minLength": 1},
            "information_withheld": {"type": "string", "minLength": 1},
            "expected_click_reason": {"type": "string", "minLength": 1},
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string", "enum": refs},
                "minItems": 1,
                "uniqueItems": True,
            },
            "selected_title_direction_alignment": {
                "type": "string",
                "enum": ["ANCHOR", "ALTERNATIVE"],
            },
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["video_id", "angles"],
        "properties": {
            "video_id": {
                "type": "string",
                "const": str(request.get("video_id") or ""),
            },
            "angles": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": item,
            },
        },
    }


def build_prompt(request: dict[str, Any], maximum_chars: int) -> str:
    prompt = (
        "You are designing PSYCHOLOGICAL PACKAGING HYPOTHESES for a YouTube "
        "video after the script and Viewer Promise are approved. Return JSON only.\n\n"
        "Rules:\n"
        "1. Generate exactly five hypotheses.\n"
        "2. Use five DIFFERENT primary_driver values. Do not create wording variants of one idea.\n"
        "3. angle_id MUST equal 'angle-<primary_driver>'.\n"
        "4. Exactly one hypothesis is ANCHOR. It preserves the human-selected title direction's underlying psychology and promise without copying its wording.\n"
        "5. The other four are ALTERNATIVE hypotheses that deliberately test different psychological explanations for why the right viewer might care.\n"
        "6. Every hypothesis needs a distinct viewer_question and expected_click_reason.\n"
        "7. Use only approved evidence. evidence_refs must come from allowed_evidence_refs.\n"
        "8. Never invent numbers, records, superlatives, danger, scientific certainty, or outcomes.\n"
        "9. information_given states what the package may reveal up front. information_withheld states the unresolved information gap; withholding must remain truthful.\n"
        "10. SEARCH prioritizes clear subject/problem/payoff. BROWSE prioritizes attention/curiosity/stakes. HYBRID balances both.\n"
        "11. Shorts need instant comprehension and immediate promise confirmation. Long-form may support deeper mystery and open loops.\n"
        "12. Do not predict CTR, virality, views, retention, or recommendation performance. expected_click_reason is a design hypothesis, not a performance forecast.\n"
        "13. Do not change the approved script, opening hook, payoff, Viewer Promise, or evidence.\n\n"
        "REQUEST:\n"
        + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt) > maximum_chars:
        raise ValueError("Psychological angle prompt exceeds configured maximum")
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
        raise ValueError("STALE_ANGLE_REQUEST")
    video_id = str(request.get("video_id") or "").strip()
    if not video_id:
        raise ValueError("Psychological angle request requires video_id")

    request_hash = sha256_file(request_path)
    slug = safe_slug(video_id)
    report_path = MODEL_RUNS_DIR / f"{slug}.psychological_angle_model_run.json"
    response_path = RESPONSES_DIR / f"{slug}.psychological_angle_response.json"

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
            return {"status": "SKIPPED_ALREADY_VALIDATED", "video_id": video_id}

    config = runner_config
    schema = response_schema(request)
    prompt = build_prompt(
        request,
        int(config["runner"].get("max_prompt_chars", 95000)),
    )
    paths = resolve_fair_paths(config)
    payload = bridge_payload(
        action="solve",
        prompt=prompt,
        schema=schema,
        config=config,
        paths=paths,
    )
    payload["settings"]["client_id"] = "youtube-packaging-angles"

    MODEL_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)

    try:
        bridge_result = call_fair_bridge(
            payload,
            python_executable=paths["python"],
            timeout_seconds=float(
                config["runner"].get("subprocess_timeout_seconds", 300)
            ),
        )
    except Exception as exc:
        report = {
            "video_id": video_id,
            "status": "RUNNER_ERROR",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "request_sha256": request_hash,
        }
        atomic_write_json(report_path, report)
        return report

    base = {
        "video_id": video_id,
        "request_source": str(request_path),
        "request_sha256": request_hash,
        "fair_request_id": bridge_result.get("request_id"),
        "fair_status": bridge_result.get("status"),
        "provider_id": bridge_result.get("provider_id"),
        "model_id": bridge_result.get("model_id"),
        "paid_inference_executed": bridge_result.get("paid_inference_executed"),
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
    report = {**base, "status": "VALIDATED", "response": str(response_path)}
    atomic_write_json(report_path, report)
    return report


def run_batch(force: bool = False) -> dict[str, Any]:
    config = load_runner_config()
    requests = (
        sorted(REQUESTS_DIR.glob("*.psychological_angle_request.json"))
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
        "angles_file": str(ANGLES_FILE),
    }
    atomic_write_json(BATCH_SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Slice 25 psychological packaging angles"
    )
    parser.add_argument("--mode", choices=("batch",), required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run_batch(force=args.force)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(exit_code_for_status(str(result.get("status") or "")))


if __name__ == "__main__":
    main()
