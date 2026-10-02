"""Human Script Gate for format-specific script branches."""

from __future__ import annotations

import argparse
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
from script_section_state import (
    SECTION_STATE_ACTION_LOCK,
    SECTION_STATE_DIR,
    assert_state_matches_draft,
    state_path_for,
)

from story_script_engine import (
    DRAFTS_DIR,
    OUTPUT_DIR,
    REQUESTS_DIR,
    load_json,
    safe_slug,
    sha256_file,
)

REVIEW_REQUESTS_DIR = OUTPUT_DIR / "script_review_requests"
RESPONSES_DIR = OUTPUT_DIR / "script_review_responses"
APPROVED_DIR = OUTPUT_DIR / "approved_scripts"
SUMMARY_FILE = OUTPUT_DIR / "script_gate_summary.json"
REVIEWER_ENV = "YOUTUBE_REVIEWER_ID"
DEFAULT_REVIEWER = "local-operator"

CRITERIA = (
    "package_promise_delivered",
    "facts_within_verified_claims",
    "claim_mapping_reasonable",
    "original_source_independent",
    "story_plan_followed",
    "opening_hook_high_impact_truthful",
    "audience_psychology_coherent",
    "structure_and_payoff_clear",
)


def reviewer_id() -> str:
    return os.getenv(REVIEWER_ENV, DEFAULT_REVIEWER).strip() or DEFAULT_REVIEWER


def _branch_key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def build_review_request(draft: dict[str, Any], draft_path: Path) -> dict[str, Any]:
    concept_id = str(draft.get("concept_id", "")).strip()
    fmt = str(draft.get("format", "")).strip()
    if not concept_id:
        raise ValueError("Script draft requires concept_id")
    if not fmt:
        raise ValueError("Script draft requires format")
    required_branches = draft.get("required_branches", [])
    if not isinstance(required_branches, list) or fmt not in required_branches:
        raise ValueError("Script draft required_branches do not include its format")

    return {
        "request_type": "human_script_gate",
        "concept_id": concept_id,
        "format": fmt,
        "required_branches": list(required_branches),
        "title": draft.get("title"),
        "opening_hook": draft.get("opening_hook"),
        "opening_hook_mechanism": draft.get("opening_hook_mechanism"),
        "opening_hook_claim_ids": draft.get("opening_hook_claim_ids", []),
        "sections": draft.get("sections", []),
        "closing": draft.get("closing"),
        "package": draft.get("package", {}),
        "story_plan": draft.get("story_plan", {}),
        "psychology_profile": draft.get("psychology_profile", {}),
        "channel_voice": draft.get("channel_voice", {}),
        "accepted_claims": draft.get("accepted_claims", []),
        "validation": draft.get("validation", {}),
        "source_overlap": draft.get("validation", {}).get("source_overlap", {}),
        "required_accept_criteria": list(CRITERIA),
        "criteria": {
            "package_promise_delivered": (
                "This branch delivers the approved title/thumbnail promise and "
                "expected payoff in a form appropriate to its format."
            ),
            "facts_within_verified_claims": (
                "Factual statements stay within human-accepted research claims."
            ),
            "claim_mapping_reasonable": (
                "Section and hook claim IDs reasonably support the factual "
                "narration they are attached to."
            ),
            "original_source_independent": (
                "The script is original and does not depend on source wording, "
                "footage, story or personality."
            ),
            "story_plan_followed": (
                "The branch remains faithful to the shared Story Plan while "
                "adapting its sequence and compression for this format."
            ),
            "opening_hook_high_impact_truthful": (
                "The first spoken line creates immediate interest, matches the "
                "package promise and does not exaggerate beyond verified research."
            ),
            "audience_psychology_coherent": (
                "The format-specific psychology profile is used coherently. For "
                "Shorts this means rapid meaningful progress and micro-payoffs; "
                "for long-form it means sustained curiosity and comprehension."
            ),
            "structure_and_payoff_clear": (
                "The hook, progression and final payoff are clear enough to produce."
            ),
        },
        "request_provenance": {
            "script_draft": str(draft_path.resolve()),
            "script_draft_sha256": sha256_file(draft_path),
        },
    }


