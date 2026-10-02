"""Human Title Direction Gate for Packaging Architecture Slice 23.

The gate preserves the existing five Short + five Long-form choice behavior but
formalizes the decision as a psychological/title direction, not immutable final
wording. Candidate and selection artifacts are hash-bound and append-only
history is preserved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from title_direction import (
    CANDIDATES_FILE,
    REQUESTS_DIR,
    RESPONSES_DIR,
    load_json,
    safe_slug,
    sha256_file,
)

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"
STATE_FILE = OUTPUT_DIR / "title_direction_gate_state.json"
APPROVED_FILE = OUTPUT_DIR / "selected_title_directions.json"
HISTORY_DIR = OUTPUT_DIR / "title_direction_history"
SUMMARY_FILE = OUTPUT_DIR / "title_direction_gate_summary.json"

REVIEWER_ENV = "YOUTUBE_REVIEWER_ID"
DEFAULT_REVIEWER = "local-operator"


def _content_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def candidates_hash() -> str | None:
    return sha256_file(CANDIDATES_FILE) if CANDIDATES_FILE.is_file() else None


def concept_fingerprint(item: dict[str, Any]) -> str:
    return _content_hash(
        {
            "concept_id": item.get("concept_id"),
            "titles": item.get("titles"),
            "request_sha256": item.get("request_sha256"),
            "response_provenance": item.get("response_provenance"),
        }
    )


def _candidate_map(item: dict[str, Any], fmt: str) -> dict[str, dict[str, Any]]:
    titles = item.get("titles", {})
    values = titles.get(fmt, []) if isinstance(titles, dict) else []
    if not isinstance(values, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for candidate in values:
        if not isinstance(candidate, dict):
            continue
        title_id = str(candidate.get("title_id") or "").strip()
        if title_id:
            if title_id in out:
                raise ValueError(f"Duplicate title_id in gate input: {title_id}")
            out[title_id] = candidate
    return out


def _normalize_selection(
    item: dict[str, Any],
    fmt: str,
    value: Any,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Select one {fmt} title direction")
    title_id = str(
        value.get("title_id")
        or value.get("candidate_id")
        or ""
    ).strip()
    if not title_id:
        raise ValueError(f"Select one {fmt} title direction")
    candidates = _candidate_map(item, fmt)
    candidate = candidates.get(title_id)
    if candidate is None:
        raise ValueError(f"Unknown {fmt} title direction: {title_id}")

    selected_text = str(
        value.get("title_text")
        or value.get("title")
        or candidate.get("title_text")
        or ""
    ).strip()
    if not selected_text:
        raise ValueError(f"{fmt} selected title text cannot be blank")

    return {
        "format": fmt,
        "selected_title_id": title_id,
        "selected_title_text": selected_text,
        "selected_psychological_angle": candidate.get("psychological_angle"),
        "selected_primary_driver": candidate.get("primary_driver"),
        "selected_secondary_driver": candidate.get("secondary_driver"),
        "core_claim": candidate.get("core_claim"),
        "evidence_refs": list(candidate.get("evidence_refs", [])),
        "character_count": len(selected_text),
        "search_intent": candidate.get("search_intent"),
        "wording_edited": (
            selected_text
            != str(candidate.get("title_text") or "").strip()
        ),
        "candidate_snapshot": candidate,
    }


def _load_candidates() -> dict[str, Any]:
    if not CANDIDATES_FILE.is_file():
        raise ValueError("WAITING_FOR_TITLE_DIRECTION_CANDIDATES")
    payload = load_json(CANDIDATES_FILE)
    if (
        not isinstance(payload, dict)
        or payload.get("artifact") != "title_direction_candidates"
    ):
        raise ValueError("INVALID_TITLE_DIRECTION_CANDIDATES")
    concepts = payload.get("concepts", [])
    if not isinstance(concepts, list):
        raise ValueError("Title direction candidates concepts must be a list")
    ids = [str(x.get("concept_id") or "") for x in concepts if isinstance(x, dict)]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate concept_id in title direction candidates")
    return payload


def _state() -> dict[str, Any]:
    if not STATE_FILE.is_file():
        return {}
    state = load_json(STATE_FILE)
    if state.get("candidates_sha256") != candidates_hash():
        return {}
    return state if isinstance(state, dict) else {}


def prepare_state() -> dict[str, Any]:
    payload = _load_candidates()
    previous = _state()
    previous_decisions = (
        previous.get("decisions", {})
        if isinstance(previous.get("decisions"), dict)
        else {}
    )
    preserved: dict[str, Any] = {}
    for item in payload.get("concepts", []):
        if not isinstance(item, dict):
            continue
        concept_id = str(item.get("concept_id") or "")
        saved = previous_decisions.get(concept_id)
        if (
            isinstance(saved, dict)
            and saved.get("decision") in {"ACCEPT", "REJECT"}
            and saved.get("concept_fingerprint") == concept_fingerprint(item)
        ):
            preserved[concept_id] = saved

    state = {
        "artifact": "title_direction_gate_state",
        "schema_version": "1.0",
        "status": "AWAITING_HUMAN_TITLE_DIRECTION",
        "candidates_sha256": candidates_hash(),
        "reviewer": (
            previous.get("reviewer")
            if isinstance(previous, dict) and previous.get("reviewer")
            else os.getenv(REVIEWER_ENV, DEFAULT_REVIEWER)
        ),
        "decisions": preserved,
    }
    atomic_write_json(STATE_FILE, state)
    _finalize_if_complete()
    return snapshot()


def _public_item(item: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    concept_id = str(item.get("concept_id") or "")
    decision = state.get("decisions", {}).get(concept_id, {})
    return {
        **item,
        "decision": decision.get("decision", "PENDING"),
        "selected_titles": decision.get("selected_titles", {}),
        "note": decision.get("note", ""),
    }


def snapshot() -> dict[str, Any]:
    if not CANDIDATES_FILE.is_file():
        return {
            "status": "WAITING_FOR_TITLE_DIRECTION_CANDIDATES",
            "complete": False,
            "ready": False,
            "concepts": [],
        }
    payload = _load_candidates()
    state = _state()
    if not state:
        return {
            "status": "READY_TO_PREPARE",
            "complete": False,
            "ready": False,
            "concepts": [],
            "concept_count": len(payload.get("concepts", [])),
        }

    items = [
        _public_item(item, state)
        for item in payload.get("concepts", [])
        if isinstance(item, dict)
    ]
    pending = sum(item["decision"] == "PENDING" for item in items)
    accepted = sum(item["decision"] == "ACCEPT" for item in items)
    rejected = sum(item["decision"] == "REJECT" for item in items)
    complete = bool(items) and pending == 0
    ready = complete and accepted == len(items) and rejected == 0

    return {
        "status": (
            "TITLE_DIRECTION_SELECTED"
            if ready
            else "TITLE_DIRECTION_REJECTED"
            if complete and rejected
            else "AWAITING_HUMAN_TITLE_DIRECTION"
        ),
        "complete": complete,
        "ready": ready,
        "reviewer": state.get("reviewer", DEFAULT_REVIEWER),
        "concept_count": len(items),
        "pending": pending,
        "accepted": accepted,
        "rejected": rejected,
        "concepts": items,
    }


def _archive_selection(payload: dict[str, Any]) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    concept_id = safe_slug(str(payload.get("concept_id") or "unknown"))
    stamp = str(payload.get("reviewed_at") or "").replace(":", "-")
    destination = HISTORY_DIR / f"{concept_id}.{stamp}.title_direction_selection.json"
    atomic_write_json(destination, payload)


def _finalize_if_complete() -> None:
    state = _state()
    if not state:
        return
    candidates = _load_candidates()
    items = {
        str(item.get("concept_id") or ""): item
        for item in candidates.get("concepts", [])
        if isinstance(item, dict)
    }
    decisions = state.get("decisions", {})
    if not items or set(decisions) != set(items):
        return

    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for concept_id in sorted(items):
        decision = decisions[concept_id]
        record = {
            "artifact": "selected_title_direction",
            "schema_version": "1.0",
            "concept_id": concept_id,
            "decision": decision.get("decision"),
            "selected_titles": decision.get("selected_titles", {}),
            "note": decision.get("note", ""),
            "reviewer": state.get("reviewer", DEFAULT_REVIEWER),
            "reviewed_at": decision.get("reviewed_at"),
            "direction_contract": (
                "PREFERRED_TITLE_AND_PSYCHOLOGICAL_DIRECTION_NOT_FINAL_WORDING"
            ),
            "final_wording_editable_later": True,
            "provenance": {
                "title_direction_candidates": str(CANDIDATES_FILE.resolve()),
                "title_direction_candidates_sha256": candidates_hash(),
                "concept_fingerprint": decision.get("concept_fingerprint"),
            },
        }
        _archive_selection(record)
        if decision.get("decision") == "ACCEPT":
            selected.append(record)
        else:
            rejected.append(record)

    artifact = {
        "artifact": "selected_title_directions",
        "schema_version": "1.0",
        "status": (
            "TITLE_DIRECTION_SELECTED"
            if selected and not rejected and len(selected) == len(items)
            else "TITLE_DIRECTION_REJECTED"
        ),
        "count": len(selected),
        "selected": selected,
        "rejected": rejected,
    }
    atomic_write_json(APPROVED_FILE, artifact)
    atomic_write_json(
        SUMMARY_FILE,
        {
            "status": artifact["status"],
            "selected": len(selected),
            "rejected": len(rejected),
        },
    )


def _request_for_item(item: dict[str, Any]) -> Path:
    request_value = str(item.get("request_file") or "")
    path = Path(request_value).resolve()
    if (
        not request_value
        or not path.is_file()
        or path.parent.resolve() != REQUESTS_DIR.resolve()
    ):
        raise ValueError("Current title direction request is missing")
    if item.get("request_sha256") != sha256_file(path):
        raise ValueError("STALE_TITLE_DIRECTION_REQUEST")
    return path


def _apply_rework(item: dict[str, Any], note: str) -> None:
    request_path = _request_for_item(item)
    request = load_json(request_path)
    request["human_rework_iteration"] = int(
        request.get("human_rework_iteration") or 0
    ) + 1
    request["human_rework_note"] = note
    request["human_rework_scope"] = "TITLE_DIRECTIONS_ONLY"
    atomic_write_json(request_path, request)

    response_path = RESPONSES_DIR / (
        f"{safe_slug(str(item.get('concept_id') or ''))}.title_direction_response.json"
    )
    if response_path.exists():
        response_path.unlink()
    if CANDIDATES_FILE.exists():
        CANDIDATES_FILE.unlink()
    # The previous active selection is no longer current after an explicit
    # rework request. Historical copies remain under HISTORY_DIR.
    if APPROVED_FILE.exists():
        APPROVED_FILE.unlink()
    if SUMMARY_FILE.exists():
        SUMMARY_FILE.unlink()


def apply_action(
    *,
    concept_id: str,
    decision: str,
    selected_titles: Any = None,
    note: str = "",
) -> dict[str, Any]:
    state = _state()
    if not state:
        raise ValueError("Title Direction Gate is not prepared or is stale")
    value = str(decision or "").strip().upper()
    if value not in {"ACCEPT", "REWORK", "REJECT"}:
        raise ValueError("Decision must be ACCEPT, REWORK, or REJECT")

    payload = _load_candidates()
    item = next(
        (
            x for x in payload.get("concepts", [])
            if isinstance(x, dict)
            and str(x.get("concept_id") or "") == str(concept_id or "")
        ),
        None,
    )
    if not isinstance(item, dict):
        raise ValueError("Unknown title-direction concept_id")

    clean_note = str(note or "").strip()
    existing = state.get("decisions", {}).get(str(concept_id))
    if isinstance(existing, dict) and existing.get("decision") in {
        "ACCEPT",
        "REJECT",
    }:
        if existing.get("decision") != value:
            raise ValueError(
                "Title direction decision is already finalized; request REWORK "
                "before changing the decision"
            )
        if value == "REJECT":
            return snapshot()
        normalized_duplicate = {
            fmt: _normalize_selection(item, fmt, (selected_titles or {}).get(fmt))
            for fmt in ("short", "long_form")
        }
        if (
            normalized_duplicate == existing.get("selected_titles", {})
            and clean_note == str(existing.get("note") or "")
        ):
            return snapshot()
        raise ValueError(
            "Conflicting duplicate Title Direction submission; request REWORK "
            "before changing an accepted selection"
        )

    if value == "REWORK":
        if not clean_note:
            raise ValueError("REWORK requires an authoritative human note")
        state.setdefault("decisions", {}).pop(str(concept_id), None)
        atomic_write_json(STATE_FILE, state)
        _apply_rework(item, clean_note)
        return {
            "status": "TITLE_DIRECTION_REWORK_REQUESTED",
            "complete": False,
            "ready": False,
            "concepts": [],
        }

    selection_payload: dict[str, Any] = {}
    if value == "ACCEPT":
        if not isinstance(selected_titles, dict):
            raise ValueError("ACCEPT requires Short and Long-form title selections")
        selection_payload = {
            fmt: _normalize_selection(item, fmt, selected_titles.get(fmt))
            for fmt in ("short", "long_form")
        }

    state.setdefault("decisions", {})[str(concept_id)] = {
        "concept_id": str(concept_id),
        "decision": value,
        "selected_titles": selection_payload,
        "note": clean_note,
        "concept_fingerprint": concept_fingerprint(item),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_json(STATE_FILE, state)
    _finalize_if_complete()
    return snapshot()


def main() -> None:
    parser = argparse.ArgumentParser(description="Human Title Direction Gate")
    parser.add_argument("--mode", choices=("prepare", "status"), required=True)
    args = parser.parse_args()
    payload = prepare_state() if args.mode == "prepare" else snapshot()
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
