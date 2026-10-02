"""Safe orchestration service for selective Human Script section review.

The browser/API supplies only logical identities (concept, format, target, action).
It never supplies filesystem paths for drafts, states, rework requests or
alternatives.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from story_script_engine import DRAFTS_DIR, load_json, safe_slug
from script_review import (
    APPROVED_DIR,
    RESPONSES_DIR as SCRIPT_REVIEW_RESPONSES_DIR,
    reviewer_id,
)
from script_section_apply import (
    SCRIPT_VERSIONS_DIR,
    SELECTION_TRANSACTIONS_DIR,
    apply_manual_edit,
    apply_selection,
)
from script_section_rework_runner import (
    ALTERNATIVES_DIR,
    REWORK_REQUESTS_DIR,
    load_runner_config,
    prepare_rework_request,
    run_one as run_section_rework,
)
from script_section_state import (
    ALLOWED_REWORK_REASONS,
    SECTION_STATE_DIR,
    apply_target_action,
    assert_state_matches_draft,
    build_targets,
    prepare_state,
    state_path_for,
)

SECTION_ACTIONS = {
    "ACCEPT",
    "LOCK",
    "UNLOCK",
    "REWORK",
    "CANCEL_REWORK",
}


def _branch_key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _draft_path(
    concept_id: str,
    fmt: str,
    *,
    drafts_dir: Path,
) -> Path:
    return drafts_dir / (
        f"{safe_slug(concept_id)}.{safe_slug(fmt)}.script_draft.json"
    )


def _alternatives_path(
    concept_id: str,
    fmt: str,
    target_id: str,
    *,
    alternatives_dir: Path,
) -> Path:
    return alternatives_dir / (
        f"{safe_slug(concept_id)}.{safe_slug(fmt)}."
        f"{safe_slug(target_id)}.alternatives.json"
    )


def _rework_request_path(
    concept_id: str,
    fmt: str,
    target_id: str,
    *,
    rework_requests_dir: Path,
) -> Path:
    return rework_requests_dir / (
        f"{safe_slug(concept_id)}.{safe_slug(fmt)}."
        f"{safe_slug(target_id)}.section_rework_request.json"
    )


def _target_text(
    draft: dict[str, Any],
    target: dict[str, Any],
) -> str:
    target_type = str(target.get("target_type") or "")
    if target_type == "OPENING_HOOK":
        return str(draft.get("opening_hook") or "")
    if target_type == "CLOSING":
        return str(draft.get("closing") or "")
    if target_type == "SECTION":
        section_id = str(target.get("section_id") or "")
        for section in draft.get("sections", []):
            if (
                isinstance(section, dict)
                and str(section.get("section_id") or "") == section_id
            ):
                return str(section.get("narration") or "")
    return ""


def _target_metadata(
    draft: dict[str, Any],
    target: dict[str, Any],
) -> dict[str, Any]:
    if str(target.get("target_type") or "") != "SECTION":
        return {}
    section_id = str(target.get("section_id") or "")
    for section in draft.get("sections", []):
        if (
            isinstance(section, dict)
            and str(section.get("section_id") or "") == section_id
        ):
            return {
                "purpose": section.get("purpose"),
                "psychology_mechanism": section.get("psychology_mechanism"),
                "reward_type": section.get("reward_type"),
                "source_story_beat_ids": section.get(
                    "source_story_beat_ids", []
                ),
                "claim_ids": section.get("claim_ids", []),
            }
    return {}


def _alternative_summary(
    path: Path,
) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    artifact = load_json(path)
    if artifact.get("artifact") != "script_section_alternatives":
        return {
            "status": "INVALID_ARTIFACT",
            "alternatives_file": str(path),
        }
    return {
        "status": artifact.get("status"),
        "target_id": artifact.get("target_id"),
        "original": artifact.get("original", {}),
        "rework_reason": artifact.get("rework_reason"),
        "custom_instruction": artifact.get("custom_instruction"),
        "alternatives": artifact.get("alternatives", []),
        "selection": artifact.get("selection"),
        "alternatives_file": str(path),
    }


def branch_snapshot(
    concept_id: str,
    fmt: str,
    *,
    drafts_dir: Path = DRAFTS_DIR,
    state_dir: Path = SECTION_STATE_DIR,
    alternatives_dir: Path = ALTERNATIVES_DIR,
) -> dict[str, Any]:
    concept = str(concept_id or "").strip()
    branch_format = str(fmt or "").strip()
    if not concept or not branch_format:
        raise ValueError("concept_id and format are required")

    draft_path = _draft_path(
        concept,
        branch_format,
        drafts_dir=drafts_dir,
    )
    if not draft_path.is_file():
        return {
            "status": "SCRIPT_DRAFT_NOT_FOUND",
            "concept_id": concept,
            "format": branch_format,
            "prepared": False,
            "targets": [],
        }

    draft = load_json(draft_path)
    if (
        str(draft.get("concept_id") or "") != concept
        or str(draft.get("format") or "") != branch_format
    ):
        return {
            "status": "SCRIPT_DRAFT_IDENTITY_MISMATCH",
            "concept_id": concept,
            "format": branch_format,
            "prepared": False,
            "targets": [],
        }
    state_path = state_path_for(concept, branch_format, state_dir)
    if not state_path.is_file():
        preview_targets = build_targets(draft)
        return {
            "status": "SECTION_STATE_NOT_PREPARED",
            "concept_id": concept,
            "format": branch_format,
            "prepared": False,
            "draft": str(draft_path),
            "targets": [
                {
                    **target,
                    "text": _target_text(draft, target),
                    "metadata": _target_metadata(draft, target),
                    "alternatives": None,
                }
                for target in preview_targets
            ],
            "rework_reasons": sorted(ALLOWED_REWORK_REASONS),
        }

    state = load_json(state_path)
    try:
        assert_state_matches_draft(state, draft_path)
    except ValueError as exc:
        return {
            "status": "STALE_SECTION_STATE",
            "concept_id": concept,
            "format": branch_format,
            "prepared": True,
            "draft": str(draft_path),
            "section_state": str(state_path),
            "error": str(exc),
            "targets": [],
            "rework_reasons": sorted(ALLOWED_REWORK_REASONS),
        }

    targets: list[dict[str, Any]] = []
    for target in sorted(
        (
            item
            for item in state.get("targets", [])
            if isinstance(item, dict)
        ),
        key=lambda item: int(item.get("ordinal") or 0),
    ):
        target_id = str(target.get("target_id") or "")
        alternatives_path = _alternatives_path(
            concept,
            branch_format,
            target_id,
            alternatives_dir=alternatives_dir,
        )
        targets.append(
            {
                **target,
                "text": _target_text(draft, target),
                "metadata": _target_metadata(draft, target),
                "alternatives": _alternative_summary(alternatives_path),
            }
        )

    return {
        "status": "READY_FOR_SECTION_REVIEW",
        "concept_id": concept,
        "format": branch_format,
        "prepared": True,
        "draft": str(draft_path),
        "section_state": str(state_path),
        "state_version": state.get("state_version"),
        "targets": targets,
        "rework_reasons": sorted(ALLOWED_REWORK_REASONS),
    }


def snapshot(
    concept_id: str | None = None,
    fmt: str | None = None,
    *,
    drafts_dir: Path = DRAFTS_DIR,
    state_dir: Path = SECTION_STATE_DIR,
    alternatives_dir: Path = ALTERNATIVES_DIR,
) -> dict[str, Any]:
    if concept_id is not None or fmt is not None:
        if concept_id is None or fmt is None:
            raise ValueError("concept_id and format must be supplied together")
        return branch_snapshot(
            concept_id,
            fmt,
            drafts_dir=drafts_dir,
            state_dir=state_dir,
            alternatives_dir=alternatives_dir,
        )

    branches: list[dict[str, Any]] = []
    if drafts_dir.exists():
        for draft_path in sorted(drafts_dir.glob("*.script_draft.json")):
            draft = load_json(draft_path)
            concept = str(draft.get("concept_id") or "").strip()
            branch_format = str(draft.get("format") or "").strip()
            if concept and branch_format:
                branches.append(
                    branch_snapshot(
                        concept,
                        branch_format,
                        drafts_dir=drafts_dir,
                        state_dir=state_dir,
                        alternatives_dir=alternatives_dir,
                    )
                )
    return {
        "status": "READY" if branches else "WAITING_FOR_SCRIPT_DRAFTS",
        "branches": branches,
    }


def _invalidate_branch_approval(
    concept_id: str,
    fmt: str,
    *,
    review_responses_dir: Path,
    approved_dir: Path,
) -> None:
    branch = _branch_key(concept_id, fmt)
    response = (
        review_responses_dir / f"{branch}.script_review_response.json"
    )
    if response.exists():
        response.unlink()

    approved = approved_dir / (
        f"{safe_slug(concept_id)}.approved_script.json"
    )
    if approved.exists():
        approved.unlink()


def apply_action(
    *,
    concept_id: str,
    fmt: str,
    action: str,
    target_id: str | None = None,
    reason: str | None = None,
    custom_instruction: str | None = None,
    selection_id: str | None = None,
    replacement_text: str | None = None,
    reviewer: str | None = None,
    drafts_dir: Path = DRAFTS_DIR,
    state_dir: Path = SECTION_STATE_DIR,
    rework_requests_dir: Path = REWORK_REQUESTS_DIR,
    alternatives_dir: Path = ALTERNATIVES_DIR,
    versions_dir: Path = SCRIPT_VERSIONS_DIR,
    transactions_dir: Path = SELECTION_TRANSACTIONS_DIR,
    review_requests_dir: Path | None = None,
    review_responses_dir: Path = SCRIPT_REVIEW_RESPONSES_DIR,
    approved_dir: Path = APPROVED_DIR,
) -> dict[str, Any]:
    """Apply a logical section-review action without accepting arbitrary paths."""
    concept = str(concept_id or "").strip()
    branch_format = str(fmt or "").strip()
    action_value = str(action or "").strip().upper()
    target_value = str(target_id or "").strip()
    reviewer_value = str(reviewer or reviewer_id()).strip()

    if not concept or not branch_format:
        raise ValueError("concept_id and format are required")

    draft_path = _draft_path(
        concept,
        branch_format,
        drafts_dir=drafts_dir,
    )
    if not draft_path.is_file():
        raise ValueError("Script draft not found")
    draft_identity = load_json(draft_path)
    if (
        str(draft_identity.get("concept_id") or "") != concept
        or str(draft_identity.get("format") or "") != branch_format
    ):
        raise ValueError("Script draft identity mismatch")

    state_path = state_path_for(concept, branch_format, state_dir)

    if action_value == "PREPARE":
        prepare_state(draft_path, state_dir=state_dir)

    elif action_value in SECTION_ACTIONS:
        if not target_value:
            raise ValueError(f"{action_value} requires target_id")
        if not state_path.is_file():
            raise ValueError("Section state is not prepared")
        apply_target_action(
            state_path,
            draft_path,
            target_id=target_value,
            action=action_value,
            reviewer=reviewer_value,
            reason=reason,
            custom_instruction=custom_instruction,
        )
        if action_value in {"UNLOCK", "REWORK"}:
            _invalidate_branch_approval(
                concept,
                branch_format,
                review_responses_dir=review_responses_dir,
                approved_dir=approved_dir,
            )

    elif action_value == "GENERATE_ALTERNATIVES":
        if not target_value:
            raise ValueError("GENERATE_ALTERNATIVES requires target_id")
        if not state_path.is_file():
            raise ValueError("Section state is not prepared")
        request_path = prepare_rework_request(
            state_path,
            draft_path,
            target_id=target_value,
            requests_dir=rework_requests_dir,
        )
        generation = run_section_rework(
            request_path,
            False,
            load_runner_config(),
        )
        if generation.get("status") not in {
            "VALIDATED",
            "SKIPPED_ALREADY_VALIDATED",
        }:
            return {
                "status": "ALTERNATIVE_GENERATION_FAILED",
                "generation": generation,
                "section_review": branch_snapshot(
                    concept,
                    branch_format,
                    drafts_dir=drafts_dir,
                    state_dir=state_dir,
                    alternatives_dir=alternatives_dir,
                ),
            }

    elif action_value == "SELECT_ALTERNATIVE":
        if not target_value:
            raise ValueError("SELECT_ALTERNATIVE requires target_id")
        alternative_path = _alternatives_path(
            concept,
            branch_format,
            target_value,
            alternatives_dir=alternatives_dir,
        )
        if not alternative_path.is_file():
            raise ValueError("Alternatives are not ready for this target")

        if review_requests_dir is None:
            from script_review import REVIEW_REQUESTS_DIR

            review_requests_dir = REVIEW_REQUESTS_DIR

        apply_selection(
            alternative_path,
            selection_id=str(selection_id or ""),
            reviewer=reviewer_value,
            versions_dir=versions_dir,
            transactions_dir=transactions_dir,
            review_requests_dir=review_requests_dir,
            review_responses_dir=review_responses_dir,
            approved_dir=approved_dir,
        )

    elif action_value == "MANUAL_EDIT":
        if not target_value:
            raise ValueError("MANUAL_EDIT requires target_id")
        if not state_path.is_file():
            raise ValueError("Section state is not prepared")
        if review_requests_dir is None:
            from script_review import REVIEW_REQUESTS_DIR

            review_requests_dir = REVIEW_REQUESTS_DIR

        apply_manual_edit(
            draft_path,
            state_path,
            target_id=target_value,
            replacement_text=str(replacement_text or ""),
            reviewer=reviewer_value,
            versions_dir=versions_dir,
            transactions_dir=transactions_dir,
            review_requests_dir=review_requests_dir,
            review_responses_dir=review_responses_dir,
            approved_dir=approved_dir,
        )

        stale_alternatives = _alternatives_path(
            concept,
            branch_format,
            target_value,
            alternatives_dir=alternatives_dir,
        )
        if stale_alternatives.exists():
            stale_alternatives.unlink()
        stale_request = _rework_request_path(
            concept,
            branch_format,
            target_value,
            rework_requests_dir=rework_requests_dir,
        )
        if stale_request.exists():
            stale_request.unlink()

    else:
        raise ValueError(f"Unsupported section review action: {action_value}")

    return branch_snapshot(
        concept,
        branch_format,
        drafts_dir=drafts_dir,
        state_dir=state_dir,
        alternatives_dir=alternatives_dir,
    )