def prepare() -> dict[str, Any]:
    REVIEW_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = (
        sorted(DRAFTS_DIR.glob("*.script_draft.json"))
        if DRAFTS_DIR.exists()
        else []
    )
    prepared: list[dict[str, Any]] = []
    current: set[Path] = set()
    for path in paths:
        req = build_review_request(load_json(path), path)
        dest = REVIEW_REQUESTS_DIR / (
            f"{_branch_key(req['concept_id'], req['format'])}."
            "script_review_request.json"
        )
        atomic_write_json(dest, req)
        current.add(dest.resolve())
        prepared.append(
            {
                "concept_id": req["concept_id"],
                "format": req["format"],
                "request": str(dest),
            }
        )
    for stale in REVIEW_REQUESTS_DIR.glob("*.script_review_request.json"):
        if stale.resolve() not in current:
            stale.unlink()
    return {
        "status": "SCRIPT_GATE_READY" if prepared else "WAITING_FOR_SCRIPT_DRAFTS",
        "prepared": len(prepared),
        "requests": prepared,
    }


def validate_response(req: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    if str(response.get("concept_id", "")) != str(req.get("concept_id", "")):
        raise ValueError("concept_id mismatch")
    if str(response.get("format", "")) != str(req.get("format", "")):
        raise ValueError("format mismatch")
    reviewer = str(response.get("reviewer", "")).strip()
    if not reviewer:
        raise ValueError("reviewer is required")
    decision = str(response.get("decision", "")).strip().upper()
    if decision not in {"ACCEPT", "REWORK", "REJECT"}:
        raise ValueError("invalid decision")
    note = str(response.get("note", "") or "").strip()
    normalized = (
        {key: True for key in CRITERIA}
        if decision == "ACCEPT"
        else {key: False for key in CRITERIA}
        if decision == "REJECT"
        else {}
    )
    if decision == "REWORK" and not note:
        raise ValueError("REWORK requires note")
    return {
        "concept_id": str(req["concept_id"]),
        "format": str(req["format"]),
        "reviewer": reviewer,
        "decision": decision,
        "criteria": normalized,
        "note": note,
    }


def assert_current_draft(req: dict[str, Any]) -> Path:
    provenance = req.get("request_provenance", {})
    source = Path(str(provenance.get("script_draft", "")))
    expected_hash = str(provenance.get("script_draft_sha256", ""))
    if not source.exists() or not expected_hash:
        raise ValueError("STALE_REVIEW_REQUEST: reviewed script draft is unavailable")
    if sha256_file(source) != expected_hash:
        raise ValueError(
            "STALE_REVIEW_REQUEST: script draft changed after review preparation"
        )
    return source


def response_path(concept_id: str, fmt: str) -> Path:
    return RESPONSES_DIR / (
        f"{_branch_key(concept_id, fmt)}.script_review_response.json"
    )


def _section_review_provenance(
    req: dict[str, Any],
    draft_path: Path,
    *,
    require_complete: bool,
) -> dict[str, Any]:
    """Return canonical section-review lineage for one branch.

    Selective review remains optional. Once prepared, however, it becomes part
    of the branch-acceptance contract: every target must be explicitly accepted
    and locked before whole-branch approval can cross into Format.
    """
    concept_id = str(req.get("concept_id") or "").strip()
    fmt = str(req.get("format") or "").strip()
    state_path = state_path_for(concept_id, fmt, SECTION_STATE_DIR).resolve()
    if not state_path.is_file():
        return {
            "prepared": False,
            "section_state": None,
            "section_state_sha256": None,
            "state_version": None,
            "target_count": 0,
            "targets": [],
        }

    state = load_json(state_path)
    assert_state_matches_draft(state, draft_path)
    targets = [
        item
        for item in state.get("targets", [])
        if isinstance(item, dict)
    ]
    unresolved = [
        str(item.get("target_id") or "")
        for item in targets
        if item.get("decision") != "ACCEPTED"
        or item.get("locked") is not True
    ]
    if require_complete and unresolved:
        raise ValueError(
            "ACCEPT blocked until prepared section review is complete: "
            + ", ".join(unresolved)
        )

    target_lineage = [
        {
            "target_id": str(item.get("target_id") or ""),
            "target_sha256": str(item.get("target_sha256") or ""),
        }
        for item in sorted(
            targets,
            key=lambda item: int(item.get("ordinal") or 0),
        )
    ]
    return {
        "prepared": True,
        "section_state": str(state_path),
        "section_state_sha256": sha256_file(state_path),
        "state_version": int(state.get("state_version") or 0),
        "target_count": len(targets),
        "targets": target_lineage,
    }


def _response_is_current(req: dict[str, Any], saved: dict[str, Any]) -> bool:
    if not saved:
        return False
    provenance = req.get("request_provenance", {})
    source = Path(str(provenance.get("script_draft", "")))
    expected = str(provenance.get("script_draft_sha256", ""))
    if not source.exists() or not expected:
        return False
    if sha256_file(source) != expected:
        return False
    return saved.get("script_draft_sha256") == expected


def _requests_for_concept(concept_id: str) -> list[tuple[Path, dict[str, Any]]]:
    items: list[tuple[Path, dict[str, Any]]] = []
    if not REVIEW_REQUESTS_DIR.exists():
        return items
    for path in sorted(REVIEW_REQUESTS_DIR.glob("*.script_review_request.json")):
        req = load_json(path)
        if str(req.get("concept_id", "")) == concept_id:
            items.append((path, req))
    return items


def _normalized_section_sequence(draft: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for section in draft.get("sections", []):
        if not isinstance(section, dict):
            continue
        text = " ".join(str(section.get("narration") or "").lower().split())
        if text:
            result.append(text)
    return result


def _assert_distinct_branch_scripts(branch_scripts: dict[str, dict[str, Any]]) -> None:
    names = sorted(branch_scripts)
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            left = _normalized_section_sequence(branch_scripts[first])
            right = _normalized_section_sequence(branch_scripts[second])
            if not left or not right:
                continue
            if left == right:
                raise ValueError(
                    f"{first} and {second} branch scripts are identical"
                )
            shorter, longer = (
                (left, right) if len(left) < len(right) else (right, left)
            )
            if shorter and longer[: len(shorter)] == shorter:
                raise ValueError(
                    f"{first} and {second} scripts differ only by truncation"
                )


def _refresh_approved_bundle(concept_id: str) -> Path | None:
    approved_path = APPROVED_DIR / f"{safe_slug(concept_id)}.approved_script.json"
    requests = _requests_for_concept(concept_id)
    if not requests:
        if approved_path.exists():
            approved_path.unlink()
        return None

    first_req = requests[0][1]
    required = first_req.get("required_branches", [])
    if not isinstance(required, list) or not required:
        raise ValueError("Script review request requires required_branches")
    required_set = {str(item) for item in required}

    by_format: dict[str, tuple[Path, dict[str, Any]]] = {}
    for request_path, req in requests:
        fmt = str(req.get("format", "")).strip()
        if fmt:
            by_format[fmt] = (request_path, req)

    if set(by_format) != required_set:
        if approved_path.exists():
            approved_path.unlink()
        return None

    branch_scripts: dict[str, dict[str, Any]] = {}
    review_provenance: dict[str, dict[str, str]] = {}
    channel_voice_fingerprint: str | None = None
    for fmt in sorted(required_set):
        request_path, req = by_format[fmt]
        saved_path = response_path(concept_id, fmt)
        saved = load_json(saved_path) if saved_path.exists() else {}
        if not _response_is_current(req, saved):
            if approved_path.exists():
                approved_path.unlink()
            return None
        if str(saved.get("decision", "")).upper() != "ACCEPT":
            if approved_path.exists():
                approved_path.unlink()
            return None

        source = assert_current_draft(req)
        draft = load_json(source)
        section_review = _section_review_provenance(
            req,
            source,
            require_complete=True,
        )
        channel_voice = draft.get("channel_voice", {})
        fingerprint = json.dumps(
            channel_voice,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if channel_voice_fingerprint is None:
            channel_voice_fingerprint = fingerprint
        elif fingerprint != channel_voice_fingerprint:
            raise ValueError(
                "script branches use different Channel Voice bindings"
            )
        branch_scripts[fmt] = {
            "format": fmt,
            "title": draft.get("title"),
            "opening_hook": draft.get("opening_hook"),
            "opening_hook_mechanism": draft.get("opening_hook_mechanism"),
            "opening_hook_claim_ids": draft.get("opening_hook_claim_ids", []),
            "sections": draft.get("sections", []),
            "closing": draft.get("closing"),
            "psychology_profile": draft.get("psychology_profile", {}),
            "validation": draft.get("validation", {}),
            "script_gate": {
                "status": "READY_FOR_PRODUCTION",
                "reviewer": saved.get("reviewer"),
                "reviewed_at": saved.get("reviewed_at"),
                "criteria": saved.get("criteria", {}),
                "note": saved.get("note", ""),
                "section_review": {
                    "prepared": section_review["prepared"],
                    "state_version": section_review["state_version"],
                    "target_count": section_review["target_count"],
                },
            },
        }
        review_provenance[fmt] = {
            "script_review_request_sha256": sha256_file(request_path),
            "script_draft_sha256": sha256_file(source),
            "script_review_response_sha256": sha256_file(saved_path),
            "section_review_prepared": section_review["prepared"],
            "section_state": section_review["section_state"],
            "section_state_sha256": section_review["section_state_sha256"],
            "section_state_version": section_review["state_version"],
            "section_target_count": section_review["target_count"],
            "section_targets": section_review["targets"],
        }

    _assert_distinct_branch_scripts(branch_scripts)

    sample_source = assert_current_draft(first_req)
    sample = load_json(sample_source)
    bundle = {
        "artifact": "approved_script_bundle",
        "status": "READY_FOR_PRODUCTION",
        "concept_id": concept_id,
        "title": sample.get("title"),
        "package": sample.get("package", {}),
        "accepted_claims": sample.get("accepted_claims", []),
        "story_plan": sample.get("story_plan", {}),
        "psychology_contract": sample.get("psychology_contract", {}),
        "channel_voice": sample.get("channel_voice", {}),
        "required_branches": sorted(required_set),
        "branch_scripts": branch_scripts,
        "script_gate": {
            "status": "READY_FOR_PRODUCTION",
            "accepted_formats": sorted(required_set),
        },
        "approved_provenance": review_provenance,
    }
    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(approved_path, bundle)
    return approved_path


def _approved_bundle_is_current(concept_id: str) -> bool:
    approved_path = APPROVED_DIR / f"{safe_slug(concept_id)}.approved_script.json"
    if not approved_path.is_file():
        return False
    try:
        bundle = load_json(approved_path)
        if (
            bundle.get("artifact") != "approved_script_bundle"
            or bundle.get("status") != "READY_FOR_PRODUCTION"
        ):
            return False

        requests = _requests_for_concept(concept_id)
        if not requests:
            return False
        required = {
            str(item)
            for item in requests[0][1].get("required_branches", [])
            if str(item).strip()
        }
        if not required:
            return False
        by_format = {
            str(req.get("format") or ""): (request_path, req)
            for request_path, req in requests
            if str(req.get("format") or "").strip()
        }
        if set(by_format) != required:
            return False
        if set(bundle.get("required_branches", [])) != required:
            return False

        provenance = bundle.get("approved_provenance", {})
        if not isinstance(provenance, dict) or set(provenance) != required:
            return False

        for fmt in sorted(required):
            request_path, req = by_format[fmt]
            saved_path = response_path(concept_id, fmt)
            saved = load_json(saved_path) if saved_path.is_file() else {}
            if (
                not _response_is_current(req, saved)
                or str(saved.get("decision") or "").upper() != "ACCEPT"
            ):
                return False
            source = assert_current_draft(req)
            record = provenance.get(fmt, {})
            if not isinstance(record, dict):
                return False
            if record.get("script_review_request_sha256") != sha256_file(request_path):
                return False
            if record.get("script_draft_sha256") != sha256_file(source):
                return False
            if record.get("script_review_response_sha256") != sha256_file(saved_path):
                return False

            section = _section_review_provenance(
                req,
                source,
                require_complete=True,
            )
            if record.get("section_review_prepared") is not section["prepared"]:
                return False
            if section["prepared"]:
                if record.get("section_state") != section["section_state"]:
                    return False
                if record.get("section_state_sha256") != section["section_state_sha256"]:
                    return False
                if int(record.get("section_state_version") or -1) != int(
                    section["state_version"]
                ):
                    return False
                if int(record.get("section_target_count") or -1) != int(
                    section["target_count"]
                ):
                    return False
                if record.get("section_targets") != section["targets"]:
                    return False
        return True
    except (FileNotFoundError, TypeError, ValueError):
        return False


def _apply_rework_feedback(
    req: dict[str, Any],
    *,
    note: str,
) -> None:
    source = assert_current_draft(req)
    draft = load_json(source)
    provenance = draft.get("draft_provenance", {})
    request_source = Path(str(provenance.get("request_source") or "")).resolve()
    requests_root = REQUESTS_DIR.resolve()
    if not request_source.exists() or requests_root not in request_source.parents:
        raise ValueError("Script rework cannot find the current script request")

    request = load_json(request_source)
    concept_id = str(req.get("concept_id") or "")
    fmt = str(req.get("format") or "")
    if (
        str(request.get("concept_id") or "") != concept_id
        or str(request.get("format") or "") != fmt
    ):
        raise ValueError("Script rework request identity mismatch")

    iteration = int(request.get("human_rework_iteration") or 0) + 1
    request["human_rework_iteration"] = iteration
    request["human_rework_mode"] = "HUMAN_INSTRUCTION_ONLY"
    request["human_rework_note"] = note
    request["human_rework_format"] = fmt
    request["human_rework_original_script"] = {
        "title": draft.get("title"),
        "opening_hook": draft.get("opening_hook"),
        "opening_hook_mechanism": draft.get("opening_hook_mechanism"),
        "opening_hook_claim_ids": draft.get("opening_hook_claim_ids", []),
        "sections": draft.get("sections", []),
        "closing": draft.get("closing"),
    }
    atomic_write_json(request_source, request)


def _apply_payload_unlocked(request_path: Path, response: dict[str, Any]) -> dict[str, Any]:
    req = load_json(request_path)
    normalized = validate_response(req, response)
    source = assert_current_draft(req)
    if normalized["decision"] == "ACCEPT":
        _section_review_provenance(
            req,
            source,
            require_complete=True,
        )
    reviewed_at = datetime.now(timezone.utc).isoformat()

    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    dest = response_path(str(req["concept_id"]), str(req["format"]))
    saved = {
        **normalized,
        "reviewed_at": reviewed_at,
        "script_draft_sha256": sha256_file(source),
    }
    atomic_write_json(dest, saved)

    if normalized["decision"] == "REWORK":
        _apply_rework_feedback(req, note=normalized["note"])

    try:
        bundle_path = _refresh_approved_bundle(str(req["concept_id"]))
    except ValueError:
        # Do not persist an ACCEPT that cannot form a valid multi-format bundle.
        if normalized["decision"] == "ACCEPT" and dest.exists():
            dest.unlink()
        _refresh_approved_bundle(str(req["concept_id"]))
        raise

    result = {
        "status": (
            "SCRIPT_BRANCH_ACCEPTED"
            if normalized["decision"] == "ACCEPT"
            else "SCRIPT_REWORK_REQUIRED"
            if normalized["decision"] == "REWORK"
            else "SCRIPT_REJECTED"
        ),
        **normalized,
        "reviewed_at": reviewed_at,
        "approved_script": str(bundle_path) if bundle_path else None,
    }
    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(SUMMARY_FILE, result)
    return result


def apply_payload(request_path: Path, response: dict[str, Any]) -> dict[str, Any]:
    with SECTION_STATE_ACTION_LOCK:
        return _apply_payload_unlocked(request_path, response)


def apply(request_path: Path, response_path_file: Path) -> dict[str, Any]:
    return apply_payload(request_path, load_json(response_path_file))


def snapshot() -> dict[str, Any]:
    if not REVIEW_REQUESTS_DIR.exists():
        return {
            "status": "READY_TO_PREPARE",
            "complete": False,
            "scripts": [],
            "pending": 0,
            "accepted": 0,
            "rework": 0,
            "rejected": 0,
            "production_ready_concept_ids": [],
        }

    scripts: list[dict[str, Any]] = []
    counts = {"pending": 0, "accepted": 0, "rework": 0, "rejected": 0}
    decision_key = {
        "ACCEPT": "accepted",
        "REWORK": "rework",
        "REJECT": "rejected",
    }

    concepts: set[str] = set()
    for path in sorted(REVIEW_REQUESTS_DIR.glob("*.script_review_request.json")):
        req = load_json(path)
        cid = str(req.get("concept_id", ""))
        fmt = str(req.get("format", ""))
        concepts.add(cid)
        rpath = response_path(cid, fmt)
        saved = load_json(rpath) if rpath.exists() else {}
        if not _response_is_current(req, saved):
            saved = {}
        decision = str(saved.get("decision") or "PENDING").upper()
        counts[decision_key.get(decision, "pending")] += 1
        scripts.append(
            {
                **req,
                "decision": decision,
                "criteria_decisions": saved.get("criteria", {}),
                "note": saved.get("note", ""),
            }
        )

    ready_ids = sorted(
        cid
        for cid in concepts
        if _approved_bundle_is_current(cid)
    )
    complete = bool(scripts) and counts["pending"] == 0
    return {
        "status": "COMPLETE" if complete else "AWAITING_HUMAN_DECISION",
        "complete": complete,
        "scripts": scripts,
        "production_ready_concept_ids": ready_ids,
        **counts,
    }


def apply_action(
    *,
    concept_id: str,
    format: str,
    decision: str,
    criteria: dict[str, Any],
    note: str | None = None,
) -> dict[str, Any]:
    fmt = str(format).strip()
    request_path = REVIEW_REQUESTS_DIR / (
        f"{_branch_key(concept_id, fmt)}.script_review_request.json"
    )
    if not request_path.exists():
        raise ValueError("Script review request not found")

    value = str(decision or "").strip().upper()
    payload = {
        "concept_id": concept_id,
        "format": fmt,
        "reviewer": reviewer_id(),
        "decision": value,
        "criteria": {},
        "note": str(note or ""),
    }
    apply_payload(request_path, payload)
    return snapshot()


def main() -> None:
    parser = argparse.ArgumentParser(description="Human Script Gate")
    parser.add_argument("--mode", choices=("prepare", "apply"), required=True)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--response", type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        result = prepare()
    else:
        if not args.request or not args.response:
            raise SystemExit("--request and --response required")
        result = apply(args.request.resolve(), args.response.resolve())
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
