"""Bounded selective Script Rework request builder.

Slice 3 only: transform one REWORK_REQUESTED review target into a provenance-
bound request artifact. This module makes no model call and never mutates a
Script Draft.
"""

from __future__ import annotations

import copy
from typing import Any

from script_section_review import validate_section_review_state

SCHEMA_VERSION = 1


def _target_by_id(state: dict[str, Any], target_id: str) -> dict[str, Any]:
    target = next(
        (
            item
            for item in state.get("targets", [])
            if isinstance(item, dict)
            and str(item.get("target_id") or "") == target_id
        ),
        None,
    )
    if target is None:
        raise ValueError(f"Unknown section review target: {target_id}")
    return target


def _section_by_id(draft: dict[str, Any], section_id: str) -> dict[str, Any]:
    matches = [
        section
        for section in draft.get("sections", [])
        if isinstance(section, dict)
        and str(section.get("section_id") or "") == section_id
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Script draft does not contain exactly one section_id {section_id}"
        )
    return matches[0]


def _target_payload(
    draft: dict[str, Any],
    state: dict[str, Any],
    target_id: str,
) -> dict[str, Any]:
    state_target = _target_by_id(state, target_id)
    target_type = str(state_target.get("target_type") or "")

    if target_type == "OPENING_HOOK":
        text = str(draft.get("opening_hook") or "")
        immutable = {
            "opening_hook_mechanism": draft.get("opening_hook_mechanism"),
            "opening_hook_claim_ids": copy.deepcopy(
                draft.get("opening_hook_claim_ids", [])
            ),
        }
    elif target_type == "SECTION":
        section_id = str(state_target.get("source_section_id") or "")
        if not section_id:
            raise ValueError("SECTION target requires source_section_id")
        section = _section_by_id(draft, section_id)
        text = str(section.get("narration") or "")
        immutable = {
            "section_id": section_id,
            "source_story_beat_ids": copy.deepcopy(
                section.get("source_story_beat_ids", [])
            ),
            "purpose": section.get("purpose"),
            "psychology_mechanism": section.get("psychology_mechanism"),
            "reward_type": section.get("reward_type"),
            "claim_ids": copy.deepcopy(section.get("claim_ids", [])),
        }
    elif target_type == "CLOSING":
        text = str(draft.get("closing") or "")
        immutable = {}
    else:
        raise ValueError(f"Unsupported target_type: {target_type}")

    if not text.strip():
        raise ValueError(f"{target_id} has empty target text")

    return {
        "target_id": target_id,
        "target_type": target_type,
        "text": text,
        "immutable_metadata": immutable,
        "review_state": state_target.get("review_state"),
        "locked": state_target.get("locked"),
        "editable": state_target.get("editable"),
        "revision": state_target.get("revision"),
        "content_sha256": state_target.get("content_sha256"),
    }


def _ordered_target_ids(draft: dict[str, Any]) -> list[str]:
    result = ["opening_hook"]
    for index, section in enumerate(draft.get("sections", [])):
        if not isinstance(section, dict):
            raise ValueError(f"Script section {index} must be an object")
        section_id = str(section.get("section_id") or "").strip()
        if not section_id:
            raise ValueError(f"Script section {index} requires section_id")
        result.append(f"section:{section_id}")
    result.append("closing")
    return result


def _context_item(
    draft: dict[str, Any],
    state: dict[str, Any],
    target_id: str,
    relationship: str,
) -> dict[str, Any]:
    payload = _target_payload(draft, state, target_id)
    return {
        "relationship": relationship,
        "target_id": payload["target_id"],
        "target_type": payload["target_type"],
        "text": payload["text"],
        "review_state": payload["review_state"],
        "locked": payload["locked"],
        "content_sha256": payload["content_sha256"],
        "read_only": True,
    }


def _adjacent_context(
    draft: dict[str, Any],
    state: dict[str, Any],
    target_id: str,
) -> list[dict[str, Any]]:
    ordered = _ordered_target_ids(draft)
    if target_id not in ordered:
        raise ValueError(f"Target {target_id} is not present in script sequence")
    index = ordered.index(target_id)
    context: list[dict[str, Any]] = []
    if index > 0:
        context.append(
            _context_item(
                draft,
                state,
                ordered[index - 1],
                "PREVIOUS",
            )
        )
    if index + 1 < len(ordered):
        context.append(
            _context_item(
                draft,
                state,
                ordered[index + 1],
                "NEXT",
            )
        )
    return context


def _relevant_story_context(
    draft: dict[str, Any],
    target: dict[str, Any],
) -> dict[str, Any]:
    story_plan = draft.get("story_plan", {})
    if not isinstance(story_plan, dict):
        raise ValueError("Script draft story_plan must be an object")

    source_ids = set(
        str(item)
        for item in target.get("immutable_metadata", {}).get(
            "source_story_beat_ids",
            [],
        )
    )
    beats = story_plan.get("beats", [])
    if not isinstance(beats, list):
        raise ValueError("Script draft story_plan beats must be a list")

    relevant_beats = [
        copy.deepcopy(beat)
        for beat in beats
        if isinstance(beat, dict)
        and str(beat.get("beat_id") or "") in source_ids
    ]
    if source_ids and {
        str(beat.get("beat_id") or "")
        for beat in relevant_beats
    } != source_ids:
        raise ValueError("Target references Story Plan beats that are unavailable")

    return {
        "title": story_plan.get("title"),
        "story_question": story_plan.get("story_question"),
        "opening_hook_intent": story_plan.get("opening_hook_intent"),
        "payoff_intent": story_plan.get("payoff_intent"),
        "closing_intent": story_plan.get("closing_intent"),
        "relevant_beats": relevant_beats,
    }


