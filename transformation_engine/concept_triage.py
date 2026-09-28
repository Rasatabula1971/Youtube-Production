"""FAIR-backed two-pass comparative triage for Transformation Engine concepts.

Pass 1 scores concepts in small resumable chunks so free providers are not asked
to return one oversized structured response for the whole candidate pool. The strongest concepts from
each chunk advance to a bounded finalist pool. Pass 2 compares those finalists
and produces the final 0-6 shortlist for the Human Concept Gate.

The full first-pass audit is preserved for every concept. Non-shortlisted
concepts remain available to the Human Concept Gate as explicit overrides.
"""

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
    atomic_write_json,
    atomic_write_text,
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

from transformation_engine import (
    CANDIDATES_FILE,
    OUTPUT_DIR,
    load_json,
    sha256_file,
)

TRIAGE_OUTPUT_FILE = OUTPUT_DIR / "concept_triage.json"
SHORTLIST_FILE = OUTPUT_DIR / "concept_candidates_triaged.json"
RUN_REPORT_FILE = OUTPUT_DIR / "concept_triage_run.json"
CHUNK_DIR = OUTPUT_DIR / "concept_triage_chunks"
FINAL_RAW_FILE = OUTPUT_DIR / "raw_concept_triage_final.txt"
FINAL_RESPONSE_FILE = OUTPUT_DIR / "concept_triage_final.json"

CHUNK_SIZE = 5
FINALISTS_PER_CHUNK = 2
MAX_FINALISTS = 10
MIN_SHORTLIST = 0
MAX_SHORTLIST = 6
ALLOWED_DECISIONS = {"SHORTLIST", "REWORK", "DROP"}
DIMENSIONS = (
    "channel_fit",
    "viewer_problem",
    "promise_clarity",
    "feasibility",
    "researchability",
    "originality",
    "overclaim_safety",
)


def response_schema(concepts: list[dict[str, Any]]) -> dict[str, Any]:
    """Small score-only schema for reliable free-provider structured output."""
    concept_ids = [str(item["concept_id"]) for item in concepts]
    score_item = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "concept_id",
            "overall_score",
            "dimension_scores",
            "rationale",
        ],
        "properties": {
            "concept_id": {"type": "string", "enum": concept_ids},
            "overall_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
            },
            "dimension_scores": {
                "type": "object",
                "additionalProperties": False,
                "required": list(DIMENSIONS),
                "properties": {
                    key: {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 5,
                    }
                    for key in DIMENSIONS
                },
            },
            "rationale": {"type": "string", "minLength": 1},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["scores", "summary"],
        "properties": {
            "scores": {
                "type": "array",
                "minItems": len(concept_ids),
                "maxItems": len(concept_ids),
                "items": score_item,
            },
            "summary": {"type": "string", "minLength": 1},
        },
    }


