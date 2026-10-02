"""Human candidate review gate for storyboard visual search results."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json, safe_slug, sha256_file
from visual_search import (
    search_request_is_current,
    search_result_is_current,
    shot_fingerprint,
)

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
RESULT_DIR = OUTPUT / "visual_search_results"
STORYBOARD_DIR = OUTPUT / "storyboards"
REVIEW_DIR = OUTPUT / "visual_candidate_reviews"

AUTO_REUSE_TIERS = {
    "OWN_LIBRARY",
    "FREE_COMMERCIAL_LICENSE",
    "PUBLIC_DOMAIN",
    "CREATIVE_COMMONS_ALLOWED",
}
RIGHTS_CONTEXT_TIERS = {
    "EDITORIAL_EXCERPT",
    "CREATOR_EDITORIAL",
}


def candidate_selection_status(candidate: dict[str, Any]) -> str:
    if not isinstance(candidate, dict):
        raise ValueError("Visual candidate must be an object")

    state = str(candidate.get("state") or "").upper()
    tier = str(candidate.get("source_tier") or "UNKNOWN").upper()
    rights = str(candidate.get("rights_status") or "UNKNOWN").upper()
    commercial = candidate.get("commercial_use_allowed")
    has_source = bool(
        str(candidate.get("source_url") or "").strip()
        or str(candidate.get("local_path") or "").strip()
    )

    requires_context = bool(
        tier in RIGHTS_CONTEXT_TIERS
        or rights == "DISCOVERY_ONLY"
        or candidate.get("human_review_required") is True
        or state == "HUMAN_REVIEW_REQUIRED"
    )
    if requires_context:
        if not has_source:
            raise ValueError(
                "Rights/context candidate is missing source provenance"
            )
        return "SELECTED_PENDING_RIGHTS_CONTEXT_GATE"

    if state == "BLOCKED":
        raise ValueError("Blocked candidate cannot be selected")

    if (
        tier in AUTO_REUSE_TIERS
        and rights == "VERIFIED"
        and commercial is True
        and has_source
    ):
        return "SELECTED"

    raise ValueError(
        "Candidate rights metadata is not eligible for automatic reuse"
    )


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _result_fingerprint(shot: dict[str, Any]) -> str:
    return _hash(
        json.dumps(
            shot,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )


def _review_path(result_path: Path) -> Path:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    return REVIEW_DIR / result_path.name.replace(
        ".visual_search_results.json",
        ".visual_candidate_review.json",
    )


def _storyboard_path(result: dict[str, Any]) -> Path:
    concept_id = safe_slug(str(result.get("concept_id") or ""))
    fmt = safe_slug(str(result.get("format") or ""))
    return STORYBOARD_DIR / f"{concept_id}.{fmt}.storyboard.json"


def _assert_result_current(
    result_path: Path,
    result: dict[str, Any],
) -> None:
    state = search_result_is_current(result_path)
    if state is None:
        raise ValueError(
            "STALE_VISUAL_SEARCH: search result is not bound to the current request"
        )
    current = state[0]
    if (
        str(current.get("concept_id") or "")
        != str(result.get("concept_id") or "")
        or str(current.get("format") or "")
        != str(result.get("format") or "")
    ):
        raise ValueError(
            "STALE_VISUAL_SEARCH: current result identity changed"
        )


def _current_storyboard_card(
    result: dict[str, Any],
    shot_id: str,
) -> dict[str, Any]:
    storyboard_path = _storyboard_path(result)
    if not storyboard_path.exists():
        raise ValueError("STALE_VISUAL_SEARCH: current storyboard is missing")
    board = load_json(storyboard_path)
    if (
        board.get("concept_id") != result.get("concept_id")
        or board.get("format") != result.get("format")
    ):
        raise ValueError("STALE_VISUAL_SEARCH: storyboard identity changed")
    card = next(
        (
            item
            for item in board.get("cards", [])
            if isinstance(item, dict)
            and str(item.get("shot_id") or "") == shot_id
        ),
        None,
    )
    if card is None:
        raise ValueError("STALE_VISUAL_SEARCH: storyboard shot no longer exists")
    return card


def _assert_result_shot_current(
    result_path: Path,
    result: dict[str, Any],
    shot: dict[str, Any],
) -> dict[str, Any]:
    _assert_result_current(result_path, result)
    shot_id = str(shot.get("shot_id") or "")
    card = _current_storyboard_card(result, shot_id)
    expected = str(shot.get("shot_fingerprint") or "")
    actual = shot_fingerprint(card)
    if not expected or expected != actual:
        raise ValueError(
            "STALE_VISUAL_SEARCH: storyboard shot changed; re-search is required"
        )
    return card


def _decision_is_current(
    result_path: Path,
    result: dict[str, Any],
    shot: dict[str, Any],
    decision: dict[str, Any],
) -> bool:
    try:
        card = _assert_result_shot_current(result_path, result, shot)
    except ValueError:
        return False
    return (
        decision.get("shot_fingerprint") == shot_fingerprint(card)
        and decision.get("shot_fingerprint") == shot.get("shot_fingerprint")
        and decision.get("result_fingerprint") == _result_fingerprint(shot)
    )


def _summary(
    result: dict[str, Any],
    decisions: dict[str, Any],
) -> dict[str, Any]:
    total = len(result.get("shots", []))
    decided = len(decisions)
    return {
        "shots_total": total,
        "shots_decided": decided,
        "complete": total > 0 and decided == total,
        "remaining_gaps": sum(
            isinstance(item, dict)
            and item.get("action") in {"REJECT_ALL", "NEEDS_BETTER_VISUAL"}
            for item in decisions.values()
        ),
    }


def _reconcile_review(
    result_path: Path,
    result: dict[str, Any],
    review: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    original = json.dumps(review, sort_keys=True, ensure_ascii=False)
    shots = {
        str(item.get("shot_id") or ""): item
        for item in result.get("shots", [])
        if isinstance(item, dict)
    }
    prior = review.get("decisions", {})
    if not isinstance(prior, dict):
        prior = {}
    decisions = {
        shot_id: decision
        for shot_id, decision in prior.items()
        if (
            shot_id in shots
            and isinstance(decision, dict)
            and _decision_is_current(
                result_path,
                result,
                shots[shot_id],
                decision,
            )
        )
    }
    review = {
        **review,
        "artifact": "visual_candidate_review",
        "concept_id": result.get("concept_id"),
        "format": result.get("format"),
        "source_result": str(result_path.resolve()),
        "source_result_sha256": sha256_file(result_path),
        "decisions": decisions,
    }
    review["summary"] = _summary(result, decisions)
    review["status"] = (
        "READY_FOR_ROUGH_CUT"
        if review["summary"]["complete"]
        else "REVIEW_IN_PROGRESS"
    )
    changed = original != json.dumps(review, sort_keys=True, ensure_ascii=False)
    return review, changed


def snapshot() -> dict[str, Any]:
    expected_results = 0
    current_results = 0
    packets: list[dict[str, Any]] = []
    stale_total = 0
    provider_errors_total = 0

    request_paths = (
        sorted(RESULT_DIR.glob("*.visual_search_request.json"))
        if RESULT_DIR.exists()
        else []
    )
    for request_path in request_paths:
        request_state = search_request_is_current(request_path)
        if request_state is None:
            continue
        request = request_state[0]
        if request.get("status") != "SEARCH_REQUIRED":
            continue
        expected_results += 1
        result_path = RESULT_DIR / request_path.name.replace(
            ".visual_search_request.json",
            ".visual_search_results.json",
        )
        result_state = search_result_is_current(result_path)
        if result_state is None:
            continue

        result = result_state[0]
        current_results += 1
        review_path = _review_path(result_path)
        review = (
            load_json(review_path)
            if review_path.exists()
            else {"decisions": {}}
        )
        review, changed = _reconcile_review(
            result_path,
            result,
            review,
        )
        if changed and review_path.exists():
            atomic_write_json(review_path, review)

        shots = []
        stale_shot_ids: list[str] = []
        for shot in result.get("shots", []):
            if not isinstance(shot, dict):
                continue
            try:
                _assert_result_shot_current(
                    result_path,
                    result,
                    shot,
                )
                current = True
            except ValueError:
                current = False
                stale_shot_ids.append(str(shot.get("shot_id") or ""))
            errors = shot.get("provider_errors", [])
            if isinstance(errors, list):
                provider_errors_total += len(errors)
            shots.append({**shot, "storyboard_current": current})

        stale_total += len(stale_shot_ids)
        packets.append(
            {
                "concept_id": result.get("concept_id"),
                "format": result.get("format"),
                "result_file": str(result_path),
                "result_sha256": sha256_file(result_path),
                "shots": shots,
                "decisions": review.get("decisions", {}),
                "stale_shot_ids": stale_shot_ids,
            }
        )

    ready_for_review = (
        expected_results > 0
        and current_results == expected_results
        and stale_total == 0
    )
    shots_total = sum(
        len(packet.get("shots", []))
        for packet in packets
    )
    decided_total = sum(
        len(packet.get("decisions", {}))
        for packet in packets
    )
    rights_context_required = sum(
        decision.get("status") == "SELECTED_PENDING_RIGHTS_CONTEXT_GATE"
        for packet in packets
        for decision in packet.get("decisions", {}).values()
        if isinstance(decision, dict)
    )
    complete = (
        ready_for_review
        and shots_total > 0
        and decided_total == shots_total
    )
    return {
        "status": (
            "VISUAL_SEARCH_STALE"
            if stale_total
            else "COMPLETE"
            if complete
            else "READY_FOR_VISUAL_CANDIDATE_REVIEW"
            if ready_for_review
            else "WAITING_FOR_VISUAL_SEARCH_RESULTS"
        ),
        "complete": complete,
        "ready_for_review": ready_for_review,
        "expected_results": expected_results,
        "current_results": current_results,
        "shots_total": shots_total,
        "shots_decided": decided_total,
        "rights_context_required": rights_context_required,
        "provider_errors": provider_errors_total,
        "stale_shots": stale_total,
        "packets": packets,
    }

def apply_action(
    *,
    result_file: str,
    shot_id: str,
    action: str,
    candidate_id: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    result_path = Path(result_file)
    if (
        not result_path.exists()
        or result_path.parent.resolve() != RESULT_DIR.resolve()
    ):
        raise ValueError("Invalid visual search result file")

    result = load_json(result_path)
    _assert_result_current(result_path, result)
    shot = next(
        (
            item
            for item in result.get("shots", [])
            if isinstance(item, dict)
            and str(item.get("shot_id") or "") == shot_id
        ),
        None,
    )
    if shot is None:
        raise ValueError("Unknown storyboard shot")
    card = _assert_result_shot_current(result_path, result, shot)

    actions = {"SELECT", "REJECT_ALL", "NEEDS_BETTER_VISUAL"}
    if action not in actions:
        raise ValueError("Unsupported candidate review action")

    candidate = None
    if action == "SELECT":
        candidate = next(
            (
                item
                for item in shot.get("candidates", [])
                if str(item.get("candidate_id")) == str(candidate_id)
            ),
            None,
        )
        if candidate is None:
            raise ValueError("Unknown candidate")
        decision_status = candidate_selection_status(candidate)
    else:
        decision_status = action

    review_path = _review_path(result_path)
    review = (
        load_json(review_path)
        if review_path.exists()
        else {"decisions": {}}
    )
    review, _ = _reconcile_review(result_path, result, review)
    review["decisions"][shot_id] = {
        "action": action,
        "status": decision_status,
        "candidate_id": candidate_id if action == "SELECT" else None,
        "note": note.strip(),
        "candidate_source_url": (
            candidate.get("source_url") if candidate else None
        ),
        "candidate_asset_url": (
            candidate.get("asset_url") if candidate else None
        ),
        "candidate_local_path": (
            candidate.get("local_path") if candidate else None
        ),
        "candidate_media_type": (
            candidate.get("media_type") if candidate else None
        ),
        "candidate_license": (
            candidate.get("license") if candidate else None
        ),
        "candidate_search_provider": (
            candidate.get("search_provider") if candidate else None
        ),
        "candidate_source_tier": (
            candidate.get("source_tier") if candidate else None
        ),
        "rights_route": (
            "HUMAN_RIGHTS_CONTEXT_GATE"
            if decision_status == "SELECTED_PENDING_RIGHTS_CONTEXT_GATE"
            else "AUTO_REUSE_VERIFIED"
            if decision_status == "SELECTED"
            else None
        ),
        "candidate_fingerprint": (
            _hash(
                json.dumps(
                    candidate,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            )
            if candidate
            else None
        ),
        "shot_fingerprint": shot_fingerprint(card),
        "result_fingerprint": _result_fingerprint(shot),
    }
    review["source_result_sha256"] = sha256_file(result_path)
    review["summary"] = _summary(result, review["decisions"])
    review["status"] = (
        "READY_FOR_ROUGH_CUT"
        if review["summary"]["complete"]
        else "REVIEW_IN_PROGRESS"
    )
    atomic_write_json(review_path, review)
    return review
