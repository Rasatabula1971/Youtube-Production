"""Human Script Gate."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from story_script_engine import (
    DRAFTS_DIR,
    OUTPUT_DIR,
    load_json,
    safe_slug,
    sha256_file,
)

REVIEW_REQUESTS_DIR = OUTPUT_DIR / "script_review_requests"
RESPONSES_DIR = OUTPUT_DIR / "script_review_responses"
APPROVED_DIR = OUTPUT_DIR / "approved_scripts"
SUMMARY_FILE = OUTPUT_DIR / "script_gate_summary.json"
UI_REVIEWER = "local-operator"

CRITERIA = (
    "package_promise_delivered",
    "facts_within_verified_claims",
    "claim_mapping_reasonable",
    "original_source_independent",
    "structure_and_payoff_clear",
)


def build_review_request(draft: dict[str, Any], draft_path: Path) -> dict[str, Any]:
    concept_id = str(draft.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Script draft requires concept_id")
    return {
        "request_type": "human_script_gate",
        "concept_id": concept_id,
        "title": draft.get("title"),
        "opening_hook": draft.get("opening_hook"),
        "sections": draft.get("sections", []),
        "closing": draft.get("closing"),
        "package": draft.get("package", {}),
        "accepted_claims": draft.get("accepted_claims", []),
        "source_overlap": draft.get("validation", {}).get("source_overlap", {}),
        "required_accept_criteria": list(CRITERIA),
        "criteria": {
            "package_promise_delivered": "The draft delivers the approved title/thumbnail promise and expected payoff.",
            "facts_within_verified_claims": "Factual statements stay within human-accepted research claims.",
            "claim_mapping_reasonable": "Section claim IDs reasonably support the factual narration they are attached to.",
            "original_source_independent": "The script is original and does not depend on source wording, footage, story or personality.",
            "structure_and_payoff_clear": "The hook, progression and final payoff are clear enough to produce.",
        },
        "request_provenance": {
            "script_draft": str(draft_path.resolve()),
            "script_draft_sha256": sha256_file(draft_path),
        },
    }


def prepare() -> dict[str, Any]:
    REVIEW_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = (
        sorted(DRAFTS_DIR.glob("*.script_draft.json")) if DRAFTS_DIR.exists() else []
    )
    prepared = []
    for path in paths:
        req = build_review_request(load_json(path), path)
        dest = (
            REVIEW_REQUESTS_DIR
            / f"{safe_slug(req['concept_id'])}.script_review_request.json"
        )
        dest.write_text(json.dumps(req, indent=2, ensure_ascii=False), encoding="utf-8")
        prepared.append({"concept_id": req["concept_id"], "request": str(dest)})
    return {
        "status": "SCRIPT_GATE_READY" if prepared else "WAITING_FOR_SCRIPT_DRAFTS",
        "prepared": len(prepared),
        "requests": prepared,
    }


def validate_response(req: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    if str(response.get("concept_id", "")) != str(req.get("concept_id", "")):
        raise ValueError("concept_id mismatch")
    reviewer = str(response.get("reviewer", "")).strip()
    if not reviewer:
        raise ValueError("reviewer is required")
    decision = str(response.get("decision", "")).strip().upper()
    if decision not in {"ACCEPT", "REWORK", "REJECT"}:
        raise ValueError("invalid decision")
    criteria = response.get("criteria")
    if not isinstance(criteria, dict):
        raise ValueError("criteria are required")
    normalized = {key: criteria.get(key) is True for key in CRITERIA}
    note = str(response.get("note", "") or "").strip()
    if decision == "ACCEPT" and not all(normalized.values()):
        raise ValueError("ACCEPT requires all criteria true")
    if decision == "REWORK" and not note:
        raise ValueError("REWORK requires note")
    return {
        "concept_id": str(req["concept_id"]),
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


def apply_payload(request_path: Path, response: dict[str, Any]) -> dict[str, Any]:
    req = load_json(request_path)
    normalized = validate_response(req, response)
    source = assert_current_draft(req)
    decision = normalized["decision"]
    reviewed_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "status": (
            "READY_FOR_PRODUCTION"
            if decision == "ACCEPT"
            else "SCRIPT_REWORK_REQUIRED" if decision == "REWORK" else "SCRIPT_REJECTED"
        ),
        **normalized,
        "reviewed_at": reviewed_at,
    }

    approved_path = (
        APPROVED_DIR / f"{safe_slug(req['concept_id'])}.approved_script.json"
    )
    if decision == "ACCEPT":
        draft = load_json(source)
        draft["script_gate"] = summary
        draft["approved_provenance"] = {
            "script_review_request_sha256": sha256_file(request_path),
            "script_draft_sha256": sha256_file(source),
        }
        APPROVED_DIR.mkdir(parents=True, exist_ok=True)
        approved_path.write_text(
            json.dumps(draft, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        summary["approved_script"] = str(approved_path)
    elif approved_path.exists():
        approved_path.unlink()

    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def apply(request_path: Path, response_path: Path) -> dict[str, Any]:
    response = load_json(response_path)
    return apply_payload(request_path, response)


def response_path(concept_id: str) -> Path:
    return RESPONSES_DIR / f"{safe_slug(concept_id)}.script_review_response.json"


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
        }

    scripts = []
    counts = {"pending": 0, "accepted": 0, "rework": 0, "rejected": 0}
    decision_key = {
        "ACCEPT": "accepted",
        "REWORK": "rework",
        "REJECT": "rejected",
    }

    for path in sorted(REVIEW_REQUESTS_DIR.glob("*.script_review_request.json")):
        req = load_json(path)
        cid = str(req.get("concept_id", ""))
        rpath = response_path(cid)
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

    complete = bool(scripts) and counts["pending"] == 0
    return {
        "status": "COMPLETE" if complete else "AWAITING_HUMAN_DECISION",
        "complete": complete,
        "scripts": scripts,
        **counts,
    }


def apply_action(
    *,
    concept_id: str,
    decision: str,
    criteria: dict[str, Any],
    note: str | None = None,
) -> dict[str, Any]:
    request_path = (
        REVIEW_REQUESTS_DIR / f"{safe_slug(concept_id)}.script_review_request.json"
    )
    if not request_path.exists():
        raise ValueError("Script review request not found")

    req = load_json(request_path)
    payload = {
        "concept_id": concept_id,
        "reviewer": UI_REVIEWER,
        "decision": decision,
        "criteria": criteria,
        "note": str(note or ""),
    }

    # Validate the human action and reviewed-draft provenance BEFORE persisting it.
    normalized = validate_response(req, payload)
    source = assert_current_draft(req)
    apply_payload(request_path, normalized)

    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    dest = response_path(concept_id)
    saved = {
        **normalized,
        "script_draft_sha256": sha256_file(source),
    }
    dest.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
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
