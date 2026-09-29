"""Human Voice Performance Gate.

A valid delivery plan cannot authorize paid rendering until a human accepts it.
This module records that decision only; it never calls Higgsfield.
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

from pipeline_integrity import atomic_write_json
from voice_performance import (
    SPECS_DIR,
    OUTPUT_DIR,
    load_json,
    safe_slug,
    sha256_file,
)

HERE = Path(__file__).resolve().parent
GATE_CONFIG_FILE = HERE / "voice_gate_config.json"
REVIEW_REQUESTS_DIR = OUTPUT_DIR / "voice_performance_review_requests"
RESPONSES_DIR = OUTPUT_DIR / "voice_performance_review_responses"
APPROVED_DIR = OUTPUT_DIR / "approved_voice_specs"
SUMMARY_FILE = OUTPUT_DIR / "voice_performance_gate_summary.json"
REVIEWER_ENV = "YOUTUBE_REVIEWER_ID"
DEFAULT_REVIEWER = "local-operator"

CRITERIA_DESCRIPTIONS = {
    "narration_text_unchanged": (
        "The performance plan changes delivery only; the approved spoken words "
        "remain immutable."
    ),
    "delivery_matches_branch_intent": (
        "The planned delivery supports this production branch's promise, purpose "
        "and payoff."
    ),
    "emotion_curve_is_restrained": (
        "Emotion changes feel intentional and restrained rather than theatrical."
    ),
    "pace_and_pauses_support_comprehension": (
        "Pace and pause choices should make the narration easier to follow."
    ),
    "emphasis_is_grounded_in_spoken_words": (
        "Every emphasized term is actually present in the immutable narration."
    ),
}


def reviewer_id() -> str:
    return os.getenv(REVIEWER_ENV, DEFAULT_REVIEWER).strip() or DEFAULT_REVIEWER


def load_gate_config(path: Path = GATE_CONFIG_FILE) -> dict[str, Any]:
    config = load_json(path)
    if not isinstance(config, dict):
        raise ValueError("Voice Performance Gate config must be an object")
    required = {"required_accept_criteria", "require_reviewer_name"}
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(
            "Voice Performance Gate config is missing: " + ", ".join(missing)
        )
    return config


def criteria_names(config: dict[str, Any] | None = None) -> tuple[str, ...]:
    config = config or load_gate_config()
    return tuple(str(item) for item in config["required_accept_criteria"])


def artifact_key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def build_review_request(
    spec: dict[str, Any],
    spec_path: Path,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or load_gate_config()
    concept_id = str(spec.get("concept_id") or "").strip()
    fmt = str(spec.get("format") or "").strip()
    if not concept_id or not fmt:
        raise ValueError("Voice Performance spec requires concept_id and format")
    validation = spec.get("validation", {})
    if not isinstance(validation, dict) or validation.get("valid") is not True:
        raise ValueError("Voice Performance spec must pass deterministic validation")
    names = criteria_names(config)
    return {
        "request_type": "human_voice_performance_gate",
        "concept_id": concept_id,
        "format": fmt,
        "title": spec.get("title"),
        "duration_intent_seconds": spec.get("duration_intent_seconds"),
        "promise_delivery": spec.get("promise_delivery"),
        "payoff": spec.get("payoff"),
        "beats": spec.get("beats", []),
        "directions": spec.get("directions", []),
        "voice_identity": spec.get("voice_identity", {}),
        "render_prerequisites_configured": bool(
            spec.get("render_prerequisites_configured")
        ),
        "required_accept_criteria": list(names),
        "criteria": {
            name: CRITERIA_DESCRIPTIONS.get(name, name)
            for name in names
        },
        "request_provenance": {
            "voice_performance_spec": str(spec_path.resolve()),
            "voice_performance_spec_sha256": sha256_file(spec_path),
        },
    }


def prepare(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_gate_config()
    REVIEW_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = (
        sorted(SPECS_DIR.glob("*.voice_performance_spec.json"))
        if SPECS_DIR.exists()
        else []
    )
    prepared: list[dict[str, Any]] = []
    current: set[Path] = set()
    for path in paths:
        request = build_review_request(load_json(path), path, config)
        key = artifact_key(request["concept_id"], request["format"])
        dest = REVIEW_REQUESTS_DIR / f"{key}.voice_review_request.json"
        atomic_write_json(dest, request)
        current.add(dest.resolve())
        prepared.append(
            {
                "concept_id": request["concept_id"],
                "format": request["format"],
                "request": str(dest),
            }
        )
    for stale in REVIEW_REQUESTS_DIR.glob("*.voice_review_request.json"):
        if stale.resolve() not in current:
            stale.unlink()
    return {
        "status": (
            "VOICE_PERFORMANCE_GATE_READY"
            if prepared
            else "WAITING_FOR_VOICE_PERFORMANCE_SPECS"
        ),
        "prepared": len(prepared),
        "requests": prepared,
    }


def validate_response(
    request: dict[str, Any],
    response: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or load_gate_config()
    if str(response.get("concept_id") or "") != str(request.get("concept_id") or ""):
        raise ValueError("concept_id mismatch")
    if str(response.get("format") or "") != str(request.get("format") or ""):
        raise ValueError("format mismatch")
    reviewer = str(response.get("reviewer") or "").strip()
    if config.get("require_reviewer_name") and not reviewer:
        raise ValueError("reviewer is required")
    decision = str(response.get("decision") or "").strip().upper()
    if decision not in {"ACCEPT", "REWORK", "REJECT"}:
        raise ValueError("invalid decision")
    supplied = response.get("criteria")
    if not isinstance(supplied, dict):
        raise ValueError("criteria are required")
    names = tuple(
        str(item) for item in request.get("required_accept_criteria", ())
    ) or criteria_names(config)
    criteria = {name: supplied.get(name) is True for name in names}
    note = str(response.get("note") or "").strip()
    if decision == "ACCEPT" and not all(criteria.values()):
        raise ValueError("ACCEPT requires all criteria true")
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


def assert_current_spec(request: dict[str, Any]) -> Path:
    provenance = request.get("request_provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError("STALE_REVIEW_REQUEST: missing provenance")
    source = Path(str(provenance.get("voice_performance_spec") or ""))
    expected = str(provenance.get("voice_performance_spec_sha256") or "")
    if not source.exists() or not expected or sha256_file(source) != expected:
        raise ValueError("STALE_REVIEW_REQUEST: voice performance spec changed")
    return source


def response_path(concept_id: str, fmt: str) -> Path:
    return RESPONSES_DIR / (
        f"{artifact_key(concept_id, fmt)}.voice_review_response.json"
    )


def _response_is_current(request: dict[str, Any], saved: dict[str, Any]) -> bool:
    if not saved:
        return False
    try:
        source = assert_current_spec(request)
    except ValueError:
        return False
    expected = str(
        request.get("request_provenance", {}).get(
            "voice_performance_spec_sha256"
        )
        or ""
    )
    return (
        sha256_file(source) == expected
        and saved.get("voice_performance_spec_sha256") == expected
    )


def apply_payload(
    request_path: Path,
    normalized: dict[str, Any],
) -> dict[str, Any]:
    request = load_json(request_path)
    source = assert_current_spec(request)
    decision = normalized["decision"]
    summary = {
        "status": (
            "PERFORMANCE_SPEC_APPROVED"
            if decision == "ACCEPT"
            else "PERFORMANCE_REWORK_REQUIRED"
            if decision == "REWORK"
            else "PERFORMANCE_REJECTED"
        ),
        **normalized,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }

    approved_path = APPROVED_DIR / (
        f"{artifact_key(request['concept_id'], request['format'])}"
        ".approved_voice_spec.json"
    )
    if decision == "ACCEPT":
        spec = load_json(source)
        spec["performance_gate"] = summary
        spec["approved_provenance"] = {
            "voice_review_request_sha256": sha256_file(request_path),
            "voice_performance_spec_sha256": sha256_file(source),
        }
        APPROVED_DIR.mkdir(parents=True, exist_ok=True)
        atomic_write_json(approved_path, spec)
        summary["approved_voice_spec"] = str(approved_path)
    elif approved_path.exists():
        approved_path.unlink()

    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def snapshot() -> dict[str, Any]:
    if not REVIEW_REQUESTS_DIR.exists():
        return {
            "status": "READY_TO_PREPARE",
            "complete": False,
            "specs": [],
            "pending": 0,
            "accepted": 0,
            "rework": 0,
            "rejected": 0,
        }
    specs: list[dict[str, Any]] = []
    stale_requests = 0
    counts = {"pending": 0, "accepted": 0, "rework": 0, "rejected": 0}
    decision_key = {
        "ACCEPT": "accepted",
        "REWORK": "rework",
        "REJECT": "rejected",
    }
    for path in sorted(
        REVIEW_REQUESTS_DIR.glob("*.voice_review_request.json")
    ):
        request = load_json(path)
        concept_id = str(request.get("concept_id") or "")
        fmt = str(request.get("format") or "")
        saved_path = response_path(concept_id, fmt)
        saved = load_json(saved_path) if saved_path.exists() else {}
        try:
            assert_current_spec(request)
        except ValueError:
            stale_requests += 1
            saved = {}
        if not isinstance(saved, dict) or not _response_is_current(request, saved):
            saved = {}
        decision = str(saved.get("decision") or "PENDING").upper()
        counts[decision_key.get(decision, "pending")] += 1
        specs.append(
            {
                **request,
                "decision": decision,
                "criteria_decisions": saved.get("criteria", {}),
                "note": saved.get("note", ""),
            }
        )
    complete = bool(specs) and counts["pending"] == 0 and stale_requests == 0
    status = (
        "READY_TO_PREPARE"
        if stale_requests
        else "COMPLETE"
        if complete
        else "AWAITING_HUMAN_DECISION"
    )
    return {
        "status": status,
        "complete": complete,
        "specs": specs,
        "stale_requests": stale_requests,
        **counts,
    }


def _apply_rework_feedback(source: Path, note: str) -> None:
    """Feed human rework guidance into the free planner and invalidate the spec."""
    spec = load_json(source)
    provenance = spec.get("spec_provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError("Voice Performance spec is missing provenance")
    request_source = Path(str(provenance.get("request_source") or ""))
    if not request_source.exists():
        raise ValueError("Voice Performance request for rework is missing")
    request = load_json(request_source)
    if not isinstance(request, dict):
        raise ValueError("Voice Performance request must be an object")
    iteration = int(request.get("human_rework_iteration") or 0) + 1
    request["human_rework_iteration"] = iteration
    request["human_rework_note"] = note
    atomic_write_json(request_source, request)
    source.unlink()


def apply_action(
    *,
    concept_id: str,
    format: str,
    decision: str,
    criteria: dict[str, Any],
    note: str | None = None,
) -> dict[str, Any]:
    key = artifact_key(concept_id, format)
    request_path = REVIEW_REQUESTS_DIR / f"{key}.voice_review_request.json"
    if not request_path.exists():
        raise ValueError("Voice Performance review request not found")
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
    source = assert_current_spec(request)
    source_hash = sha256_file(source)
    apply_payload(request_path, normalized)
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    saved = {
        **normalized,
        "voice_performance_spec_sha256": source_hash,
    }
    atomic_write_json(response_path(concept_id, format), saved)
    if normalized["decision"] == "REWORK":
        _apply_rework_feedback(source, normalized["note"])
    return snapshot()


def main() -> None:
    parser = argparse.ArgumentParser(description="Human Voice Performance Gate")
    parser.add_argument("--mode", choices=("prepare",), required=True)
    parser.parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
