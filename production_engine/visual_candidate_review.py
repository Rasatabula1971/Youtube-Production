"""Human candidate review gate for storyboard visual search results."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json, safe_slug, sha256_file
from visual_search import shot_fingerprint

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
RESULT_DIR = OUTPUT / "visual_search_results"
STORYBOARD_DIR = OUTPUT / "storyboards"
REVIEW_DIR = OUTPUT / "visual_candidate_reviews"


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
    result: dict[str, Any],
    shot: dict[str, Any],
) -> dict[str, Any]:
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
    result: dict[str, Any],
    shot: dict[str, Any],
    decision: dict[str, Any],
) -> bool:
    try:
        card = _assert_result_shot_current(result, shot)
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
            and _decision_is_current(result, shots[shot_id], decision)
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
    packets: list[dict[str, Any]] = []
    stale_total = 0
    paths = (
        sorted(RESULT_DIR.glob("*.visual_search_results.json"))
        if RESULT_DIR.exists()
        else []
    )
    for result_path in paths:
        result = load_json(result_path)
        review_path = _review_path(result_path)
        review = (
            load_json(review_path)
            if review_path.exists()
            else {"decisions": {}}
        )
        review, changed = _reconcile_review(result_path, result, review)
        if changed and review_path.exists():
            atomic_write_json(review_path, review)

        shots = []
        stale_shot_ids: list[str] = []
        for shot in result.get("shots", []):
            if not isinstance(shot, dict):
                continue
            try:
                _assert_result_shot_current(result, shot)
                current = True
            except ValueError:
                current = False
                stale_shot_ids.append(str(shot.get("shot_id") or ""))
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
    return {
        "status": (
            "VISUAL_SEARCH_STALE"
            if stale_total
            else "READY_FOR_VISUAL_CANDIDATE_REVIEW"
            if packets
            else "WAITING_FOR_VISUAL_SEARCH_RESULTS"
        ),
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
    card = _assert_result_shot_current(result, shot)

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
        if candidate.get("state") == "BLOCKED":
            raise ValueError("Blocked candidate cannot be selected")
        decision_status = (
            "SELECTED_PENDING_RIGHTS_CONTEXT_GATE"
            if candidate.get("state") == "HUMAN_REVIEW_REQUIRED"
            else "SELECTED"
        )
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
        "candidate_source_tier": (
            candidate.get("source_tier") if candidate else None
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
