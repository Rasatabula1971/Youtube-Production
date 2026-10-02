"""FAIR-backed Slice 25 runner for thumbnail concepts."""

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
from thumbnail_concepts import (
    CONCEPTS_FILE,
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
MODEL_RUNS_DIR = OUTPUT_DIR / "thumbnail_concept_model_runs"
RAW_OUTPUTS_DIR = OUTPUT_DIR / "raw_thumbnail_concept_outputs"
BATCH_SUMMARY_FILE = OUTPUT_DIR / "thumbnail_concept_model_batch_summary.json"


def response_schema(request: dict[str, Any]) -> dict[str, Any]:
    refs = [str(x) for x in request.get("allowed_evidence_refs", [])]
    angle_ids = [
        str(item.get("angle_id"))
        for item in request.get("angles", [])
        if isinstance(item, dict) and str(item.get("angle_id") or "").strip()
    ]
    count = len(angle_ids)
    item = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "thumbnail_id",
            "angle_id",
            "hero_subject",
            "secondary_element",
            "visual_anomaly",
            "visual_action",
            "emotion",
            "composition",
            "background",
            "subject_separation_method",
            "text",
            "text_word_count",
            "viewer_visual_question",
            "timestamp_safe",
            "mobile_legibility_intent",
            "evidence_refs",
            "aspect_ratio",
            "primary_focal_points",
            "meaningful_visual_elements",
            "critical_bottom_right_content",
            "face_present",
        ],
        "properties": {
            "thumbnail_id": {"type": "string", "minLength": 1},
            "angle_id": {"type": "string", "enum": angle_ids},
            "hero_subject": {"type": "string", "minLength": 1},
            "secondary_element": {"type": ["string", "null"]},
            "visual_anomaly": {"type": ["string", "null"]},
            "visual_action": {"type": "string", "minLength": 1},
            "emotion": {"type": "string", "minLength": 1},
            "composition": {"type": "string", "minLength": 1},
            "background": {"type": "string", "minLength": 1},
            "subject_separation_method": {"type": "string", "minLength": 1},
            "text": {"type": "string"},
            "text_word_count": {"type": "integer", "minimum": 0, "maximum": 4},
            "viewer_visual_question": {"type": "string", "minLength": 1},
            "timestamp_safe": {"type": "boolean", "const": True},
            "mobile_legibility_intent": {"type": "string", "minLength": 1},
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string", "enum": refs},
                "minItems": 1,
                "uniqueItems": True,
            },
            "aspect_ratio": {"type": "string", "const": "16:9"},
            "primary_focal_points": {"type": "integer", "const": 1},
            "meaningful_visual_elements": {
                "type": "integer",
                "minimum": 1,
                "maximum": 3,
            },
            "critical_bottom_right_content": {"type": "boolean", "const": False},
            "face_present": {"type": "boolean"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["video_id", "thumbnail_concepts"],
        "properties": {
            "video_id": {
                "type": "string",
                "const": str(request.get("video_id") or ""),
            },
            "thumbnail_concepts": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": item,
            },
        },
    }


def build_prompt(request: dict[str, Any], maximum_chars: int) -> str:
    prompt = (
        "You are designing STRUCTURED YOUTUBE THUMBNAIL CONCEPTS. Return JSON only. "
        "Do not generate images.\n\n"
        "Rules:\n"
        "1. Create exactly one thumbnail concept for every psychological angle supplied.\n"
        "2. thumbnail_id MUST equal 'thumbnail-<angle_id>'.\n"
        "3. The concept must express the angle visually; do not merely illustrate or restate the selected title.\n"
        "4. One thumbnail = one visual proposition. Use exactly one primary focal point and no more than three meaningful visual elements.\n"
        "5. Use 16:9. Keep critical content out of the bottom-right timestamp zone.\n"
        "6. Thumbnail text should be 0-3 words when possible. Four words are allowed only when necessary. text_word_count must exactly match.\n"
        "7. Thumbnail text must add information and must not just repeat words already doing the same job in the selected title direction.\n"
        "8. visual_anomaly is preferred when truthful, but may be null when another visual strategy is stronger.\n"
        "9. Make the concept legible on a phone: strong separation, simple composition, understandable hero subject.\n"
        "10. Every factual visual or text claim must be grounded in evidence_refs from the approved set and must remain connected to the source angle's evidence.\n"
        "11. Never invent numbers, records, superlatives, danger, scientific claims, results, scale, or transformation.\n"
        "12. Faces are optional. Do not invent reactions or expressions unsupported by the content.\n"
        "13. Do not predict CTR, virality, views, watch time, retention, or recommendation performance.\n"
        "14. Do not change the approved Viewer Promise, opening hook, payoff, script, or evidence.\n\n"
        "REQUEST:\n"
        + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt) > maximum_chars:
        raise ValueError("Thumbnail concept prompt exceeds configured maximum")
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
        raise ValueError("STALE_THUMBNAIL_REQUEST")
    video_id = str(request.get("video_id") or "").strip()
    if not video_id:
        raise ValueError("Thumbnail request requires video_id")

    request_hash = sha256_file(request_path)
    slug = safe_slug(video_id)
    report_path = MODEL_RUNS_DIR / f"{slug}.thumbnail_concept_model_run.json"
    response_path = RESPONSES_DIR / f"{slug}.thumbnail_concept_response.json"

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
    payload["settings"]["client_id"] = "youtube-thumbnail-concepts"

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
        sorted(REQUESTS_DIR.glob("*.thumbnail_concept_request.json"))
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
        "thumbnail_concepts_file": str(CONCEPTS_FILE),
    }
    atomic_write_json(BATCH_SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Slice 25 thumbnail concepts")
    parser.add_argument("--mode", choices=("batch",), required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run_batch(force=args.force)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(exit_code_for_status(str(result.get("status") or "")))


if __name__ == "__main__":
    main()
