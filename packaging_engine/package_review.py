"""Incremental UI controller for the human Packaging Gate."""

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
    atomic_write_json(path, payload)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidates_hash() -> str | None:
    return sha256_file(DEFAULT_CANDIDATES) if DEFAULT_CANDIDATES.exists() else None


def package_fingerprint(item: dict[str, Any]) -> str:
    """Fingerprint only the review-visible package content."""
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
    request: dict[str, Any],
    previous: dict[str, Any],
) -> dict[str, Any]:
    prior = previous.get("decisions", {}) if isinstance(previous, dict) else {}
    if not isinstance(prior, dict):
        return {}
    preserved: dict[str, Any] = {}
    for item in request.get("items", []):
        package_id = str(item.get("package_id") or "")
        saved = prior.get(package_id)
        if not isinstance(saved, dict):
            continue
        # A REWORK decision must always come back to the human after regeneration.
        if str(saved.get("decision") or "").upper() == "REWORK":
            continue
        if saved.get("package_fingerprint") != package_fingerprint(item):
            continue
        preserved[package_id] = saved
    return preserved


def prepare_state() -> dict[str, Any]:
    if not DEFAULT_CANDIDATES.exists():
        return {"status": "WAITING_FOR_PACKAGE_CANDIDATES", "packages": []}

    candidates = load_json(DEFAULT_CANDIDATES)
    request = build_review_request(candidates, load_config())
    write_json(REVIEW_REQUEST_FILE, request)
    previous = load_json(STATE_FILE) if STATE_FILE.exists() else {}
    preserved = _preserved_decisions(request, previous)
    state: dict[str, Any] = {
        "schema_version": "1.1",
        "status": (
            "AWAITING_HUMAN_DECISION"
            if request.get("items")
            else "NO_PACKAGES_TO_REVIEW"
        ),
        "candidates_sha256": candidates_hash(),
        "reviewer": (
            previous.get("reviewer")
            if isinstance(previous, dict) and previous.get("reviewer")
            else os.getenv(REVIEWER_ENV, DEFAULT_REVIEWER)
        ),
        "decisions": preserved,
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


def _safe_output_path(value: Any, *, label: str) -> Path:
    path = Path(str(value or "")).expanduser().resolve()
    root = OUTPUT_DIR.resolve()
    if not str(value or "").strip() or (path != root and root not in path.parents):
        raise ValueError(f"{label} must be inside Packaging Engine output")
    return path


def _apply_rework_feedback(
    *,
    package_id: str,
    note: str,
    criteria: dict[str, bool],
) -> None:
    """Make human Packaging Gate feedback authoritative for regeneration."""
    candidates = load_json(DEFAULT_CANDIDATES)
    package = next(
        (
            item
            for item in candidates.get("packages", [])
            if str(item.get("package_id") or "") == package_id
        ),
        None,
    )
    if not isinstance(package, dict):
        raise ValueError("Reworked package is missing from current candidates")

    response_path = _safe_output_path(
        package.get("response_source"),
        label="Package response source",
    )
    if not response_path.exists():
        raise ValueError("Package model response for rework is missing")
    response = load_json(response_path)
    provenance = response.get("response_provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError("Package model response is missing provenance")

    request_path = _safe_output_path(
        provenance.get("request_source"),
        label="Package request source",
    )
    if not request_path.exists():
        raise ValueError("Package request for rework is missing")
    request = load_json(request_path)
    if not isinstance(request, dict):
        raise ValueError("Package request must be an object")

    iteration = int(request.get("human_rework_iteration") or 0) + 1
    request["human_rework_iteration"] = iteration
    request["human_rework_note"] = note
    request["human_rework_package_id"] = package_id
    request["human_rework_keep_criteria"] = sorted(
        key for key, passed in criteria.items() if passed
    )
    request["human_rework_change_criteria"] = sorted(
        key for key, passed in criteria.items() if not passed
    )
    request["human_rework_original_package"] = {
        key: value
        for key, value in package.items()
        if key not in {"response_source", "source_overlap"}
    }
    request["human_rework_original_packages"] = [
        {
            key: value
            for key, value in item.items()
            if key not in {"response_source", "source_overlap"}
        }
        for item in response.get("packages", [])
        if isinstance(item, dict)
    ]
    atomic_write_json(request_path, request)

    # Changing the request hash is not enough: remove the stale model response so
    # readiness immediately exposes package_generate to the automatic workflow.
    response_path.unlink()


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
        "package_fingerprint": package_fingerprint(item),
    }

    if value == "ACCEPT":
        # Choosing one package closes the remaining undecided variants for that
        # concept. The human is selecting a package, not grading every variant.
        concept_id = str(item.get("concept_id", ""))
        for candidate in request.get("items", []):
            sibling_id = str(candidate.get("package_id") or "")
            if (
                sibling_id
                and sibling_id != package_id
                and str(candidate.get("concept_id") or "") == concept_id
                and sibling_id not in state.setdefault("decisions", {})
            ):
                sibling_required = list(
                    candidate.get("required_accept_criteria", [])
                )
                state["decisions"][sibling_id] = {
                    "package_id": sibling_id,
                    "decision": "REJECT",
                    "criteria": {
                        criterion: False for criterion in sibling_required
                    },
                    "note": (
                        "Automatically closed after package "
                        f"{package_id} was accepted for this concept."
                    ),
                    "auto_closed": True,
                    "superseded_by_package_id": package_id,
                    "package_fingerprint": package_fingerprint(candidate),
                }

    state["status"] = "AWAITING_HUMAN_DECISION"

    if value == "REWORK":
        # Persist the human instruction before invalidating the machine artifact.
        write_json(STATE_FILE, state)
        _apply_rework_feedback(
            package_id=package_id,
            note=clean_note,
            criteria=normalized,
        )
        return snapshot()

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
