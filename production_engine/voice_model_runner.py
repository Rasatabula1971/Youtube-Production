"""FAIR-backed Voice Performance planner.

This runner is free-only. It creates performance annotations but never renders
audio or invokes Higgsfield.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import (
    atomic_write_json,
    atomic_write_text,
    batch_status,
    exit_code_for_status,
    tolerant_load_json,
)

EXP2_DIR = _ROOT / "experiment_02_analysis"
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

from voice_performance import (
    MODEL_RUNS_DIR,
    RAW_OUTPUTS_DIR,
    REQUESTS_DIR,
    RESPONSES_DIR,
    SPECS_DIR,
    load_json,
    safe_slug,
    sha256_file,
    validate_response,
    validation_contract_sha256,
)

BATCH_SUMMARY_FILE = SPECS_DIR.parent / "voice_performance_model_batch_summary.json"


def response_schema(request: dict[str, Any]) -> dict[str, Any]:
    beats = request.get("beats", [])
    beat_ids = [
        str(item.get("beat_id") or "")
        for item in beats
        if isinstance(item, dict)
    ]
    controls = request.get("performance_controls", {})
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["concept_id", "format", "directions"],
        "properties": {
            "concept_id": {
                "type": "string",
                "const": str(request.get("concept_id") or ""),
            },
            "format": {
                "type": "string",
                "const": str(request.get("format") or ""),
            },
            "directions": {
                "type": "array",
                "minItems": len(beat_ids),
                "maxItems": len(beat_ids),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "beat_id",
                        "emotion",
                        "intensity",
                        "speed",
                        "pause_before_ms",
                        "pause_after_ms",
                        "emphasis_terms",
                    ],
                    "properties": {
                        "beat_id": {"type": "string", "enum": beat_ids},
                        "emotion": {
                            "type": "string",
                            "enum": list(controls.get("allowed_emotions", [])),
                        },
                        "intensity": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": float(controls.get("max_intensity", 1)),
                        },
                        "speed": {
                            "type": "number",
                            "minimum": float(controls.get("speed_min", 0.1)),
                            "maximum": float(controls.get("speed_max", 5)),
                        },
                        "pause_before_ms": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": int(controls.get("pause_ms_max", 0)),
                        },
                        "pause_after_ms": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": int(controls.get("pause_ms_max", 0)),
                        },
                        "emphasis_terms": {
                            "type": "array",
                            "maxItems": int(controls.get("emphasis_terms_max", 0)),
                            "items": {"type": "string", "minLength": 1},
                            "uniqueItems": True,
                        },
                    },
                },
            },
        },
    }


def build_prompt(request: dict[str, Any], maximum_chars: int) -> str:
    prompt = (
        "You are the Voice Performance planner for a faceless YouTube production. "
        "Return JSON only. Annotate HOW the immutable narration should be delivered.\n\n"
        "Hard rules:\n"
        "1. Never rewrite, paraphrase, add, remove, summarize or reorder spoken words.\n"
        "2. Return exactly one direction for each beat, in request order.\n"
        "3. Keep emotion restrained. Prefer pace, pauses and grounded emphasis.\n"
        "4. Use surprised only when reveal_beat is true.\n"
        "5. Emphasis terms must occur verbatim in that beat's immutable_narration.\n"
        "6. Respect all numeric control bounds in the request.\n"
        "7. Do not score virality, retention, quality or choose a winning take.\n"
        "8. This is planning only. Do not claim audio was rendered.\n\n"
        "VOICE PERFORMANCE REQUEST:\n"
        + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt) > maximum_chars:
        raise ValueError("Voice Performance prompt exceeds configured maximum")
    return prompt


def artifact_slug(request: dict[str, Any]) -> str:
    return (
        f"{safe_slug(str(request.get('concept_id') or 'unknown'))}."
        f"{safe_slug(str(request.get('format') or 'unknown'))}"
    )


def run_one(path: Path, force: bool, config: dict[str, Any]) -> dict[str, Any]:
    path = path.resolve()
    request = load_json(path)
    concept_id = str(request.get("concept_id") or "").strip()
    fmt = str(request.get("format") or "").strip()
    if not concept_id or not fmt:
        raise ValueError("Voice Performance request requires concept_id and format")

    slug = artifact_slug(request)
    request_hash = sha256_file(path)
    contract_hash = validation_contract_sha256()
    report_path = MODEL_RUNS_DIR / f"{slug}.model_run.json"
    response_path = RESPONSES_DIR / f"{slug}.json"
    spec_path = SPECS_DIR / f"{slug}.voice_performance_spec.json"

    if report_path.exists() and spec_path.exists() and not force:
        report = tolerant_load_json(report_path) or {}
        spec = tolerant_load_json(spec_path) or {}
        provenance = spec.get("spec_provenance", {})
        if (
            report.get("status") == "VALIDATED"
            and isinstance(provenance, dict)
            and provenance.get("request_sha256") == request_hash
            and provenance.get("validation_contract_sha256") == contract_hash
        ):
            return {
                "status": "SKIPPED_ALREADY_VALIDATED",
                "concept_id": concept_id,
                "format": fmt,
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
    payload["settings"]["client_id"] = "youtube-voice-performance"

    for directory in (
        MODEL_RUNS_DIR,
        RAW_OUTPUTS_DIR,
        RESPONSES_DIR,
        SPECS_DIR,
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
    except (OSError, TimeoutError, RuntimeError, ValueError, TypeError, KeyError) as exc:
        report = {
            "concept_id": concept_id,
            "format": fmt,
            "request_source": str(path),
            "request_sha256": request_hash,
            "status": "RUNNER_ERROR",
            "error_type": type(exc).__name__,
        }
        atomic_write_json(report_path, report)
        return report

    base = {
        "concept_id": concept_id,
        "format": fmt,
        "request_source": str(path),
        "request_sha256": request_hash,
        "validation_contract_sha256": contract_hash,
        "fair_request_id": result.get("request_id"),
        "fair_status": result.get("status"),
        "fair_reason_code": result.get("reason_code"),
        "provider_id": result.get("provider_id"),
        "model_id": result.get("model_id"),
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
        validation = validate_response(response, request)
    except (OSError, TimeoutError, RuntimeError, ValueError, TypeError, KeyError) as exc:
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

    atomic_write_json(response_path, response)
    spec = {
        "artifact": "voice_performance_spec",
        "concept_id": concept_id,
        "format": fmt,
        "title": request.get("title"),
        "duration_intent_seconds": request.get("duration_intent_seconds"),
        "promise_delivery": request.get("promise_delivery"),
        "payoff": request.get("payoff"),
        "opening_hook": request.get("opening_hook"),
        "closing": request.get("closing"),
        "beats": request.get("beats", []),
        "directions": validation["directions"],
        "voice_identity": request.get("voice_identity", {}),
        "render_prerequisites_configured": bool(
            request.get("render_prerequisites_configured")
        ),
        "validation": validation,
        "spec_provenance": {
            "request_source": str(path),
            "request_sha256": request_hash,
            "validation_contract_sha256": contract_hash,
            "provider_id": result.get("provider_id"),
            "model_id": result.get("model_id"),
            "paid_inference_executed": False,
        },
    }
    atomic_write_json(spec_path, spec)
    report = {
        **base,
        "status": "VALIDATED",
        "voice_performance_spec": str(spec_path),
    }
    atomic_write_json(report_path, report)
    return report


def run_batch(
    requests_dir: Path,
    force: bool,
    maximum: int | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    paths = sorted(requests_dir.glob("*.voice_request.json"))
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
        except (OSError, TimeoutError, RuntimeError, ValueError, TypeError, KeyError) as exc:
            item = {
                "status": "RUNNER_ERROR",
                "request_source": str(path),
                "error_type": type(exc).__name__,
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
    parser = argparse.ArgumentParser(description="FAIR Voice Performance planner")
    parser.add_argument("--mode", choices=("run", "batch"), required=True)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--requests-dir", type=Path, default=REQUESTS_DIR)
    parser.add_argument("--max-requests", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    config = load_runner_config()
    if args.mode == "run":
        if not args.request:
            raise SystemExit("--request is required for run mode")
        result = run_one(args.request, args.force, config)
    else:
        result = run_batch(
            args.requests_dir.resolve(),
            args.force,
            args.max_requests,
            config,
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.mode == "batch":
        raise SystemExit(exit_code_for_status(result["status"]))


if __name__ == "__main__":
    main()
