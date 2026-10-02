"""Deterministic section-level review contract for Script Gate.

Slice 1 only: build and validate review state. No human actions, model calls,
regeneration, alternatives, or draft mutation are implemented here.
"""

from __future__ import annotations

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

    return {"valid": not errors, "errors": errors}