def compact_concepts(concepts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact = []
    for item in concepts:
        compact.append(
            {
                "concept_id": item.get("concept_id"),
                "mechanism_id": item.get("mechanism_id"),
                "working_title": item.get("working_title"),
                "premise": item.get("premise"),
                "audience_promise": item.get("audience_promise"),
                "viewer_problem": item.get("viewer_problem"),
                "viewer_moment": item.get("viewer_moment"),
                "desired_outcome": item.get("desired_outcome"),
                "content_gap": item.get("content_gap", {}),
                "channel_fit": item.get("channel_fit", {}),
                "title_clarity_test": item.get("title_clarity_test", {}),
                "format_intent": item.get("format_intent"),
                "mechanism_application": item.get("mechanism_application"),
                "transformation_method": item.get("transformation_method"),
                "research_questions": item.get("research_questions", []),
                "source_dependency_test": item.get("source_dependency_test", {}),
            }
        )
    return compact


def build_prompt(
    payload: dict[str, Any],
    maximum_chars: int,
    *,
    phase: str = "final",
) -> str:
    concepts = payload.get("concepts", [])
    if phase not in {"chunk", "final"}:
        raise ValueError("triage phase must be chunk or final")

    purpose = (
        "This is FIRST-PASS scoring for one small chunk. Score every concept "
        "honestly. Do not choose winners; deterministic code will advance the two "
        "highest-scoring concepts to the final comparative pass."
        if phase == "chunk"
        else (
            "This is FINAL comparative scoring across the strongest first-pass "
            "finalists. Do not produce a shortlist; deterministic code will derive "
            "SHORTLIST/REWORK/DROP from the scores and select at most six."
        )
    )

    prompt = (
        "You are the comparative concept scoring stage for a YouTube production "
        "system. Infer the intended channel/audience direction from the candidate "
        "pool and each candidate's channel_fit evidence. Return JSON only.\n\n"
        + purpose
        + "\n\nEvaluate EVERY concept independently and comparatively on seven "
        "dimensions, scored 0-5: channel_fit, viewer_problem, promise_clarity, "
        "feasibility, researchability, originality, overclaim_safety. Also provide "
        "an overall_score from 0-100 and a concise rationale.\n\n"
        "Scoring guidance:\n"
        "- 70-100 means strong enough to be eligible for the final shortlist.\n"
        "- 45-69 means useful but needs rework.\n"
        "- 0-44 means weak enough to drop from the default shortlist.\n\n"
        "Rules:\n"
        "1. Prefer concepts aligned with the intended channel/audience direction.\n"
        "2. Penalize promises that assume research conclusions before research exists.\n"
        "3. Penalize unrealistic, unsafe, or highly specialized original testing.\n"
        "4. Treat content_gap HYPOTHESIS/UNASSESSED honestly.\n"
        "5. Prefer concepts independently researchable with credible sources.\n"
        "6. Prefer clear viewer moments, concrete outcomes, and packageable payoff.\n"
        "7. Penalize terminology errors, false precision, and category mistakes.\n"
        "8. Do not reward a concept merely because it has a catchy title.\n"
        "9. Account for every concept exactly once.\n"
        "10. Return only scores and rationales; Python code derives decisions.\n\n"
        "CANDIDATES:\n"
        + json.dumps(
            compact_concepts(concepts),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    if len(prompt) > maximum_chars:
        raise ValueError(
            f"Concept triage prompt is {len(prompt):,} characters; maximum is "
            f"{maximum_chars:,}."
        )
    return prompt


def validate_scores(
    response: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = {str(item["concept_id"]) for item in candidates}
    scores = response.get("scores")
    if not isinstance(scores, list):
        raise ValueError("triage scores must be a list")

    mapped: dict[str, dict[str, Any]] = {}
    for item in scores:
        if not isinstance(item, dict):
            raise ValueError("every triage score must be an object")
        concept_id = str(item.get("concept_id", "")).strip()
        if concept_id not in expected:
            raise ValueError(f"unknown concept_id in triage: {concept_id}")
        if concept_id in mapped:
            raise ValueError(f"duplicate triage score: {concept_id}")

        score = int(item.get("overall_score", -1))
        if not 0 <= score <= 100:
            raise ValueError(f"invalid overall_score for {concept_id}")

        dimensions = item.get("dimension_scores")
        if not isinstance(dimensions, dict):
            raise ValueError(
                f"dimension_scores must be an object for {concept_id}"
            )
        normalized_dimensions: dict[str, int] = {}
        for key in DIMENSIONS:
            value = int(dimensions.get(key, -1))
            if not 0 <= value <= 5:
                raise ValueError(
                    f"invalid {key} score for {concept_id}"
                )
            normalized_dimensions[key] = value

        rationale = str(item.get("rationale", "")).strip()
        if not rationale:
            raise ValueError(f"rationale is required for {concept_id}")

        mapped[concept_id] = {
            "concept_id": concept_id,
            "overall_score": score,
            "dimension_scores": normalized_dimensions,
            "rationale": rationale,
        }

    if set(mapped) != expected:
        missing = sorted(expected - set(mapped))
        raise ValueError("triage omitted concept(s): " + ", ".join(missing))

    return {
        "scores": [mapped[cid] for cid in sorted(mapped)],
        "summary": str(response.get("summary", "")).strip(),
    }


def decision_for_score(score: int) -> str:
    if score >= 70:
        return "SHORTLIST"
    if score >= 45:
        return "REWORK"
    return "DROP"


def normalize_scored_triage(
    validated: dict[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    decisions = []
    for item in validated["scores"]:
        score = int(item["overall_score"])
        decisions.append(
            {
                **item,
                "decision": decision_for_score(score),
                "strengths": [],
                "risks": [],
            }
        )

    shortlist_ids: list[str] = []
    if phase == "final":
        eligible = [
            item
            for item in decisions
            if int(item["overall_score"]) >= 70
        ]
        ranked = sorted(eligible, key=decision_rank, reverse=True)
        shortlist_ids = [
            str(item["concept_id"])
            for item in ranked[:MAX_SHORTLIST]
        ]
        shortlist_set = set(shortlist_ids)
        for item in decisions:
            if (
                item["decision"] == "SHORTLIST"
                and item["concept_id"] not in shortlist_set
            ):
                item["decision"] = "REWORK"
                item["capped_from_shortlist"] = True

    return {
        "decisions": decisions,
        "shortlist_ids": shortlist_ids,
        "summary": validated.get("summary", ""),
    }


# Backwards-compatible validator retained for historical tests/artifacts.
def validate_triage(
    response: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    max_shortlist: int | None = None,
) -> dict[str, Any]:
    del max_shortlist
    if "scores" in response:
        return normalize_scored_triage(
            validate_scores(response, candidates),
            phase="final",
        )

    expected = {str(item["concept_id"]) for item in candidates}
    decisions = response.get("decisions")
    shortlist_ids = response.get("shortlist_ids")
    if not isinstance(decisions, list):
        raise ValueError("triage decisions must be a list")
    if not isinstance(shortlist_ids, list):
        raise ValueError("shortlist_ids must be a list")

    mapped: dict[str, dict[str, Any]] = {}
    for item in decisions:
        if not isinstance(item, dict):
            raise ValueError("every triage decision must be an object")
        concept_id = str(item.get("concept_id", "")).strip()
        if concept_id not in expected:
            raise ValueError(f"unknown concept_id in triage: {concept_id}")
        if concept_id in mapped:
            raise ValueError(f"duplicate triage decision: {concept_id}")
        decision = str(item.get("decision", "")).upper()
        if decision not in ALLOWED_DECISIONS:
            raise ValueError(f"invalid triage decision for {concept_id}")
        score = int(item.get("overall_score", -1))
        expected_decision = decision_for_score(score)
        if decision != expected_decision:
            raise ValueError(
                f"triage decision/score mismatch for {concept_id}: "
                f"{decision} with score {score}"
            )
        mapped[concept_id] = item

    if set(mapped) != expected:
        missing = sorted(expected - set(mapped))
        raise ValueError("triage omitted concept(s): " + ", ".join(missing))

    shortlist = [str(value) for value in shortlist_ids]
    if len(shortlist) != len(set(shortlist)):
        raise ValueError("shortlist_ids must be unique")
    if not set(shortlist).issubset(expected):
        raise ValueError("shortlist contains unknown concept_id")
    if len(shortlist) > min(MAX_SHORTLIST, len(expected)):
        raise ValueError("shortlist size is outside configured bounds")
    decision_shortlist = {
        cid
        for cid, item in mapped.items()
        if str(item.get("decision", "")).upper() == "SHORTLIST"
    }
    if set(shortlist) != decision_shortlist:
        raise ValueError(
            "shortlist_ids must exactly match concepts classified SHORTLIST"
        )

    return {
        "decisions": [mapped[cid] for cid in sorted(mapped)],
        "shortlist_ids": shortlist,
        "summary": str(response.get("summary", "")),
    }


def chunk_concepts(
    concepts: list[dict[str, Any]],
    *,
    chunk_size: int = CHUNK_SIZE,
) -> list[list[dict[str, Any]]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    return [
        concepts[index : index + chunk_size]
        for index in range(0, len(concepts), chunk_size)
    ]


def decision_rank(item: dict[str, Any]) -> tuple[int, int, str]:
    dimensions = item.get("dimension_scores", {})
    dimension_total = sum(
        int(dimensions.get(key, 0))
        for key in DIMENSIONS
        if isinstance(dimensions, dict)
    )
    return (
        int(item.get("overall_score", 0)),
        dimension_total,
        str(item.get("concept_id", "")),
    )


def select_finalist_ids(
    chunk_triages: list[dict[str, Any]],
    *,
    per_chunk: int = FINALISTS_PER_CHUNK,
    maximum: int = MAX_FINALISTS,
) -> list[str]:
    selected: list[dict[str, Any]] = []
    for triage in chunk_triages:
        ranked = sorted(
            triage.get("decisions", []),
            key=decision_rank,
            reverse=True,
        )
        selected.extend(ranked[:per_chunk])

    ranked_all = sorted(selected, key=decision_rank, reverse=True)
    seen: set[str] = set()
    finalist_ids: list[str] = []
    for item in ranked_all:
        concept_id = str(item.get("concept_id", ""))
        if not concept_id or concept_id in seen:
            continue
        seen.add(concept_id)
        finalist_ids.append(concept_id)
        if len(finalist_ids) >= maximum:
            break
    return finalist_ids


def build_shortlist_payload(
    candidates_payload: dict[str, Any],
    triage: dict[str, Any],
    source_hash: str,
) -> dict[str, Any]:
    by_id = {
        str(item["concept_id"]): item for item in candidates_payload.get("concepts", [])
    }
    decisions = {str(item["concept_id"]): item for item in triage["decisions"]}
    concepts = []
    overrides = []
    shortlist_ids = set(triage["shortlist_ids"])
    for concept_id, original in by_id.items():
        concept = dict(original)
        concept["llm_triage"] = decisions[concept_id]
        if concept_id in shortlist_ids:
            concepts.append(concept)
        else:
            overrides.append(concept)

    return {
        "artifact": "triaged_concept_candidates",
        "source_candidates_sha256": source_hash,
        "concept_count": len(concepts),
        "concepts": concepts,
        "override_concepts": overrides,
        "triage_summary": triage.get("summary"),
        "notes": [
            "Triage is an LLM prefilter, not human approval.",
            "SHORTLIST concepts enter the Human Concept Gate by default.",
            "REWORK and DROP concepts remain available as explicit human overrides.",
            "Triage used resumable 5-concept first-pass chunks followed by a bounded finalist comparison.",
        ],
    }


def fair_call(
    concepts: list[dict[str, Any]],
    *,
    phase: str,
    client_id: str,
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None, str]:
    prompt = build_prompt(
        {"concepts": concepts},
        int(config["runner"].get("max_prompt_chars", 95000)),
        phase=phase,
    )
    schema = response_schema(concepts)
    schema_chars = len(json.dumps(schema, separators=(",", ":")))
    if schema_chars > 19000:
        raise ValueError(
            f"Generated triage schema is {schema_chars:,} characters; "
            "FAIR supports schemas below 20,000 characters."
        )

    paths = resolve_fair_paths(config)
    payload = bridge_payload(
        action="solve",
        prompt=prompt,
        schema=schema,
        config=config,
        paths=paths,
    )
    payload["settings"]["client_id"] = client_id

    try:
        result = call_fair_bridge(
            payload,
            python_executable=paths["python"],
            timeout_seconds=float(
                config["runner"].get("subprocess_timeout_seconds", 300)
            ),
        )
    except Exception as exc:
        return (
            {
                "status": "RUNNER_ERROR",
                "error_type": type(exc).__name__,
            },
            None,
            "",
        )

    base = {
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
        return ({**base, "status": "COST_POLICY_VIOLATION"}, None, "")

    if result.get("status") != "ACCEPTED":
        return (
            {
                **base,
                "status": (
                    "MODEL_ESCALATION_REQUIRED"
                    if result.get("status") == "ESCALATION_REQUIRED"
                    else "MODEL_FAILED"
                ),
            },
            None,
            "",
        )

    raw = str(result.get("output") or "")
    try:
        parsed = parse_model_json(raw)
        validated = validate_scores(parsed, concepts)
        triage = normalize_scored_triage(validated, phase=phase)
    except Exception as exc:
        return (
            {
                **base,
                "status": "MODEL_OUTPUT_VALIDATION_ERROR",
                "error_type": type(exc).__name__,
                "message": str(exc)[:1000],
            },
            None,
            raw,
        )

    return ({**base, "status": "VALIDATED"}, triage, raw)


def chunk_paths(index: int) -> tuple[Path, Path, Path]:
    stem = f"chunk_{index:03d}"
    return (
        CHUNK_DIR / f"{stem}.json",
        CHUNK_DIR / f"{stem}.report.json",
        CHUNK_DIR / f"{stem}.raw.txt",
    )


def load_current_chunk(
    index: int,
    *,
    source_hash: str,
    concept_ids: list[str],
) -> dict[str, Any] | None:
    triage_path, report_path, _ = chunk_paths(index)
    if not triage_path.exists() or not report_path.exists():
        return None
    try:
        triage_artifact = load_json(triage_path)
        report = load_json(report_path)
    except (OSError, json.JSONDecodeError):
        return None
    if (
        report.get("status") == "VALIDATED"
        and triage_artifact.get("source_candidates_sha256") == source_hash
        and triage_artifact.get("concept_ids") == concept_ids
    ):
        return triage_artifact
    return None


def run_chunk(
    concepts: list[dict[str, Any]],
    *,
    index: int,
    source_hash: str,
    config: dict[str, Any],
    force: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    concept_ids = [str(item["concept_id"]) for item in concepts]
    triage_path, report_path, raw_path = chunk_paths(index)
    if not force:
        current = load_current_chunk(
            index,
            source_hash=source_hash,
            concept_ids=concept_ids,
        )
        if current is not None:
            return (
                {
                    "status": "SKIPPED_ALREADY_VALIDATED",
                    "chunk": index,
                    "concept_ids": concept_ids,
                    "triage": str(triage_path),
                },
                current,
            )

    report, triage, raw = fair_call(
        concepts,
        phase="chunk",
        client_id=f"youtube-concept-triage-chunk-{index:03d}",
        config=config,
    )
    report = {
        **report,
        "chunk": index,
        "concept_ids": concept_ids,
        "source_candidates_sha256": source_hash,
    }
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    if raw:
        atomic_write_text(raw_path, raw)

    if triage is None:
        atomic_write_json(report_path, report)
        return report, None

    artifact = {
        "artifact": "concept_triage_chunk",
        "chunk": index,
        "source_candidates_sha256": source_hash,
        "concept_ids": concept_ids,
        **triage,
        "model_provenance": {
            "provider_id": report.get("provider_id"),
            "model_id": report.get("model_id"),
            "fair_request_id": report.get("fair_request_id"),
        },
    }
    atomic_write_json(triage_path, artifact)
    atomic_write_json(report_path, report)
    return report, artifact


def merge_full_audit(
    first_pass: list[dict[str, Any]],
    final_triage: dict[str, Any],
    finalist_ids: list[str],
) -> list[dict[str, Any]]:
    first_map = {
        str(item["concept_id"]): dict(item)
        for triage in first_pass
        for item in triage.get("decisions", [])
    }
    final_map = {
        str(item["concept_id"]): dict(item)
        for item in final_triage.get("decisions", [])
    }
    finalist_set = set(finalist_ids)

    merged = []
    for concept_id in sorted(first_map):
        first = first_map[concept_id]
        if concept_id in finalist_set and concept_id in final_map:
            final = final_map[concept_id]
            final["first_pass"] = {
                "decision": first.get("decision"),
                "overall_score": first.get("overall_score"),
                "dimension_scores": first.get("dimension_scores", {}),
                "rationale": first.get("rationale"),
            }
            final["final_selection"] = (
                "FINAL_SHORTLIST"
                if concept_id in set(final_triage.get("shortlist_ids", []))
                else "FINALIST_NOT_SHORTLISTED"
            )
            final["triage_stage"] = "FINALIST"
            merged.append(final)
        else:
            first["first_pass_decision"] = first.get("decision")
            first["decision"] = "NOT_FINALIST"
            first["final_selection"] = "NOT_FINALIST"
            first["triage_stage"] = "FIRST_PASS_ONLY"
            merged.append(first)
    return merged


def run_first_pass(
    chunks: list[list[dict[str, Any]]],
    *,
    source_hash: str,
    config: dict[str, Any],
    force: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[int]]:
    chunk_results: list[dict[str, Any]] = []
    chunk_triages: list[dict[str, Any]] = []
    failed_chunks: list[int] = []
    for index, chunk in enumerate(chunks, start=1):
        result, triage = run_chunk(
            chunk,
            index=index,
            source_hash=source_hash,
            config=config,
            force=force,
        )
        chunk_results.append(result)
        if triage is None:
            failed_chunks.append(index)
            continue
        chunk_triages.append(triage)
    return chunk_results, chunk_triages, failed_chunks


def run(*, force: bool = False) -> dict[str, Any]:
    if not CANDIDATES_FILE.exists():
        return {
            "status": "WAITING_FOR_CONCEPT_CANDIDATES",
            "candidates": str(CANDIDATES_FILE),
        }

    candidates_payload = load_json(CANDIDATES_FILE)
    concepts = candidates_payload.get("concepts", [])
    if not isinstance(concepts, list) or not concepts:
        raise ValueError("Concept triage requires at least one candidate")

    source_hash = sha256_file(CANDIDATES_FILE)
    if (
        not force
        and TRIAGE_OUTPUT_FILE.exists()
        and SHORTLIST_FILE.exists()
        and RUN_REPORT_FILE.exists()
    ):
        existing = load_json(TRIAGE_OUTPUT_FILE)
        shortlist = load_json(SHORTLIST_FILE)
        if (
            existing.get("source_candidates_sha256") == source_hash
            and shortlist.get("source_candidates_sha256") == source_hash
        ):
            return {
                "status": "SKIPPED_ALREADY_TRIAGED",
                "candidates_found": len(concepts),
                "shortlisted": int(shortlist.get("concept_count", 0)),
                "triage": str(TRIAGE_OUTPUT_FILE),
                "shortlist": str(SHORTLIST_FILE),
            }

    config = load_runner_config()
    chunks = chunk_concepts(concepts)
    chunk_results, chunk_triages, failed_chunks = run_first_pass(
        chunks,
        source_hash=source_hash,
        config=config,
        force=force,
    )

    if failed_chunks:
        report = {
            "status": "PARTIAL",
            "phase": "FIRST_PASS",
            "source_candidates": str(CANDIDATES_FILE),
            "source_candidates_sha256": source_hash,
            "candidates_found": len(concepts),
            "chunks_total": len(chunks),
            "chunks_complete": len(chunk_triages),
            "failed_chunks": failed_chunks,
            "retryable_failed_chunks": failed_chunks,
            "chunk_results": chunk_results,
        }
        atomic_write_json(RUN_REPORT_FILE, report)
        return report

    finalist_ids = select_finalist_ids(chunk_triages)
    by_id = {str(item["concept_id"]): item for item in concepts}
    finalists = [by_id[concept_id] for concept_id in finalist_ids]

    final_report, final_triage, final_raw = fair_call(
        finalists,
        phase="final",
        client_id="youtube-concept-triage-final",
        config=config,
    )
    if final_raw:
        atomic_write_text(FINAL_RAW_FILE, final_raw)

    if final_triage is None:
        report = {
            **final_report,
            "status": "PARTIAL",
            "phase": "FINAL_PASS",
            "source_candidates": str(CANDIDATES_FILE),
            "source_candidates_sha256": source_hash,
            "candidates_found": len(concepts),
            "chunks_total": len(chunks),
            "chunks_complete": len(chunk_triages),
            "finalists": finalist_ids,
            "chunk_results": chunk_results,
        }
        atomic_write_json(RUN_REPORT_FILE, report)
        return report

    atomic_write_json(
        FINAL_RESPONSE_FILE,
        {
            "artifact": "concept_triage_finalists",
            "source_candidates_sha256": source_hash,
            "finalist_ids": finalist_ids,
            **final_triage,
            "model_provenance": {
                "provider_id": final_report.get("provider_id"),
                "model_id": final_report.get("model_id"),
                "fair_request_id": final_report.get("fair_request_id"),
            },
        },
    )

    full_decisions = merge_full_audit(
        chunk_triages,
        final_triage,
        finalist_ids,
    )
    triage_artifact = {
        "artifact": "concept_llm_triage",
        "triage_design": "TWO_PASS_CHUNKED",
        "source_candidates": str(CANDIDATES_FILE),
        "source_candidates_sha256": source_hash,
        "candidate_count": len(concepts),
        "chunk_size": CHUNK_SIZE,
        "chunks": len(chunks),
        "finalist_count": len(finalist_ids),
        "finalist_ids": finalist_ids,
        "decisions": full_decisions,
        "shortlist_ids": final_triage["shortlist_ids"],
        "summary": final_triage["summary"],
        "first_pass": {
            "chunks": [
                {
                    "chunk": item.get("chunk"),
                    "concept_ids": item.get("concept_ids", []),
                    "summary": item.get("summary"),
                }
                for item in chunk_triages
            ]
        },
        "final_model_provenance": {
            "provider_id": final_report.get("provider_id"),
            "model_id": final_report.get("model_id"),
            "fair_request_id": final_report.get("fair_request_id"),
        },
    }
    shortlist = build_shortlist_payload(
        candidates_payload,
        triage_artifact,
        source_hash,
    )

    atomic_write_json(TRIAGE_OUTPUT_FILE, triage_artifact)
    atomic_write_json(SHORTLIST_FILE, shortlist)

    counts = {
        value: sum(1 for item in full_decisions if item.get("decision") == value)
        for value in ("SHORTLIST", "REWORK", "DROP")
    }
    report = {
        **final_report,
        "status": "TRIAGE_COMPLETE",
        "triage_design": "TWO_PASS_CHUNKED",
        "source_candidates": str(CANDIDATES_FILE),
        "source_candidates_sha256": source_hash,
        "candidates_found": len(concepts),
        "chunks_total": len(chunks),
        "chunks_complete": len(chunk_triages),
        "finalist_count": len(finalist_ids),
        "finalists": finalist_ids,
        "shortlisted": len(final_triage["shortlist_ids"]),
        "rework": counts["REWORK"],
        "dropped": counts["DROP"],
        "chunk_results": chunk_results,
        "triage": str(TRIAGE_OUTPUT_FILE),
        "shortlist": str(SHORTLIST_FILE),
    }
    atomic_write_json(RUN_REPORT_FILE, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FAIR-backed two-pass Concept Candidate Triage"
    )
    parser.add_argument("--mode", choices=("run",), required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run(force=args.force)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(exit_code_for_status(result.get("status", "FAILED")))


if __name__ == "__main__":
    main()
