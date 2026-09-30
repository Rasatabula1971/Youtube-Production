"""Incremental UI controller for the existing human Concept Gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_INTEGRITY_ROOT = Path(__file__).resolve().parent.parent
if str(_INTEGRITY_ROOT) not in sys.path:
    sys.path.insert(0, str(_INTEGRITY_ROOT))

from pipeline_integrity import atomic_write_json

from concept_gate import (
    DEFAULT_CANDIDATES,
    RESEARCH_HANDOFF_FILE,
    REVIEW_REQUEST_FILE,
    REVIEWED_FILE,
    SUMMARY_FILE,
    apply_gate,
    build_review_request,
    load_config,
    load_json,
)

from transformation_engine import OUTPUT_DIR, sha256_file

STATE_FILE = OUTPUT_DIR / "concept_gate_ui_state.json"
IDEA_BANK_DIR = OUTPUT_DIR.parent.parent / ".idea_bank"
SAVED_IDEAS_FILE = IDEA_BANK_DIR / "saved_ideas.json"
REVIEWER_ENV = "YOUTUBE_REVIEWER_ID"
DEFAULT_REVIEWER = "local-operator"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_json(path, payload)


def candidates_hash() -> str | None:
    return sha256_file(DEFAULT_CANDIDATES) if DEFAULT_CANDIDATES.exists() else None


def idea_id_for(item: dict[str, Any]) -> str:
    seed = "\0".join(
        [
            str(item.get("concept_id") or ""),
            str(item.get("working_title") or ""),
            str(item.get("premise") or ""),
        ]
    ).encode("utf-8")
    return hashlib.sha256(seed).hexdigest()[:16]


def load_saved_ideas() -> dict[str, Any]:
    if not SAVED_IDEAS_FILE.exists():
        return {"schema_version": "1.0", "ideas": []}
    try:
        payload = load_json(SAVED_IDEAS_FILE)
    except (OSError, json.JSONDecodeError):
        return {"schema_version": "1.0", "ideas": []}
    if not isinstance(payload, dict) or not isinstance(payload.get("ideas"), list):
        return {"schema_version": "1.0", "ideas": []}
    return payload


def save_idea(item: dict[str, Any], *, note: str, reviewer: str) -> dict[str, Any]:
    bank = load_saved_ideas()
    ideas = [value for value in bank.get("ideas", []) if isinstance(value, dict)]
    idea_id = idea_id_for(item)
    now = datetime.now(timezone.utc).isoformat()
    triage = item.get("llm_triage", {})
    title_test = item.get("title_clarity_test", {})
    entry = {
        "idea_id": idea_id,
        "concept_id": str(item.get("concept_id") or ""),
        "working_title": str(item.get("working_title") or ""),
        "title_options": list(title_test.get("options", []))
        if isinstance(title_test, dict)
        else [],
        "premise": str(item.get("premise") or ""),
        "audience_promise": str(item.get("audience_promise") or ""),
        "viewer_problem": str(item.get("viewer_problem") or ""),
        "viewer_need_evidence": item.get("viewer_need_evidence", {}),
        "mechanism_id": item.get("mechanism_id"),
        "mechanism_label": item.get("mechanism_label"),
        "format_intent": item.get("format_intent"),
        "triage_score": (
            triage.get("overall_score") if isinstance(triage, dict) else None
        ),
        "triage_decision": (
            triage.get("decision") if isinstance(triage, dict) else None
        ),
        "triage_rationale": (
            triage.get("rationale") if isinstance(triage, dict) else None
        ),
        "note": note,
        "saved_by": reviewer,
        "source_candidates_sha256": candidates_hash(),
        "saved_at": now,
        "last_saved_at": now,
    }

    existing = next(
        (value for value in ideas if str(value.get("idea_id")) == idea_id),
        None,
    )
    if existing is not None:
        entry["saved_at"] = existing.get("saved_at") or now
        if not note:
            entry["note"] = str(existing.get("note") or "")
        ideas = [
            entry if str(value.get("idea_id")) == idea_id else value
            for value in ideas
        ]
    else:
        ideas.append(entry)

    bank = {"schema_version": "1.0", "ideas": ideas}
    write_json(SAVED_IDEAS_FILE, bank)
    return entry


def prepare_state() -> dict[str, Any]:
    if not DEFAULT_CANDIDATES.exists():
        return {
            "status": "WAITING_FOR_CONCEPT_CANDIDATES",
            "concepts": [],
        }

    candidates = load_json(DEFAULT_CANDIDATES)
    request = build_review_request(candidates, load_config())
    write_json(REVIEW_REQUEST_FILE, request)

    state: dict[str, Any] = {
        "schema_version": "1.0",
        "status": (
            "AWAITING_HUMAN_DECISION"
            if request.get("items")
            else "NO_CONCEPTS_TO_REVIEW"
        ),
        "candidates_sha256": candidates_hash(),
        "reviewer": os.getenv(REVIEWER_ENV, DEFAULT_REVIEWER),
        "decisions": {},
        "active_override_ids": [],
    }
    write_json(STATE_FILE, state)
    return snapshot()


def current_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    state = load_json(STATE_FILE)
    if state.get("candidates_sha256") != candidates_hash():
        return {}
    return state


def public_item(
    item: dict[str, Any],
    state: dict[str, Any],
    saved_ids: set[str] | None = None,
) -> dict[str, Any]:
    concept_id = str(item["concept_id"])
    decision = state.get("decisions", {}).get(concept_id, {})
    idea_id = idea_id_for(item)
    return {
        **item,
        "decision": decision.get("decision", "PENDING"),
        "criteria_decisions": decision.get("criteria", {}),
        "note": decision.get("note", ""),
        "idea_id": idea_id,
        "idea_saved": idea_id in (saved_ids or set()),
    }


def snapshot() -> dict[str, Any]:
    if not DEFAULT_CANDIDATES.exists():
        return {
            "status": "WAITING_FOR_CONCEPT_CANDIDATES",
            "concepts": [],
            "complete": False,
        }

    candidates = load_json(DEFAULT_CANDIDATES)
    config = load_config()
    request = build_review_request(candidates, config)

    state = current_state()
    if not state:
        return {
            "status": "READY_TO_PREPARE",
            "concepts": [],
            "complete": False,
            "concept_count": request["concept_count"],
        }

    saved_bank = load_saved_ideas()
    saved_ideas = [
        value for value in saved_bank.get("ideas", []) if isinstance(value, dict)
    ]
    saved_ids = {str(value.get("idea_id")) for value in saved_ideas}
    active_overrides = set(state.get("active_override_ids", []))
    all_items = request.get("items", [])
    active_items = [
        item
        for item in all_items
        if item.get("triage_default") is True
        or str(item.get("concept_id")) in active_overrides
    ]
    override_items = [
        public_item(item, state, saved_ids)
        for item in all_items
        if item.get("triage_default") is not True
        and str(item.get("concept_id")) not in active_overrides
    ]
    items = [public_item(item, state, saved_ids) for item in active_items]
    decisions = state.get("decisions", {})
    pending = sum(str(item["concept_id"]) not in decisions for item in active_items)

    status = str(state.get("status") or "AWAITING_HUMAN_DECISION")
    research_status = None
    accepted = 0
    rework = 0
    rejected = 0
    saved = 0
    if REVIEWED_FILE.exists() and state.get("status") == "COMPLETE":
        reviewed = load_json(REVIEWED_FILE)
        counts = reviewed.get("counts", {})
        accepted = int(counts.get("accepted", 0))
        rework = int(counts.get("rework", 0))
        rejected = int(counts.get("rejected", 0))
        saved = int(counts.get("saved", 0))
    if RESEARCH_HANDOFF_FILE.exists() and state.get("status") == "COMPLETE":
        research_status = load_json(RESEARCH_HANDOFF_FILE).get("status")

    return {
        "status": status,
        "complete": status == "COMPLETE",
        "reviewer": state.get("reviewer", DEFAULT_REVIEWER),
        "concept_count": request["concept_count"],
        "pending": pending,
        "accepted": accepted,
        "rework": rework,
        "rejected": rejected,
        "saved": saved,
        "research_status": research_status,
        "criteria": request.get("criteria", {}),
        "concepts": items,
        "override_concepts": override_items,
        "saved_idea_count": len(saved_ideas),
        "saved_ideas": saved_ideas,
    }


def normalize_criteria(
    criteria: Any,
    required: list[str],
) -> dict[str, bool]:
    if not isinstance(criteria, dict):
        criteria = {}
    return {criterion: criteria.get(criterion) is True for criterion in required}


def finalize_if_complete(
    state: dict[str, Any],
    request: dict[str, Any],
) -> None:
    active_overrides = set(state.get("active_override_ids", []))
    active_items = [
        item
        for item in request.get("items", [])
        if item.get("triage_default") is True
        or str(item.get("concept_id")) in active_overrides
    ]
    expected = {str(item["concept_id"]) for item in active_items}
    if not expected or expected != set(state.get("decisions", {})):
        write_json(STATE_FILE, state)
        return

    response = {
        "reviewer": state.get("reviewer", DEFAULT_REVIEWER),
        "decisions": [
            state["decisions"][concept_id] for concept_id in sorted(expected)
        ],
        "overall_note": "",
    }
    active_request = dict(request)
    active_request["items"] = active_items
    active_request["concept_count"] = len(active_items)
    reviewed, handoff = apply_gate(
        load_json(DEFAULT_CANDIDATES),
        active_request,
        response,
        load_config(),
    )
    write_json(REVIEWED_FILE, reviewed)
    write_json(RESEARCH_HANDOFF_FILE, handoff)
    write_json(
        SUMMARY_FILE,
        {
            "status": handoff["status"],
            "accepted": reviewed["counts"]["accepted"],
            "rework": reviewed["counts"]["rework"],
            "rejected": reviewed["counts"]["rejected"],
            "saved": reviewed["counts"]["saved"],
            "reviewed_file": str(REVIEWED_FILE),
            "research_handoff": str(RESEARCH_HANDOFF_FILE),
        },
    )
    state["status"] = "COMPLETE"
    write_json(STATE_FILE, state)


def apply_action(
    *,
    concept_id: str,
    decision: str,
    criteria: Any,
    note: str | None,
) -> dict[str, Any]:
    state = current_state()
    if not state:
        raise ValueError("Concept Gate is not prepared or is stale")

    candidates = load_json(DEFAULT_CANDIDATES)
    request = build_review_request(candidates, load_config())
    item = next(
        (
            value
            for value in request.get("items", [])
            if str(value.get("concept_id")) == concept_id
        ),
        None,
    )
    if item is None:
        raise ValueError("Unknown concept_id")

    value = str(decision or "").strip().upper()
    clean_note = str(note or "").strip()
    active = set(state.get("active_override_ids", []))
    is_active = (
        item.get("triage_default") is True
        or concept_id in active
    )

    if value == "SAVE_IDEA":
        save_idea(
            item,
            note=clean_note,
            reviewer=str(state.get("reviewer") or DEFAULT_REVIEWER),
        )
        # Saving from the closed gate or from the non-active override bank is a
        # bookmark-only action. Saving an active gate concept is a terminal
        # fourth decision that parks it and lets the gate move on.
        if state.get("status") == "COMPLETE" or not is_active:
            return snapshot()

    if state.get("status") == "COMPLETE":
        raise ValueError("Concept Gate is already complete")

    if value == "OVERRIDE":
        if item.get("triage_default") is True:
            raise ValueError("Concept is already in the default Human Gate shortlist")
        active.add(concept_id)
        state["active_override_ids"] = sorted(active)
        state["status"] = "AWAITING_HUMAN_DECISION"
        write_json(STATE_FILE, state)
        return snapshot()
    if value not in {"ACCEPT", "REWORK", "REJECT", "SAVE_IDEA"}:
        raise ValueError(
            "Decision must be ACCEPT, REWORK, REJECT, or SAVE_IDEA"
        )

    required = list(item.get("required_accept_criteria", []))
    if value == "ACCEPT":
        normalized = {criterion: True for criterion in required}
    elif value == "REWORK":
        normalized = normalize_criteria(criteria, required)
        if normalized and all(normalized.values()):
            raise ValueError(
                "REWORK must leave at least one criterion unchecked to mark what changes"
            )
    else:
        normalized = {criterion: False for criterion in required}

    state.setdefault("decisions", {})[concept_id] = {
        "concept_id": concept_id,
        "decision": value,
        "criteria": normalized,
        "note": clean_note,
    }
    state["status"] = "AWAITING_HUMAN_DECISION"
    finalize_if_complete(state, request)
    return snapshot()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Incremental Transformation Engine Concept Gate controller"
    )
    parser.add_argument(
        "--mode",
        choices=("prepare", "status"),
        required=True,
    )
    args = parser.parse_args()

    payload = prepare_state() if args.mode == "prepare" else snapshot()
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
