"""FAIR-backed runner for post-script title directions."""

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
from title_direction import (
    CANDIDATES_FILE,
    PROMPT_VERSION,
    REQUESTS_DIR,
    RESPONSES_DIR,
    SCHEMA_VERSION,
    load_json,
    run_apply,
    safe_slug,
    sha256_file,
    validate_response,
)

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"
MODEL_RUNS_DIR = OUTPUT_DIR / "title_direction_model_runs"
RAW_OUTPUTS_DIR = OUTPUT_DIR / "raw_title_direction_outputs"
BATCH_SUMMARY_FILE = OUTPUT_DIR / "title_direction_model_batch_summary.json"


def response_schema(request: dict[str, Any]) -> dict[str, Any]:
    angles = [str(x) for x in request.get("psychological_angles", [])]
    refs = [str(x) for x in request.get("allowed_evidence_refs", [])]

    def candidate(fmt: str) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "title_id",
                "title_text",
                "psychological_angle",
                "primary_driver",
                "secondary_driver",
                "core_claim",
                "evidence_refs",
                "search_intent",
            ],
            "properties": {
                "title_id": {"type": "string", "minLength": 1},
                "title_text": {"type": "string", "minLength": 1},
                "psychological_angle": {"type": "string", "enum": angles},
                "primary_driver": {"type": "string", "minLength": 1},
                "secondary_driver": {"type": "string"},
                "core_claim": {"type": "string", "minLength": 1},
                "evidence_refs": {
                    "type": "array",
                    "items": {"type": "string", "enum": refs},
                    "uniqueItems": True,
                },
                "search_intent": {
                    "type": "string",
                    "enum": ["SEARCH", "BROWSE", "HYBRID"],
                },
            },
        }

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["concept_id", "titles"],
        "properties": {
            "concept_id": {
                "type": "string",
                "const": str(request.get("concept_id") or ""),
            },
            "titles": {
                "type": "object",
                "additionalProperties": False,
                "required": ["short", "long_form"],
                "properties": {
                    "short": {
                        "type": "array",
                        "minItems": 5,
                        "maxItems": 5,
                        "items": candidate("short"),
                    },
                    "long_form": {
                        "type": "array",
                        "minItems": 5,
                        "maxItems": 5,
                        "items": candidate("long_form"),
                    },
                },
            },
        },
    }


def build_prompt(request: dict[str, Any], maximum_chars: int) -> str:
    prompt = (
        "You are generating POST-SCRIPT YouTube title-direction candidates. "
        "The script, hook, payoff and approved evidence are already stable. "
        "Return JSON only.\n\n"
        "Rules:\n"
        "1. Generate exactly five Short and five Long-form titles.\n"
        "2. Use each psychological_angle exactly once per format.\n"
        "3. title_id MUST equal '<format>-<psychological_angle>', for example short-curiosity.\n"
        "4. These are public-title DIRECTIONS, not permanently locked final wording.\n"
        "5. The approved script is the truth boundary. Never promise material the script does not deliver.\n"
        "6. Never invent numbers, records, fastest/best/first/only/never claims, danger, certainty or scientific claims.\n"
        "7. Any factual material claim must cite evidence_refs from allowed_evidence_refs only.\n"
        "8. Short and Long-form sets must be independently written, not resized copies.\n"
        "9. Front-load compelling information where practical; keep one main proposition.\n"
        "10. Prefer specificity when truthful. Character length is a guideline, not a hard pass/fail threshold.\n"
        "11. search_intent must be SEARCH, BROWSE or HYBRID and should describe the title strategy.\n"
        "12. primary_driver and secondary_driver describe psychology; do not predict performance.\n"
        "13. Do not produce a viral score, CTR prediction or winner ranking.\n"
        "14. If human_rework_note exists, preserve already approved upstream script and evidence and regenerate only the title-direction set.\n\n"
        "REQUEST:\n"
        + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt) > maximum_chars:
        raise ValueError("Title direction prompt exceeds configured maximum")
    return prompt


def run_one(
    request_path: Path,
    *,
    force: bool,
    runner_config: dict[str, Any],
) -> dict[str, Any]:
    request_path = request_path.resolve()
    request = load_json(request_path)
    concept_id = str(request.get("concept_id") or "").strip()
    if not concept_id:
        raise ValueError("Title direction request requires concept_id")

    request_hash = sha256_file(request_path)
    slug = safe_slug(concept_id)
    report_path = MODEL_RUNS_DIR / f"{slug}.title_direction_model_run.json"
    response_path = RESPONSES_DIR / f"{slug}.title_direction_response.json"

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
    payload["settings"]["client_id"] = "youtube-title-direction"

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
            "error": str(exc),
            "request_sha256": request_hash,
        }
        atomic_write_json(report_path, report)
        return report

    base = {
        "concept_id": concept_id,
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
            "status": "INVALID_MODEL_OUTPUT",
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
        sorted(REQUESTS_DIR.glob("*.title_direction_request.json"))
        if REQUESTS_DIR.exists()
        else []
    )
    results = [
        run_one(path, force=force, runner_config=config)
        for path in requests
    ]
    run_apply()
    status = batch_status([str(item.get("status") or "") for item in results])
    summary = {
        "status": status,
        "requests": len(requests),
        "results": results,
        "candidates_file": str(CANDIDATES_FILE),
    }
    atomic_write_json(BATCH_SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate post-script title directions")
    parser.add_argument("--mode", choices=("batch",), required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run_batch(force=args.force)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(exit_code_for_status(str(result.get("status") or "")))


if __name__ == "__main__":
    main()
