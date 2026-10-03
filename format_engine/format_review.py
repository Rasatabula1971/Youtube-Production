"""Human Format Gate.

A deterministically valid format plan is not producible until a human accepts
that its production branches are genuinely separate and still deliver the
approved package promise.
"""

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

from format_engine import (
    OUTPUT_DIR,
    PLANS_DIR,
    REQUESTS_DIR,
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
REVIEWER_ENV = "YOUTUBE_REVIEWER_ID"
DEFAULT_REVIEWER = "local-operator"


def reviewer_id() -> str:
    return os.getenv(REVIEWER_ENV, DEFAULT_REVIEWER).strip() or DEFAULT_REVIEWER

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


def _current_plan_request_path(
    plan: dict[str, Any],
) -> Path | None:
    concept_id = str(plan.get("concept_id") or "").strip()
    provenance = plan.get("plan_provenance", {})
    if not concept_id or not isinstance(provenance, dict):
        return None

    expected = (
        REQUESTS_DIR / f"{safe_slug(concept_id)}.format_request.json"
    ).resolve()
    recorded = Path(
        str(provenance.get("request_source") or "")
    ).resolve()
    expected_hash = str(
        provenance.get("request_sha256") or ""
    ).strip()
    if (
        recorded != expected
        or not expected.is_file()
        or not expected_hash
        or sha256_file(expected) != expected_hash
    ):
        return None
    request = load_json(expected)
    if str(request.get("concept_id") or "").strip() != concept_id:
        return None
    return expected


def _remove_if_exists(path: Path) -> bool:
    if not path.exists():
        return False
    if not path.is_file():
        raise ValueError(f"Expected Format Gate file: {path}")
    path.unlink()
    return True


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
    paths = (
        sorted(PLANS_DIR.glob("*.format_plan.json"))
        if PLANS_DIR.exists()
        else []
    )
    prepared = []
    skipped_stale = []
    current_slugs: set[str] = set()

    for path in paths:
        plan = load_json(path)
        if _current_plan_request_path(plan) is None:
            skipped_stale.append(str(path.resolve()))
            continue

        request = build_review_request(plan, path, config)
        slug = safe_slug(request["concept_id"])
        current_slugs.add(slug)
        dest = (
            REVIEW_REQUESTS_DIR
            / f"{slug}.format_review_request.json"
        )
        current_plan_hash = sha256_file(path)

        existing_response = response_path(request["concept_id"])
        if existing_response.is_file():
            saved = load_json(existing_response)
            if saved.get("format_plan_sha256") != current_plan_hash:
                existing_response.unlink()

        approved_path = (
            APPROVED_DIR / f"{slug}.approved_format_plan.json"
        )
        if approved_path.is_file():
            approved = load_json(approved_path)
            provenance = approved.get("approved_provenance", {})
            if (
                not isinstance(provenance, dict)
                or provenance.get("format_plan_sha256")
                != current_plan_hash
            ):
                approved_path.unlink()

        atomic_write_json(dest, request)
        prepared.append(
            {
                "concept_id": request["concept_id"],
                "request": str(dest),
            }
        )

    removed_stale_gate_artifacts: list[str] = []
    for directory, suffix in (
        (REVIEW_REQUESTS_DIR, ".format_review_request.json"),
        (RESPONSES_DIR, ".format_review_response.json"),
        (APPROVED_DIR, ".approved_format_plan.json"),
    ):
        if not directory.exists():
            continue
        for path in directory.glob(f"*{suffix}"):
            slug = path.name[: -len(suffix)]
            if slug not in current_slugs and _remove_if_exists(path):
                removed_stale_gate_artifacts.append(
                    str(path.resolve())
                )

    if removed_stale_gate_artifacts:
        _remove_if_exists(SUMMARY_FILE)

    return {
        "status": "FORMAT_GATE_READY" if prepared else "WAITING_FOR_FORMAT_PLANS",
        "prepared": len(prepared),
        "requests": prepared,
        "skipped_stale_plans": skipped_stale,
        "removed_stale_gate_artifacts": removed_stale_gate_artifacts,
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
    note = str(response.get("note", "") or "").strip()
    normalized = (
        {name: True for name in names}
        if decision == "ACCEPT"
        else {name: False for name in names}
        if decision == "REJECT"
        else {}
    )
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


def _apply_rework_feedback(
    request: dict[str, Any],
    *,
    note: str,
) -> None:
    source = assert_current_plan(request)
    plan = load_json(source)
    provenance = plan.get("plan_provenance", {})
    request_source = Path(str(provenance.get("request_source") or "")).resolve()
    requests_root = REQUESTS_DIR.resolve()
    if not request_source.exists() or requests_root not in request_source.parents:
        raise ValueError("Format rework cannot find the current format request")

    original_request = load_json(request_source)
    concept_id = str(request.get("concept_id") or "")
    if str(original_request.get("concept_id") or "") != concept_id:
        raise ValueError("Format rework request concept_id mismatch")

    original_request["human_rework_iteration"] = (
        int(original_request.get("human_rework_iteration") or 0) + 1
    )
    original_request["human_rework_mode"] = "HUMAN_INSTRUCTION_ONLY"
    original_request["human_rework_note"] = note
    original_request["human_rework_original_plan"] = {
        "format_intent": plan.get("format_intent"),
        "required_branches": plan.get("required_branches", []),
        "branches": plan.get("branches", []),
        "validation": plan.get("validation", {}),
    }
    atomic_write_json(request_source, original_request)


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
        atomic_write_json(approved_path, plan)
        summary["approved_format_plan"] = str(approved_path)
    elif approved_path.exists():
        approved_path.unlink()

    if decision == "REWORK":
        _apply_rework_feedback(request, note=normalized["note"])

    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(SUMMARY_FILE, summary)
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
    value = str(decision or "").strip().upper()
    payload = {
        "concept_id": concept_id,
        "reviewer": reviewer_id(),
        "decision": value,
        "criteria": {},
        "note": str(note or ""),
    }

    # Validate the human action and reviewed-plan provenance BEFORE persisting it.
    normalized = validate_response(request, payload)
    source = assert_current_plan(request)
    apply_payload(request_path, normalized)

    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    dest = response_path(concept_id)
    saved = {**normalized, "format_plan_sha256": sha256_file(source)}
    atomic_write_json(dest, saved)
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
