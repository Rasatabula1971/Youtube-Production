"""Incremental UI controller for the human Research Gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

_INTEGRITY_ROOT = Path(__file__).resolve().parent.parent
if str(_INTEGRITY_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEGRITY_ROOT))

from pipeline_integrity import atomic_write_json

from research_gate import (
    DEFAULT_DRAFTS_DIR,
    REVIEW_REQUESTS_DIR,
    REVIEWED_DIR,
    SUMMARY_FILE,
    VERIFIED_DIR,
    apply_gate,
    build_review_request,
    load_config,
    load_json,
    safe_slug,
)

OUTPUT_DIR = DEFAULT_DRAFTS_DIR.parent
STATE_FILE = OUTPUT_DIR / "research_gate_ui_state.json"
REVIEWER_ENV = "YOUTUBE_REVIEWER_ID"
DEFAULT_REVIEWER = "local-operator"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_json(path, payload)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def claim_fingerprint(item: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in item.items()
        if key not in {"decision", "criteria_decisions", "note"}
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _preserved_decisions(
    requests: list[dict[str, Any]],
    previous: dict[str, Any],
) -> dict[str, Any]:
    prior = previous.get("decisions", {}) if isinstance(previous, dict) else {}
    if not isinstance(prior, dict):
        return {}
    preserved: dict[str, Any] = {}
    for bundle in requests:
        concept_id = bundle["concept_id"]
        for item in bundle["request"].get("items", []):
            claim_id = str(item.get("claim_id") or "")
            key = key_for(concept_id, claim_id)
            saved = prior.get(key)
            if not isinstance(saved, dict):
                continue
            if str(saved.get("decision") or "").upper() == "REWORK":
                continue
            if saved.get("claim_fingerprint") != claim_fingerprint(item):
                continue
            preserved[key] = saved
    return preserved


def _apply_rework_feedback(
    *,
    concept_id: str,
    claim_id: str,
    item: dict[str, Any],
    note: str,
) -> None:
    plans_dir = OUTPUT_DIR / "plans"
    plan_path = plans_dir / f"{safe_slug(concept_id)}.research_plan.json"
    if not plan_path.exists():
        raise ValueError("Research rework cannot find the current research plan")

    plan = load_json(plan_path)
    if str(plan.get("concept_id") or "") != concept_id:
        raise ValueError("Research rework plan concept_id mismatch")

    requests = plan.get("human_rework_requests", [])
    if not isinstance(requests, list):
        requests = []
    previous = [
        value
        for value in requests
        if isinstance(value, dict)
        and str(value.get("claim_id") or "") != claim_id
    ]
    iteration = 1 + max(
        (
            int(value.get("iteration") or 0)
            for value in requests
            if isinstance(value, dict)
            and str(value.get("claim_id") or "") == claim_id
        ),
        default=0,
    )
    question_id = f"hrw_{safe_slug(claim_id)}"
    request = {
        "claim_id": claim_id,
        "iteration": iteration,
        "note": note,
        "question_id": question_id,
        "original_claim": {
            key: value
            for key, value in item.items()
            if key not in {
                "required_accept_criteria",
                "criteria_descriptions",
                "criteria_decisions",
                "decision",
                "note",
            }
        },
    }
    previous.append(request)
    plan["human_rework_requests"] = previous
    plan["human_rework_mode"] = "HUMAN_INSTRUCTION_ONLY"

    questions = plan.get("research_questions", [])
    if not isinstance(questions, list):
        questions = []
    questions = [
        question
        for question in questions
        if not (
            isinstance(question, dict)
            and str(question.get("rework_claim_id") or "") == claim_id
        )
    ]
    questions.append(
        {
            "question_id": question_id,
            "question": note,
            "origin": "human_rework",
            "rework_claim_id": claim_id,
        }
    )
    plan["research_questions"] = questions

    instructions = plan.get("instructions", [])
    if not isinstance(instructions, list):
        instructions = []
    directive = (
        "Human Research Gate rework instructions are authoritative: investigate "
        "the requested issue again using acquired evidence. The instruction may "
        "change what must be researched, but it never authorizes invented facts."
    )
    if directive not in instructions:
        instructions.append(directive)
    plan["instructions"] = instructions
    write_json(plan_path, plan)


def current_drafts() -> list[Path]:
    if not DEFAULT_DRAFTS_DIR.exists():
        return []
    return sorted(DEFAULT_DRAFTS_DIR.glob("*.draft_research_package.json"))


def drafts_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in current_drafts():
        package = load_json(path)
        concept_id = str(package.get("concept_id", "")).strip()
        if concept_id:
            hashes[concept_id] = sha256_file(path)
    return hashes


def build_requests() -> list[dict[str, Any]]:
    requests = []
    config = load_config()
    REVIEW_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    for draft_path in current_drafts():
        package = load_json(draft_path)
        request = build_review_request(package, config)
        concept_id = str(request["concept_id"])
        request_path = (
            REVIEW_REQUESTS_DIR / f"{safe_slug(concept_id)}.research_gate_request.json"
        )
        write_json(request_path, request)
        requests.append(
            {
                "concept_id": concept_id,
                "draft_path": str(draft_path),
                "request_path": str(request_path),
                "request": request,
            }
        )
    return requests


def prepare_state() -> dict[str, Any]:
    requests = build_requests()
    if not requests:
        return {"status": "WAITING_FOR_DRAFT_RESEARCH_PACKAGES", "claims": []}

    previous = load_json(STATE_FILE) if STATE_FILE.exists() else {}
    state = {
        "schema_version": "1.1",
        "status": "AWAITING_HUMAN_DECISION",
        "draft_hashes": drafts_hashes(),
        "reviewer": os.getenv(REVIEWER_ENV, DEFAULT_REVIEWER),
        "decisions": _preserved_decisions(requests, previous),
    }
    write_json(STATE_FILE, state)
    return snapshot()


def current_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    state = load_json(STATE_FILE)
    if state.get("draft_hashes") != drafts_hashes():
        return {}
    return state


def key_for(concept_id: str, claim_id: str) -> str:
    return f"{concept_id}::{claim_id}"


def snapshot() -> dict[str, Any]:
    requests = build_requests() if current_drafts() else []
    if not requests:
        return {
            "status": "WAITING_FOR_DRAFT_RESEARCH_PACKAGES",
            "claims": [],
            "complete": False,
        }

    state = current_state()
    claim_count = sum(int(item["request"].get("claim_count", 0)) for item in requests)
    if not state:
        return {
            "status": "READY_TO_PREPARE",
            "claims": [],
            "complete": False,
            "claim_count": claim_count,
        }

    decisions = state.get("decisions", {})
    claims = []
    for bundle in requests:
        request = bundle["request"]
        concept_id = bundle["concept_id"]
        for item in request.get("items", []):
            claim_id = str(item["claim_id"])
            decision = decisions.get(key_for(concept_id, claim_id), {})
            claims.append(
                {
                    **item,
                    "concept_id": concept_id,
                    "concept": request.get("concept", {}),
                    "research_questions": request.get("research_questions", []),
                    "criteria_descriptions": request.get("criteria", {}),
                    "decision": decision.get("decision", "PENDING"),
                    "criteria_decisions": decision.get("criteria", {}),
                    "note": decision.get("note", ""),
                }
            )

    pending = sum(item["decision"] == "PENDING" for item in claims)
    verified_statuses = []
    current_concept_ids = {bundle["concept_id"] for bundle in requests}
    if state.get("status") == "COMPLETE" and VERIFIED_DIR.exists():
        for path in sorted(VERIFIED_DIR.glob("*.verified_research_package.json")):
            payload = load_json(path)
            if str(payload.get("concept_id", "")) not in current_concept_ids:
                continue
            verified_statuses.append(
                {
                    "concept_id": payload.get("concept_id"),
                    "status": payload.get("status"),
                    "unresolved_question_ids": payload.get(
                        "unresolved_question_ids", []
                    ),
                }
            )

    ready_count = sum(
        item.get("status") == "READY_FOR_STORY_SCRIPT" for item in verified_statuses
    )
    return {
        "status": str(state.get("status") or "AWAITING_HUMAN_DECISION"),
        "complete": state.get("status") == "COMPLETE",
        "reviewer": state.get("reviewer", DEFAULT_REVIEWER),
        "claim_count": claim_count,
        "pending": pending,
        "claims": claims,
        "verified_packages": verified_statuses,
        "ready_for_story_script": ready_count,
    }


def normalize_criteria(criteria: Any, required: list[str]) -> dict[str, bool]:
    if not isinstance(criteria, dict):
        criteria = {}
    return {criterion: criteria.get(criterion) is True for criterion in required}


def finalize_if_complete(
    state: dict[str, Any],
    requests: list[dict[str, Any]],
) -> None:
    expected = {
        key_for(bundle["concept_id"], str(item["claim_id"]))
        for bundle in requests
        for item in bundle["request"].get("items", [])
    }
    if expected != set(state.get("decisions", {})):
        write_json(STATE_FILE, state)
        return

    REVIEWED_DIR.mkdir(parents=True, exist_ok=True)
    VERIFIED_DIR.mkdir(parents=True, exist_ok=True)
    current_concept_ids = {bundle["concept_id"] for bundle in requests}
    for directory, pattern in (
        (REVIEWED_DIR, "*.research_gate_reviewed.json"),
        (VERIFIED_DIR, "*.verified_research_package.json"),
    ):
        for stale_path in directory.glob(pattern):
            payload = load_json(stale_path)
            if str(payload.get("concept_id", "")) not in current_concept_ids:
                stale_path.unlink()

    summaries = []
    for bundle in requests:
        concept_id = bundle["concept_id"]
        package = load_json(Path(bundle["draft_path"]))
        request = bundle["request"]
        response = {
            "concept_id": concept_id,
            "reviewer": state.get("reviewer", DEFAULT_REVIEWER),
            "decisions": [
                state["decisions"][key_for(concept_id, str(item["claim_id"]))]
                for item in request.get("items", [])
            ],
            "overall_note": "",
        }
        reviewed, verified = apply_gate(
            package,
            request,
            response,
            load_config(),
        )
        slug = safe_slug(concept_id)
        reviewed_path = REVIEWED_DIR / f"{slug}.research_gate_reviewed.json"
        verified_path = VERIFIED_DIR / f"{slug}.verified_research_package.json"
        write_json(reviewed_path, reviewed)
        write_json(verified_path, verified)
        summaries.append(
            {
                "concept_id": concept_id,
                "status": verified["status"],
                "accepted": reviewed["counts"]["accepted"],
                "rework": reviewed["counts"]["rework"],
                "rejected": reviewed["counts"]["rejected"],
                "unresolved_questions": len(verified["unresolved_question_ids"]),
                "verified_package": str(verified_path),
            }
        )

    write_json(
        SUMMARY_FILE,
        {
            "status": (
                "READY_FOR_STORY_SCRIPT"
                if summaries
                and all(
                    item["status"] == "READY_FOR_STORY_SCRIPT" for item in summaries
                )
                else "RESEARCH_INCOMPLETE"
            ),
            "packages": summaries,
        },
    )
    state["status"] = "COMPLETE"
    write_json(STATE_FILE, state)


def apply_action(
    *,
    concept_id: str,
    claim_id: str,
    decision: str,
    criteria: Any,
    note: str | None,
) -> dict[str, Any]:
    state = current_state()
    if not state:
        raise ValueError("Research Gate is not prepared or is stale")
    if state.get("status") == "COMPLETE":
        raise ValueError("Research Gate is already complete")

    requests = build_requests()
    bundle = next(
        (item for item in requests if item["concept_id"] == concept_id),
        None,
    )
    if bundle is None:
        raise ValueError("Unknown concept_id")
    item = next(
        (
            value
            for value in bundle["request"].get("items", [])
            if str(value.get("claim_id")) == claim_id
        ),
        None,
    )
    if item is None:
        raise ValueError("Unknown claim_id")

    value = str(decision or "").strip().upper()
    if value not in {"ACCEPT", "REWORK", "REJECT"}:
        raise ValueError("Decision must be ACCEPT, REWORK, or REJECT")

    required = list(item.get("required_accept_criteria", []))
    clean_note = str(note or "").strip()
    # REWORK and REJECT both record every criterion as unconfirmed; the gate's
    # final validation requires every criterion key on every decision.
    normalized = {criterion: value == "ACCEPT" for criterion in required}
    if value == "REWORK" and not clean_note:
        raise ValueError("REWORK requires a note explaining what must change")
    if (
        value == "ACCEPT"
        and item.get("coverage", {}).get("state") == "CONFLICTED"
        and load_config().get("require_conflict_resolution_note")
        and not clean_note
    ):
        raise ValueError("Accepted conflicted claim requires a resolution note")

    state.setdefault("decisions", {})[key_for(concept_id, claim_id)] = {
        "claim_id": claim_id,
        "decision": value,
        "criteria": normalized,
        "note": clean_note,
        "claim_fingerprint": claim_fingerprint(item),
    }

    if value == "REWORK":
        _apply_rework_feedback(
            concept_id=concept_id,
            claim_id=claim_id,
            item=item,
            note=clean_note,
        )

    state["status"] = "AWAITING_HUMAN_DECISION"
    finalize_if_complete(state, requests)
    return snapshot()


def main() -> None:
    parser = argparse.ArgumentParser(description="Incremental Research Gate controller")
    parser.add_argument("--mode", choices=("prepare", "status"), required=True)
    args = parser.parse_args()
    result = prepare_state() if args.mode == "prepare" else snapshot()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
