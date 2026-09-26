"""Packaging Engine framework.

Consumes human-accepted concept candidates and prepares structured packaging
requests. Returned packages are validated for promise clarity, title/thumbnail
complementarity, format context, and explicit research dependencies.

No model, network, or YouTube API calls are made here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent

CONFIG_FILE = HERE / "packaging_config.json"
DEFAULT_CONCEPT_HANDOFF = (
    PROJECT_ROOT
    / "transformation_engine"
    / "output"
    / "research_handoff.json"
)

OUTPUT_DIR = HERE / "output"
REQUESTS_DIR = OUTPUT_DIR / "package_requests"
RESPONSES_DIR = OUTPUT_DIR / "package_responses"
CANDIDATES_FILE = OUTPUT_DIR / "package_candidates.json"
REJECTED_FILE = OUTPUT_DIR / "rejected_packages.json"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_FILE)
    required = {
        "packages_per_concept",
        "allowed_format_intents",
        "minimum_research_dependencies",
    }
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit(
            "Packaging config is missing: " + ", ".join(missing)
        )
    return config


def safe_slug(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in "-_." else "_"
        for char in value
    ).strip("._")
    return cleaned or "unknown"


def build_package_request(
    concept: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    concept_id = str(concept.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Accepted concept requires concept_id")

    return {
        "request_type": "packaging_generation",
        "concept_id": concept_id,
        "concept": {
            "working_title": concept.get("working_title"),
            "premise": concept.get("premise"),
            "audience_promise": concept.get("audience_promise"),
            "format_intent": concept.get("format_intent"),
            "mechanism_id": concept.get("mechanism_id"),
            "mechanism_label": concept.get("mechanism_label"),
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
            "concept_gate": concept.get("concept_gate", {}),
        },
        "package_count_requested": int(
            config["packages_per_concept"]
        ),
        "allowed_format_intents": list(
            config["allowed_format_intents"]
        ),
        "instructions": [
            "Create package options before script drafting.",
            "Treat title and thumbnail as one communication unit.",
            "Title and thumbnail should complement rather than repeat each other.",
            "Each package must communicate one main promise and one expected payoff.",
            "Define the intended viewer and their awareness level explicitly.",
            "The package must remain faithful to the accepted concept and must not invent unsupported facts.",
            "List factual or evidentiary dependencies that research must verify before the package can be considered fully supported.",
            "Do not rank the package options.",
            "Do not optimize for clickbait that the future video cannot deliver.",
        ],
        "response_schema": {
            "concept_id": concept_id,
            "packages": [
                {
                    "package_id": "unique stable id",
                    "title": "candidate title",
                    "thumbnail": {
                        "message": "what the thumbnail communicates",
                        "visual_concept": "visual idea",
                        "text_overlay": "optional short overlay or empty string",
                    },
                    "opening_frame": {
                        "purpose": "what the first frame should establish",
                        "visual_concept": "first-frame idea",
                    },
                    "expected_viewer": "who this package is for",
                    "awareness_level": "what that viewer already understands",
                    "core_promise": "single main promise",
                    "curiosity_gap": "important missing answer",
                    "expected_payoff": "what must be delivered",
                    "format_intent": "long_form|short|either",
                    "title_thumbnail_relationship": "how title and thumbnail complement each other",
                    "research_dependencies": [
                        "fact or claim that must be verified before script"
                    ],
                }
            ],
        },
    }


def validate_package(
    package: dict[str, Any],
    *,
    concept_id: str,
    config: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    package_id = str(package.get("package_id", "")).strip()
    if not package_id:
        errors.append("package_id is required")

    for field in (
        "title",
        "expected_viewer",
        "awareness_level",
        "core_promise",
        "curiosity_gap",
        "expected_payoff",
        "title_thumbnail_relationship",
    ):
        if not str(package.get(field, "")).strip():
            errors.append(f"{field} is required")

    format_intent = str(package.get("format_intent", "")).strip()
    if format_intent not in config["allowed_format_intents"]:
        errors.append(
            "format_intent must be one of "
            + ", ".join(config["allowed_format_intents"])
        )

    thumbnail = package.get("thumbnail")
    if not isinstance(thumbnail, dict):
        errors.append("thumbnail must be an object")
    else:
        if not str(thumbnail.get("message", "")).strip():
            errors.append("thumbnail.message is required")
        if not str(
            thumbnail.get("visual_concept", "")
        ).strip():
            errors.append(
                "thumbnail.visual_concept is required"
            )

    opening_frame = package.get("opening_frame")
    if not isinstance(opening_frame, dict):
        errors.append("opening_frame must be an object")
    else:
        if not str(
            opening_frame.get("purpose", "")
        ).strip():
            errors.append("opening_frame.purpose is required")
        if not str(
            opening_frame.get("visual_concept", "")
        ).strip():
            errors.append(
                "opening_frame.visual_concept is required"
            )

    dependencies = package.get("research_dependencies")
    if not isinstance(dependencies, list):
        errors.append("research_dependencies must be a list")
    else:
        valid = [
            str(value).strip()
            for value in dependencies
            if str(value).strip()
        ]
        if len(valid) < int(
            config["minimum_research_dependencies"]
        ):
            errors.append(
                "research_dependencies must contain at least "
                f"{config['minimum_research_dependencies']} non-empty item(s)"
            )

    declared_concept_id = str(
        package.get("concept_id", concept_id)
    ).strip()
    if declared_concept_id not in {"", concept_id}:
        errors.append("package concept_id does not match request")

    return errors


def validate_response(
    response: dict[str, Any],
    request: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    concept_id = str(request["concept_id"])
    if str(response.get("concept_id", "")) != concept_id:
        raise ValueError(
            "Packaging response concept_id does not match request"
        )

    packages = response.get("packages")
    if not isinstance(packages, list):
        raise ValueError("Packaging response packages must be a list")

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, package in enumerate(packages):
        if not isinstance(package, dict):
            rejected.append(
                {
                    "index": index,
                    "package": package,
                    "errors": ["package must be an object"],
                }
            )
            continue

        errors = validate_package(
            package,
            concept_id=concept_id,
            config=config,
        )

        package_id = str(
            package.get("package_id", "")
        ).strip()
        if package_id and package_id in seen_ids:
            errors.append(
                "package_id must be unique within response"
            )
        if package_id:
            seen_ids.add(package_id)

        normalized = dict(package)
        normalized["concept_id"] = concept_id
        normalized["concept_context"] = request["concept"]

        if errors:
            rejected.append(
                {
                    "index": index,
                    "package": normalized,
                    "errors": errors,
                }
            )
        else:
            accepted.append(normalized)

    return {
        "concept_id": concept_id,
        "accepted": accepted,
        "rejected": rejected,
    }


def run_prepare(
    concept_handoff_path: Path,
) -> dict[str, Any]:
    config = load_config()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)

    if not concept_handoff_path.exists():
        summary = {
            "status": "WAITING_FOR_ACCEPTED_CONCEPTS",
            "concept_handoff": str(concept_handoff_path),
            "requests_created": 0,
        }
        SUMMARY_FILE.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return summary

    handoff = load_json(concept_handoff_path)
    concepts = handoff.get("concepts", [])
    if not isinstance(concepts, list):
        raise ValueError(
            "Accepted concept handoff concepts must be a list"
        )

    paths = []
    seen_concept_ids: set[str] = set()

    for concept in concepts:
        request = build_package_request(concept, config)
        concept_id = str(request["concept_id"])
        if concept_id in seen_concept_ids:
            raise ValueError(
                f"Duplicate concept_id in accepted concept handoff: {concept_id}"
            )
        seen_concept_ids.add(concept_id)

        destination = (
            REQUESTS_DIR
            / f"{safe_slug(concept_id)}.package_request.json"
        )
        destination.write_text(
            json.dumps(request, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        paths.append(str(destination))

    summary = {
        "status": (
            "PACKAGE_REQUESTS_READY"
            if paths
            else "NO_ACCEPTED_CONCEPTS"
        ),
        "requests_created": len(paths),
        "requests": paths,
        "network_calls": 0,
        "model_calls": 0,
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def run_apply() -> dict[str, Any]:
    config = load_config()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    global_package_ids: set[str] = set()

    if not RESPONSES_DIR.exists():
        summary = {
            "status": "WAITING_FOR_PACKAGE_RESPONSES",
            "accepted_packages": 0,
            "rejected_packages": 0,
        }
        SUMMARY_FILE.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return summary

    for response_path in sorted(
        RESPONSES_DIR.glob("*.json")
    ):
        response = load_json(response_path)
        concept_id = str(
            response.get("concept_id", "")
        ).strip()
        request_path = (
            REQUESTS_DIR
            / f"{safe_slug(concept_id)}.package_request.json"
        )
        if not request_path.exists():
            rejected.append(
                {
                    "response": str(response_path),
                    "errors": [
                        "matching package request not found"
                    ],
                }
            )
            continue

        request = load_json(request_path)
        try:
            result = validate_response(
                response,
                request,
                config,
            )
        except ValueError as exc:
            rejected.append(
                {
                    "response": str(response_path),
                    "errors": [str(exc)],
                }
            )
            continue

        for package in result["accepted"]:
            package_id = str(package["package_id"])
            if package_id in global_package_ids:
                rejected.append(
                    {
                        "response": str(response_path),
                        "package": package,
                        "errors": [
                            "package_id must be globally unique"
                        ],
                    }
                )
                continue
            global_package_ids.add(package_id)
            package["response_source"] = str(
                response_path
            )
            accepted.append(package)

        for item in result["rejected"]:
            item["response_source"] = str(response_path)
            rejected.append(item)

    CANDIDATES_FILE.write_text(
        json.dumps(
            {
                "artifact": "package_candidates",
                "count": len(accepted),
                "packages": accepted,
                "notes": [
                    "Packages are not ranked.",
                    "Structural validity does not equal human approval.",
                    "Package research dependencies must be incorporated into downstream research.",
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
                "artifact": "rejected_packages",
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
            "PACKAGE_CANDIDATES_READY"
            if accepted
            else "NO_VALID_PACKAGE_CANDIDATES"
        ),
        "accepted_packages": len(accepted),
        "rejected_packages": len(rejected),
        "candidates_file": str(CANDIDATES_FILE),
        "rejected_file": str(REJECTED_FILE),
        "network_calls": 0,
        "model_calls": 0,
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Packaging Engine framework"
    )
    parser.add_argument(
        "--mode",
        choices=("prepare", "apply"),
        required=True,
    )
    parser.add_argument(
        "--concept-handoff",
        type=Path,
        default=DEFAULT_CONCEPT_HANDOFF,
    )
    args = parser.parse_args()

    if args.mode == "prepare":
        result = run_prepare(
            args.concept_handoff.resolve()
        )
    else:
        result = run_apply()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
