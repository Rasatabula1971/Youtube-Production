"""FAIR-backed comparative triage for Transformation Engine concepts.

Consumes all structurally valid concept candidates, asks FAIR to classify every
candidate as SHORTLIST, REWORK, or DROP, and writes a bounded shortlist for the
human Concept Gate. The full audit is preserved.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
EXP2_DIR = PROJECT_ROOT / "experiment_02_analysis"
if str(EXP2_DIR) not in sys.path:
    sys.path.insert(0, str(EXP2_DIR))

from analysis_model_runner import (  # noqa: E402
    bridge_payload,
    call_fair_bridge,
    load_runner_config,
    parse_model_json,
    resolve_fair_paths,
    safe_attempts,
)

from transformation_engine import (  # noqa: E402
    CANDIDATES_FILE,
    OUTPUT_DIR,
    load_json,
    sha256_file,
)

TRIAGE_OUTPUT_FILE = OUTPUT_DIR / "concept_triage.json"
SHORTLIST_FILE = OUTPUT_DIR / "concept_candidates_triaged.json"
RAW_OUTPUT_FILE = OUTPUT_DIR / "raw_concept_triage.txt"
RUN_REPORT_FILE = OUTPUT_DIR / "concept_triage_run.json"

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
    concept_ids = [str(item["concept_id"]) for item in concepts]
    decision_item = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "concept_id",
            "decision",
            "overall_score",
            "dimension_scores",
            "strengths",
            "risks",
            "rationale",
        ],
        "properties": {
            "concept_id": {"type": "string", "enum": concept_ids},
            "decision": {
                "type": "string",
                "enum": ["SHORTLIST", "REWORK", "DROP"],
            },
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
            "strengths": {
                "type": "array",
                "maxItems": 4,
                "items": {"type": "string", "minLength": 1},
            },
            "risks": {
                "type": "array",
                "maxItems": 4,
                "items": {"type": "string", "minLength": 1},
            },
            "rationale": {"type": "string", "minLength": 1},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["decisions", "shortlist_ids", "summary"],
        "properties": {
            "decisions": {
                "type": "array",
                "minItems": len(concept_ids),
                "maxItems": len(concept_ids),
                "items": decision_item,
            },
            "shortlist_ids": {
                "type": "array",
                "minItems": MIN_SHORTLIST,
                "maxItems": min(MAX_SHORTLIST, len(concept_ids)),
                "uniqueItems": True,
                "items": {"type": "string", "enum": concept_ids},
            },
            "summary": {"type": "string", "minLength": 1},
        },
    }


def build_prompt(payload: dict[str, Any], maximum_chars: int) -> str:
    concepts = payload.get("concepts", [])
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
                "source_dependency_test": item.get(
                    "source_dependency_test", {}
                ),
            }
        )

    prompt = (
        "You are the comparative concept triage stage for a YouTube production "
        "system. Infer the intended channel/audience direction from the candidate "
        "pool and each candidate's channel_fit evidence. Return JSON only.\n\n"
        "Your job is NOT to approve a concept for production. Your job is to reduce "
        "a large structurally-valid candidate pool to the strongest 0-6 concepts for "
        "a later Human Concept Gate.\n\n"
        "Evaluate EVERY concept independently and comparatively on seven dimensions, "
        "scored 0-5: channel_fit, viewer_problem, promise_clarity, feasibility, "
        "researchability, originality, overclaim_safety.\n\n"
        "Decision meanings:\n"
        "- SHORTLIST: overall_score 70-100; strong enough to spend human review and research effort on now.\n"
        "- REWORK: overall_score 45-69; useful core idea but wording, promise, feasibility, precision, or channel fit needs correction.\n"
        "- DROP: overall_score 0-44; weak, off-channel, redundant, confused, or unjustifiably difficult compared with stronger alternatives.\n\n"
        "Rules:\n"
        "1. Prefer concepts aligned with the intended channel/audience direction "
        "described across the candidate pool. Penalize mechanism transfer into unrelated "
        "fields unless the candidate makes a strong, explicit channel-fit case.\n"
        "2. Penalize promises that assume research conclusions before research exists "
        "(for example 'optimal', 'exact', 'safest', or specific performance outcomes).\n"
        "3. Penalize concepts whose proposed test would require unrealistic, unsafe, "
        "or highly specialized original testing when credible independent research may "
        "not exist.\n"
        "4. Treat content_gap HYPOTHESIS/UNASSESSED honestly; do not reward it as proven demand.\n"
        "5. Prefer concepts that can be independently researched with credible sources.\n"
        "6. Prefer clear viewer moments, concrete outcomes, and a packageable curiosity/payoff.\n"
        "7. Penalize terminology errors, false precision, category mistakes, and "
        "comparisons that confuse distinct technical variables.\n"
        "8. Do not reward a concept merely because it has a catchy title.\n"
        "9. Account for every concept exactly once.\n"
        "10. shortlist_ids must contain exactly the concepts you classify SHORTLIST, "
        "with a minimum of 0 and maximum of 6. If none deserve human time, return an empty shortlist.\n"
        "11. Decision and overall_score must obey the thresholds above exactly.\n\n"
        "CANDIDATES:\n"
        + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt) > maximum_chars:
        raise ValueError(
            f"Concept triage prompt is {len(prompt):,} characters; maximum is "
            f"{maximum_chars:,}."
        )
    return prompt


def validate_triage(
    response: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
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
        expected_decision = (
            "SHORTLIST" if score >= 70
            else "REWORK" if score >= 45
            else "DROP"
        )
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
    if not MIN_SHORTLIST <= len(shortlist) <= min(MAX_SHORTLIST, len(expected)):
        raise ValueError("shortlist size is outside configured bounds")
    if not set(shortlist).issubset(expected):
        raise ValueError("shortlist contains unknown concept_id")

    decision_shortlist = {
        cid
        for cid, item in mapped.items()
        if str(item.get("decision")).upper() == "SHORTLIST"
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


def build_shortlist_payload(
    candidates_payload: dict[str, Any],
    triage: dict[str, Any],
    source_hash: str,
) -> dict[str, Any]:
    by_id = {
        str(item["concept_id"]): item
        for item in candidates_payload.get("concepts", [])
    }
    decisions = {
        str(item["concept_id"]): item
        for item in triage["decisions"]
    }
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
            "Only SHORTLIST concepts enter the Human Concept Gate.",
            "REWORK and DROP decisions remain in concept_triage.json.",
        ],
    }


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
    prompt = build_prompt(
        candidates_payload,
        int(config["runner"].get("max_prompt_chars", 95000)),
    )
    schema = response_schema(concepts)
    paths = resolve_fair_paths(config)
    payload = bridge_payload(
        action="solve",
        prompt=prompt,
        schema=schema,
        config=config,
        paths=paths,
    )
    payload["settings"]["client_id"] = "youtube-concept-triage"

    result = call_fair_bridge(
        payload,
        python_executable=paths["python"],
        timeout_seconds=float(
            config["runner"].get("subprocess_timeout_seconds", 300)
        ),
    )

    base_report = {
        "source_candidates": str(CANDIDATES_FILE),
        "source_candidates_sha256": source_hash,
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
        report = {**base_report, "status": "COST_POLICY_VIOLATION"}
        RUN_REPORT_FILE.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return report

    if result.get("status") != "ACCEPTED":
        report = {
            **base_report,
            "status": (
                "MODEL_ESCALATION_REQUIRED"
                if result.get("status") == "ESCALATION_REQUIRED"
                else "MODEL_FAILED"
            ),
        }
        RUN_REPORT_FILE.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return report

    raw = str(result.get("output") or "")
    RAW_OUTPUT_FILE.write_text(raw, encoding="utf-8")
    parsed = parse_model_json(raw)
    triage = validate_triage(parsed, concepts)

    triage_artifact = {
        "artifact": "concept_llm_triage",
        "source_candidates": str(CANDIDATES_FILE),
        "source_candidates_sha256": source_hash,
        "candidate_count": len(concepts),
        **triage,
        "model_provenance": {
            "provider_id": result.get("provider_id"),
            "model_id": result.get("model_id"),
            "fair_request_id": result.get("request_id"),
        },
    }
    shortlist = build_shortlist_payload(
        candidates_payload,
        triage,
        source_hash,
    )

    TRIAGE_OUTPUT_FILE.write_text(
        json.dumps(triage_artifact, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    SHORTLIST_FILE.write_text(
        json.dumps(shortlist, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    counts = {
        value: sum(
            1
            for item in triage["decisions"]
            if item["decision"] == value
        )
        for value in ("SHORTLIST", "REWORK", "DROP")
    }
    report = {
        **base_report,
        "status": "TRIAGE_COMPLETE",
        "candidates_found": len(concepts),
        "shortlisted": counts["SHORTLIST"],
        "rework": counts["REWORK"],
        "dropped": counts["DROP"],
        "triage": str(TRIAGE_OUTPUT_FILE),
        "shortlist": str(SHORTLIST_FILE),
    }
    RUN_REPORT_FILE.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FAIR-backed Concept Candidate Triage"
    )
    parser.add_argument("--mode", choices=("run",), required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(force=args.force), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
