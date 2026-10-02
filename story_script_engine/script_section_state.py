"""Provenance-bound per-target review state for selective script rework.

Slice 1 intentionally contains no model calls and does not mutate script drafts.
It establishes stable review targets for the opening hook, each generated script
section, and the closing so later slices can request bounded alternatives safely.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import atomic_write_json
from story_script_engine import OUTPUT_DIR, load_json, safe_slug, sha256_file

SECTION_STATE_DIR = OUTPUT_DIR / "script_section_states"

ALLOWED_DECISIONS = {"PENDING", "ACCEPTED", "REWORK_REQUESTED"}
ALLOWED_ACTIONS = {"ACCEPT", "LOCK", "UNLOCK", "REWORK", "CANCEL_REWORK"}
ALLOWED_REWORK_REASONS = {
    "TOO_BORING",
    "TOO_LONG",
    "TOO_TECHNICAL",
    "NOT_DRAMATIC_ENOUGH",
    "WEAK_TRANSITION",
    "FACT_UNCLEAR",
    "UNNATURAL",
    "WEAK_CURIOSITY",
    "WEAK_EMOTION",
    "CUSTOM",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _draft_identity(draft: dict[str, Any]) -> tuple[str, str]:
    concept_id = str(draft.get("concept_id") or "").strip()
    fmt = str(draft.get("format") or "").strip()
    if not concept_id:
        raise ValueError("Script draft requires concept_id")
    if not fmt:
        raise ValueError("Script draft requires format")
    return concept_id, fmt


def _target_record(
    *,
    target_id: str,
    target_type: str,
    ordinal: int,
    payload: dict[str, Any],
    section_id: str | None = None,
) -> dict[str, Any]:
    return {
        "target_id": target_id,
        "target_type": target_type,
        "section_id": section_id,
        "ordinal": ordinal,
        "target_sha256": _canonical_sha256(payload),
        "decision": "PENDING",
        "locked": False,
        "rework_reason": None,
        "custom_instruction": None,
    }


def build_targets(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Create collision-free stable targets without changing the draft schema."""
    _draft_identity(draft)

    opening_hook = str(draft.get("opening_hook") or "").strip()
    if not opening_hook:
        raise ValueError("Script draft requires opening_hook")

    closing = str(draft.get("closing") or "").strip()
    if not closing:
        raise ValueError("Script draft requires closing")

    sections = draft.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("Script draft requires a non-empty sections list")

    records = [
        _target_record(
            target_id="hook:opening",
            target_type="OPENING_HOOK",
            ordinal=0,
            payload={
                "opening_hook": draft.get("opening_hook"),
                "opening_hook_mechanism": draft.get("opening_hook_mechanism"),
                "opening_hook_claim_ids": draft.get("opening_hook_claim_ids", []),
            },
        )
    ]

    seen_section_ids: set[str] = set()
    for index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            raise ValueError(f"Script section {index} must be an object")
        section_id = str(section.get("section_id") or "").strip()
        if not section_id:
            raise ValueError(f"Script section {index} requires section_id")
        if section_id in seen_section_ids:
            raise ValueError(f"Duplicate script section_id: {section_id}")
        seen_section_ids.add(section_id)
        records.append(
            _target_record(
                target_id=f"section:{section_id}",
                target_type="SECTION",
                section_id=section_id,
                ordinal=index,
                payload=section,
            )
        )

    records.append(
        _target_record(
            target_id="closing:closing",
            target_type="CLOSING",
            ordinal=len(records),
            payload={"closing": draft.get("closing")},
        )
    )
    return records


def build_state(draft: dict[str, Any], draft_path: Path) -> dict[str, Any]:
    """Build a fresh section-review state bound to one exact script draft."""
    draft_path = draft_path.resolve()
    if not draft_path.is_file():
        raise FileNotFoundError(draft_path)

    concept_id, fmt = _draft_identity(draft)
    if load_json(draft_path) != draft:
        raise ValueError("Script draft payload does not match draft_path")

    now = _utc_now()
    return {
        "artifact": "script_section_state",
        "schema_version": 1,
        "status": "READY_FOR_SECTION_REVIEW",
        "concept_id": concept_id,
        "format": fmt,
        "source_draft": str(draft_path),
        "source_draft_sha256": sha256_file(draft_path),
        "state_version": 1,
        "created_at": now,
        "updated_at": now,
        "targets": build_targets(draft),
        "history": [],
    }


