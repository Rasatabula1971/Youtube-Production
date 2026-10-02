"""FAIR-backed selective script target alternative generation.

Slice 2 is deliberately non-destructive: it may generate A/B/C replacements for
one target that is already marked REWORK_REQUESTED, but it never edits the
script draft. Human selection and replacement are a later slice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import atomic_write_json, atomic_write_text
from source_overlap import check_texts
from story_script_engine import OUTPUT_DIR, load_json, safe_slug, sha256_file
from script_section_state import (
    SECTION_STATE_ACTION_LOCK,
    assert_state_matches_draft,
)

EXP2_DIR = _ROOT / "experiment_02_analysis"
if str(EXP2_DIR) not in sys.path:
    sys.path.insert(0, str(EXP2_DIR))

from analysis_model_runner import (
    bridge_payload,
    call_fair_bridge,
    inference_cost_authorized,
    load_runner_config,
    parse_model_json,
    resolve_fair_paths,
    safe_attempts,
)

REWORK_REQUESTS_DIR = OUTPUT_DIR / "script_section_rework_requests"
REWORK_RESPONSES_DIR = OUTPUT_DIR / "script_section_rework_responses"
ALTERNATIVES_DIR = OUTPUT_DIR / "script_section_alternatives"
MODEL_RUNS_DIR = OUTPUT_DIR / "script_section_rework_model_runs"
RAW_OUTPUTS_DIR = OUTPUT_DIR / "raw_script_section_rework_outputs"

ALTERNATIVE_IDS = ["A", "B", "C"]
_NUMERIC_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])[-+]?\d+(?:,\d{3})*(?:\.\d+)?%?"
)


def _allowed_claim_ids(request: dict[str, Any]) -> list[str]:
    claims = request.get("accepted_claims", [])
    if not isinstance(claims, list):
        raise ValueError("accepted_claims must be a list")
    ids: list[str] = []
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("accepted_claims entries must be objects")
        claim_id = str(claim.get("claim_id") or "").strip()
        if not claim_id:
            raise ValueError("accepted_claims entries require claim_id")
        ids.append(claim_id)
    if len(ids) != len(set(ids)):
        raise ValueError("accepted_claims contains duplicate claim_id values")
    return ids


def _numeric_tokens(text: str) -> set[str]:
    return {
        match.group(0).replace(",", "")
        for match in _NUMERIC_TOKEN_RE.finditer(str(text or ""))
    }


def _allowed_numeric_tokens(request: dict[str, Any]) -> set[str]:
    texts = [
        str(
            request.get("selected_target", {}).get("original_text")
            or ""
        )
    ]
    for claim in request.get("accepted_claims", []):
        if isinstance(claim, dict):
            texts.append(str(claim.get("statement") or ""))
    return _numeric_tokens("\n".join(texts))


def validation_contract_sha256() -> str:
    digest = hashlib.sha256()
    for path in (
        Path(__file__).resolve(),
        (_ROOT / "source_overlap.py").resolve(),
    ):
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _target(state: dict[str, Any], target_id: str) -> dict[str, Any]:
    normalized = str(target_id or "").strip()
    for item in state.get("targets", []):
        if isinstance(item, dict) and item.get("target_id") == normalized:
            return item
    raise ValueError(f"Unknown script rework target: {normalized}")


def _section_by_id(draft: dict[str, Any], section_id: str) -> dict[str, Any]:
    for section in draft.get("sections", []):
        if (
            isinstance(section, dict)
            and str(section.get("section_id") or "") == section_id
        ):
            return section
    raise ValueError(f"Script section not found: {section_id}")


def _target_text_and_metadata(
    draft: dict[str, Any],
    target: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    target_type = str(target.get("target_type") or "")
    if target_type == "OPENING_HOOK":
        text = str(draft.get("opening_hook") or "")
        metadata = {
            "opening_hook_mechanism": draft.get("opening_hook_mechanism"),
            "opening_hook_claim_ids": draft.get("opening_hook_claim_ids", []),
        }
    elif target_type == "SECTION":
        section_id = str(target.get("section_id") or "")
        section = _section_by_id(draft, section_id)
        text = str(section.get("narration") or "")
        metadata = {
            "section_id": section_id,
            "source_story_beat_ids": section.get("source_story_beat_ids", []),
            "purpose": section.get("purpose"),
            "psychology_mechanism": section.get("psychology_mechanism"),
            "reward_type": section.get("reward_type"),
            "claim_ids": section.get("claim_ids", []),
        }
    elif target_type == "CLOSING":
        text = str(draft.get("closing") or "")
        metadata = {}
    else:
        raise ValueError(f"Unsupported target_type: {target_type}")

    if not text.strip():
        raise ValueError("Selected rework target has no text")
    return text, metadata


def _compact_context_entry(
    draft: dict[str, Any],
    target: dict[str, Any],
) -> dict[str, Any]:
    text, _ = _target_text_and_metadata(draft, target)
    return {
        "target_id": target.get("target_id"),
        "target_type": target.get("target_type"),
        "decision": target.get("decision"),
        "locked": target.get("locked"),
        "text": text,
    }


def _bound_script_request(
    draft: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    provenance = draft.get("draft_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Script draft is missing draft_provenance")

    source = Path(str(provenance.get("request_source") or "")).resolve()
    expected = str(provenance.get("request_sha256") or "")
    if not source.is_file() or not expected:
        raise ValueError("Script draft is missing its bound script request")
    if sha256_file(source) != expected:
        raise ValueError("STALE_SCRIPT_REQUEST: original script request changed")

    request = load_json(source)
    if str(request.get("concept_id") or "") != str(draft.get("concept_id") or ""):
        raise ValueError("Script request concept_id mismatch")
    if str(request.get("format") or "") != str(draft.get("format") or ""):
        raise ValueError("Script request format mismatch")
    return source, request


def build_rework_request(
    state: dict[str, Any],
    state_path: Path,
    draft: dict[str, Any],
    draft_path: Path,
    *,
    target_id: str,
    review_request_path: Path,
) -> dict[str, Any]:
    """Build one bounded model request for one selected target."""
    draft_path = draft_path.resolve()
    state_path = state_path.resolve()
    if not state_path.is_file():
        raise FileNotFoundError(state_path)

    assert_state_matches_draft(state, draft_path)
    if load_json(draft_path) != draft:
        raise ValueError("Script draft payload does not match draft_path")
    if load_json(state_path) != state:
        raise ValueError("Section state payload does not match state_path")

    target = _target(state, target_id)
    if target.get("decision") != "REWORK_REQUESTED":
        raise ValueError("Selected target is not marked REWORK_REQUESTED")
    if target.get("locked") is True:
        raise ValueError("Selected rework target is locked")

    original_text, target_metadata = _target_text_and_metadata(draft, target)
    targets = sorted(
        [item for item in state.get("targets", []) if isinstance(item, dict)],
        key=lambda item: int(item.get("ordinal") or 0),
    )
    selected_index = next(
        index
        for index, item in enumerate(targets)
        if item.get("target_id") == target.get("target_id")
    )

    before = (
        _compact_context_entry(draft, targets[selected_index - 1])
        if selected_index > 0
        else None
    )
    after = (
        _compact_context_entry(draft, targets[selected_index + 1])
        if selected_index + 1 < len(targets)
        else None
    )

    script_request_path, script_request = _bound_script_request(draft)

    review_request_path = review_request_path.resolve()
    if not review_request_path.is_file():
        raise ValueError("Human Script Gate review request is unavailable")
    review_request = load_json(review_request_path)
    if str(review_request.get("concept_id") or "") != str(draft.get("concept_id") or ""):
        raise ValueError("Human Script Gate request concept_id mismatch")
    if str(review_request.get("format") or "") != str(draft.get("format") or ""):
        raise ValueError("Human Script Gate request format mismatch")
    review_provenance = review_request.get("request_provenance")
    if not isinstance(review_provenance, dict):
        raise ValueError("Human Script Gate request is missing provenance")
    if str(review_provenance.get("script_draft_sha256") or "") != sha256_file(draft_path):
        raise ValueError("STALE_REWORK_REQUEST: Human Script Gate request is stale")

    story_plan = script_request.get("story_plan", {})
    source_beat_ids = {
        str(item)
        for item in target_metadata.get("source_story_beat_ids", [])
    }
    story_beats = (
        story_plan.get("beats", [])
        if isinstance(story_plan, dict)
        else []
    )
    relevant_beats = [
        beat
        for beat in story_beats
        if isinstance(beat, dict)
        and str(beat.get("beat_id") or "") in source_beat_ids
    ]
    if source_beat_ids and {
        str(beat.get("beat_id") or "")
        for beat in relevant_beats
    } != source_beat_ids:
        raise ValueError("Selected target references missing Story Plan beats")

    target_claim_ids = target_metadata.get("claim_ids")
    if target_claim_ids is None:
        target_claim_ids = target_metadata.get("opening_hook_claim_ids", [])
    allowed_claim_ids = {str(item) for item in target_claim_ids or []}
    all_claims = script_request.get("accepted_claims", [])
    if not isinstance(all_claims, list):
        raise ValueError("Script request accepted_claims must be a list")
    claims_by_id = {
        str(item.get("claim_id") or ""): item
        for item in all_claims
        if isinstance(item, dict) and str(item.get("claim_id") or "")
    }
    missing_claims = sorted(allowed_claim_ids - set(claims_by_id))
    if missing_claims:
        raise ValueError(
            "Selected target references unavailable accepted claims: "
            + ", ".join(missing_claims)
        )
    allowed_claims = [
        claims_by_id[claim_id]
        for claim_id in sorted(allowed_claim_ids)
    ]

    return {
        "artifact": "script_section_rework_request",
        "concept_id": draft.get("concept_id"),
        "format": draft.get("format"),
        "target_id": target.get("target_id"),
        "target_type": target.get("target_type"),
        "target_sha256": target.get("target_sha256"),
        "state_version": state.get("state_version"),
        "rework_reason": target.get("rework_reason"),
        "custom_instruction": target.get("custom_instruction"),
        "selected_target": {
            "original_text": original_text,
            "immutable_metadata": target_metadata,
        },
        "adjacent_context": {
            "before": before,
            "after": after,
            "rule": (
                "Context is read-only. Do not rewrite, replace or paraphrase "
                "adjacent targets."
            ),
        },
        "locked_target_ids": [
            str(item.get("target_id"))
            for item in targets
            if item.get("locked") is True
        ],
        "package": script_request.get("package", {}),
        "story_constraints": {
            "story_question": (
                story_plan.get("story_question")
                if isinstance(story_plan, dict)
                else None
            ),
            "opening_hook_intent": (
                story_plan.get("opening_hook_intent")
                if isinstance(story_plan, dict)
                else None
            ),
            "viewer_state": (
                story_plan.get("viewer_state", {})
                if isinstance(story_plan, dict)
                else {}
            ),
            "relevant_beats": relevant_beats,
            "payoff_intent": (
                story_plan.get("payoff_intent")
                if isinstance(story_plan, dict)
                else None
            ),
            "closing_intent": (
                story_plan.get("closing_intent")
                if isinstance(story_plan, dict)
                else None
            ),
        },
        "accepted_claims": allowed_claims,
        "psychology_contract": script_request.get("psychology_contract", {}),
        "psychology_profile": script_request.get("psychology_profile", {}),
        "channel_voice": script_request.get("channel_voice", {}),
        "instructions": [
            "Rewrite only the selected target.",
            "Return exactly three alternatives labeled A, B and C.",
            "Do not rewrite adjacent context or any locked target.",
            "Preserve the selected target's immutable metadata.",
            "Preserve verified facts, Story Plan intent, open loops, format identity and approved package promise.",
            "Do not introduce factual claims beyond accepted_claims.",
            "Do not copy source-video wording, personality, sequence or exact execution.",
            "Make A the most surgical correction, B a stronger correction of the human issue, and C a materially different wording route that still preserves all constraints.",
            "Do not claim virality or guaranteed performance.",
        ],
        "request_provenance": {
            "script_draft": str(draft_path),
            "script_draft_sha256": sha256_file(draft_path),
            "section_state": str(state_path),
            "section_state_sha256": sha256_file(state_path),
            "script_request": str(script_request_path),
            "script_request_sha256": sha256_file(script_request_path),
            "script_review_request": str(review_request_path),
            "script_review_request_sha256": sha256_file(review_request_path),
            "state_version": state.get("state_version"),
            "target_sha256": target.get("target_sha256"),
        },
    }


def _prepare_rework_request_unlocked(
    state_path: Path,
    draft_path: Path,
    *,
    target_id: str,
    requests_dir: Path = REWORK_REQUESTS_DIR,
    review_requests_dir: Path | None = None,
) -> Path:
    state_path = state_path.resolve()
    draft_path = draft_path.resolve()
    state = load_json(state_path)
    draft = load_json(draft_path)
    if review_requests_dir is None:
        from script_review import REVIEW_REQUESTS_DIR

        review_requests_dir = REVIEW_REQUESTS_DIR
    review_request_path = review_requests_dir / (
        f"{safe_slug(str(draft.get('concept_id') or ''))}."
        f"{safe_slug(str(draft.get('format') or ''))}.script_review_request.json"
    )
    request = build_rework_request(
        state,
        state_path,
        draft,
        draft_path,
        target_id=target_id,
        review_request_path=review_request_path,
    )
    destination = requests_dir / (
        f"{safe_slug(str(request['concept_id']))}."
        f"{safe_slug(str(request['format']))}."
        f"{safe_slug(str(request['target_id']))}.section_rework_request.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(destination, request)
    return destination


def prepare_rework_request(
    state_path: Path,
    draft_path: Path,
    *,
    target_id: str,
    requests_dir: Path = REWORK_REQUESTS_DIR,
    review_requests_dir: Path | None = None,
) -> Path:
    with SECTION_STATE_ACTION_LOCK:
        return _prepare_rework_request_unlocked(
            state_path,
            draft_path,
            target_id=target_id,
            requests_dir=requests_dir,
            review_requests_dir=review_requests_dir,
        )


def _assert_request_current_unlocked(request: dict[str, Any]) -> None:
    provenance = request.get("request_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Rework request is missing provenance")

    draft_path = Path(str(provenance.get("script_draft") or "")).resolve()
    state_path = Path(str(provenance.get("section_state") or "")).resolve()
    script_request_path = Path(
        str(provenance.get("script_request") or "")
    ).resolve()
    review_request_path = Path(
        str(provenance.get("script_review_request") or "")
    ).resolve()

    checks = (
        (draft_path, "script_draft_sha256", "script draft"),
        (state_path, "section_state_sha256", "section state"),
        (script_request_path, "script_request_sha256", "script request"),
        (
            review_request_path,
            "script_review_request_sha256",
            "Human Script Gate request",
        ),
    )
    for path, hash_key, label in checks:
        expected = str(provenance.get(hash_key) or "")
        if not path.is_file() or not expected:
            raise ValueError(f"STALE_REWORK_REQUEST: {label} unavailable")
        if sha256_file(path) != expected:
            raise ValueError(f"STALE_REWORK_REQUEST: {label} changed")

    state = load_json(state_path)
    draft = load_json(draft_path)
    assert_state_matches_draft(state, draft_path)
    target = _target(state, str(request.get("target_id") or ""))
    if target.get("decision") != "REWORK_REQUESTED":
        raise ValueError("STALE_REWORK_REQUEST: target no longer requests rework")
    if target.get("locked") is True:
        raise ValueError("STALE_REWORK_REQUEST: target is now locked")
    if int(state.get("state_version") or 0) != int(request.get("state_version") or -1):
        raise ValueError("STALE_REWORK_REQUEST: section state version changed")
    if str(target.get("target_sha256") or "") != str(
        request.get("target_sha256") or ""
    ):
        raise ValueError("STALE_REWORK_REQUEST: target content changed")
    if str(draft.get("concept_id") or "") != str(request.get("concept_id") or ""):
        raise ValueError("STALE_REWORK_REQUEST: concept_id changed")
    if str(draft.get("format") or "") != str(request.get("format") or ""):
        raise ValueError("STALE_REWORK_REQUEST: format changed")

    expected = build_rework_request(
        state,
        state_path,
        draft,
        draft_path,
        target_id=str(request.get("target_id") or ""),
        review_request_path=review_request_path,
    )
    if request != expected:
        raise ValueError(
            "STALE_REWORK_REQUEST: prepared request content changed"
        )


def assert_request_current(request: dict[str, Any]) -> None:
    with SECTION_STATE_ACTION_LOCK:
        _assert_request_current_unlocked(request)


def response_schema(request: dict[str, Any]) -> dict[str, Any]:
    allowed_claim_ids = _allowed_claim_ids(request)
    claim_id_schema: dict[str, Any] = {
        "type": "array",
        "uniqueItems": True,
        "minItems": len(allowed_claim_ids),
        "maxItems": len(allowed_claim_ids),
        "items": {"type": "string"},
    }
    if allowed_claim_ids:
        claim_id_schema["items"] = {
            "type": "string",
            "enum": allowed_claim_ids,
        }

    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "concept_id",
            "format",
            "target_id",
            "alternatives",
        ],
        "properties": {
            "concept_id": {
                "type": "string",
                "const": str(request.get("concept_id") or ""),
            },
            "format": {
                "type": "string",
                "const": str(request.get("format") or ""),
            },
            "target_id": {
                "type": "string",
                "const": str(request.get("target_id") or ""),
            },
            "alternatives": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "alternative_id",
                        "replacement_text",
                        "change_summary",
                        "claim_ids_used",
                    ],
                    "properties": {
                        "alternative_id": {
                            "type": "string",
                            "enum": ALTERNATIVE_IDS,
                        },
                        "replacement_text": {
                            "type": "string",
                            "minLength": 1,
                        },
                        "change_summary": {
                            "type": "string",
                            "minLength": 1,
                        },
                        "claim_ids_used": claim_id_schema,
                    },
                },
            },
        },
    }


def build_prompt(request: dict[str, Any], maximum_chars: int) -> str:
    prompt = (
        "You are revising ONE selected target inside an already-written YouTube "
        "script. Return JSON only.\n\n"
        "NON-NEGOTIABLE RULES:\n"
        "1. Rewrite ONLY selected_target.original_text.\n"
        "2. adjacent_context is READ-ONLY. Never return rewritten adjacent text.\n"
        "3. locked_target_ids are immutable.\n"
        "4. Preserve selected_target.immutable_metadata exactly; your response contains only replacement wording, not metadata.\n"
        "5. Produce exactly A, B and C. A is surgical, B is stronger, C is materially different while staying inside the same facts and story function.\n"
        "6. Correct the supplied rework_reason/custom_instruction rather than improving unrelated parts.\n"
        "7. Use only accepted_claims for factual assertions. Do not invent facts or stakes.\n"
        "8. Every alternative must return claim_ids_used exactly matching the selected target's accepted claim IDs, in the supplied order; return [] when none are allowed.\n"
        "9. Do not introduce new numeric facts unless that numeric value already appears in selected_target.original_text or accepted_claims.\n"
        "10. Preserve package promise, story intent, open loops, payoff logic, target format and approved Channel Voice when active.\n"
        "11. Do not copy source-video wording, personality, sequence or exact execution.\n"
        "12. Do not claim virality or guaranteed performance.\n\n"
        "REWORK REQUEST:\n"
        + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt) > maximum_chars:
        raise ValueError("Section rework prompt exceeds configured maximum")
    return prompt


def validate_response(
    response: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    expected_top_keys = {
        "concept_id",
        "format",
        "target_id",
        "alternatives",
    }
    if not isinstance(response, dict):
        return {
            "valid": False,
            "errors": ["response must be an object"],
            "source_overlap": {},
        }

    actual_top_keys = set(response)
    missing_top = sorted(expected_top_keys - actual_top_keys)
    extra_top = sorted(actual_top_keys - expected_top_keys)
    if missing_top:
        errors.append(
            "response missing fields: " + ", ".join(missing_top)
        )
    if extra_top:
        errors.append(
            "response has unsupported fields: " + ", ".join(extra_top)
        )

    for field in ("concept_id", "format", "target_id"):
        if not isinstance(response.get(field), str):
            errors.append(f"{field} must be a string")

    if response.get("concept_id") != request.get("concept_id"):
        errors.append("concept_id mismatch")
    if response.get("format") != request.get("format"):
        errors.append("format mismatch")
    if response.get("target_id") != request.get("target_id"):
        errors.append("target_id mismatch")

    alternatives = response.get("alternatives")
    if not isinstance(alternatives, list):
        errors.append("alternatives must be a list")
        alternatives = []

    ids = [
        item.get("alternative_id")
        for item in alternatives
        if isinstance(item, dict)
    ]
    if ids != ALTERNATIVE_IDS:
        errors.append("alternatives must be exactly A, B, C in order")

    original = " ".join(
        str(request.get("selected_target", {}).get("original_text") or "")
        .split()
    ).casefold()
    allowed_claim_ids = _allowed_claim_ids(request)
    allowed_numeric_tokens = _allowed_numeric_tokens(request)
    seen_text: set[str] = set()
    overlap_reports: dict[str, Any] = {}
    expected_alt_keys = {
        "alternative_id",
        "replacement_text",
        "change_summary",
        "claim_ids_used",
    }

    for index, item in enumerate(alternatives):
        if not isinstance(item, dict):
            errors.append(f"alternative {index} must be an object")
            continue

        alt_id = item.get("alternative_id")
        label = alt_id if isinstance(alt_id, str) and alt_id else str(index)
        actual_alt_keys = set(item)
        missing_alt = sorted(expected_alt_keys - actual_alt_keys)
        extra_alt = sorted(actual_alt_keys - expected_alt_keys)
        if missing_alt:
            errors.append(
                f"alternative {label} missing fields: "
                + ", ".join(missing_alt)
            )
        if extra_alt:
            errors.append(
                f"alternative {label} has unsupported fields: "
                + ", ".join(extra_alt)
            )

        if not isinstance(alt_id, str):
            errors.append(f"alternative {index} alternative_id must be a string")

        text_value = item.get("replacement_text")
        summary_value = item.get("change_summary")
        if not isinstance(text_value, str):
            errors.append(
                f"alternative {label} replacement_text must be a string"
            )
            text = ""
        else:
            text = text_value.strip()
        if not isinstance(summary_value, str):
            errors.append(
                f"alternative {label} change_summary must be a string"
            )
            summary = ""
        else:
            summary = summary_value.strip()

        claims_used = item.get("claim_ids_used")
        if not isinstance(claims_used, list) or any(
            not isinstance(claim_id, str) for claim_id in claims_used
        ):
            errors.append(
                f"alternative {label} claim_ids_used must be a list of strings"
            )
            claims_used = []
        if claims_used != allowed_claim_ids:
            errors.append(
                f"alternative {label} claim_ids_used must exactly match "
                "the selected target's accepted claim IDs"
            )

        if not text:
            errors.append(f"alternative {label} requires replacement_text")
            continue
        if not summary:
            errors.append(f"alternative {label} requires change_summary")

        unsupported_numbers = sorted(
            _numeric_tokens(text) - allowed_numeric_tokens
        )
        if unsupported_numbers:
            errors.append(
                f"alternative {label} introduces unsupported numeric facts: "
                + ", ".join(unsupported_numbers)
            )

        normalized = " ".join(text.split()).casefold()
        if normalized == original:
            errors.append(f"alternative {label} is unchanged from original")
        if normalized in seen_text:
            errors.append(f"alternative {label} duplicates another alternative")
        seen_text.add(normalized)

        overlap = check_texts(
            [{"field": f"alternative.{label}", "text": text}]
        )
        overlap_reports[str(label)] = overlap
        if overlap.get("blocking"):
            errors.append(f"alternative {label} fails source-overlap block")

    return {
        "valid": not errors,
        "errors": errors,
        "source_overlap": overlap_reports,
        "allowed_claim_ids": allowed_claim_ids,
        "allowed_numeric_tokens": sorted(allowed_numeric_tokens),
    }

def build_alternatives_artifact(
    response: dict[str, Any],
    request: dict[str, Any],
    validation: dict[str, Any],
    *,
    request_path: Path,
    provider_id: str | None,
    model_id: str | None,
    response_path: Path | None = None,
) -> dict[str, Any]:
    return {
        "artifact": "script_section_alternatives",
        "status": "ALTERNATIVES_READY",
        "concept_id": request.get("concept_id"),
        "format": request.get("format"),
        "target_id": request.get("target_id"),
        "target_type": request.get("target_type"),
        "target_sha256": request.get("target_sha256"),
        "state_version": request.get("state_version"),
        "original": {
            "text": request.get("selected_target", {}).get("original_text"),
            "immutable_metadata": request.get(
                "selected_target", {}
            ).get("immutable_metadata", {}),
        },
        "rework_reason": request.get("rework_reason"),
        "custom_instruction": request.get("custom_instruction"),
        "alternatives": response.get("alternatives", []),
        "validation": validation,
        "selection": None,
        "artifact_provenance": {
            "rework_request": str(request_path.resolve()),
            "rework_request_sha256": sha256_file(request_path),
            "script_draft": request.get("request_provenance", {}).get(
                "script_draft"
            ),
            "script_draft_sha256": request.get(
                "request_provenance", {}
            ).get("script_draft_sha256"),
            "section_state": request.get("request_provenance", {}).get(
                "section_state"
            ),
            "section_state_sha256": request.get(
                "request_provenance", {}
            ).get("section_state_sha256"),
            "provider_id": provider_id,
            "model_id": model_id,
            "validation_contract_sha256": validation_contract_sha256(),
            "model_response": (
                str(response_path.resolve())
                if response_path is not None
                else None
            ),
            "model_response_sha256": (
                sha256_file(response_path)
                if response_path is not None and response_path.is_file()
                else None
            ),
        },
    }


def _cached_artifact_errors(
    artifact: dict[str, Any],
    request: dict[str, Any],
    *,
    request_path: Path,
    response_path: Path,
    contract_hash: str,
) -> list[str]:
    errors: list[str] = []
    if artifact.get("artifact") != "script_section_alternatives":
        errors.append("artifact type mismatch")
    if artifact.get("status") != "ALTERNATIVES_READY":
        errors.append("artifact status is not ALTERNATIVES_READY")
    if artifact.get("selection") is not None:
        errors.append("artifact already has a human selection")

    provenance = artifact.get("artifact_provenance")
    if not isinstance(provenance, dict):
        return errors + ["artifact provenance is missing"]

    if provenance.get("rework_request_sha256") != sha256_file(request_path):
        errors.append("rework request hash mismatch")
    if provenance.get("validation_contract_sha256") != contract_hash:
        errors.append("validation contract hash mismatch")
    if provenance.get("model_response") != str(response_path.resolve()):
        errors.append("model response path mismatch")
    if not response_path.is_file():
        errors.append("model response file is unavailable")
        return errors
    if provenance.get("model_response_sha256") != sha256_file(response_path):
        errors.append("model response hash mismatch")
        return errors

    response = load_json(response_path)
    validation = validate_response(response, request)
    if not validation["valid"]:
        errors.append(
            "cached model response fails deterministic validation: "
            + "; ".join(validation["errors"])
        )
        return errors

    expected = build_alternatives_artifact(
        response,
        request,
        validation,
        request_path=request_path,
        provider_id=provenance.get("provider_id"),
        model_id=provenance.get("model_id"),
        response_path=response_path,
    )
    if artifact != expected:
        errors.append("alternatives artifact content changed")
    return errors


def run_one(
    path: Path,
    force: bool,
    config: dict[str, Any],
) -> dict[str, Any]:
    path = path.resolve()
    request = load_json(path)
    assert_request_current(request)

    concept_id = str(request.get("concept_id") or "").strip()
    fmt = str(request.get("format") or "").strip()
    target_id = str(request.get("target_id") or "").strip()
    if not concept_id or not fmt or not target_id:
        raise ValueError("Section rework request requires concept_id, format and target_id")

    slug = (
        f"{safe_slug(concept_id)}.{safe_slug(fmt)}."
        f"{safe_slug(target_id)}"
    )
    request_hash = sha256_file(path)
    contract_hash = validation_contract_sha256()
    report_path = MODEL_RUNS_DIR / f"{slug}.model_run.json"
    response_path = REWORK_RESPONSES_DIR / f"{slug}.json"
    artifact_path = ALTERNATIVES_DIR / f"{slug}.alternatives.json"

    if report_path.exists() and artifact_path.exists() and not force:
        existing = load_json(report_path)
        if (
            existing.get("status") == "VALIDATED"
            and existing.get("validation_contract_sha256") == contract_hash
            and existing.get("request_sha256") == request_hash
        ):
            artifact = load_json(artifact_path)
            cache_errors = _cached_artifact_errors(
                artifact,
                request,
                request_path=path,
                response_path=response_path,
                contract_hash=contract_hash,
            )
            if cache_errors:
                return {
                    "status": "CACHED_ALTERNATIVES_INVALID",
                    "concept_id": concept_id,
                    "format": fmt,
                    "target_id": target_id,
                    "errors": cache_errors,
                    "alternatives": str(artifact_path),
                }
            return {
                "status": "SKIPPED_ALREADY_VALIDATED",
                "concept_id": concept_id,
                "format": fmt,
                "target_id": target_id,
                "alternatives": str(artifact_path),
            }

    prompt = build_prompt(
        request,
        int(config["runner"].get("max_prompt_chars", 95000)),
    )
    schema = response_schema(request)
    paths = resolve_fair_paths(config)
    payload = bridge_payload(
        action="solve",
        prompt=prompt,
        schema=schema,
        config=config,
        paths=paths,
    )
    payload["settings"]["client_id"] = "youtube-script-section-rework"

    for directory in (
        MODEL_RUNS_DIR,
        RAW_OUTPUTS_DIR,
        REWORK_RESPONSES_DIR,
        ALTERNATIVES_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    try:
        result = call_fair_bridge(
            payload,
            python_executable=paths["python"],
            timeout_seconds=float(
                config["runner"].get("subprocess_timeout_seconds", 300)
            ),
        )
    except Exception as exc:
        report = {
            "concept_id": concept_id,
            "format": fmt,
            "target_id": target_id,
            "request_source": str(path),
            "request_sha256": request_hash,
            "status": "RUNNER_ERROR",
            "error_type": type(exc).__name__,
        }
        atomic_write_json(report_path, report)
        return report

    base = {
        "concept_id": concept_id,
        "format": fmt,
        "target_id": target_id,
        "request_source": str(path),
        "request_sha256": request_hash,
        "validation_contract_sha256": contract_hash,
        "fair_request_id": result.get("request_id"),
        "fair_status": result.get("status"),
        "fair_reason_code": result.get("reason_code"),
        "provider_id": result.get("provider_id"),
        "model_id": result.get("model_id"),
        "paid_inference_executed": result.get("paid_inference_executed"),
        "direct_backup_used": result.get("direct_backup_used", False),
        "direct_backup_may_bill": result.get("direct_backup_may_bill", False),
        "billing_authorization": result.get("billing_authorization"),
        "attempts": safe_attempts(result),
    }

    if not inference_cost_authorized(result):
        report = {**base, "status": "COST_POLICY_VIOLATION"}
        atomic_write_json(report_path, report)
        return report

    if result.get("status") != "ACCEPTED":
        report = {
            **base,
            "status": (
                "MODEL_ESCALATION_REQUIRED"
                if result.get("status") == "ESCALATION_REQUIRED"
                else "MODEL_FAILED"
            ),
        }
        atomic_write_json(report_path, report)
        return report

    try:
        assert_request_current(request)
    except (OSError, TypeError, ValueError) as exc:
        report = {
            **base,
            "status": "STALE_REWORK_REQUEST",
            "message": str(exc)[:1000],
        }
        atomic_write_json(report_path, report)
        return report

    raw = str(result.get("output") or "")
    raw_path = RAW_OUTPUTS_DIR / f"{slug}.txt"
    atomic_write_text(raw_path, raw)

    try:
        response = parse_model_json(raw)
        validation = validate_response(response, request)
    except Exception as exc:
        report = {
            **base,
            "status": "MODEL_OUTPUT_VALIDATION_ERROR",
            "error_type": type(exc).__name__,
            "message": str(exc)[:1000],
            "raw_output": str(raw_path),
        }
        atomic_write_json(report_path, report)
        return report

    if not validation["valid"]:
        report = {
            **base,
            "status": "MODEL_OUTPUT_VALIDATION_ERROR",
            "errors": validation["errors"],
            "raw_output": str(raw_path),
        }
        atomic_write_json(report_path, report)
        return report

    atomic_write_json(response_path, response)
    artifact = build_alternatives_artifact(
        response,
        request,
        validation,
        request_path=path,
        provider_id=result.get("provider_id"),
        model_id=result.get("model_id"),
        response_path=response_path,
    )
    atomic_write_json(artifact_path, artifact)

    report = {
        **base,
        "status": "VALIDATED",
        "alternatives": str(artifact_path),
    }
    atomic_write_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate alternatives for one selected script target"
    )
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run_one(
        args.request.resolve(),
        args.force,
        load_runner_config(),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