def _allowed_claims(
    draft: dict[str, Any],
    target: dict[str, Any],
) -> list[dict[str, Any]]:
    immutable = target.get("immutable_metadata", {})
    claim_ids = immutable.get("claim_ids")
    if claim_ids is None:
        claim_ids = immutable.get("opening_hook_claim_ids", [])
    allowed = {str(item) for item in claim_ids or []}

    claims = draft.get("accepted_claims", [])
    if not isinstance(claims, list):
        raise ValueError("Script draft accepted_claims must be a list")
    by_id = {
        str(claim.get("claim_id") or ""): claim
        for claim in claims
        if isinstance(claim, dict)
        and str(claim.get("claim_id") or "")
    }
    missing = sorted(allowed - set(by_id))
    if missing:
        raise ValueError(
            "Target references accepted claims unavailable from the draft: "
            + ", ".join(missing)
        )
    return [copy.deepcopy(by_id[claim_id]) for claim_id in sorted(allowed)]


def build_section_rework_request(
    *,
    draft: dict[str, Any],
    review_request: dict[str, Any],
    section_state: dict[str, Any],
    target_id: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """Build one bounded, non-destructive selective rework request."""
    if not isinstance(draft, dict) or not isinstance(review_request, dict):
        raise ValueError("draft and review_request must be objects")

    validation = validate_section_review_state(section_state)
    if not validation["valid"]:
        raise ValueError(
            "Invalid section review state: " + "; ".join(validation["errors"])
        )

    normalized_target_id = str(target_id or "").strip()
    if not normalized_target_id:
        raise ValueError("target_id is required")

    state_target = _target_by_id(section_state, normalized_target_id)
    if state_target.get("review_state") != "REWORK_REQUESTED":
        raise ValueError(
            "Selective rework request requires a REWORK_REQUESTED target"
        )
    if state_target.get("locked") is not False or state_target.get("editable") is not True:
        raise ValueError(
            "REWORK_REQUESTED target must be unlocked and editable"
        )

    target = _target_payload(draft, section_state, normalized_target_id)
    concept_id = str(review_request.get("concept_id") or "").strip()
    fmt = str(review_request.get("format") or "").strip()
    if not concept_id or not fmt:
        raise ValueError("review_request requires concept_id and format")
    if (
        str(draft.get("concept_id") or "").strip() != concept_id
        or str(draft.get("format") or "").strip() != fmt
    ):
        raise ValueError("draft and review_request identity mismatch")

    required_provenance = (
        "script_draft",
        "script_draft_sha256",
        "section_state",
        "section_state_sha256",
        "script_review_request",
        "script_review_request_sha256",
        "script_request",
        "script_request_sha256",
    )
    missing = [
        key
        for key in required_provenance
        if not str(provenance.get(key) or "").strip()
    ]
    if missing:
        raise ValueError(
            "Selective rework provenance missing: " + ", ".join(missing)
        )

    package = draft.get("package", {})
    if not isinstance(package, dict):
        raise ValueError("Script draft package must be an object")

    return {
        "artifact": "script_section_rework_request",
        "schema_version": SCHEMA_VERSION,
        "request_mode": "SELECTIVE_SECTION_REWORK",
        "concept_id": concept_id,
        "format": fmt,
        "title": draft.get("title"),
        "target": target,
        "adjacent_context": _adjacent_context(
            draft,
            section_state,
            normalized_target_id,
        ),
        "human_rework": {
            "reason": state_target.get("rework_reason"),
            "note": state_target.get("rework_note"),
        },
        "package_constraints": {
            "title": package.get("title"),
            "one_sentence_promise": package.get("one_sentence_promise"),
            "expected_payoff": package.get("expected_payoff"),
            "desired_outcome": package.get("desired_outcome"),
        },
        "story_context": _relevant_story_context(draft, target),
        "psychology_contract": copy.deepcopy(
            draft.get("psychology_contract", {})
        ),
        "psychology_profile": copy.deepcopy(
            draft.get("psychology_profile", {})
        ),
        "channel_voice": copy.deepcopy(draft.get("channel_voice", {})),
        "allowed_claims": _allowed_claims(draft, target),
        "instructions": [
            "Rewrite only the selected target in a later generation step.",
            "Adjacent context is read-only and must not be rewritten.",
            "Preserve every field in target.immutable_metadata exactly.",
            "Do not add factual claims outside target.allowed claim IDs.",
            "Preserve the approved package promise, Story Plan intent, psychology constraints, and bound Channel Voice.",
            "Do not copy or closely paraphrase source-video wording.",
            "Return no replacement during Slice 3; this artifact is request preparation only.",
        ],
        "request_provenance": {
            **copy.deepcopy(provenance),
            "state_revision": section_state.get("state_revision"),
            "script_revision": section_state.get("script_revision"),
            "target_revision": state_target.get("revision"),
            "target_content_sha256": state_target.get("content_sha256"),
        },
    }
