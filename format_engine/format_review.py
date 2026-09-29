"""Human Format Gate.

A deterministically valid format plan is not producible until a human accepts
that its production branches are genuinely separate and still deliver the
approved package promise.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from format_engine import (
    OUTPUT_DIR,
    PLANS_DIR,
    load_json,
    safe_slug,
    sha256_file,
)

HERE = Path(__file__).resolve().parent
GATE_CONFIG_FILE = HERE / "format_gate_config.json"

REVIEW_REQUESTS_DIR = OUTPUT_DIR / "format_review_requests"
RESPONSES_DIR = OUTPUT_DIR / "format_review_responses"
APPROVED_DIR = OUTPUT_DIR / "approved_format_plans"
SUMMARY_FILE = OUTPUT_DIR / "format_gate_summary.json"
UI_REVIEWER = "local-operator"

CRITERIA_DESCRIPTIONS = {
    "branches_are_separate_productions": (
        "Each production branch is planned in its own shape rather than as the "
        "same timeline re-cut or truncated."
    ),
    "promise_preserved_per_branch": (
        "Every branch still delivers the approved package promise and expected "
        "payoff for its own viewing context."
    ),
    "facts_within_accepted_claims": (
        "Factual beats stay within human-accepted research claims."
    ),
    "duration_intent_realistic": (
        "The stated duration intent is achievable for the planned beats."
    ),
    "producible_from_available_material": (
        "The plan can actually be produced from material the project can create "
        "or lawfully obtain."
    ),
}


def load_gate_config(path: Path = GATE_CONFIG_FILE) -> dict[str, Any]:
    config = load_json(path)
    required = {"required_accept_criteria", "require_reviewer_name"}
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit("Format Gate config is missing: " + ", ".join(missing))
    return config


def criteria_names(config: dict[str, Any] | None = None) -> tuple[str, ...]:
    config = config or load_gate_config()
    return tuple(str(name) for name in config["required_accept_criteria"])


def build_review_request(
    plan: dict[str, Any],
    plan_path: Path,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or load_gate_config()
    concept_id = str(plan.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Format plan requires concept_id")
    validation = plan.get("validation", {})
    if not isinstance(validation, dict):
        validation = {}
    names = criteria_names(config)
    return {
        "request_type": "human_format_gate",
        "concept_id": concept_id,
        "format_intent": plan.get("format_intent"),
        "required_branches": plan.get("required_branches", []),
        "branch_constraints": plan.get("branch_constraints", {}),
        "branches": plan.get("branches", []),
        "package": plan.get("package", {}),
        "accepted_claims": plan.get("accepted_claims", []),
        "branch_separation": validation.get("branch_separation", {}),
        "claim_usage_by_branch": validation.get("claim_usage_by_branch", {}),
        "unused_accepted_claim_ids": validation.get("unused_accepted_claim_ids", []),
        "source_overlap": validation.get("source_overlap", {}),
        "required_accept_criteria": list(names),
        "criteria": {name: CRITERIA_DESCRIPTIONS.get(name, name) for name in names},
        "request_provenance": {
            "format_plan": str(plan_path.resolve()),
            "format_plan_sha256": sha256_file(plan_path),
        },
    }


def prepare(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_gate_config()
    REVIEW_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = sorted(PLANS_DIR.glob("*.format_plan.json")) if PLANS_DIR.exists() else []
    prepared = []
    for path in paths:
        request = build_review_request(load_json(path), path, config)
        dest = (
            REVIEW_REQUESTS_DIR
            / f"{safe_slug(request['concept_id'])}.format_review_request.json"
        )
        dest.write_text(
            json.dumps(request, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        prepared.append({"concept_id": request["concept_id"], "request": str(dest)})
    return {
        "status": "FORMAT_GATE_READY" if prepared else "WAITING_FOR_FORMAT_PLANS",
        "prepared": len(prepared),
        "requests": prepared,
    }


def validate_response(
    request: dict[str, Any],
    response: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or load_gate_config()
    names = tuple(str(name) for name in request.get("required_accept_criteria", ()))
    if not names:
        names = criteria_names(config)

    if str(response.get("concept_id", "")) != str(request.get("concept_id", "")):
        raise ValueError("concept_id mismatch")
    reviewer = str(response.get("reviewer", "")).strip()
    if config.get("require_reviewer_name") and not reviewer:
        raise ValueError("reviewer is required")
    decision = str(response.get("decision", "")).strip().upper()
    if decision not in {"ACCEPT", "REWORK", "REJECT"}:
        raise ValueError("invalid decision")
    criteria = response.get("criteria")
    if not isinstance(criteria, dict):
        raise ValueError("criteria are required")
    normalized = {name: criteria.get(name) is True for name in names}
    note = str(response.get("note", "") or "").strip()
    if decision == "ACCEPT" and not all(normalized.values()):
        raise ValueError("ACCEPT requires all criteria true")
    if decision == "REWORK" and not note:
        raise ValueError("REWORK requires note")
    return {
        "concept_id": str(request["concept_id"]),
        "reviewer": reviewer,
        "decision": decision,
        "criteria": normalized,
        "note": note,
    }


def assert_current_plan(request: dict[str, Any]) -> Path:
    provenance = request.get("request_provenance", {})
    source = Path(str(provenance.get("format_plan", "")))
    expected_hash = str(provenance.get("format_plan_sha256", ""))
    if not source.exists() or not expected_hash:
        raise ValueError("STALE_REVIEW_REQUEST: reviewed format plan is unavailable")
    if sha256_file(source) != expected_hash:
        raise ValueError(
            "STALE_REVIEW_REQUEST: format plan changed after review preparation"
        )
    return source


def apply_payload(request_path: Path, response: dict[str, Any]) -> dict[str, Any]:
    request = load_json(request_path)
    normalized = validate_response(request, response)
    source = assert_current_plan(request)
    decision = normalized["decision"]
    summary = {
        "status": (
            "READY_FOR_PRODUCTION_ENGINE"
            if decision == "ACCEPT"
            else "FORMAT_REWORK_REQUIRED"
            if decision == "REWORK"
            else "FORMAT_REJECTED"
        ),
        **normalized,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }

    approved_path = (
        APPROVED_DIR / f"{safe_slug(request['concept_id'])}.approved_format_plan.json"
    )
    if decision == "ACCEPT":
        plan = load_json(source)
        plan["format_gate"] = summary
        plan["approved_provenance"] = {
            "format_review_request_sha256": sha256_file(request_path),
            "format_plan_sha256": sha256_file(source),
        }
        APPROVED_DIR.mkdir(parents=True, exist_ok=True)
        approved_path.write_text(
            json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        summary["approved_format_plan"] = str(approved_path)
    elif approved_path.exists():
        approved_path.unlink()

    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def apply(request_path: Path, response_path: Path) -> dict[str, Any]:
    return apply_payload(request_path, load_json(response_path))


def response_path(concept_id: str) -> Path:
    return RESPONSES_DIR / f"{safe_slug(concept_id)}.format_review_response.json"


def _response_is_current(request: dict[str, Any], saved: dict[str, Any]) -> bool:
    if not saved:
        return False
    provenance = request.get("request_provenance", {})
    source = Path(str(provenance.get("format_plan", "")))
    expected = str(provenance.get("format_plan_sha256", ""))
    if not source.exists() or not expected:
        return False
    if sha256_file(source) != expected:
        return False
    return saved.get("format_plan_sha256") == expected


def snapshot() -> dict[str, Any]:
    if not REVIEW_REQUESTS_DIR.exists():
        return {
            "status": "READY_TO_PREPARE",
            "complete": False,
            "plans": [],
            "pending": 0,
            "accepted": 0,
            "rework": 0,
            "rejected": 0,
        }

    plans = []
    counts = {"pending": 0, "accepted": 0, "rework": 0, "rejected": 0}
    decision_key = {"ACCEPT": "accepted", "REWORK": "rework", "REJECT": "rejected"}

    for path in sorted(REVIEW_REQUESTS_DIR.glob("*.format_review_request.json")):
        request = load_json(path)
        concept_id = str(request.get("concept_id", ""))
        saved_path = response_path(concept_id)
        saved = load_json(saved_path) if saved_path.exists() else {}
        if not _response_is_current(request, saved):
            saved = {}
        decision = str(saved.get("decision") or "PENDING").upper()
        counts[decision_key.get(decision, "pending")] += 1
        plans.append(
            {
                **request,
                "decision": decision,
                "criteria_decisions": saved.get("criteria", {}),
                "note": saved.get("note", ""),
            }
        )

    complete = bool(plans) and counts["pending"] == 0
    return {
        "status": "COMPLETE" if complete else "AWAITING_HUMAN_DECISION",
        "complete": complete,
        "plans": plans,
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
        REVIEW_REQUESTS_DIR / f"{safe_slug(concept_id)}.format_review_request.json"
    )
    if not request_path.exists():
        raise ValueError("Format review request not found")

    request = load_json(request_path)
    payload = {
        "concept_id": concept_id,
        "reviewer": UI_REVIEWER,
        "decision": decision,
        "criteria": criteria,
        "note": str(note or ""),
    }

    # Validate the human action and reviewed-plan provenance BEFORE persisting it.
    normalized = validate_response(request, payload)
    source = assert_current_plan(request)
    apply_payload(request_path, normalized)

    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    dest = response_path(concept_id)
    saved = {**normalized, "format_plan_sha256": sha256_file(source)}
    dest.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
    return snapshot()


def main() -> None:
    parser = argparse.ArgumentParser(description="Human Format Gate")
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
