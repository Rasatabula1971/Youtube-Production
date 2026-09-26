"""Human Concept Gate for Transformation Engine candidates.

Requires an explicit ACCEPT / REWORK / REJECT decision for every concept.
ACCEPT requires all configured human criteria to be affirmed. Only accepted
concepts enter the Research Engine handoff.

No model or network calls are made.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "concept_gate_config.json"

OUTPUT_DIR = HERE / "output"
DEFAULT_CANDIDATES = OUTPUT_DIR / "concept_candidates.json"
REVIEW_REQUEST_FILE = OUTPUT_DIR / "concept_gate_request.json"
REVIEWED_FILE = OUTPUT_DIR / "concept_gate_reviewed.json"
RESEARCH_HANDOFF_FILE = OUTPUT_DIR / "research_handoff.json"
SUMMARY_FILE = OUTPUT_DIR / "concept_gate_summary.json"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_FILE)
    required = {
        "required_accept_criteria",
        "require_reviewer_name",
    }
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit(
            "Concept Gate config is missing: " + ", ".join(missing)
        )
    return config


def build_review_request(
    candidates_payload: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    concepts = candidates_payload.get("concepts", [])
    if not isinstance(concepts, list):
        raise ValueError("concept_candidates concepts must be a list")

    items = []
    seen_ids: set[str] = set()
    for concept in concepts:
        concept_id = str(concept.get("concept_id", "")).strip()
        if not concept_id:
            raise ValueError("Every concept candidate requires concept_id")
        if concept_id in seen_ids:
            raise ValueError(
                f"Duplicate concept_id in candidates: {concept_id}"
            )
        seen_ids.add(concept_id)

        items.append(
            {
                "concept_id": concept_id,
                "mechanism_id": concept.get("mechanism_id"),
                "mechanism_label": concept.get("mechanism_label"),
                "working_title": concept.get("working_title"),
                "premise": concept.get("premise"),
                "audience_promise": concept.get("audience_promise"),
                "format_intent": concept.get("format_intent"),
                "mechanism_application": concept.get(
                    "mechanism_application"
                ),
                "transformation_method": concept.get(
                    "transformation_method"
                ),
                "research_questions": concept.get(
                    "research_questions", []
                ),
                "source_dependency_test": concept.get(
                    "source_dependency_test", {}
                ),
                "required_accept_criteria": list(
                    config["required_accept_criteria"]
                ),
            }
        )

    return {
        "request_type": "human_concept_gate",
        "concept_count": len(items),
        "criteria": {
            "originality_clear": (
                "The concept is genuinely distinct from the source examples."
            ),
            "audience_promise_clear": (
                "The viewer can understand what value or answer the concept promises."
            ),
            "source_independent": (
                "The concept retains its main value without source wording, footage, story, personality, or exact execution."
            ),
            "feasible": (
                "The concept appears realistically producible with available resources."
            ),
            "researchable": (
                "The concept can be supported through independent research before scripting."
            ),
        },
        "items": items,
        "response_schema": {
            "reviewer": "reviewer name or identifier",
            "decisions": [
                {
                    "concept_id": "exact concept_id",
                    "decision": "ACCEPT|REWORK|REJECT",
                    "criteria": {
                        criterion: True
                        for criterion in config[
                            "required_accept_criteria"
                        ]
                    },
                    "note": "required when REWORK, optional otherwise",
                }
            ],
            "overall_note": "optional",
        },
        "notes": [
            "No concept score is calculated.",
            "ACCEPT requires every configured criterion to be true.",
            "REWORK preserves the concept for revision but does not send it to research.",
            "REJECT removes the concept from the forward handoff.",
        ],
    }


def validate_decisions(
    request: dict[str, Any],
    response: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    reviewer = str(response.get("reviewer", "")).strip()
    if config["require_reviewer_name"] and not reviewer:
        raise ValueError("Concept Gate response requires reviewer")

    decisions = response.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("Concept Gate decisions must be a list")

    expected = {
        str(item["concept_id"])
        for item in request.get("items", [])
    }
    mapped: dict[str, dict[str, Any]] = {}

    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            raise ValueError(f"Decision {index} must be an object")

        concept_id = str(
            decision.get("concept_id", "")
        ).strip()
        if concept_id not in expected:
            raise ValueError(
                f"Unknown concept_id in gate response: {concept_id}"
            )
        if concept_id in mapped:
            raise ValueError(
                f"Duplicate decision for concept_id: {concept_id}"
            )

        value = str(
            decision.get("decision", "")
        ).strip().upper()
        if value not in {"ACCEPT", "REWORK", "REJECT"}:
            raise ValueError(
                f"Invalid decision for {concept_id}: {value!r}"
            )

        criteria = decision.get("criteria")
        if not isinstance(criteria, dict):
            raise ValueError(
                f"Decision criteria are required for {concept_id}"
            )

        required_criteria = config["required_accept_criteria"]
        missing_criteria = [
            criterion
            for criterion in required_criteria
            if criterion not in criteria
        ]
        if missing_criteria:
            raise ValueError(
                f"Missing criteria for {concept_id}: "
                + ", ".join(missing_criteria)
            )

        normalized_criteria = {
            criterion: criteria.get(criterion) is True
            for criterion in required_criteria
        }

        note = str(decision.get("note", "") or "").strip()
        if value == "ACCEPT" and not all(
            normalized_criteria.values()
        ):
            raise ValueError(
                f"ACCEPT requires every criterion true for {concept_id}"
            )
        if value == "REWORK" and not note:
            raise ValueError(
                f"REWORK requires a note for {concept_id}"
            )

        mapped[concept_id] = {
            "concept_id": concept_id,
            "decision": value,
            "criteria": normalized_criteria,
            "note": note,
        }

    missing = sorted(expected - set(mapped))
    if missing:
        raise ValueError(
            "Concept Gate is incomplete; missing decisions for: "
            + ", ".join(missing)
        )

    return mapped


def apply_gate(
    candidates_payload: dict[str, Any],
    request: dict[str, Any],
    response: dict[str, Any],
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    mapped = validate_decisions(request, response, config)
    concepts = candidates_payload.get("concepts", [])
    by_id = {
        str(concept["concept_id"]): concept
        for concept in concepts
    }

    reviewer = str(response.get("reviewer", "")).strip()
    reviewed_at = datetime.now(timezone.utc).isoformat()

    buckets = {
        "accepted": [],
        "rework": [],
        "rejected": [],
    }

    for concept_id in sorted(mapped):
        decision = mapped[concept_id]
        concept = dict(by_id[concept_id])
        concept["concept_gate"] = {
            "decision": decision["decision"],
            "criteria": decision["criteria"],
            "note": decision["note"],
            "reviewer": reviewer,
            "reviewed_at": reviewed_at,
        }

        if decision["decision"] == "ACCEPT":
            buckets["accepted"].append(concept)
        elif decision["decision"] == "REWORK":
            buckets["rework"].append(concept)
        else:
            buckets["rejected"].append(concept)

    reviewed = {
        "artifact": "concept_gate_reviewed",
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "overall_note": str(
            response.get("overall_note", "") or ""
        ),
        "accepted": buckets["accepted"],
        "rework": buckets["rework"],
        "rejected": buckets["rejected"],
        "counts": {
            key: len(value)
            for key, value in buckets.items()
        },
        "notes": [
            "No concept ranking or composite score is calculated.",
            "Only ACCEPT concepts are eligible for the Research Engine handoff.",
        ],
    }

    research_handoff = {
        "artifact": "research_handoff",
        "status": (
            "READY_FOR_RESEARCH"
            if buckets["accepted"]
            else "NO_ACCEPTED_CONCEPTS"
        ),
        "concept_count": len(buckets["accepted"]),
        "concepts": [
            {
                "concept_id": concept["concept_id"],
                "mechanism_id": concept.get("mechanism_id"),
                "mechanism_label": concept.get(
                    "mechanism_label"
                ),
                "working_title": concept.get("working_title"),
                "premise": concept.get("premise"),
                "audience_promise": concept.get(
                    "audience_promise"
                ),
                "format_intent": concept.get("format_intent"),
                "mechanism_application": concept.get(
                    "mechanism_application"
                ),
                "transformation_method": concept.get(
                    "transformation_method"
                ),
                "research_questions": concept.get(
                    "research_questions", []
                ),
                "source_dependency_test": concept.get(
                    "source_dependency_test", {}
                ),
                "concept_gate": concept["concept_gate"],
            }
            for concept in buckets["accepted"]
        ],
        "notes": [
            "Working titles are not final packaging.",
            "Research must independently verify factual claims before scripting.",
        ],
    }

    return reviewed, research_handoff


def run_prepare(candidates_path: Path) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not candidates_path.exists():
        summary = {
            "status": "WAITING_FOR_CONCEPT_CANDIDATES",
            "candidates": str(candidates_path),
            "reviewable_concepts": 0,
        }
        SUMMARY_FILE.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return summary

    candidates = load_json(candidates_path)
    config = load_config()
    request = build_review_request(candidates, config)
    REVIEW_REQUEST_FILE.write_text(
        json.dumps(request, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = {
        "status": (
            "CONCEPT_GATE_READY"
            if request["concept_count"]
            else "NO_CONCEPTS_TO_REVIEW"
        ),
        "reviewable_concepts": request["concept_count"],
        "request": str(REVIEW_REQUEST_FILE),
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def run_apply(
    candidates_path: Path,
    response_path: Path,
) -> dict[str, Any]:
    candidates = load_json(candidates_path)
    request = load_json(REVIEW_REQUEST_FILE)
    response = load_json(response_path)
    config = load_config()

    reviewed, research_handoff = apply_gate(
        candidates,
        request,
        response,
        config,
    )

    REVIEWED_FILE.write_text(
        json.dumps(reviewed, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    RESEARCH_HANDOFF_FILE.write_text(
        json.dumps(
            research_handoff,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = {
        "status": research_handoff["status"],
        "accepted": reviewed["counts"]["accepted"],
        "rework": reviewed["counts"]["rework"],
        "rejected": reviewed["counts"]["rejected"],
        "reviewed_file": str(REVIEWED_FILE),
        "research_handoff": str(RESEARCH_HANDOFF_FILE),
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Human Concept Gate"
    )
    parser.add_argument(
        "--mode",
        choices=("prepare", "apply"),
        required=True,
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=DEFAULT_CANDIDATES,
    )
    parser.add_argument(
        "--response",
        type=Path,
        default=None,
    )
    args = parser.parse_args()

    if args.mode == "prepare":
        result = run_prepare(args.candidates.resolve())
    else:
        if args.response is None:
            raise SystemExit(
                "--response is required for Concept Gate apply"
            )
        result = run_apply(
            args.candidates.resolve(),
            args.response.resolve(),
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
