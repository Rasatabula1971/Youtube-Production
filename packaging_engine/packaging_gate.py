"""Human Packaging Gate.

Reviews package candidates and allows at most one approved package per concept.
Approved package dependencies are carried into the Research Engine handoff.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "packaging_gate_config.json"

OUTPUT_DIR = HERE / "output"
DEFAULT_CANDIDATES = OUTPUT_DIR / "package_candidates.json"
REVIEW_REQUEST_FILE = OUTPUT_DIR / "packaging_gate_request.json"
REVIEWED_FILE = OUTPUT_DIR / "packaging_gate_reviewed.json"
APPROVED_FILE = OUTPUT_DIR / "approved_packages.json"
RESEARCH_HANDOFF_FILE = OUTPUT_DIR / "research_handoff.json"
SUMMARY_FILE = OUTPUT_DIR / "packaging_gate_summary.json"


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
            "Packaging Gate config is missing: "
            + ", ".join(missing)
        )
    return config


def build_review_request(
    candidates_payload: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    packages = candidates_payload.get("packages", [])
    if not isinstance(packages, list):
        raise ValueError(
            "package_candidates packages must be a list"
        )

    seen_ids: set[str] = set()
    items = []

    for package in packages:
        package_id = str(
            package.get("package_id", "")
        ).strip()
        concept_id = str(
            package.get("concept_id", "")
        ).strip()

        if not package_id:
            raise ValueError(
                "Every package candidate requires package_id"
            )
        if package_id in seen_ids:
            raise ValueError(
                f"Duplicate package_id in candidates: {package_id}"
            )
        if not concept_id:
            raise ValueError(
                f"Package {package_id} requires concept_id"
            )
        seen_ids.add(package_id)

        items.append(
            {
                "package_id": package_id,
                "concept_id": concept_id,
                "title": package.get("title"),
                "thumbnail": package.get("thumbnail"),
                "opening_frame": package.get(
                    "opening_frame"
                ),
                "expected_viewer": package.get(
                    "expected_viewer"
                ),
                "awareness_level": package.get(
                    "awareness_level"
                ),
                "core_promise": package.get(
                    "core_promise"
                ),
                "curiosity_gap": package.get(
                    "curiosity_gap"
                ),
                "expected_payoff": package.get(
                    "expected_payoff"
                ),
                "format_intent": package.get(
                    "format_intent"
                ),
                "title_thumbnail_relationship": package.get(
                    "title_thumbnail_relationship"
                ),
                "research_dependencies": package.get(
                    "research_dependencies", []
                ),
                "concept_context": package.get(
                    "concept_context", {}
                ),
                "required_accept_criteria": list(
                    config["required_accept_criteria"]
                ),
            }
        )

    return {
        "request_type": "human_packaging_gate",
        "package_count": len(items),
        "criteria": {
            "promise_clear": (
                "The package communicates one understandable main promise."
            ),
            "concept_aligned": (
                "The package accurately represents the accepted concept."
            ),
            "title_thumbnail_complementary": (
                "Title and thumbnail add complementary information rather than merely repeating each other."
            ),
            "not_misleading": (
                "The package does not promise evidence, certainty, or drama the planned video cannot support."
            ),
            "viewer_awareness_fit": (
                "Vocabulary and framing fit the intended viewer's awareness level."
            ),
            "payoff_defined": (
                "The package makes clear what satisfying answer or outcome the video must deliver."
            ),
            "research_dependencies_explicit": (
                "Facts needed to safely support the package are listed for downstream research."
            ),
        },
        "items": items,
        "response_schema": {
            "reviewer": "reviewer name or identifier",
            "decisions": [
                {
                    "package_id": "exact package_id",
                    "decision": "ACCEPT|REWORK|REJECT",
                    "criteria": {
                        criterion: True
                        for criterion in config[
                            "required_accept_criteria"
                        ]
                    },
                    "note": (
                        "required for REWORK; optional otherwise"
                    ),
                }
            ],
            "overall_note": "optional",
        },
        "notes": [
            "Every package candidate requires a decision.",
            "At most one package may be ACCEPTED per concept.",
            "No clickability score or CTR prediction is calculated.",
            "Accepted package research dependencies become mandatory research questions.",
        ],
    }


def validate_decisions(
    request: dict[str, Any],
    response: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    reviewer = str(
        response.get("reviewer", "")
    ).strip()
    if config["require_reviewer_name"] and not reviewer:
        raise ValueError(
            "Packaging Gate response requires reviewer"
        )

    decisions = response.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError(
            "Packaging Gate decisions must be a list"
        )

    items = {
        str(item["package_id"]): item
        for item in request.get("items", [])
    }
    expected = set(items)
    mapped: dict[str, dict[str, Any]] = {}

    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            raise ValueError(
                f"Decision {index} must be an object"
            )

        package_id = str(
            decision.get("package_id", "")
        ).strip()
        if package_id not in expected:
            raise ValueError(
                f"Unknown package_id: {package_id}"
            )
        if package_id in mapped:
            raise ValueError(
                f"Duplicate package decision: {package_id}"
            )

        value = str(
            decision.get("decision", "")
        ).strip().upper()
        if value not in {
            "ACCEPT",
            "REWORK",
            "REJECT",
        }:
            raise ValueError(
                f"Invalid decision for {package_id}: {value!r}"
            )

        criteria = decision.get("criteria")
        if not isinstance(criteria, dict):
            raise ValueError(
                f"Decision criteria are required for {package_id}"
            )

        required = config[
            "required_accept_criteria"
        ]
        missing = [
            criterion
            for criterion in required
            if criterion not in criteria
        ]
        if missing:
            raise ValueError(
                f"Missing criteria for {package_id}: "
                + ", ".join(missing)
            )

        normalized = {
            criterion: (
                criteria.get(criterion) is True
            )
            for criterion in required
        }
        note = str(
            decision.get("note", "") or ""
        ).strip()

        if value == "ACCEPT" and not all(
            normalized.values()
        ):
            raise ValueError(
                f"ACCEPT requires all criteria true for {package_id}"
            )
        if value == "REWORK" and not note:
            raise ValueError(
                f"REWORK requires a note for {package_id}"
            )

        mapped[package_id] = {
            "package_id": package_id,
            "decision": value,
            "criteria": normalized,
            "note": note,
            "concept_id": items[package_id][
                "concept_id"
            ],
        }

    missing = sorted(expected - set(mapped))
    if missing:
        raise ValueError(
            "Packaging Gate is incomplete; missing decisions for: "
            + ", ".join(missing)
        )

    accepted_by_concept: dict[str, list[str]] = {}
    for package_id, decision in mapped.items():
        if decision["decision"] != "ACCEPT":
            continue
        accepted_by_concept.setdefault(
            decision["concept_id"], []
        ).append(package_id)

    conflicts = {
        concept_id: package_ids
        for concept_id, package_ids in accepted_by_concept.items()
        if len(package_ids) > 1
    }
    if conflicts:
        details = "; ".join(
            f"{concept_id}: {', '.join(ids)}"
            for concept_id, ids in sorted(
                conflicts.items()
            )
        )
        raise ValueError(
            "Only one package may be ACCEPTED per concept: "
            + details
        )

    return mapped


def apply_gate(
    candidates_payload: dict[str, Any],
    request: dict[str, Any],
    response: dict[str, Any],
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    mapped = validate_decisions(
        request,
        response,
        config,
    )
    packages = candidates_payload.get(
        "packages", []
    )
    by_id = {
        str(package["package_id"]): package
        for package in packages
    }

    reviewer = str(
        response.get("reviewer", "")
    ).strip()
    reviewed_at = datetime.now(
        timezone.utc
    ).isoformat()

    buckets = {
        "accepted": [],
        "rework": [],
        "rejected": [],
    }

    for package_id in sorted(mapped):
        package = dict(by_id[package_id])
        decision = mapped[package_id]
        package["packaging_gate"] = {
            "decision": decision["decision"],
            "criteria": decision["criteria"],
            "note": decision["note"],
            "reviewer": reviewer,
            "reviewed_at": reviewed_at,
        }

        if decision["decision"] == "ACCEPT":
            buckets["accepted"].append(package)
        elif decision["decision"] == "REWORK":
            buckets["rework"].append(package)
        else:
            buckets["rejected"].append(package)

    reviewed = {
        "artifact": "packaging_gate_reviewed",
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
    }

    handoff_concepts = []
    for package in buckets["accepted"]:
        concept = dict(
            package.get("concept_context", {})
        )
        concept["concept_id"] = package[
            "concept_id"
        ]
        concept["packaging"] = {
            key: package.get(key)
            for key in (
                "package_id",
                "title",
                "thumbnail",
                "opening_frame",
                "expected_viewer",
                "awareness_level",
                "core_promise",
                "curiosity_gap",
                "expected_payoff",
                "format_intent",
                "title_thumbnail_relationship",
                "research_dependencies",
                "packaging_gate",
            )
        }
        handoff_concepts.append(concept)

    research_handoff = {
        "artifact": "packaging_research_handoff",
        "status": (
            "READY_FOR_RESEARCH"
            if handoff_concepts
            else "NO_APPROVED_PACKAGES"
        ),
        "concept_count": len(
            handoff_concepts
        ),
        "concepts": handoff_concepts,
        "notes": [
            "Only concepts with one human-approved package are included.",
            "Package research dependencies must be resolved before Story / Script.",
            "The approved package defines the promise the eventual script must fulfill.",
        ],
    }

    return reviewed, research_handoff


def run_prepare(
    candidates_path: Path,
) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not candidates_path.exists():
        summary = {
            "status": "WAITING_FOR_PACKAGE_CANDIDATES",
            "reviewable_packages": 0,
        }
        SUMMARY_FILE.write_text(
            json.dumps(
                summary,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return summary

    candidates = load_json(
        candidates_path
    )
    config = load_config()
    request = build_review_request(
        candidates,
        config,
    )
    REVIEW_REQUEST_FILE.write_text(
        json.dumps(
            request,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = {
        "status": (
            "PACKAGING_GATE_READY"
            if request["package_count"]
            else "NO_PACKAGES_TO_REVIEW"
        ),
        "reviewable_packages": request[
            "package_count"
        ],
        "request": str(
            REVIEW_REQUEST_FILE
        ),
    }
    SUMMARY_FILE.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return summary


def run_apply(
    candidates_path: Path,
    response_path: Path,
) -> dict[str, Any]:
    candidates = load_json(
        candidates_path
    )
    request = load_json(
        REVIEW_REQUEST_FILE
    )
    response = load_json(
        response_path
    )
    config = load_config()

    reviewed, research_handoff = apply_gate(
        candidates,
        request,
        response,
        config,
    )

    REVIEWED_FILE.write_text(
        json.dumps(
            reviewed,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    APPROVED_FILE.write_text(
        json.dumps(
            {
                "artifact": "approved_packages",
                "count": reviewed["counts"][
                    "accepted"
                ],
                "packages": reviewed[
                    "accepted"
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
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
        "status": research_handoff[
            "status"
        ],
        "accepted": reviewed["counts"][
            "accepted"
        ],
        "rework": reviewed["counts"][
            "rework"
        ],
        "rejected": reviewed["counts"][
            "rejected"
        ],
        "research_handoff": str(
            RESEARCH_HANDOFF_FILE
        ),
    }
    SUMMARY_FILE.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Human Packaging Gate"
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
        result = run_prepare(
            args.candidates.resolve()
        )
    else:
        if args.response is None:
            raise SystemExit(
                "--response is required for Packaging Gate apply"
            )
        result = run_apply(
            args.candidates.resolve(),
            args.response.resolve(),
        )

    print(json.dumps(
        result,
        indent=2,
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
