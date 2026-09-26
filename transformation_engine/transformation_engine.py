"""Transformation Engine framework.

Consumes the Experiment 02 transformation handoff and prepares mechanism-bound
concept-generation requests. Returned concepts are validated structurally and
must pass the Source Dependency Test before entering the Concept Gate.

No model, network, or YouTube API calls are made here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent

CONFIG_FILE = HERE / "transformation_config.json"
DEFAULT_HANDOFF = (
    PROJECT_ROOT
    / "experiment_02_analysis"
    / "output"
    / "synthesis"
    / "transformation_handoff.json"
)

OUTPUT_DIR = HERE / "output"
REQUESTS_DIR = OUTPUT_DIR / "concept_requests"
RESPONSES_DIR = OUTPUT_DIR / "concept_responses"
CANDIDATES_FILE = OUTPUT_DIR / "concept_candidates.json"
REJECTED_FILE = OUTPUT_DIR / "rejected_concepts.json"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_FILE)
    required = {
        "concepts_per_mechanism",
        "allowed_format_intents",
        "require_ready_handoff",
        "minimum_research_questions",
    }
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit(
            "Transformation config is missing: " + ", ".join(missing)
        )
    return config


def safe_slug(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in "-_." else "_"
        for char in value
    ).strip("._")
    return cleaned or "unknown"


def ready_entries(
    handoff: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    entries = handoff.get("entries", [])
    if not isinstance(entries, list):
        return []

    if not config["require_ready_handoff"]:
        return list(entries)

    return [
        entry
        for entry in entries
        if entry.get("handoff_status")
        == "READY_FOR_TRANSFORMATION_ENGINE"
    ]


def build_concept_request(
    entry: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    mechanism_id = str(entry.get("mechanism_id", "")).strip()
    if not mechanism_id:
        raise ValueError("Transformation handoff entry requires mechanism_id")

    source_video_ids = list(
        entry.get("replication", {}).get("video_ids", [])
    )

    return {
        "request_type": "transformation_concept_generation",
        "mechanism_id": mechanism_id,
        "mechanism_label": entry.get("label"),
        "pattern_state": entry.get("pattern_state"),
        "replication": entry.get("replication", {}),
        "scope": entry.get("scope", {}),
        "transferable_descriptions": entry.get(
            "transferable_descriptions", []
        ),
        "observed_examples": entry.get("observed_examples", []),
        "source_specific_elements_to_avoid": entry.get(
            "source_specific_elements_to_avoid", []
        ),
        "existing_transformation_directions": entry.get(
            "existing_transformation_directions", []
        ),
        "source_video_ids": source_video_ids,
        "concept_count_requested": int(
            config["concepts_per_mechanism"]
        ),
        "allowed_format_intents": list(
            config["allowed_format_intents"]
        ),
        "instructions": [
            "Generate genuinely new video concepts that use the transferable mechanism without copying source expression.",
            "Do not reuse source titles, scripts, footage, story sequences, personalities, or exact examples.",
            "Each concept must have a distinct premise and audience promise.",
            "The source creator's material must not be required for the concept to retain its main value.",
            "Do not claim the mechanism will cause views, virality, retention, or recommendation.",
            "Do not rank the concepts.",
            "Include concrete research questions that would need independent answers before scripting.",
        ],
        "response_schema": {
            "mechanism_id": mechanism_id,
            "concepts": [
                {
                    "concept_id": "unique stable id",
                    "working_title": "working title, not final packaging",
                    "premise": "what the new video investigates or explains",
                    "audience_promise": "what the viewer is promised",
                    "format_intent": "long_form|short|either",
                    "mechanism_application": "how the mechanism is used in the new concept",
                    "transformation_method": "how this differs from the source examples",
                    "research_questions": [
                        "independent question that must be researched"
                    ],
                    "source_specific_elements_used": [],
                    "source_dependency_test": {
                        "passes": True,
                        "source_assets_required": False,
                        "rationale": "why the concept still works without source expression",
                    },
                }
            ],
        },
    }


def validate_concept(
    concept: dict[str, Any],
    *,
    mechanism_id: str,
    source_video_ids: set[str],
    config: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    concept_id = str(concept.get("concept_id", "")).strip()
    if not concept_id:
        errors.append("concept_id is required")

    for field in (
        "working_title",
        "premise",
        "audience_promise",
        "mechanism_application",
        "transformation_method",
    ):
        if not str(concept.get(field, "")).strip():
            errors.append(f"{field} is required")

    format_intent = str(concept.get("format_intent", "")).strip()
    if format_intent not in config["allowed_format_intents"]:
        errors.append(
            "format_intent must be one of "
            + ", ".join(config["allowed_format_intents"])
        )

    questions = concept.get("research_questions")
    if not isinstance(questions, list):
        errors.append("research_questions must be a list")
    else:
        valid_questions = [
            str(question).strip()
            for question in questions
            if str(question).strip()
        ]
        if len(valid_questions) < int(
            config["minimum_research_questions"]
        ):
            errors.append(
                "research_questions must contain at least "
                f"{config['minimum_research_questions']} non-empty item(s)"
            )

    used = concept.get("source_specific_elements_used")
    if not isinstance(used, list):
        errors.append("source_specific_elements_used must be a list")
    elif used:
        errors.append(
            "source_specific_elements_used must be empty for an accepted concept"
        )

    dependency = concept.get("source_dependency_test", {})
    if not isinstance(dependency, dict):
        errors.append("source_dependency_test must be an object")
    else:
        if dependency.get("passes") is not True:
            errors.append("source_dependency_test.passes must be true")
        if dependency.get("source_assets_required") is not False:
            errors.append(
                "source_dependency_test.source_assets_required must be false"
            )
        if not str(dependency.get("rationale", "")).strip():
            errors.append(
                "source_dependency_test.rationale is required"
            )

    serialized = json.dumps(concept, ensure_ascii=False)
    referenced_sources = [
        source_id
        for source_id in source_video_ids
        if source_id and source_id in serialized
    ]
    if referenced_sources:
        errors.append(
            "concept directly references source video id(s): "
            + ", ".join(sorted(referenced_sources))
        )

    if str(concept.get("mechanism_id", mechanism_id)).strip() not in {
        "",
        mechanism_id,
    }:
        errors.append("concept mechanism_id does not match request")

    return errors


def validate_response(
    response: dict[str, Any],
    request: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    mechanism_id = str(request["mechanism_id"])
    if str(response.get("mechanism_id", "")) != mechanism_id:
        raise ValueError(
            "Response mechanism_id does not match concept request"
        )

    concepts = response.get("concepts")
    if not isinstance(concepts, list):
        raise ValueError("Response concepts must be a list")

    source_video_ids = {
        str(value)
        for value in request.get("source_video_ids", [])
        if str(value)
    }

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, concept in enumerate(concepts):
        if not isinstance(concept, dict):
            rejected.append(
                {
                    "index": index,
                    "concept": concept,
                    "errors": ["concept must be an object"],
                }
            )
            continue

        errors = validate_concept(
            concept,
            mechanism_id=mechanism_id,
            source_video_ids=source_video_ids,
            config=config,
        )
        concept_id = str(concept.get("concept_id", "")).strip()
        if concept_id and concept_id in seen_ids:
            errors.append("concept_id must be unique within response")
        if concept_id:
            seen_ids.add(concept_id)

        normalized = dict(concept)
        normalized["mechanism_id"] = mechanism_id
        normalized["mechanism_label"] = request.get(
            "mechanism_label"
        )
        normalized["pattern_state"] = request.get("pattern_state")
        normalized["mechanism_scope"] = request.get("scope", {})
        normalized["source_dependency_rule"] = (
            "Concept must retain its main value without source wording, "
            "footage, story, personality, or exact execution."
        )

        if errors:
            rejected.append(
                {
                    "index": index,
                    "concept": normalized,
                    "errors": errors,
                }
            )
        else:
            accepted.append(normalized)

    return {
        "mechanism_id": mechanism_id,
        "accepted": accepted,
        "rejected": rejected,
    }


def run_prepare(handoff_path: Path) -> dict[str, Any]:
    config = load_config()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)

    if not handoff_path.exists():
        summary = {
            "status": "WAITING_FOR_EXPERIMENT_02_HANDOFF",
            "handoff": str(handoff_path),
            "requests_created": 0,
            "model_calls": 0,
        }
        SUMMARY_FILE.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return summary

    handoff = load_json(handoff_path)
    entries = ready_entries(handoff, config)

    if not entries:
        status = (
            "WAITING_FOR_HUMAN_CONFIRMED_PATTERNS"
            if handoff.get("entries")
            else "NO_REPLICATED_PATTERNS"
        )
        summary = {
            "status": status,
            "handoff_status": handoff.get("status"),
            "requests_created": 0,
            "model_calls": 0,
        }
        SUMMARY_FILE.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return summary

    requests = []
    for entry in entries:
        request = build_concept_request(entry, config)
        destination = (
            REQUESTS_DIR
            / f"{safe_slug(request['mechanism_id'])}.concept_request.json"
        )
        destination.write_text(
            json.dumps(request, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        requests.append(str(destination))

    summary = {
        "status": "CONCEPT_REQUESTS_PREPARED",
        "handoff_status": handoff.get("status"),
        "ready_mechanisms": len(entries),
        "requests_created": len(requests),
        "requests": requests,
        "model_calls": 0,
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def merge_candidate_files() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    if not RESPONSES_DIR.exists():
        return accepted, rejected

    config = load_config()
    for response_path in sorted(RESPONSES_DIR.glob("*.json")):
        response = load_json(response_path)
        mechanism_id = str(response.get("mechanism_id", ""))
        request_path = (
            REQUESTS_DIR
            / f"{safe_slug(mechanism_id)}.concept_request.json"
        )
        if not request_path.exists():
            rejected.append(
                {
                    "response": str(response_path),
                    "errors": [
                        "matching concept request not found"
                    ],
                }
            )
            continue

        request = load_json(request_path)
        try:
            result = validate_response(response, request, config)
        except ValueError as exc:
            rejected.append(
                {
                    "response": str(response_path),
                    "errors": [str(exc)],
                }
            )
            continue

        for concept in result["accepted"]:
            concept["response_source"] = str(response_path)
            accepted.append(concept)
        for item in result["rejected"]:
            item["response_source"] = str(response_path)
            rejected.append(item)

    return accepted, rejected


def run_apply() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    accepted, rejected = merge_candidate_files()

    CANDIDATES_FILE.write_text(
        json.dumps(
            {
                "artifact": "concept_candidates",
                "count": len(accepted),
                "concepts": accepted,
                "notes": [
                    "Concepts are not ranked.",
                    "Acceptance here means structural/source-dependency validation only.",
                    "Human Concept Gate approval is still required.",
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    REJECTED_FILE.write_text(
        json.dumps(
            {
                "artifact": "rejected_concepts",
                "count": len(rejected),
                "items": rejected,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = {
        "status": (
            "CONCEPT_CANDIDATES_READY"
            if accepted
            else "NO_VALID_CONCEPT_CANDIDATES"
        ),
        "accepted_concepts": len(accepted),
        "rejected_concepts": len(rejected),
        "candidates_file": str(CANDIDATES_FILE),
        "rejected_file": str(REJECTED_FILE),
        "model_calls": 0,
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transformation Engine framework"
    )
    parser.add_argument(
        "--mode",
        choices=("prepare", "apply"),
        required=True,
    )
    parser.add_argument(
        "--handoff",
        type=Path,
        default=DEFAULT_HANDOFF,
    )
    args = parser.parse_args()

    if args.mode == "prepare":
        result = run_prepare(args.handoff.resolve())
    else:
        result = run_apply()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
