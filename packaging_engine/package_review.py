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
SAVED_PACKAGES_FILE = OUTPUT_DIR / "saved_package_ideas.json"
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
        "selected_titles": decision.get("selected_titles", {}),
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
        "saved": (
            len(load_json(SAVED_PACKAGES_FILE).get("items", []))
            if SAVED_PACKAGES_FILE.exists()
            else 0
        ),
        "research_status": research_status,
        "criteria": request.get("criteria", {}),
        "packages": items,
    }


def normalize_criteria(criteria: Any, required: list[str]) -> dict[str, bool]:
    if not isinstance(criteria, dict):
        criteria = {}
    return {criterion: criteria.get(criterion) is True for criterion in required}


def save_package_idea(
    item: dict[str, Any],
    *,
    note: str,
    reviewer: str,
) -> None:
    payload: dict[str, Any] = {
        "artifact": "saved_package_ideas",
        "items": [],
    }
    if SAVED_PACKAGES_FILE.exists():
        loaded = load_json(SAVED_PACKAGES_FILE)
        if isinstance(loaded, dict):
            payload = loaded
    items = payload.get("items")
    if not isinstance(items, list):
        items = []

    fingerprint = package_fingerprint(item)
    saved = {
        "package_id": str(item.get("package_id") or ""),
        "concept_id": str(item.get("concept_id") or ""),
        "title": item.get("title"),
        "titles": item.get("titles", {}),
        "thumbnail": item.get("thumbnail"),
        "opening_frame": item.get("opening_frame"),
        "expected_viewer": item.get("expected_viewer"),
        "one_sentence_promise": item.get("one_sentence_promise"),
        "note": note,
        "reviewer": reviewer,
        "package_fingerprint": fingerprint,
    }
    items = [
        existing
        for existing in items
        if not (
            isinstance(existing, dict)
            and existing.get("package_fingerprint") == fingerprint
        )
    ]
    items.append(saved)
    payload["items"] = items
    payload["count"] = len(items)
    write_json(SAVED_PACKAGES_FILE, payload)


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
    request["human_rework_mode"] = (
        "CRITERIA_GUIDED" if criteria else "HUMAN_INSTRUCTION_ONLY"
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
    selected_titles: Any = None,
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
    if value not in {"ACCEPT", "REWORK", "REJECT", "SAVE_IDEA"}:
        raise ValueError(
            "Decision must be ACCEPT, REWORK, REJECT, or SAVE_IDEA"
        )

    required = list(item.get("required_accept_criteria", []))
    clean_note = str(note or "").strip()

    if value == "SAVE_IDEA":
        save_package_idea(
            item,
            note=clean_note,
            reviewer=str(state.get("reviewer") or DEFAULT_REVIEWER),
        )
        return snapshot()

    # The human gate is intentionally a decision gate, not a checklist form.
    # Lower-level audit contracts still receive explicit criteria.
    normalized = (
        {criterion: True for criterion in required}
        if value == "ACCEPT"
        else {criterion: False for criterion in required}
        if value == "REJECT"
        else {}
    )
    if value == "REWORK" and not clean_note:
        raise ValueError("REWORK requires a note explaining what must change")

    clean_selected_titles: dict[str, dict[str, str]] = {}
    if value == "ACCEPT":
        available_sets = item.get("titles", {})
        has_new_title_sets = (
            isinstance(available_sets, dict)
            and isinstance(available_sets.get("short"), list)
            and bool(available_sets.get("short"))
            and isinstance(available_sets.get("long_form"), list)
            and bool(available_sets.get("long_form"))
        )
        if not isinstance(selected_titles, dict):
            if has_new_title_sets:
                raise ValueError(
                    "ACCEPT requires one Short title and one Long-form title selection"
                )
            legacy_title = str(item.get("title") or "").strip()
            selected_titles = {
                "short": {"candidate_id": "legacy", "title": legacy_title},
                "long_form": {"candidate_id": "legacy", "title": legacy_title},
            }
        for fmt in ("short", "long_form"):
            selection = selected_titles.get(fmt)
            if not isinstance(selection, dict):
                raise ValueError(f"ACCEPT requires selected_titles.{fmt}")
            title_text = str(selection.get("title") or "").strip()
            candidate_id = str(selection.get("candidate_id") or "").strip()
            if not title_text:
                raise ValueError(f"ACCEPT requires a non-empty {fmt} title")
            if not candidate_id:
                candidate_id = "manual"
            if candidate_id not in {"manual", "legacy"}:
                candidates = (
                    available_sets.get(fmt, [])
                    if isinstance(available_sets, dict)
                    else []
                )
                match = next(
                    (
                        candidate
                        for candidate in candidates
                        if isinstance(candidate, dict)
                        and str(candidate.get("candidate_id") or "")
                        == candidate_id
                    ),
                    None,
                )
                if not isinstance(match, dict):
                    raise ValueError(f"Unknown {fmt} title candidate")
                if str(match.get("title") or "").strip() != title_text:
                    raise ValueError(
                        f"{fmt} selected title does not match its candidate"
                    )
            clean_selected_titles[fmt] = {
                "candidate_id": candidate_id,
                "title": title_text,
            }

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
        "selected_titles": clean_selected_titles,
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