def validate_state(state: Any) -> dict[str, Any]:
    """Validate deterministic section-state invariants."""
    errors: list[str] = []
    if not isinstance(state, dict):
        return {"valid": False, "errors": ["state must be an object"]}

    if state.get("artifact") != "script_section_state":
        errors.append("artifact must be script_section_state")
    if state.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if not str(state.get("concept_id") or "").strip():
        errors.append("concept_id is required")
    if not str(state.get("format") or "").strip():
        errors.append("format is required")
    if not str(state.get("source_draft") or "").strip():
        errors.append("source_draft is required")
    if not str(state.get("source_draft_sha256") or "").strip():
        errors.append("source_draft_sha256 is required")

    version = state.get("state_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        errors.append("state_version must be a positive integer")

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

        if str(target.get("decision") or "") not in ALLOWED_DECISIONS:
            errors.append(f"{target_id or index} has invalid decision")
        if not isinstance(target.get("locked"), bool):
            errors.append(f"{target_id or index} locked must be boolean")
        if not str(target.get("target_sha256") or "").strip():
            errors.append(f"{target_id or index} requires target_sha256")

    history = state.get("history")
    if not isinstance(history, list):
        errors.append("history must be a list")

    return {"valid": not errors, "errors": errors}


def assert_state_matches_draft(state: dict[str, Any], draft_path: Path) -> dict[str, Any]:
    """Fail closed if review state no longer describes the exact draft."""
    validation = validate_state(state)
    if not validation["valid"]:
        raise ValueError("Invalid section state: " + "; ".join(validation["errors"]))

    draft_path = draft_path.resolve()
    if not draft_path.is_file():
        raise ValueError("STALE_SECTION_STATE: script draft is unavailable")
    if str(state.get("source_draft") or "") != str(draft_path):
        raise ValueError("STALE_SECTION_STATE: script draft path changed")
    if str(state.get("source_draft_sha256") or "") != sha256_file(draft_path):
        raise ValueError("STALE_SECTION_STATE: script draft changed")

    draft = load_json(draft_path)
    concept_id, fmt = _draft_identity(draft)
    if concept_id != str(state.get("concept_id") or ""):
        raise ValueError("STALE_SECTION_STATE: concept_id changed")
    if fmt != str(state.get("format") or ""):
        raise ValueError("STALE_SECTION_STATE: format changed")

    current_targets = build_targets(draft)
    expected = {
        str(item["target_id"]): str(item["target_sha256"])
        for item in current_targets
    }
    actual = {
        str(item.get("target_id") or ""): str(item.get("target_sha256") or "")
        for item in state.get("targets", [])
        if isinstance(item, dict)
    }
    if actual != expected:
        raise ValueError("STALE_SECTION_STATE: target set or content changed")
    return draft


def state_path_for(concept_id: str, fmt: str, state_dir: Path = SECTION_STATE_DIR) -> Path:
    return state_dir / (
        f"{safe_slug(str(concept_id))}.{safe_slug(str(fmt))}.section_state.json"
    )


def prepare_state(
    draft_path: Path,
    *,
    state_dir: Path = SECTION_STATE_DIR,
) -> dict[str, Any]:
    """Create one state file or return the current state unchanged."""
    draft_path = draft_path.resolve()
    draft = load_json(draft_path)
    concept_id, fmt = _draft_identity(draft)
    destination = state_path_for(concept_id, fmt, state_dir)

    if destination.exists():
        existing = load_json(destination)
        assert_state_matches_draft(existing, draft_path)
        return existing

    state = build_state(draft, draft_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(destination, state)
    return state


def _target_by_id(state: dict[str, Any], target_id: str) -> dict[str, Any]:
    normalized = str(target_id or "").strip()
    for target in state.get("targets", []):
        if isinstance(target, dict) and target.get("target_id") == normalized:
            return target
    raise ValueError(f"Unknown script rework target: {normalized}")


def apply_target_action(
    state_path: Path,
    draft_path: Path,
    *,
    target_id: str,
    action: str,
    reviewer: str,
    reason: str | None = None,
    custom_instruction: str | None = None,
) -> dict[str, Any]:
    """Apply one deterministic review-state action without mutating the draft."""
    state_path = state_path.resolve()
    draft_path = draft_path.resolve()
    if not state_path.is_file():
        raise FileNotFoundError(state_path)

    state = load_json(state_path)
    assert_state_matches_draft(state, draft_path)

    reviewer_value = str(reviewer or "").strip()
    if not reviewer_value:
        raise ValueError("reviewer is required")

    action_value = str(action or "").strip().upper()
    if action_value not in ALLOWED_ACTIONS:
        raise ValueError(f"Unsupported section action: {action_value}")

    target = _target_by_id(state, target_id)
    before = {
        "decision": target["decision"],
        "locked": target["locked"],
        "rework_reason": target.get("rework_reason"),
        "custom_instruction": target.get("custom_instruction"),
    }

    reason_value = str(reason or "").strip().upper() or None
    custom_value = str(custom_instruction or "").strip() or None

    if action_value == "ACCEPT":
        target["decision"] = "ACCEPTED"
        target["locked"] = True
        target["rework_reason"] = None
        target["custom_instruction"] = None

    elif action_value == "LOCK":
        if target.get("decision") == "REWORK_REQUESTED":
            raise ValueError(
                "Cannot lock a target while rework is requested; cancel rework first"
            )
        target["locked"] = True

    elif action_value == "UNLOCK":
        target["locked"] = False
        if target.get("decision") == "ACCEPTED":
            target["decision"] = "PENDING"

    elif action_value == "REWORK":
        if target.get("locked") is True:
            raise ValueError("Locked target cannot be reworked until it is unlocked")
        if reason_value is None and custom_value is None:
            raise ValueError("REWORK requires a reason or custom instruction")
        if reason_value is not None and reason_value not in ALLOWED_REWORK_REASONS:
            raise ValueError(f"Unsupported rework reason: {reason_value}")
        if reason_value == "CUSTOM" and not custom_value:
            raise ValueError("CUSTOM rework reason requires custom_instruction")
        target["decision"] = "REWORK_REQUESTED"
        target["rework_reason"] = reason_value or "CUSTOM"
        target["custom_instruction"] = custom_value

    elif action_value == "CANCEL_REWORK":
        if target.get("decision") != "REWORK_REQUESTED":
            raise ValueError("Target does not have rework requested")
        target["decision"] = "PENDING"
        target["rework_reason"] = None
        target["custom_instruction"] = None

    state["state_version"] = int(state.get("state_version") or 0) + 1
    state["updated_at"] = _utc_now()
    after = {
        "decision": target["decision"],
        "locked": target["locked"],
        "rework_reason": target.get("rework_reason"),
        "custom_instruction": target.get("custom_instruction"),
    }
    state["history"].append(
        {
            "state_version": state["state_version"],
            "reviewed_at": state["updated_at"],
            "reviewer": reviewer_value,
            "target_id": target["target_id"],
            "action": action_value,
            "before": before,
            "after": after,
        }
    )
    atomic_write_json(state_path, state)
    return state
