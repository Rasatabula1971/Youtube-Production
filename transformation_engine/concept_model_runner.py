"""FAIR-backed Transformation Engine concept runner.

Prepared concept requests are sent through the existing FAIR subprocess bridge.
The runner is free-only, validates model output through transformation_engine,
and writes only request-bound responses for the deterministic merge step.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
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
    call_direct_gemini_backup,
    call_fair_bridge,
    direct_gemini_available,
    inference_cost_authorized,
    load_runner_config,
    parse_model_json,
    resolve_fair_paths,
    safe_attempts,
)
from evidence_ingest import sha256_file
from human_framing import response_schema as human_framing_response_schema

from transformation_engine import (
    OUTPUT_DIR,
    REQUESTS_DIR,
    RESPONSES_DIR,
    load_config,
    load_json,
    run_apply,
    safe_slug,
    validate_response,
    validation_contract_sha256,
)

MODEL_RUNS_DIR = OUTPUT_DIR / "concept_model_runs"
# Which route generates concepts (D-146): "fair" (free models through FAIR) or
# "direct_gemini" (the project's Gemini key only, no FAIR and no fallback).
# Kept out of the validation contract, so switching never regenerates
# mechanisms that already validated.
ROUTE_FILE = Path(__file__).resolve().parent / "concept_model_route.json"
ROUTES = {"fair", "direct_gemini"}
RAW_OUTPUTS_DIR = OUTPUT_DIR / "raw_concept_outputs"
BATCH_SUMMARY_FILE = OUTPUT_DIR / "concept_model_batch_summary.json"


def response_schema(request: dict[str, Any]) -> dict[str, Any]:
    mechanism_id = str(request.get("mechanism_id", ""))
    allowed_formats = list(request.get("allowed_format_intents", []))

    concept_schema: dict[str, Any] = {
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
            "human_framing",
            "viewer_need_evidence",
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
            "human_framing": human_framing_response_schema(),
            "viewer_need_evidence": {
                "type": "object",
                "additionalProperties": False,
                "required": ["status", "evidence_basis", "rationale"],
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["OBSERVED", "INFERRED", "HYPOTHESIS"],
                    },
                    "evidence_basis": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "rationale": {"type": "string", "minLength": 1},
                },
            },
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

    rework_concept_id = str(
        request.get("human_rework_concept_id") or ""
    ).strip()
    rework_mode = bool(request.get("human_rework_note") and rework_concept_id)
    if rework_mode:
        concept_schema["properties"]["concept_id"] = {
            "type": "string",
            "const": rework_concept_id,
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
                "maxItems": (
                    1 if rework_mode else int(request.get("concept_count_requested", 5))
                ),
                "items": concept_schema,
            },
        },
    }


def provider_schema(schema: Any) -> Any:
    """The response schema as sent to providers (D-145, revised by D-148).

    Every field bound stays: without them the model invented drama levels
    outside 4-10 and too few opening moments (laptop run, 4 October 2026).
    Only the number of concepts in one answer is left to the runner, which
    keeps at most the requested number (``_cap_concepts``).
    """
    shaped = json.loads(json.dumps(schema))
    concepts = (shaped.get("properties") or {}).get("concepts")
    if isinstance(concepts, dict):
        concepts.pop("maxItems", None)
    return shaped


def _cap_concepts(request: dict[str, Any], response: Any) -> int:
    """Keep at most the requested number of concepts; return how many were dropped."""
    if not isinstance(response, dict) or not isinstance(response.get("concepts"), list):
        return 0
    rework = bool(request.get("human_rework_note") and request.get("human_rework_concept_id"))
    limit = 1 if rework else max(1, int(request.get("concept_count_requested") or 5))
    dropped = max(0, len(response["concepts"]) - limit)
    response["concepts"] = response["concepts"][:limit]
    return dropped


def concept_route() -> str:
    try:
        route = str(load_json(ROUTE_FILE).get("route") or "fair").strip()
    except (OSError, ValueError, AttributeError):
        return "fair"
    if route not in ROUTES:
        raise ValueError(f"concept_model_route.json route must be one of {sorted(ROUTES)}, not {route!r}")
    return route


def concepts_per_call() -> int | None:
    """How many concepts one model call is asked for (D-147); None means all at once.

    Free models drop required nested sections when asked for five full
    concepts in one answer, so a mechanism's concepts are generated in
    several smaller calls.
    """
    try:
        value = load_json(ROUTE_FILE).get("concepts_per_call")
    except (OSError, ValueError, AttributeError):
        return None
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("concept_model_route.json concepts_per_call must be a positive integer")
    return value


def pause_between_calls() -> float:
    """Seconds to wait between one mechanism's calls (D-148).

    Groq's free tier limits tokens per minute; a second concept call in the
    same minute was refused as RATE_LIMITED and fell to models that fail the
    schema.
    """
    try:
        value = load_json(ROUTE_FILE).get("pause_between_calls_seconds", 0)
    except (OSError, ValueError, AttributeError):
        return 0.0
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError("concept_model_route.json pause_between_calls_seconds must be a non-negative number")
    return float(value)


def call_gemini_only(payload: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
    """Generate on the project's Gemini key alone; FAIR is not called."""
    not_run = {
        "status": "ESCALATION_REQUIRED",
        "reason_code": "GEMINI_ONLY_ROUTE",
        "paid_inference_executed": False,
        "attempts": [],
    }
    if not direct_gemini_available():
        return {**not_run, "reason_code": "DIRECT_GEMINI_NOT_CONFIGURED"}
    return call_direct_gemini_backup(payload, timeout_seconds=timeout_seconds, fair_result=not_run)


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
        "desired outcome, and an honest viewer-need evidence state.\n"
        "5. Set viewer_need_evidence.status to OBSERVED only when the request contains "
        "concrete audience-signal evidence such as repeated questions, comments, or "
        "search-intent evidence. Use INFERRED when the need is a reasoned inference "
        "from available market/source evidence, and HYPOTHESIS when it is unverified.\n"
        "6. Do not invent audience evidence or content-gap evidence. If a content gap "
        "is not proven, use HYPOTHESIS or UNASSESSED.\n"
        "7. Do not predict views, virality, CTR, retention, or recommendation.\n"
        "8. Channel fit may be REVIEW or UNASSESSED when it cannot be defended.\n"
        "9. Provide at least three clear working-title options as an idea clarity test.\n"
        "10. Include at least two independent research questions before scripting.\n"
        "11. The Source Dependency Test must pass: the concept must keep its main "
        "value without source wording, footage, story, personality, or exact execution.\n"
        "12. Build the human framing BEFORE settling on the technical title. Start with "
        "what the viewer can see, experience, lose, fear, question, compare, or find "
        "contradictory; the mechanism is usually the answer, not the doorway.\n"
        "13. Drama has a hard floor of 4/10. Treat 5/10 as the normal center, but "
        "actively raise it when the real opportunity supports stronger consequence, "
        "danger, loss, surprise, transformation, scale, conflict, or decision tension.\n"
        "14. Never manufacture drama. Record both the truthful drama source and a "
        "constraint on what must not be exaggerated. Levels 9-10 require genuinely "
        "extreme real-world stakes or spectacle.\n"
        "15. Do not waste a high-drama opportunity with textbook framing. The selected "
        "target may not sit more than three points below the assessed drama capacity.\n"
        "16. Use a changing drama curve with rises and releases, never a flat line. "
        "Use a separate changing tempo curve; tempo may slow while drama remains high.\n"
        "17. The visual opening plan must SHOW the problem, contradiction, consequence, "
        "transformation, decision, or mystery before asking the viewer to absorb the "
        "technical explanation.\n"
        "18. Do not rank or score concepts.\n"
        "19. If human_rework_note is present, it is an AUTHORITATIVE human instruction for the one concept identified by human_rework_concept_id. Return exactly one revised concept with that same concept_id. Correct the requested issue while preserving unrelated strengths where possible.\n"
        "20. Human rework never authorizes invented audience evidence, unsupported drama, source copying, or false certainty. If the instruction conflicts with evidence constraints, preserve the constraint and make the safest valid correction.\n"
        "21. If already_generated_concepts is present, those concepts exist already for this mechanism. Generate genuinely different premises, viewer problems and titles, and reuse none of their concept_ids.\n"
        "22. Every concept must include every field of the response schema, including the complete human_framing and viewer_need_evidence objects.\n"
        "23. Drama numbers: capacity, target, hook_level and every story_curve value are whole numbers from 4 to 10; target may not exceed capacity; the highest story_curve value must reach the target; every tempo_curve value is a whole number from 1 to 10; story_curve and tempo_curve each have 4 to 8 values. visual_opening_plan.moments has 3 to 5 moments.\n\n"
        "CONCEPT REQUEST:\n"
        + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt) > maximum_chars:
        raise ValueError(
            f"Concept prompt is {len(prompt):,} characters; configured maximum "
            f"is {maximum_chars:,}."
        )
    return prompt



