"""Incremental UI controller for the human Packaging Gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from packaging_gate import (
    APPROVED_FILE,
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

from packaging_engine import OUTPUT_DIR

STATE_FILE = OUTPUT_DIR / "packaging_gate_ui_state.json"
REVIEWER_ENV = "YOUTUBE_REVIEWER_ID"
DEFAULT_REVIEWER = "local-operator"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidates_hash() -> str | None:
    return sha256_file(DEFAULT_CANDIDATES) if DEFAULT_CANDIDATES.exists() else None


def prepare_state() -> dict[str, Any]:
    if not DEFAULT_CANDIDATES.exists():
        return {"status": "WAITING_FOR_PACKAGE_CANDIDATES", "packages": []}

    candidates = load_json(DEFAULT_CANDIDATES)
    request = build_review_request(candidates, load_config())
    write_json(REVIEW_REQUEST_FILE, request)
    state = {
        "schema_version": "1.0",
        "status": (
            "AWAITING_HUMAN_DECISION"
            if request.get("items")
            else "NO_PACKAGES_TO_REVIEW"
        ),
        "candidates_sha256": candidates_hash(),
        "reviewer": os.getenv(REVIEWER_ENV, DEFAULT_REVIEWER),
        "decisions": {},
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


def public_item(item: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    package_id = str(item["package_id"])
    decision = state.get("decisions", {}).get(package_id, {})
    return {
        **item,
        "decision": decision.get("decision", "PENDING"),
        "criteria_decisions": decision.get("criteria", {}),
        "note": decision.get("note", ""),
    }


def snapshot() -> dict[str, Any]:
    if not DEFAULT_CANDIDATES.exists():
        return {
            "status": "WAITING_FOR_PACKAGE_CANDIDATES",
            "packages": [],
            "complete": False,
        }

    candidates = load_json(DEFAULT_CANDIDATES)
    config = load_config()
    request = build_review_request(candidates, config)
    state = current_state()
    if not state:
        return {
            "status": "READY_TO_PREPARE",
            "packages": [],
            "complete": False,
            "package_count": request["package_count"],
        }

    items = [public_item(item, state) for item in request.get("items", [])]
    decisions = state.get("decisions", {})
    pending = sum(
        str(item["package_id"]) not in decisions for item in request.get("items", [])
    )

    status = str(state.get("status") or "AWAITING_HUMAN_DECISION")
    accepted = rework = rejected = 0
    research_status = None
    if REVIEWED_FILE.exists() and status == "COMPLETE":
        reviewed = load_json(REVIEWED_FILE)
        counts = reviewed.get("counts", {})
        accepted = int(counts.get("accepted", 0))
        rework = int(counts.get("rework", 0))
        rejected = int(counts.get("rejected", 0))
    if RESEARCH_HANDOFF_FILE.exists() and status == "COMPLETE":
        research_status = load_json(RESEARCH_HANDOFF_FILE).get("status")

    return {
        "status": status,
        "complete": status == "COMPLETE",
        "reviewer": state.get("reviewer", DEFAULT_REVIEWER),
        "package_count": request["package_count"],
        "pending": pending,
        "accepted": accepted,
        "rework": rework,
        "rejected": rejected,
        "research_status": research_status,
        "criteria": request.get("criteria", {}),
        "packages": items,
    }


def normalize_criteria(criteria: Any, required: list[str]) -> dict[str, bool]:
    if not isinstance(criteria, dict):
        criteria = {}
    return {criterion: criteria.get(criterion) is True for criterion in required}


def finalize_if_complete(
    state: dict[str, Any],
    request: dict[str, Any],
) -> None:
    expected = {str(item["package_id"]) for item in request.get("items", [])}
    if expected != set(state.get("decisions", {})):
        write_json(STATE_FILE, state)
        return

    response = {
        "reviewer": state.get("reviewer", DEFAULT_REVIEWER),
        "decisions": [
            state["decisions"][package_id] for package_id in sorted(expected)
        ],
        "overall_note": "",
    }
    reviewed, handoff = apply_gate(
        load_json(DEFAULT_CANDIDATES),
        request,
        response,
        load_config(),
    )
    write_json(REVIEWED_FILE, reviewed)
    write_json(
        APPROVED_FILE,
        {
            "artifact": "approved_packages",
            "count": reviewed["counts"]["accepted"],
            "packages": reviewed["accepted"],
        },
    )
    write_json(RESEARCH_HANDOFF_FILE, handoff)
    write_json(
        SUMMARY_FILE,
        {
            "status": handoff["status"],
            "accepted": reviewed["counts"]["accepted"],
            "rework": reviewed["counts"]["rework"],
            "rejected": reviewed["counts"]["rejected"],
            "research_handoff": str(RESEARCH_HANDOFF_FILE),
        },
    )
    state["status"] = "COMPLETE"
    write_json(STATE_FILE, state)


def apply_action(
    *,
    package_id: str,
    decision: str,
    criteria: Any,
    note: str | None,
) -> dict[str, Any]:
    state = current_state()
    if not state:
        raise ValueError("Packaging Gate is not prepared or is stale")
    if state.get("status") == "COMPLETE":
        raise ValueError("Packaging Gate is already complete")

    candidates = load_json(DEFAULT_CANDIDATES)
    request = build_review_request(candidates, load_config())
    item = next(
        (
            value
            for value in request.get("items", [])
            if str(value.get("package_id")) == package_id
        ),
        None,
    )
    if item is None:
        raise ValueError("Unknown package_id")

    value = str(decision or "").strip().upper()
    if value not in {"ACCEPT", "REWORK", "REJECT"}:
        raise ValueError("Decision must be ACCEPT, REWORK, or REJECT")

    required = list(item.get("required_accept_criteria", []))
    normalized = normalize_criteria(criteria, required)
    clean_note = str(note or "").strip()

    if value == "ACCEPT" and not all(normalized.values()):
        missing = [key for key, passed in normalized.items() if not passed]
        raise ValueError(
            "ACCEPT requires every criterion confirmed: " + ", ".join(missing)
        )
    if value == "REWORK" and not clean_note:
        raise ValueError("REWORK requires a note explaining what must change")

    if value == "ACCEPT":
        concept_id = str(item.get("concept_id", ""))
        conflicts = [
            existing_id
            for existing_id, existing in state.get("decisions", {}).items()
            if existing_id != package_id
            and existing.get("decision") == "ACCEPT"
            and next(
                (
                    str(candidate.get("concept_id", ""))
                    for candidate in request.get("items", [])
                    if str(candidate.get("package_id")) == existing_id
                ),
                "",
            )
            == concept_id
        ]
        if conflicts:
            raise ValueError(
                "Only one package may be accepted per concept. "
                "Reject or rework the existing accepted package first."
            )

    state.setdefault("decisions", {})[package_id] = {
        "package_id": package_id,
        "decision": value,
        "criteria": normalized,
        "note": clean_note,
    }
    state["status"] = "AWAITING_HUMAN_DECISION"
    finalize_if_complete(state, request)
    return snapshot()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Incremental Packaging Gate controller"
    )
    parser.add_argument("--mode", choices=("prepare", "status"), required=True)
    args = parser.parse_args()
    payload = prepare_state() if args.mode == "prepare" else snapshot()
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
