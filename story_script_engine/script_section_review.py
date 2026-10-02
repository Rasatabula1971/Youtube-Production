"""Deterministic section-level review contract for Script Gate.

Slice 1 only: build and validate review state. No human actions, model calls,
regeneration, alternatives, or draft mutation are implemented here.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

SCHEMA_VERSION = 1
INITIAL_SCRIPT_REVISION = 0
INITIAL_STATE_REVISION = 0

REVIEW_STATES = (
    "PENDING",
    "ACCEPTED",
    "REWORK_REQUESTED",
)

SECTION_ACTIONS = (
    "ACCEPT",
    "LOCK",
    "UNLOCK",
    "REWORK",
    "CANCEL_REWORK",
)

REWORK_REASONS = (
    "TOO_BORING",
    "TOO_LONG",
    "TOO_TECHNICAL",
    "NOT_DRAMATIC_ENOUGH",
    "WEAK_TRANSITION",
    "FACT_UNCLEAR",
    "UNNATURAL",
    "WEAK_CURIOSITY",
    "WEAK_EMOTION",
    "CUSTOM_INSTRUCTION",
)


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _base_target(
    *,
    target_id: str,
    target_type: str,
    content: Any,
    source_section_id: str | None,
    source_story_beat_ids: list[str],
    claim_ids: list[str],
) -> dict[str, Any]:
    return {
        "target_id": target_id,
        "target_type": target_type,
        "source_section_id": source_section_id,
        "source_story_beat_ids": source_story_beat_ids,
        "claim_ids": claim_ids,
        "review_state": "PENDING",
        "locked": False,
        "editable": True,
        "revision": 0,
        "rework_reason": None,
        "rework_note": None,
        "last_action": None,
        "last_reviewer": None,
        "last_updated_at": None,
        "content_sha256": _canonical_sha256(content),
    }


def build_section_review_state(
    draft: dict[str, Any],
    *,
    source_draft_sha256: str,
) -> dict[str, Any]:
    """Create deterministic per-target review state for one exact script draft."""
    if not isinstance(draft, dict):
        raise ValueError("Script draft must be an object")

    draft_hash = str(source_draft_sha256 or "").strip()
    if not draft_hash:
        raise ValueError("source_draft_sha256 is required")

    opening_hook = str(draft.get("opening_hook") or "").strip()
    if not opening_hook:
        raise ValueError("Script draft requires opening_hook for section review")

    closing = str(draft.get("closing") or "").strip()
    if not closing:
        raise ValueError("Script draft requires closing for section review")

    sections = draft.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("Script draft requires sections for section review")

    targets: list[dict[str, Any]] = [
        _base_target(
            target_id="opening_hook",
            target_type="OPENING_HOOK",
            content={
                "opening_hook": draft.get("opening_hook"),
                "opening_hook_mechanism": draft.get("opening_hook_mechanism"),
                "opening_hook_claim_ids": draft.get(
                    "opening_hook_claim_ids",
                    [],
                ),
            },
            source_section_id=None,
            source_story_beat_ids=[],
            claim_ids=[
                str(item)
                for item in draft.get("opening_hook_claim_ids", [])
            ],
        )
    ]

    seen_section_ids: set[str] = set()
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            raise ValueError(f"Script section {index} must be an object")
        section_id = str(section.get("section_id") or "").strip()
        if not section_id:
            raise ValueError(f"Script section {index} requires section_id")
        if section_id in seen_section_ids:
            raise ValueError(f"Duplicate script section_id: {section_id}")
        seen_section_ids.add(section_id)

        narration = str(section.get("narration") or "").strip()
        if not narration:
            raise ValueError(
                f"Script section {section_id} requires narration"
            )

        source_story_beat_ids = section.get("source_story_beat_ids", [])
        if not isinstance(source_story_beat_ids, list):
            raise ValueError(
                f"Script section {section_id} source_story_beat_ids must be a list"
            )
        claim_ids = section.get("claim_ids", [])
        if not isinstance(claim_ids, list):
            raise ValueError(
                f"Script section {section_id} claim_ids must be a list"
            )

        targets.append(
            _base_target(
                target_id=f"section:{section_id}",
                target_type="SECTION",
                content=section,
                source_section_id=section_id,
                source_story_beat_ids=[
                    str(item) for item in source_story_beat_ids
                ],
                claim_ids=[str(item) for item in claim_ids],
            )
        )

    targets.append(
        _base_target(
            target_id="closing",
            target_type="CLOSING",
            content={"closing": draft.get("closing")},
            source_section_id=None,
            source_story_beat_ids=[],
            claim_ids=[],
        )
    )

    return {
        "artifact": "script_section_review_state",
        "schema_version": SCHEMA_VERSION,
        "source_draft_sha256": draft_hash,
        "script_revision": INITIAL_SCRIPT_REVISION,
        "state_revision": INITIAL_STATE_REVISION,
        "allowed_review_states": list(REVIEW_STATES),
        "allowed_rework_reasons": list(REWORK_REASONS),
        "targets": targets,
    }


def validate_section_review_state(state: Any) -> dict[str, Any]:
    """Validate Slice 1 state without applying any review action."""
    errors: list[str] = []
    if not isinstance(state, dict):
        return {
            "valid": False,
            "errors": ["section review state must be an object"],
        }

    if state.get("artifact") != "script_section_review_state":
        errors.append("artifact must be script_section_review_state")
    if state.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must equal {SCHEMA_VERSION}")

    source_hash = str(state.get("source_draft_sha256") or "").strip()
    if not source_hash:
        errors.append("source_draft_sha256 is required")

    for field in ("script_revision", "state_revision"):
        value = state.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"{field} must be a non-negative integer")

    targets = state.get("targets")
    if not isinstance(targets, list) or not targets:
        errors.append("targets must be a non-empty list")
        targets = []

    seen: set[str] = set()
    for index, target in enumerate(targets):
        if not isinstance(target, dict):
            errors.append(f"target {index} must be an object")
            continue
        target_id = str(target.get("target_id") or "").strip()
        if not target_id:
            errors.append(f"target {index} requires target_id")
        elif target_id in seen:
            errors.append(f"duplicate target_id: {target_id}")
        seen.add(target_id)

        target_type = str(target.get("target_type") or "")
        if target_type not in {"OPENING_HOOK", "SECTION", "CLOSING"}:
            errors.append(f"{target_id or index} has invalid target_type")

        review_state = str(target.get("review_state") or "")
        if review_state not in REVIEW_STATES:
            errors.append(f"{target_id or index} has invalid review_state")

        if not isinstance(target.get("locked"), bool):
            errors.append(f"{target_id or index} locked must be boolean")
        if not isinstance(target.get("editable"), bool):
            errors.append(f"{target_id or index} editable must be boolean")

        revision = target.get("revision")
        if (
            not isinstance(revision, int)
            or isinstance(revision, bool)
            or revision < 0
        ):
            errors.append(
                f"{target_id or index} revision must be non-negative integer"
            )

        content_hash = str(target.get("content_sha256") or "").strip()
        if not content_hash:
            errors.append(f"{target_id or index} requires content_sha256")

        reason = target.get("rework_reason")
        if reason is not None and str(reason) not in REWORK_REASONS:
            errors.append(f"{target_id or index} has invalid rework_reason")

        note = target.get("rework_note")
        if note is not None and not isinstance(note, str):
            errors.append(f"{target_id or index} rework_note must be string or null")

        locked = target.get("locked")
        editable = target.get("editable")
        if isinstance(locked, bool) and isinstance(editable, bool):
            if locked and editable:
                errors.append(
                    f"{target_id or index} locked target cannot be editable"
                )
            if not locked and not editable:
                errors.append(
                    f"{target_id or index} unlocked target must be editable"
                )

        if review_state == "ACCEPTED":
            if locked is not True or editable is not False:
                errors.append(
                    f"{target_id or index} ACCEPTED target must be locked and non-editable"
                )
            if reason is not None or note is not None:
                errors.append(
                    f"{target_id or index} ACCEPTED target cannot retain rework metadata"
                )
        elif review_state == "REWORK_REQUESTED":
            if locked is not False or editable is not True:
                errors.append(
                    f"{target_id or index} REWORK_REQUESTED target must be unlocked and editable"
                )
            if reason is None:
                errors.append(
                    f"{target_id or index} REWORK_REQUESTED target requires rework_reason"
                )
            if reason == "CUSTOM_INSTRUCTION" and not str(note or "").strip():
                errors.append(
                    f"{target_id or index} CUSTOM_INSTRUCTION requires rework_note"
                )
        elif review_state == "PENDING":
            if reason is not None or note is not None:
                errors.append(
                    f"{target_id or index} PENDING target cannot retain rework metadata"
                )

        for field in ("last_action", "last_reviewer", "last_updated_at"):
            value = target.get(field)
            if value is not None and not isinstance(value, str):
                errors.append(
                    f"{target_id or index} {field} must be string or null"
                )

    return {"valid": not errors, "errors": errors}


def apply_target_action(
    state: dict[str, Any],
    *,
    source_draft_sha256: str,
    target_id: str,
    action: str,
    reviewer: str,
    updated_at: str,
    reason: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Apply one Slice 2 state transition without mutating script text."""
    validation = validate_section_review_state(state)
    if not validation["valid"]:
        raise ValueError(
            "Invalid section review state: " + "; ".join(validation["errors"])
        )

    expected_hash = str(state.get("source_draft_sha256") or "")
    actual_hash = str(source_draft_sha256 or "").strip()
    if not actual_hash or actual_hash != expected_hash:
        raise ValueError(
            "STALE_SECTION_REVIEW_STATE: source draft hash does not match"
        )

    normalized_target_id = str(target_id or "").strip()
    if not normalized_target_id:
        raise ValueError("target_id is required")

    normalized_action = str(action or "").strip().upper()
    if normalized_action not in SECTION_ACTIONS:
        raise ValueError("invalid section review action")

    normalized_reviewer = str(reviewer or "").strip()
    if not normalized_reviewer:
        raise ValueError("reviewer is required")
    normalized_updated_at = str(updated_at or "").strip()
    if not normalized_updated_at:
        raise ValueError("updated_at is required")

    normalized_reason = (
        str(reason).strip().upper() if reason is not None else None
    )
    normalized_note = str(note).strip() if note is not None else None
    if normalized_note == "":
        normalized_note = None

    revised = copy.deepcopy(state)
    targets = revised.get("targets", [])
    target = next(
        (
            item
            for item in targets
            if isinstance(item, dict)
            and str(item.get("target_id") or "") == normalized_target_id
        ),
        None,
    )
    if target is None:
        raise ValueError(f"Unknown section review target: {normalized_target_id}")

    previous = copy.deepcopy(target)
    previous_review_state = str(target.get("review_state") or "")
    previous_locked = bool(target.get("locked"))

    if normalized_action == "REWORK":
        if previous_locked:
            raise ValueError(
                "Locked target cannot be marked for rework; unlock it first"
            )
        if normalized_reason not in REWORK_REASONS:
            raise ValueError("REWORK requires a valid rework_reason")
        if (
            normalized_reason == "CUSTOM_INSTRUCTION"
            and not normalized_note
        ):
            raise ValueError(
                "CUSTOM_INSTRUCTION requires a non-empty rework_note"
            )
        target["review_state"] = "REWORK_REQUESTED"
        target["locked"] = False
        target["editable"] = True
        target["rework_reason"] = normalized_reason
        target["rework_note"] = normalized_note

    elif normalized_action == "CANCEL_REWORK":
        if previous_review_state != "REWORK_REQUESTED":
            raise ValueError(
                "CANCEL_REWORK requires a REWORK_REQUESTED target"
            )
        target["review_state"] = "PENDING"
        target["locked"] = False
        target["editable"] = True
        target["rework_reason"] = None
        target["rework_note"] = None

    elif normalized_action == "ACCEPT":
        target["review_state"] = "ACCEPTED"
        target["locked"] = True
        target["editable"] = False
        target["rework_reason"] = None
        target["rework_note"] = None

    elif normalized_action == "LOCK":
        if previous_review_state == "REWORK_REQUESTED":
            raise ValueError(
                "Cancel rework before locking a REWORK_REQUESTED target"
            )
        target["locked"] = True
        target["editable"] = False

    elif normalized_action == "UNLOCK":
        target["locked"] = False
        target["editable"] = True
        if previous_review_state == "ACCEPTED":
            target["review_state"] = "PENDING"
        target["rework_reason"] = None
        target["rework_note"] = None

    comparable_before = {
        key: value
        for key, value in previous.items()
        if key not in {"revision", "last_action", "last_reviewer", "last_updated_at"}
    }
    comparable_after = {
        key: value
        for key, value in target.items()
        if key not in {"revision", "last_action", "last_reviewer", "last_updated_at"}
    }
    changed = comparable_after != comparable_before

    if changed:
        target["revision"] = int(previous.get("revision") or 0) + 1
        target["last_action"] = normalized_action
        target["last_reviewer"] = normalized_reviewer
        target["last_updated_at"] = normalized_updated_at
        revised["state_revision"] = int(state.get("state_revision") or 0) + 1

    post_validation = validate_section_review_state(revised)
    if not post_validation["valid"]:
        raise ValueError(
            "Section review transition produced invalid state: "
            + "; ".join(post_validation["errors"])
        )

    return {
        "state": revised,
        "changed": changed,
        "target": copy.deepcopy(target),
        "previous_review_state": previous_review_state,
        "previous_locked": previous_locked,
        "invalidates_branch_approval": bool(
            changed
            and (
                normalized_action == "REWORK"
                or (
                    normalized_action == "UNLOCK"
                    and previous_review_state == "ACCEPTED"
                )
            )
        ),
    }
