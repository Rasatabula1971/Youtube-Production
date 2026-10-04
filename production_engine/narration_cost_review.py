"""Human Narration Spend Gate.

A current provider quote may authorize paid narration only after a human accepts
its worst-case cost. This gate records authorization; it never calls a provider.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import atomic_write_json, named_lock
import video_budget
from narration_render import (
    ESTIMATES_DIR,
    OUTPUT_DIR,
    artifact_key,
    load_json,
    sha256_file,
    snapshot as narration_render_snapshot,
)

REVIEW_REQUESTS_DIR = OUTPUT_DIR / "narration_spend_review_requests"
RESPONSES_DIR = OUTPUT_DIR / "narration_spend_review_responses"
APPROVED_DIR = OUTPUT_DIR / "approved_narration_spend"
SUMMARY_FILE = OUTPUT_DIR / "narration_spend_gate_summary.json"
REVIEWER_ENV = "YOUTUBE_REVIEWER_ID"
DEFAULT_REVIEWER = "local-operator"

REQUIRED_ACCEPT_CRITERIA = (
    "provider_quote_is_current",
    "worst_case_cost_is_accepted",
    "voice_identity_and_license_are_confirmed",
    "provider_contract_is_verified",
)

CRITERIA_DESCRIPTIONS = {
    "provider_quote_is_current": (
        "The quote is bound to this exact narration render request."
    ),
    "worst_case_cost_is_accepted": (
        "The reviewer accepts the displayed worst-case cost before any paid call."
    ),
    "voice_identity_and_license_are_confirmed": (
        "The configured voice identity, licence reference and calibration are approved."
    ),
    "provider_contract_is_verified": (
        "The narration endpoint/schema is verified against current provider documentation."
    ),
}


def reviewer_id() -> str:
    return os.getenv(REVIEWER_ENV, DEFAULT_REVIEWER).strip() or DEFAULT_REVIEWER


def _load_dict_or_none(path: Path) -> dict[str, Any] | None:
    try:
        value = load_json(path)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _remove_if_exists(path: Path) -> bool:
    if not path.exists():
        return False
    if not path.is_file():
        raise ValueError(f"Expected narration spend gate file: {path}")
    path.unlink()
    return True


def build_review_request(
    estimate: dict[str, Any],
    estimate_path: Path,
) -> dict[str, Any]:
    if estimate.get("status") != "READY_FOR_SPEND_GATE":
        raise ValueError("Narration cost estimate is not READY_FOR_SPEND_GATE")
    initial = estimate.get("initial_estimate_usd")
    worst = estimate.get("worst_case_estimate_usd")
    if initial is None or worst is None:
        raise ValueError("Narration cost estimate is missing provider costs")
    return {
        "request_type": "human_narration_spend_gate",
        "concept_id": str(estimate.get("concept_id") or ""),
        "format": str(estimate.get("format") or ""),
        "provider": str(estimate.get("provider") or ""),
        "currency": str(estimate.get("currency") or ""),
        "initial_estimate_usd": float(initial),
        "worst_case_estimate_usd": float(worst),
        "segment_count": int(estimate.get("segment_count") or 0),
        "max_attempts_per_segment": int(
            estimate.get("max_attempts_per_segment") or 0
        ),
        "provider_quote": estimate.get("provider_quote"),
        "required_accept_criteria": list(REQUIRED_ACCEPT_CRITERIA),
        "criteria": dict(CRITERIA_DESCRIPTIONS),
        "request_provenance": {
            "narration_cost_estimate": str(estimate_path.resolve()),
            "narration_cost_estimate_sha256": sha256_file(estimate_path),
            "render_request_sha256": estimate.get("render_request_sha256"),
        },
    }


def prepare() -> dict[str, Any]:
    for directory in (REVIEW_REQUESTS_DIR, RESPONSES_DIR, APPROVED_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    render_state = narration_render_snapshot()
    ready_keys = {
        artifact_key(
            str(item.get("concept_id") or ""),
            str(item.get("format") or ""),
        )
        for item in render_state.get("items", [])
        if isinstance(item, dict)
        and item.get("status") == "READY_FOR_SPEND_GATE"
    }

    paths = (
        sorted(ESTIMATES_DIR.glob("*.narration_cost_estimate.json"))
        if ESTIMATES_DIR.exists()
        else []
    )
    prepared: list[dict[str, Any]] = []
    current_keys: set[str] = set()
    for path in paths:
        estimate = _load_dict_or_none(path)
        if not isinstance(estimate, dict) or estimate.get("status") != "READY_FOR_SPEND_GATE":
            continue
        key = artifact_key(
            str(estimate.get("concept_id") or ""),
            str(estimate.get("format") or ""),
        )
        if key not in ready_keys:
            continue

        request = build_review_request(estimate, path)
        current_keys.add(key)
        dest = REVIEW_REQUESTS_DIR / f"{key}.narration_spend_review_request.json"
        estimate_hash = sha256_file(path)

        response = response_path(request["concept_id"], request["format"])
        if response.is_file():
            saved = _load_dict_or_none(response)
            if (
                not isinstance(saved, dict)
                or saved.get("narration_cost_estimate_sha256") != estimate_hash
            ):
                response.unlink()

        approved_path = APPROVED_DIR / f"{key}.approved_narration_spend.json"
        if approved_path.is_file():
            approved = _load_dict_or_none(approved_path)
            provenance = (
                approved.get("approved_provenance", {})
                if isinstance(approved, dict)
                else {}
            )
            if (
                not isinstance(provenance, dict)
                or provenance.get("narration_cost_estimate_sha256")
                != estimate_hash
            ):
                approved_path.unlink()

        atomic_write_json(dest, request)
        prepared.append(
            {
                "concept_id": request["concept_id"],
                "format": request["format"],
                "request": str(dest),
            }
        )

    removed_stale: list[str] = []
    for directory, suffix in (
        (REVIEW_REQUESTS_DIR, ".narration_spend_review_request.json"),
        (RESPONSES_DIR, ".narration_spend_review_response.json"),
        (APPROVED_DIR, ".approved_narration_spend.json"),
    ):
        for path in directory.glob(f"*{suffix}"):
            key = path.name[: -len(suffix)]
            if key not in current_keys and _remove_if_exists(path):
                removed_stale.append(str(path.resolve()))

    if removed_stale:
        _remove_if_exists(SUMMARY_FILE)

    return {
        "status": (
            "NARRATION_SPEND_GATE_READY"
            if prepared
            else "WAITING_FOR_PROVIDER_QUOTE"
        ),
        "prepared": len(prepared),
        "requests": prepared,
        "removed_stale_gate_artifacts": removed_stale,
    }

def assert_current_estimate(request: dict[str, Any]) -> Path:
    provenance = request.get("request_provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError("STALE_SPEND_REVIEW: missing provenance")
    source = Path(str(provenance.get("narration_cost_estimate") or ""))
    expected = str(provenance.get("narration_cost_estimate_sha256") or "")
    if not source.exists() or not expected or sha256_file(source) != expected:
        raise ValueError("STALE_SPEND_REVIEW: narration cost estimate changed")
    estimate = load_json(source)
    if not isinstance(estimate, dict) or estimate.get("status") != "READY_FOR_SPEND_GATE":
        raise ValueError("STALE_SPEND_REVIEW: estimate is no longer spend-gate ready")
    return source


def response_path(concept_id: str, fmt: str) -> Path:
    return RESPONSES_DIR / (
        f"{artifact_key(concept_id, fmt)}.narration_spend_review_response.json"
    )


def validate_response(
    request: dict[str, Any],
    response: dict[str, Any],
) -> dict[str, Any]:
    if str(response.get("concept_id") or "") != str(request.get("concept_id") or ""):
        raise ValueError("concept_id mismatch")
    if str(response.get("format") or "") != str(request.get("format") or ""):
        raise ValueError("format mismatch")
    reviewer = str(response.get("reviewer") or "").strip()
    if not reviewer:
        raise ValueError("reviewer is required")
    decision = str(response.get("decision") or "").strip().upper()
    if decision not in {"ACCEPT", "REWORK", "REJECT"}:
        raise ValueError("invalid decision")
    supplied = response.get("criteria")
    if not isinstance(supplied, dict):
        raise ValueError("criteria are required")
    criteria = {
        name: supplied.get(name) is True for name in REQUIRED_ACCEPT_CRITERIA
    }
    note = str(response.get("note") or "").strip()
    if decision == "ACCEPT" and not all(criteria.values()):
        raise ValueError("ACCEPT requires all spend criteria true")
    if decision == "REWORK" and not note:
        raise ValueError("REWORK requires note")
    return {
        "concept_id": str(request["concept_id"]),
        "format": str(request["format"]),
        "reviewer": reviewer,
        "decision": decision,
        "criteria": criteria,
        "note": note,
    }


def apply_payload(
    request_path: Path,
    normalized: dict[str, Any],
) -> dict[str, Any]:
    request = load_json(request_path)
    source = assert_current_estimate(request)
    decision = normalized["decision"]
    summary = {
        "status": (
            "NARRATION_SPEND_APPROVED"
            if decision == "ACCEPT"
            else "NARRATION_SPEND_REWORK_REQUIRED"
            if decision == "REWORK"
            else "NARRATION_SPEND_REJECTED"
        ),
        **normalized,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "initial_estimate_usd": request["initial_estimate_usd"],
        "worst_case_estimate_usd": request["worst_case_estimate_usd"],
        "currency": request["currency"],
    }

    approved_path = APPROVED_DIR / (
        f"{artifact_key(request['concept_id'], request['format'])}"
        ".approved_narration_spend.json"
    )
    budget_video = video_budget.video_id(request["concept_id"], request["format"])
    if decision == "ACCEPT":
        # The approved worst case is this video's narration reservation (D-136).
        video_budget.reserve(
            video=budget_video,
            category="narration",
            ref="narration",
            amount_usd=float(request["worst_case_estimate_usd"]),
            note="Narration spend approved at the worst-case estimate",
            ledger=video_budget.ledger_in(APPROVED_DIR.parent),
        )
        estimate = load_json(source)
        payload = {
            **estimate,
            "spend_gate": summary,
            "approved_provenance": {
                "spend_review_request_sha256": sha256_file(request_path),
                "narration_cost_estimate_sha256": sha256_file(source),
            },
        }
        APPROVED_DIR.mkdir(parents=True, exist_ok=True)
        atomic_write_json(approved_path, payload)
        summary["approved_narration_spend"] = str(approved_path)
    else:
        video_budget.release(
            video=budget_video, category="narration", ref="narration", note=decision,
            ledger=video_budget.ledger_in(APPROVED_DIR.parent),
        )
        if approved_path.exists():
            approved_path.unlink()

    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def _response_is_current(request: dict[str, Any], saved: dict[str, Any]) -> bool:
    if not saved:
        return False
    try:
        source = assert_current_estimate(request)
    except ValueError:
        return False
    expected = str(
        request.get("request_provenance", {}).get(
            "narration_cost_estimate_sha256"
        )
        or ""
    )
    return (
        sha256_file(source) == expected
        and saved.get("narration_cost_estimate_sha256") == expected
    )


def snapshot() -> dict[str, Any]:
    render_state = narration_render_snapshot()
    eligible = {
        artifact_key(
            str(item.get("concept_id") or ""),
            str(item.get("format") or ""),
        )
        for item in render_state.get("items", [])
        if isinstance(item, dict)
        and item.get("status") == "READY_FOR_SPEND_GATE"
    }

    items: list[dict[str, Any]] = []
    stale_requests = 0
    counts = {"pending": 0, "accepted": 0, "rework": 0, "rejected": 0}
    decision_key = {
        "ACCEPT": "accepted",
        "REWORK": "rework",
        "REJECT": "rejected",
    }

    if REVIEW_REQUESTS_DIR.exists():
        for path in sorted(
            REVIEW_REQUESTS_DIR.glob("*.narration_spend_review_request.json")
        ):
            request = _load_dict_or_none(path)
            if not isinstance(request, dict):
                stale_requests += 1
                continue
            concept_id = str(request.get("concept_id") or "")
            fmt = str(request.get("format") or "")
            key = artifact_key(concept_id, fmt)
            if key not in eligible:
                stale_requests += 1
                continue

            saved_path = response_path(concept_id, fmt)
            saved = _load_dict_or_none(saved_path) if saved_path.exists() else {}
            try:
                source = assert_current_estimate(request)
            except ValueError:
                stale_requests += 1
                saved = {}
                source = None
            if (
                source is None
                or not isinstance(saved, dict)
                or not _response_is_current(request, saved)
            ):
                saved = {}
            decision = str(saved.get("decision") or "PENDING").upper()
            counts[decision_key.get(decision, "pending")] += 1
            items.append(
                {
                    **request,
                    "decision": decision,
                    "criteria_decisions": saved.get("criteria", {}),
                    "note": saved.get("note", ""),
                }
            )

    complete = (
        bool(items)
        and len(items) == len(eligible)
        and counts["pending"] == 0
        and stale_requests == 0
    )
    if not eligible:
        status = "WAITING_FOR_PROVIDER_QUOTE"
    elif not items or stale_requests:
        status = "READY_TO_PREPARE"
    elif complete:
        status = "COMPLETE"
    else:
        status = "AWAITING_HUMAN_DECISION"

    return {
        "status": status,
        "complete": complete,
        "items": items,
        "eligible": len(eligible),
        "stale_requests": stale_requests,
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
    key = artifact_key(concept_id, format)
    # Two decisions on the same video at once (two tabs, or a person and the
    # gate policy) must not interleave reserve/release with the approval file
    # (audit 2026-10-04).
    with named_lock(f"narration_spend_gate:{key}"):
        return _apply_action(key, concept_id, format, decision, criteria, note)


def _apply_action(
    key: str, concept_id: str, format: str, decision: str, criteria: dict[str, Any], note: str | None
) -> dict[str, Any]:
    request_path = (
        REVIEW_REQUESTS_DIR / f"{key}.narration_spend_review_request.json"
    )
    if not request_path.exists():
        raise ValueError("Narration spend review request not found")
    request = load_json(request_path)
    payload = {
        "concept_id": concept_id,
        "format": format,
        "reviewer": reviewer_id(),
        "decision": decision,
        "criteria": criteria,
        "note": str(note or ""),
    }
    normalized = validate_response(request, payload)
    source = assert_current_estimate(request)
    source_hash = sha256_file(source)
    apply_payload(request_path, normalized)

    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    saved = {
        **normalized,
        "narration_cost_estimate_sha256": source_hash,
    }
    atomic_write_json(response_path(concept_id, format), saved)
    return snapshot()


def main() -> None:
    parser = argparse.ArgumentParser(description="Human Narration Spend Gate")
    parser.add_argument("--mode", choices=("prepare", "status"), required=True)
    args = parser.parse_args()
    payload = prepare() if args.mode == "prepare" else snapshot()
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