def _merge_human_rework_response(
    request: dict[str, Any],
    response: dict[str, Any],
) -> dict[str, Any]:
    note = str(request.get("human_rework_note") or "").strip()
    target = str(request.get("human_rework_concept_id") or "").strip()
    if not note or not target:
        return response

    generated = response.get("concepts")
    if not isinstance(generated, list) or len(generated) != 1:
        raise ValueError("Human concept rework must return exactly one revised concept")
    replacement = generated[0]
    if (
        not isinstance(replacement, dict)
        or str(replacement.get("concept_id") or "") != target
    ):
        raise ValueError("Human concept rework concept_id must remain stable")

    originals = request.get("human_rework_original_concepts")
    if not isinstance(originals, list) or not originals:
        raise ValueError("Human concept rework is missing the original concept set")

    merged: list[dict[str, Any]] = []
    replaced = False
    for item in originals:
        if not isinstance(item, dict):
            continue
        if str(item.get("concept_id") or "") == target:
            merged.append(replacement)
            replaced = True
        else:
            merged.append(item)
    if not replaced:
        raise ValueError("Human concept rework target is missing from original set")

    return {
        "mechanism_id": response.get("mechanism_id"),
        "concepts": merged,
    }


def _rejection_error_summary(validation: dict[str, Any]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in validation.get("rejected", []):
        if not isinstance(item, dict):
            continue
        for error in item.get("errors", []):
            text = str(error).strip()
            if text:
                counts[text] = counts.get(text, 0) + 1
    return [
        {"error": error, "count": count}
        for error, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    ]


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
    validation_contract = validation_contract_sha256()
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
            and existing.get("validation_contract_sha256")
            == validation_contract
            and isinstance(provenance, dict)
            and provenance.get("request_sha256") == request_hash
            and provenance.get("validation_contract_sha256")
            == validation_contract
        ):
            return {
                "status": "SKIPPED_ALREADY_VALIDATED",
                "mechanism_id": mechanism_id,
                "report": str(report_path),
            }

    rework = bool(request.get("human_rework_note") and request.get("human_rework_concept_id"))
    per_call = None if rework else concepts_per_call()
    if per_call is not None and per_call < max(1, int(request.get("concept_count_requested") or 5)):
        return _run_in_calls(
            request, request_path=request_path, request_hash=request_hash,
            validation_contract=validation_contract, slug=slug, report_path=report_path,
            response_path=response_path, per_call=per_call, runner_config=runner_config,
        )

    prompt = build_prompt(
        request,
        maximum_chars=int(runner_config["runner"].get("max_prompt_chars", 95000)),
    )
    schema = provider_schema(response_schema(request))
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
        timeout = float(runner_config["runner"].get("subprocess_timeout_seconds", 300))
        if concept_route() == "direct_gemini":
            bridge_result = call_gemini_only(payload, timeout_seconds=timeout)
        else:
            bridge_result = call_fair_bridge(
                payload,
                python_executable=paths["python"],
                timeout_seconds=timeout,
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

    if not inference_cost_authorized(bridge_result):
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
        "validation_contract_sha256": validation_contract,
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
        concepts_dropped = _cap_concepts(request, response)
        response = _merge_human_rework_response(request, response)
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

    initial_validation_errors = _rejection_error_summary(validation)
    # No paid "validation repair": direct Gemini replaces exhausted free
    # capacity only (vision §101, D-068, D-129). A batch where every concept
    # fails validation is reported with its errors so the request or prompt
    # can be repaired and the batch rerun on the free route.
    repair_result: dict[str, Any] | None = None
    repair_raw_path: Path | None = None

    response["response_provenance"] = {
        "request_source": str(request_path),
        "request_sha256": request_hash,
        "validation_contract_sha256": validation_contract,
        "provider_id": bridge_result.get("provider_id"),
        "model_id": bridge_result.get("model_id"),
    }
    atomic_write_json(response_path, response)

    accepted_count = len(validation["accepted"])
    rejected_count = len(validation["rejected"])
    report = {
        **base_report,
        "status": (
            "VALIDATED"
            if accepted_count > 0
            else "MODEL_OUTPUT_VALIDATION_ERROR"
        ),
        "error_type": None if accepted_count > 0 else "NoAcceptedConcepts",
        "model_response": str(response_path),
        "raw_output": str(raw_path),
        "structurally_accepted": accepted_count,
        "structurally_rejected": rejected_count,
        "concepts_beyond_request_dropped": concepts_dropped,
        "validation_rejection_summary": _rejection_error_summary(validation),
        "initial_validation_rejection_summary": initial_validation_errors,
        "validation_repair_attempted": repair_result is not None,
        "validation_repair_raw_output": str(repair_raw_path) if repair_raw_path else None,
    }
    atomic_write_json(report_path, report)
    return report



def _call_route(payload: dict[str, Any], paths: dict[str, Path], timeout: float) -> dict[str, Any]:
    if concept_route() == "direct_gemini":
        return call_gemini_only(payload, timeout_seconds=timeout)
    return call_fair_bridge(payload, python_executable=paths["python"], timeout_seconds=timeout)


def _run_in_calls(
    request: dict[str, Any], *, request_path: Path, request_hash: str, validation_contract: str,
    slug: str, report_path: Path, response_path: Path, per_call: int, runner_config: dict[str, Any],
) -> dict[str, Any]:
    """Generate one mechanism's concepts in several small calls (D-147).

    Each call asks for at most ``per_call`` concepts and is told which concepts
    already exist, so later calls add different ideas. Only concepts that pass
    validation count towards the requested total; one spare call covers a
    call that returns nothing usable. Concepts from successful calls are kept
    even when a later call fails.
    """
    mechanism_id = str(request["mechanism_id"])
    total = max(1, int(request.get("concept_count_requested") or 5))
    max_calls = -(-total // per_call) + 1
    config = load_config()
    paths = resolve_fair_paths(runner_config)
    timeout = float(runner_config["runner"].get("subprocess_timeout_seconds", 300))
    maximum_chars = int(runner_config["runner"].get("max_prompt_chars", 95000))
    for directory in (MODEL_RUNS_DIR, RAW_OUTPUTS_DIR, RESPONSES_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    collected: list[dict[str, Any]] = []
    accepted_titles: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    raw_paths: list[str] = []
    seen_ids: set[str] = set()
    dropped = 0
    last: dict[str, Any] = {}
    stop: dict[str, Any] | None = None

    pause = pause_between_calls()
    while len(accepted_titles) < total and len(calls) < max_calls:
        number = len(calls) + 1
        if number > 1 and pause:
            time.sleep(pause)
        chunk = dict(request)
        chunk["concept_count_requested"] = min(per_call, total - len(accepted_titles))
        if accepted_titles:
            chunk["already_generated_concepts"] = list(accepted_titles)
        schema = provider_schema(response_schema(chunk))
        payload = bridge_payload(
            action="solve", prompt=build_prompt(chunk, maximum_chars=maximum_chars),
            schema=schema, config=runner_config, paths=paths,
        )
        payload["settings"]["client_id"] = "youtube-transformation-concepts"
        call: dict[str, Any] = {"call": number, "concepts_requested": chunk["concept_count_requested"]}
        calls.append(call)
        try:
            result = _call_route(payload, paths, timeout)
        except Exception as exc:
            call.update(status="RUNNER_ERROR", error_type=type(exc).__name__)
            stop = {"status": "RUNNER_ERROR", "error_type": type(exc).__name__}
            break
        last = result
        attempts.extend(safe_attempts(result))
        call.update(
            fair_status=result.get("status"), fair_reason_code=result.get("reason_code"),
            provider_id=result.get("provider_id"), model_id=result.get("model_id"),
        )
        if not inference_cost_authorized(result):
            report = {
                "mechanism_id": mechanism_id, "status": "COST_POLICY_VIOLATION",
                "request_source": str(request_path), "request_sha256": request_hash,
                "fair_status": result.get("status"), "calls": calls,
            }
            atomic_write_json(report_path, report)
            return report
        if result.get("status") != "ACCEPTED":
            call["status"] = "MODEL_ESCALATION_REQUIRED" if result.get("status") == "ESCALATION_REQUIRED" else "MODEL_FAILED"
            stop = {"status": call["status"]}
            break
        raw_path = RAW_OUTPUTS_DIR / f"{slug}.call{number}.txt"
        atomic_write_text(raw_path, str(result.get("output") or ""))
        raw_paths.append(str(raw_path))
        try:
            response = parse_model_json(str(result.get("output") or ""))
            dropped += _cap_concepts(chunk, response)
            concepts = [c for c in response.get("concepts") or [] if isinstance(c, dict)]
        except Exception as exc:
            call.update(status="MODEL_OUTPUT_VALIDATION_ERROR", error_type=type(exc).__name__)
            continue
        for concept in concepts:
            concept_id = str(concept.get("concept_id") or "").strip()
            if concept_id in seen_ids:
                concept["concept_id"] = f"{concept_id}-{number}"
            seen_ids.add(str(concept.get("concept_id") or ""))
        validation = validate_response({"mechanism_id": mechanism_id, "concepts": concepts}, request, config)
        collected.extend(concepts)
        accepted_titles.extend(
            {"concept_id": c.get("concept_id"), "working_title": c.get("working_title"), "premise": c.get("premise")}
            for c in validation["accepted"]
        )
        call.update(
            status="VALIDATED" if validation["accepted"] else "MODEL_OUTPUT_VALIDATION_ERROR",
            concepts_returned=len(concepts), accepted=len(validation["accepted"]),
            rejection_summary=_rejection_error_summary(validation),
        )

    base_report = {
        "mechanism_id": mechanism_id,
        "request_source": str(request_path),
        "request_sha256": request_hash,
        "validation_contract_sha256": validation_contract,
        "fair_request_id": last.get("request_id"),
        "fair_status": last.get("status"),
        "fair_reason_code": last.get("reason_code"),
        "provider_id": last.get("provider_id"),
        "model_id": last.get("model_id"),
        "best_quality_score": last.get("best_quality_score"),
        "verification_state": last.get("verification_state"),
        "paid_inference_executed": last.get("paid_inference_executed"),
        "direct_backup_used": last.get("direct_backup_used", False),
        "direct_backup_may_bill": last.get("direct_backup_may_bill", False),
        "billing_authorization": last.get("billing_authorization"),
        "attempts": attempts,
        "concepts_per_call": per_call,
        "calls": calls,
    }
    if not collected:
        report = {**base_report, **(stop or {"status": "MODEL_OUTPUT_VALIDATION_ERROR", "error_type": "NoAcceptedConcepts"})}
        atomic_write_json(report_path, report)
        return report

    response = {
        "mechanism_id": mechanism_id,
        "concepts": collected,
        "response_provenance": {
            "request_source": str(request_path),
            "request_sha256": request_hash,
            "validation_contract_sha256": validation_contract,
            "provider_id": last.get("provider_id"),
            "model_id": last.get("model_id"),
            "calls": len(calls),
        },
    }
    validation = validate_response(response, request, config)
    atomic_write_json(response_path, response)
    accepted_count = len(validation["accepted"])
    report = {
        **base_report,
        "status": "VALIDATED" if accepted_count > 0 else "MODEL_OUTPUT_VALIDATION_ERROR",
        "error_type": None if accepted_count > 0 else "NoAcceptedConcepts",
        "model_response": str(response_path),
        "raw_output": raw_paths,
        "structurally_accepted": accepted_count,
        "structurally_rejected": len(validation["rejected"]),
        "concepts_requested": total,
        "concepts_beyond_request_dropped": dropped,
        "validation_rejection_summary": _rejection_error_summary(validation),
        "initial_validation_rejection_summary": _rejection_error_summary(validation),
        "validation_repair_attempted": False,
        "validation_repair_raw_output": None,
        "stopped_early": stop,
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
    provider_batch_status = batch_status(
        results,
        expected_count=len(paths),
        processed_count=len(results),
    )
    newly_validated_results = sum(
        str(item.get("status") or "") == "VALIDATED" for item in results
    )
    if (
        provider_batch_status == "PARTIAL"
        and results
        and newly_validated_results > 0
    ):
        # Only newly validated responses count as progress. Cached/skipped
        # responses preserve prior work but must not make a provider stall look
        # like fresh progress.
        provider_batch_status = "BATCH_PROGRESS"

    merge_status = str(merge_summary.get("status") or "")
    status = (
        "CONCEPT_CANDIDATES_READY"
        if merge_status == "CONCEPT_CANDIDATES_READY"
        else provider_batch_status
    )
    if status == "COMPLETE" and merge_status == "INCOMPLETE_MECHANISM_COVERAGE":
        # Every request ran, yet a mechanism has no valid concept: the stage is
        # not complete and triage must not start (D-129). Exit as partial.
        status = "INCOMPLETE_MECHANISM_COVERAGE"

    summary = {
        "status": status,
        "provider_batch_status": provider_batch_status,
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
        if result["status"] == "BATCH_PROGRESS":
            raise SystemExit(0)
        raise SystemExit(exit_code_for_status(result["status"]))


if __name__ == "__main__":
    main()
