"""Human Research Gate.

Reviews draft research claims against their source evidence and determines which
claims are safe to carry into the Story / Script Engine.

ACCEPT requires all configured criteria. Conflicted claims require an explicit
resolution note. The final package remains RESEARCH_INCOMPLETE when any original
research question lacks an accepted claim.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "research_gate_config.json"

OUTPUT_DIR = HERE / "output"
DEFAULT_DRAFTS_DIR = OUTPUT_DIR / "draft_packages"
REVIEW_REQUESTS_DIR = OUTPUT_DIR / "review_requests"
REVIEWED_DIR = OUTPUT_DIR / "reviewed_packages"
VERIFIED_DIR = OUTPUT_DIR / "verified_packages"
SUMMARY_FILE = OUTPUT_DIR / "research_gate_summary.json"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_FILE)
    required = {
        "required_accept_criteria",
        "require_reviewer_name",
        "require_conflict_resolution_note",
    }
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit(
            "Research Gate config is missing: " + ", ".join(missing)
        )
    return config


def safe_slug(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in "-_." else "_"
        for char in value
    ).strip("._")
    return cleaned or "unknown"


def compact_source_lookup(
    package: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        str(source["source_id"]): source
        for source in package.get("sources", [])
        if isinstance(source, dict) and source.get("source_id")
    }


def build_review_request(
    package: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    concept_id = str(package.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Draft research package requires concept_id")

    source_lookup = compact_source_lookup(package)
    items = []
    seen_claim_ids: set[str] = set()

    for claim in package.get("claims", []):
        claim_id = str(claim.get("claim_id", "")).strip()
        if not claim_id:
            raise ValueError("Every research claim requires claim_id")
        if claim_id in seen_claim_ids:
            raise ValueError(
                f"Duplicate claim_id in draft package: {claim_id}"
            )
        seen_claim_ids.add(claim_id)

        evidence = []
        for link in claim.get("evidence_links", []):
            source = source_lookup.get(str(link.get("source_id")))
            evidence.append(
                {
                    "source_id": link.get("source_id"),
                    "stance": link.get("stance"),
                    "locator": link.get("locator"),
                    "evidence_note": link.get("evidence_note"),
                    "source": (
                        {
                            "title": source.get("title"),
                            "publisher": source.get("publisher"),
                            "url": source.get("url"),
                            "source_type": source.get("source_type"),
                        }
                        if source
                        else None
                    ),
                }
            )

        items.append(
            {
                "claim_id": claim_id,
                "statement": claim.get("statement"),
                "role": claim.get("role"),
                "question_ids": list(
                    claim.get("question_ids", [])
                ),
                "coverage": claim.get("coverage", {}),
                "evidence": evidence,
                "required_accept_criteria": list(
                    config["required_accept_criteria"]
                ),
            }
        )

    return {
        "request_type": "human_research_gate",
        "concept_id": concept_id,
        "concept": package.get("concept", {}),
        "research_questions": package.get(
            "research_questions", []
        ),
        "claim_count": len(items),
        "items": items,
        "criteria": {
            "source_traceable": (
                "The claim can be traced to the cited source and locator."
            ),
            "wording_supported": (
                "The claim wording does not overstate what the cited evidence supports."
            ),
            "conflicts_addressed": (
                "Any contradiction or qualification has been handled explicitly."
            ),
            "safe_for_script": (
                "The claim is suitable to use as factual support in the script."
            ),
        },
        "response_schema": {
            "concept_id": concept_id,
            "reviewer": "reviewer name or identifier",
            "decisions": [
                {
                    "claim_id": "exact claim_id",
                    "decision": "ACCEPT|REWORK|REJECT",
                    "criteria": {
                        criterion: True
                        for criterion in config[
                            "required_accept_criteria"
                        ]
                    },
                    "note": "required for REWORK and for accepted conflicted claims",
                }
            ],
            "overall_note": "optional",
        },
        "notes": [
            "No claim is accepted automatically from its coverage state.",
            "MULTI_SOURCE is evidence breadth, not automatic truth.",
            "Conflicted claims require an explicit resolution note before acceptance.",
        ],
    }


def validate_decisions(
    request: dict[str, Any],
    response: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if str(response.get("concept_id", "")) != str(
        request.get("concept_id", "")
    ):
        raise ValueError(
            "Research Gate response concept_id does not match request"
        )

    reviewer = str(response.get("reviewer", "")).strip()
    if config["require_reviewer_name"] and not reviewer:
        raise ValueError("Research Gate response requires reviewer")

    decisions = response.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("Research Gate decisions must be a list")

    item_lookup = {
        str(item["claim_id"]): item
        for item in request.get("items", [])
    }
    expected = set(item_lookup)
    mapped: dict[str, dict[str, Any]] = {}

    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            raise ValueError(
                f"Research Gate decision {index} must be an object"
            )

        claim_id = str(
            decision.get("claim_id", "")
        ).strip()
        if claim_id not in expected:
            raise ValueError(
                f"Unknown claim_id in Research Gate: {claim_id}"
            )
        if claim_id in mapped:
            raise ValueError(
                f"Duplicate Research Gate decision: {claim_id}"
            )

        value = str(
            decision.get("decision", "")
        ).strip().upper()
        if value not in {"ACCEPT", "REWORK", "REJECT"}:
            raise ValueError(
                f"Invalid decision for {claim_id}: {value!r}"
            )

        criteria = decision.get("criteria")
        if not isinstance(criteria, dict):
            raise ValueError(
                f"Decision criteria are required for {claim_id}"
            )

        required = config["required_accept_criteria"]
        missing = [
            criterion
            for criterion in required
            if criterion not in criteria
        ]
        if missing:
            raise ValueError(
                f"Missing criteria for {claim_id}: "
                + ", ".join(missing)
            )

        normalized = {
            criterion: criteria.get(criterion) is True
            for criterion in required
        }
        note = str(decision.get("note", "") or "").strip()

        if value == "ACCEPT" and not all(
            normalized.values()
        ):
            raise ValueError(
                f"ACCEPT requires all criteria true for {claim_id}"
            )

        if value == "REWORK" and not note:
            raise ValueError(
                f"REWORK requires a note for {claim_id}"
            )

        coverage_state = (
            item_lookup[claim_id]
            .get("coverage", {})
            .get("state")
        )
        if (
            value == "ACCEPT"
            and coverage_state == "CONFLICTED"
            and config["require_conflict_resolution_note"]
            and not note
        ):
            raise ValueError(
                f"Accepted conflicted claim {claim_id} requires a resolution note"
            )

        mapped[claim_id] = {
            "claim_id": claim_id,
            "decision": value,
            "criteria": normalized,
            "note": note,
        }

    missing = sorted(expected - set(mapped))
    if missing:
        raise ValueError(
            "Research Gate is incomplete; missing decisions for: "
            + ", ".join(missing)
        )

    return mapped


def apply_gate(
    package: dict[str, Any],
    request: dict[str, Any],
    response: dict[str, Any],
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    mapped = validate_decisions(
        request,
        response,
        config,
    )

    claims_by_id = {
        str(claim["claim_id"]): claim
        for claim in package.get("claims", [])
    }
    reviewer = str(response.get("reviewer", "")).strip()
    reviewed_at = datetime.now(timezone.utc).isoformat()

    buckets = {
        "accepted": [],
        "rework": [],
        "rejected": [],
    }

    for claim_id in sorted(mapped):
        claim = dict(claims_by_id[claim_id])
        decision = mapped[claim_id]
        claim["research_gate"] = {
            "decision": decision["decision"],
            "criteria": decision["criteria"],
            "note": decision["note"],
            "reviewer": reviewer,
            "reviewed_at": reviewed_at,
        }

        if decision["decision"] == "ACCEPT":
            buckets["accepted"].append(claim)
        elif decision["decision"] == "REWORK":
            buckets["rework"].append(claim)
        else:
            buckets["rejected"].append(claim)

    accepted_claim_ids = {
        str(claim["claim_id"])
        for claim in buckets["accepted"]
    }

    question_status = []
    unresolved = []
    for question in package.get("research_questions", []):
        question_id = str(question["question_id"])
        linked = [
            claim
            for claim in buckets["accepted"]
            if question_id in claim.get("question_ids", [])
        ]
        resolved = bool(linked)
        if not resolved:
            unresolved.append(question_id)
        question_status.append(
            {
                "question_id": question_id,
                "question": question.get("question"),
                "status": (
                    "RESOLVED_FOR_SCRIPT"
                    if resolved
                    else "UNRESOLVED"
                ),
                "accepted_claim_ids": [
                    claim["claim_id"]
                    for claim in linked
                ],
            }
        )

    used_source_ids = {
        str(link.get("source_id"))
        for claim in buckets["accepted"]
        for link in claim.get("evidence_links", [])
        if str(link.get("source_id", "")).strip()
    }
    verified_sources = [
        source
        for source in package.get("sources", [])
        if str(source.get("source_id")) in used_source_ids
    ]

    reviewed = {
        "artifact": "research_gate_reviewed",
        "concept_id": package.get("concept_id"),
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
        "question_status": question_status,
    }

    verified = {
        "artifact": "verified_research_package",
        "concept_id": package.get("concept_id"),
        "status": (
            "READY_FOR_STORY_SCRIPT"
            if buckets["accepted"] and not unresolved
            else "RESEARCH_INCOMPLETE"
        ),
        "concept": package.get("concept", {}),
        "research_questions": package.get(
            "research_questions", []
        ),
        "question_status": question_status,
        "unresolved_question_ids": unresolved,
        "sources": verified_sources,
        "claims": buckets["accepted"],
        "research_gate": {
            "reviewer": reviewer,
            "reviewed_at": reviewed_at,
            "accepted_claim_ids": sorted(
                accepted_claim_ids
            ),
        },
        "notes": [
            "Verified means human-approved for this project's script use, not universal truth.",
            "Only sources referenced by accepted claims are retained.",
            "The Story / Script Engine must stay within accepted claim wording and evidence scope.",
        ],
    }

    return reviewed, verified


def run_prepare(
    draft_path: Path,
) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)

    package = load_json(draft_path)
    config = load_config()
    request = build_review_request(package, config)

    concept_id = str(request["concept_id"])
    destination = (
        REVIEW_REQUESTS_DIR
        / f"{safe_slug(concept_id)}.research_gate_request.json"
    )
    destination.write_text(
        json.dumps(request, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return {
        "status": "RESEARCH_GATE_READY",
        "concept_id": concept_id,
        "claim_count": request["claim_count"],
        "request": str(destination),
    }


def run_batch_prepare(
    drafts_dir: Path,
) -> dict[str, Any]:
    if not drafts_dir.exists():
        return {
            "status": "WAITING_FOR_DRAFT_RESEARCH_PACKAGES",
            "prepared": 0,
        }

    prepared = []
    failures = []
    for draft_path in sorted(drafts_dir.glob("*.json")):
        try:
            prepared.append(run_prepare(draft_path))
        except Exception as exc:
            failures.append(
                {
                    "draft": str(draft_path),
                    "error_type": type(exc).__name__,
                }
            )

    return {
        "status": "COMPLETE",
        "prepared": len(prepared),
        "failures": failures,
        "requests_dir": str(REVIEW_REQUESTS_DIR),
    }


def run_apply(
    draft_path: Path,
    request_path: Path,
    response_path: Path,
) -> dict[str, Any]:
    package = load_json(draft_path)
    request = load_json(request_path)
    response = load_json(response_path)
    config = load_config()

    reviewed, verified = apply_gate(
        package,
        request,
        response,
        config,
    )

    REVIEWED_DIR.mkdir(parents=True, exist_ok=True)
    VERIFIED_DIR.mkdir(parents=True, exist_ok=True)

    concept_id = safe_slug(
        str(package.get("concept_id", "unknown"))
    )
    reviewed_path = (
        REVIEWED_DIR
        / f"{concept_id}.research_gate_reviewed.json"
    )
    verified_path = (
        VERIFIED_DIR
        / f"{concept_id}.verified_research_package.json"
    )

    reviewed_path.write_text(
        json.dumps(reviewed, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    verified_path.write_text(
        json.dumps(verified, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = {
        "status": verified["status"],
        "concept_id": package.get("concept_id"),
        "accepted": reviewed["counts"]["accepted"],
        "rework": reviewed["counts"]["rework"],
        "rejected": reviewed["counts"]["rejected"],
        "unresolved_questions": len(
            verified["unresolved_question_ids"]
        ),
        "reviewed_file": str(reviewed_path),
        "verified_package": str(verified_path),
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Human Research Gate"
    )
    parser.add_argument(
        "--mode",
        choices=("prepare", "batch-prepare", "apply"),
        required=True,
    )
    parser.add_argument("--draft", type=Path, default=None)
    parser.add_argument(
        "--drafts-dir",
        type=Path,
        default=DEFAULT_DRAFTS_DIR,
    )
    parser.add_argument("--request", type=Path, default=None)
    parser.add_argument("--response", type=Path, default=None)
    args = parser.parse_args()

    if args.mode == "prepare":
        if args.draft is None:
            raise SystemExit(
                "--draft is required for Research Gate prepare"
            )
        result = run_prepare(args.draft.resolve())
    elif args.mode == "batch-prepare":
        result = run_batch_prepare(
            args.drafts_dir.resolve()
        )
    else:
        if (
            args.draft is None
            or args.request is None
            or args.response is None
        ):
            raise SystemExit(
                "--draft, --request and --response are required for Research Gate apply"
            )
        result = run_apply(
            args.draft.resolve(),
            args.request.resolve(),
            args.response.resolve(),
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
