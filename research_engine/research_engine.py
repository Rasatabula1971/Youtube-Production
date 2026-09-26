"""Research Engine framework.

Consumes human-accepted concept handoffs, prepares research plans, validates
structured source/claim evidence, detects support and contradiction patterns,
and produces draft research packages.

The framework does not browse the web, call an LLM, or declare claims true.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent

CONFIG_FILE = HERE / "research_config.json"
DEFAULT_HANDOFF = (
    PROJECT_ROOT
    / "transformation_engine"
    / "output"
    / "research_handoff.json"
)

OUTPUT_DIR = HERE / "output"
PLANS_DIR = OUTPUT_DIR / "plans"
RESPONSES_DIR = OUTPUT_DIR / "research_responses"
DRAFTS_DIR = OUTPUT_DIR / "draft_packages"
REJECTED_FILE = OUTPUT_DIR / "rejected_research_inputs.json"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_FILE)
    required = {
        "allowed_source_types",
        "allowed_stances",
        "allowed_claim_roles",
        "require_source_locator",
    }
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit(
            "Research config is missing: " + ", ".join(missing)
        )
    return config


def safe_slug(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in "-_." else "_"
        for char in value
    ).strip("._")
    return cleaned or "unknown"


def source_host(url: str) -> str | None:
    value = str(url or "").strip()
    if not value:
        return None
    try:
        host = urlparse(value).hostname
    except ValueError:
        return None
    return host.lower() if host else None


def build_research_plan(concept: dict[str, Any]) -> dict[str, Any]:
    concept_id = str(concept.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Research handoff concept requires concept_id")

    raw_questions = concept.get("research_questions", [])
    if not isinstance(raw_questions, list) or not raw_questions:
        raise ValueError(
            f"Concept {concept_id} requires research_questions"
        )

    questions = []
    for index, question in enumerate(raw_questions, start=1):
        text = str(question).strip()
        if not text:
            raise ValueError(
                f"Concept {concept_id} has an empty research question"
            )
        questions.append(
            {
                "question_id": f"rq{index:03d}",
                "question": text,
            }
        )

    return {
        "artifact": "research_plan",
        "concept_id": concept_id,
        "working_title": concept.get("working_title"),
        "premise": concept.get("premise"),
        "audience_promise": concept.get("audience_promise"),
        "format_intent": concept.get("format_intent"),
        "mechanism_id": concept.get("mechanism_id"),
        "mechanism_label": concept.get("mechanism_label"),
        "concept_gate": concept.get("concept_gate"),
        "research_questions": questions,
        "instructions": [
            "Research the concept independently from the source videos that inspired the mechanism.",
            "Record source provenance before using a source to support a claim.",
            "Paraphrase evidence notes; do not copy long source passages.",
            "Link every factual claim to one or more research questions.",
            "Record supporting, contradicting, and qualifying evidence instead of silently reconciling disagreements.",
            "Do not mark a claim verified merely because multiple sources agree.",
            "Working title and audience promise remain provisional until Packaging Engine review.",
        ],
        "response_schema": {
            "concept_id": concept_id,
            "sources": [
                {
                    "source_id": "src001",
                    "title": "source title",
                    "publisher": "publisher or organization",
                    "url": "https://example.com/source",
                    "source_type": "primary|secondary|dataset|documentation|expert_statement",
                    "published_at": "optional date or datetime",
                    "accessed_at": "optional date or datetime",
                    "provenance_note": "why this source is relevant",
                }
            ],
            "claims": [
                {
                    "claim_id": "clm001",
                    "statement": "factual statement to potentially use later",
                    "role": "core|supporting|context",
                    "question_ids": ["rq001"],
                    "evidence_links": [
                        {
                            "source_id": "src001",
                            "stance": "SUPPORTS|CONTRADICTS|QUALIFIES",
                            "locator": "page, section, timestamp, table, or other locator",
                            "evidence_note": "brief paraphrase of what the source says",
                        }
                    ],
                }
            ],
        },
    }


def validate_source(
    source: dict[str, Any],
    config: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    source_id = str(source.get("source_id", "")).strip()
    if not source_id:
        errors.append("source_id is required")

    if not str(source.get("title", "")).strip():
        errors.append("title is required")

    if not str(source.get("publisher", "")).strip():
        errors.append("publisher is required")

    source_type = str(source.get("source_type", "")).strip()
    if source_type not in config["allowed_source_types"]:
        errors.append(
            "source_type must be one of "
            + ", ".join(config["allowed_source_types"])
        )

    if not str(source.get("provenance_note", "")).strip():
        errors.append("provenance_note is required")

    url = str(source.get("url", "") or "").strip()
    if url and source_host(url) is None:
        errors.append("url is not a valid absolute web URL")

    return errors


def claim_coverage_state(
    evidence_links: list[dict[str, Any]],
) -> dict[str, Any]:
    supporting_sources = {
        str(link.get("source_id"))
        for link in evidence_links
        if link.get("stance") == "SUPPORTS"
    }
    contradicting_sources = {
        str(link.get("source_id"))
        for link in evidence_links
        if link.get("stance") == "CONTRADICTS"
    }
    qualifying_sources = {
        str(link.get("source_id"))
        for link in evidence_links
        if link.get("stance") == "QUALIFIES"
    }

    if contradicting_sources:
        state = "CONFLICTED"
    elif len(supporting_sources) >= 2:
        state = "MULTI_SOURCE"
    elif len(supporting_sources) == 1:
        state = "SINGLE_SOURCE"
    else:
        state = "UNSUPPORTED"

    return {
        "state": state,
        "supporting_source_count": len(supporting_sources),
        "contradicting_source_count": len(
            contradicting_sources
        ),
        "qualifying_source_count": len(qualifying_sources),
        "supporting_source_ids": sorted(supporting_sources),
        "contradicting_source_ids": sorted(
            contradicting_sources
        ),
        "qualifying_source_ids": sorted(qualifying_sources),
    }


def validate_claim(
    claim: dict[str, Any],
    *,
    source_ids: set[str],
    question_ids: set[str],
    config: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    claim_id = str(claim.get("claim_id", "")).strip()
    if not claim_id:
        errors.append("claim_id is required")

    if not str(claim.get("statement", "")).strip():
        errors.append("statement is required")

    role = str(claim.get("role", "")).strip()
    if role not in config["allowed_claim_roles"]:
        errors.append(
            "role must be one of "
            + ", ".join(config["allowed_claim_roles"])
        )

    linked_questions = claim.get("question_ids")
    if not isinstance(linked_questions, list) or not linked_questions:
        errors.append("question_ids must be a non-empty list")
    else:
        unknown_questions = sorted(
            {
                str(value)
                for value in linked_questions
                if str(value) not in question_ids
            }
        )
        if unknown_questions:
            errors.append(
                "unknown question_ids: "
                + ", ".join(unknown_questions)
            )

    evidence_links = claim.get("evidence_links")
    if not isinstance(evidence_links, list):
        errors.append("evidence_links must be a list")
        return errors

    for index, link in enumerate(evidence_links):
        if not isinstance(link, dict):
            errors.append(
                f"evidence_links[{index}] must be an object"
            )
            continue

        source_id = str(link.get("source_id", "")).strip()
        if source_id not in source_ids:
            errors.append(
                f"evidence_links[{index}] uses unknown source_id {source_id!r}"
            )

        stance = str(link.get("stance", "")).strip()
        if stance not in config["allowed_stances"]:
            errors.append(
                f"evidence_links[{index}] has invalid stance {stance!r}"
            )

        if (
            config["require_source_locator"]
            and not str(link.get("locator", "")).strip()
        ):
            errors.append(
                f"evidence_links[{index}] requires locator"
            )

        if not str(link.get("evidence_note", "")).strip():
            errors.append(
                f"evidence_links[{index}] requires evidence_note"
            )

    return errors


def validate_research_response(
    response: dict[str, Any],
    plan: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    concept_id = str(plan["concept_id"])
    if str(response.get("concept_id", "")) != concept_id:
        raise ValueError(
            "Research response concept_id does not match plan"
        )

    sources = response.get("sources")
    claims = response.get("claims")
    if not isinstance(sources, list):
        raise ValueError("Research response sources must be a list")
    if not isinstance(claims, list):
        raise ValueError("Research response claims must be a list")

    valid_sources: list[dict[str, Any]] = []
    rejected_sources: list[dict[str, Any]] = []
    source_ids: set[str] = set()

    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            rejected_sources.append(
                {
                    "index": index,
                    "source": source,
                    "errors": ["source must be an object"],
                }
            )
            continue

        errors = validate_source(source, config)
        source_id = str(source.get("source_id", "")).strip()
        if source_id and source_id in source_ids:
            errors.append("source_id must be unique")
        if source_id:
            source_ids.add(source_id)

        normalized = dict(source)
        normalized["host"] = source_host(
            str(source.get("url", "") or "")
        )

        if errors:
            rejected_sources.append(
                {
                    "index": index,
                    "source": normalized,
                    "errors": errors,
                }
            )
        else:
            valid_sources.append(normalized)

    valid_source_ids = {
        str(source["source_id"])
        for source in valid_sources
    }
    question_ids = {
        str(question["question_id"])
        for question in plan["research_questions"]
    }

    valid_claims: list[dict[str, Any]] = []
    rejected_claims: list[dict[str, Any]] = []
    claim_ids: set[str] = set()

    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            rejected_claims.append(
                {
                    "index": index,
                    "claim": claim,
                    "errors": ["claim must be an object"],
                }
            )
            continue

        errors = validate_claim(
            claim,
            source_ids=valid_source_ids,
            question_ids=question_ids,
            config=config,
        )
        claim_id = str(claim.get("claim_id", "")).strip()
        if claim_id and claim_id in claim_ids:
            errors.append("claim_id must be unique")
        if claim_id:
            claim_ids.add(claim_id)

        normalized = dict(claim)
        if isinstance(claim.get("evidence_links"), list):
            normalized["coverage"] = claim_coverage_state(
                claim["evidence_links"]
            )

        if errors:
            rejected_claims.append(
                {
                    "index": index,
                    "claim": normalized,
                    "errors": errors,
                }
            )
        else:
            valid_claims.append(normalized)

    question_coverage = []
    for question in plan["research_questions"]:
        question_id = str(question["question_id"])
        linked_claims = [
            claim
            for claim in valid_claims
            if question_id in claim.get("question_ids", [])
        ]
        question_coverage.append(
            {
                "question_id": question_id,
                "question": question["question"],
                "claim_ids": [
                    claim["claim_id"]
                    for claim in linked_claims
                ],
                "has_claims": bool(linked_claims),
            }
        )

    return {
        "artifact": "draft_research_package",
        "concept_id": concept_id,
        "concept": {
            key: plan.get(key)
            for key in (
                "working_title",
                "premise",
                "audience_promise",
                "format_intent",
                "mechanism_id",
                "mechanism_label",
                "concept_gate",
            )
        },
        "research_questions": plan["research_questions"],
        "sources": valid_sources,
        "claims": valid_claims,
        "question_coverage": question_coverage,
        "rejected_sources": rejected_sources,
        "rejected_claims": rejected_claims,
        "notes": [
            "Coverage states describe evidence structure, not truth.",
            "MULTI_SOURCE is not automatic verification.",
            "CONFLICTED claims require explicit human handling before script use.",
            "Only Research Gate accepted claims may enter the verified research package.",
        ],
    }


def run_prepare(handoff_path: Path) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PLANS_DIR.mkdir(parents=True, exist_ok=True)

    if not handoff_path.exists():
        summary = {
            "status": "WAITING_FOR_RESEARCH_HANDOFF",
            "handoff": str(handoff_path),
            "plans_created": 0,
        }
        SUMMARY_FILE.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return summary

    handoff = load_json(handoff_path)
    concepts = handoff.get("concepts", [])
    if not isinstance(concepts, list):
        raise ValueError("Research handoff concepts must be a list")

    paths = []
    for concept in concepts:
        plan = build_research_plan(concept)
        destination = (
            PLANS_DIR
            / f"{safe_slug(plan['concept_id'])}.research_plan.json"
        )
        destination.write_text(
            json.dumps(plan, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        paths.append(str(destination))

    summary = {
        "status": (
            "RESEARCH_PLANS_READY"
            if paths
            else "NO_ACCEPTED_CONCEPTS"
        ),
        "plans_created": len(paths),
        "plans": paths,
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
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

    rejected: list[dict[str, Any]] = []
    drafts: list[str] = []

    if not RESPONSES_DIR.exists():
        summary = {
            "status": "WAITING_FOR_RESEARCH_RESPONSES",
            "draft_packages": 0,
            "rejected_inputs": 0,
        }
        SUMMARY_FILE.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return summary

    for response_path in sorted(RESPONSES_DIR.glob("*.json")):
        response = load_json(response_path)
        concept_id = str(response.get("concept_id", "")).strip()
        plan_path = (
            PLANS_DIR
            / f"{safe_slug(concept_id)}.research_plan.json"
        )
        if not plan_path.exists():
            rejected.append(
                {
                    "response": str(response_path),
                    "errors": [
                        "matching research plan not found"
                    ],
                }
            )
            continue

        plan = load_json(plan_path)
        try:
            draft = validate_research_response(
                response,
                plan,
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

        destination = (
            DRAFTS_DIR
            / f"{safe_slug(concept_id)}.draft_research_package.json"
        )
        destination.write_text(
            json.dumps(draft, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        drafts.append(str(destination))

    REJECTED_FILE.write_text(
        json.dumps(
            {
                "artifact": "rejected_research_inputs",
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
            "DRAFT_RESEARCH_PACKAGES_READY"
            if drafts
            else "NO_VALID_RESEARCH_PACKAGES"
        ),
        "draft_packages": len(drafts),
        "rejected_inputs": len(rejected),
        "drafts": drafts,
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
        description="Research Engine framework"
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
