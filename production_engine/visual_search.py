"""Storyboard-driven visual search contract and candidate normalizer.

Provider adapters write raw candidate result files; this module normalizes them
into a rights-aware search packet. It does not scrape, download, or approve
third-party footage, and it never calls paid generation providers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json, safe_slug, sha256_file
from storyboard import storyboard_is_current

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"
STORYBOARD_DIR = OUTPUT_DIR / "storyboards"
RAW_DIR = OUTPUT_DIR / "visual_search_raw"
RESULT_DIR = OUTPUT_DIR / "visual_search_results"
SUMMARY_FILE = OUTPUT_DIR / "visual_search_summary.json"

SOURCE_PRIORITY = [
    "OWN_LIBRARY",
    "FREE_COMMERCIAL_LICENSE",
    "PUBLIC_DOMAIN",
    "CREATIVE_COMMONS_ALLOWED",
    "EDITORIAL_EXCERPT",
]
AUTO_ELIGIBLE = {
    "OWN_LIBRARY",
    "FREE_COMMERCIAL_LICENSE",
    "PUBLIC_DOMAIN",
    "CREATIVE_COMMONS_ALLOWED",
}


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def shot_fingerprint(card: dict[str, Any]) -> str:
    encoded = json.dumps(
        card,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def request_fingerprint(request: dict[str, Any]) -> str:
    encoded = json.dumps(
        request,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def raw_matches_request(
    request: dict[str, Any],
    raw: dict[str, Any],
) -> bool:
    if (
        str(raw.get("concept_id") or "")
        != str(request.get("concept_id") or "")
        or str(raw.get("format") or "")
        != str(request.get("format") or "")
        or raw.get("search_request_fingerprint")
        not in {None, request_fingerprint(request)}
    ):
        return False
    fingerprints = raw.get("shot_fingerprints", {})
    if not isinstance(fingerprints, dict):
        return False
    for shot in request.get("shots", []):
        if not isinstance(shot, dict):
            continue
        shot_id = str(shot.get("shot_id") or "")
        if (
            not shot_id
            or fingerprints.get(shot_id) != shot.get("shot_fingerprint")
        ):
            return False
    return True


def build_search_request(board: dict[str, Any], board_path: Path) -> dict[str, Any]:
    if board.get("status") != "READY_FOR_VISUAL_SEARCH":
        raise ValueError("Storyboard is not ready for visual search")
    shots = []
    for card in board.get("cards", []):
        if not isinstance(card, dict):
            continue
        strategy = card.get("source_strategy", {})
        if strategy.get("selected_candidate_id"):
            continue
        shots.append({
            "shot_id": card.get("shot_id"),
            "creative_version": int(card.get("creative_version") or 1),
            "beat_id": card.get("beat_id"),
            "time_range": card.get("time_range"),
            "desired_visual": card.get("desired_visual"),
            "search_terms": card.get("search_terms", []),
            "cinematic_direction": card.get("cinematic_direction", {}),
            "creative_instruction": card.get("creative_instruction"),
            "source_priority": SOURCE_PRIORITY,
            "max_candidates_per_source": 5,
            "creator_search_allowed": bool(strategy.get("creator_excerpt_allowed_only_after_human_rights_context_review")),
            "premium_generation_candidate": bool(card.get("premium_generation_candidate")),
            "shot_fingerprint": shot_fingerprint(card),
        })
    return {
        "artifact": "visual_search_request",
        "concept_id": board.get("concept_id"),
        "format": board.get("format"),
        "status": "SEARCH_REQUIRED" if shots else "NO_SEARCH_REQUIRED",
        "shots": shots,
        "policy": {
            "search_existing_before_generation": True,
            "download_does_not_equal_reuse_permission": True,
            "creator_excerpts_never_auto_approved": True,
            "unknown_rights_never_auto_approved": True,
            "paid_generation_calls_allowed": False,
        },
        "provenance": {"storyboard": str(board_path.resolve()), "storyboard_sha256": sha256_file(board_path)},
    }


def normalize_candidate(raw: dict[str, Any], shot_id: str) -> dict[str, Any]:
    tier = str(raw.get("source_tier") or "UNKNOWN").upper()
    rights = str(raw.get("rights_status") or "UNKNOWN").upper()
    commercial = raw.get("commercial_use_allowed")
    url = str(raw.get("source_url") or "").strip()
    local = str(raw.get("local_path") or "").strip()
    asset_url = str(
        raw.get("asset_url") or raw.get("preview_media_url") or ""
    ).strip()
    creator = str(raw.get("creator") or "").strip() or None
    licence = str(raw.get("license") or "").strip() or None
    if tier == "EDITORIAL_EXCERPT":
        state, reason = "HUMAN_REVIEW_REQUIRED", "CREATOR_EXCERPT_RIGHTS_CONTEXT_REVIEW"
    elif tier not in AUTO_ELIGIBLE:
        state, reason = "BLOCKED", "UNKNOWN_OR_UNSUPPORTED_RIGHTS_TIER"
    elif rights != "VERIFIED":
        state, reason = "BLOCKED", "RIGHTS_NOT_VERIFIED"
    elif commercial is not True:
        state, reason = "BLOCKED", "COMMERCIAL_USE_NOT_VERIFIED"
    elif not (url or local):
        state, reason = "BLOCKED", "MISSING_PROVENANCE"
    else:
        state, reason = "ELIGIBLE", "VERIFIED_REUSE_RIGHTS"
    return {
        "candidate_id": str(raw.get("candidate_id") or f"{shot_id}-candidate"),
        "shot_id": shot_id,
        "title": raw.get("title"),
        "media_type": raw.get("media_type"),
        "source_tier": tier,
        "source_url": url or None,
        "asset_url": asset_url or None,
        "local_path": local or None,
        "creator": creator,
        "license": licence,
        "rights_status": rights,
        "commercial_use_allowed": commercial,
        "duration_seconds": raw.get("duration_seconds"),
        "thumbnail_url": raw.get("thumbnail_url"),
        "search_provider": raw.get("search_provider"),
        "state": state,
        "reason": reason,
        "estimated_cost_usd": float(raw.get("estimated_cost_usd") or 0.0),
    }


def compile_results(request: dict[str, Any], request_path: Path, raw: dict[str, Any]) -> dict[str, Any]:
    raw_by_shot = raw.get("shots", {}) if isinstance(raw, dict) else {}
    results = []
    for shot in request.get("shots", []):
        shot_id = str(shot.get("shot_id") or "")
        entries = raw_by_shot.get(shot_id, []) if isinstance(raw_by_shot, dict) else []
        candidates = [normalize_candidate(x, shot_id) for x in entries if isinstance(x, dict)]
        priority = {tier: i for i, tier in enumerate(SOURCE_PRIORITY)}
        candidates.sort(key=lambda x: (0 if x["state"] == "ELIGIBLE" else 1 if x["state"] == "HUMAN_REVIEW_REQUIRED" else 2, priority.get(x["source_tier"], 99), x["estimated_cost_usd"]))
        shot_errors = (
            raw.get("provider_errors", {}).get(shot_id, [])
            if isinstance(raw, dict)
            and isinstance(raw.get("provider_errors"), dict)
            else []
        )
        results.append({
            "shot_id": shot_id,
            "creative_version": int(shot.get("creative_version") or 1),
            "shot_fingerprint": shot.get("shot_fingerprint"),
            "candidates": candidates,
            "eligible": sum(x["state"] == "ELIGIBLE" for x in candidates),
            "human_review_required": sum(x["state"] == "HUMAN_REVIEW_REQUIRED" for x in candidates),
            "search_gap": not any(x["state"] in {"ELIGIBLE", "HUMAN_REVIEW_REQUIRED"} for x in candidates),
            "provider_errors": shot_errors if isinstance(shot_errors, list) else [],
            "premium_generation_candidate": bool(shot.get("premium_generation_candidate")),
        })
    return {
        "artifact": "visual_search_results",
        "concept_id": request.get("concept_id"),
        "format": request.get("format"),
        "status": "READY_FOR_CANDIDATE_REVIEW",
        "shots": results,
        "premium_generation_authorized": False,
        "provenance": {"search_request": str(request_path.resolve()), "search_request_sha256": sha256_file(request_path)},
    }


def _load_dict(path: Path) -> dict[str, Any] | None:
    try:
        value = load_json(path)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def search_request_is_current(
    request_path: Path,
) -> tuple[dict[str, Any], Path] | None:
    request = _load_dict(request_path)
    if not isinstance(request, dict):
        return None
    provenance = request.get("provenance", {})
    if not isinstance(provenance, dict):
        return None
    board_path = Path(str(provenance.get("storyboard") or ""))
    if (
        not board_path.is_file()
        or provenance.get("storyboard_sha256") != sha256_file(board_path)
        or storyboard_is_current(board_path) is None
    ):
        return None
    board = _load_dict(board_path)
    if not isinstance(board, dict):
        return None
    if (
        str(request.get("concept_id") or "")
        != str(board.get("concept_id") or "")
        or str(request.get("format") or "")
        != str(board.get("format") or "")
    ):
        return None
    expected = build_search_request(board, board_path)
    if request != expected:
        return None
    return request, board_path


def snapshot() -> dict[str, Any]:
    current_boards = []
    if STORYBOARD_DIR.exists():
        for board_path in sorted(STORYBOARD_DIR.glob("*.storyboard.json")):
            state = storyboard_is_current(board_path)
            if state is not None:
                current_boards.append(board_path)

    items: list[dict[str, Any]] = []
    current_requests = 0
    search_required = 0
    for board_path in current_boards:
        board = _load_dict(board_path)
        if not isinstance(board, dict):
            continue
        key = _key(
            str(board.get("concept_id") or ""),
            str(board.get("format") or ""),
        )
        request_path = RESULT_DIR / f"{key}.visual_search_request.json"
        state = search_request_is_current(request_path)
        is_current = state is not None
        if state is not None:
            current_requests += 1
            request = state[0]
            if request.get("status") == "SEARCH_REQUIRED":
                search_required += 1
        items.append(
            {
                "concept_id": board.get("concept_id"),
                "format": board.get("format"),
                "request": str(request_path),
                "current": is_current,
            }
        )

    ready = bool(current_boards) and current_requests == len(current_boards)
    return {
        "status": (
            "READY_FOR_SEARCH_ADAPTERS"
            if ready
            else "STALE_VISUAL_SEARCH_REQUESTS"
            if current_boards
            else "WAITING_FOR_STORYBOARDS"
        ),
        "prepared": current_requests,
        "expected": len(current_boards),
        "search_required": search_required,
        "items": items,
        "paid_generation_calls_allowed": False,
    }


def search_result_is_current(
    result_path: Path,
) -> tuple[dict[str, Any], Path, dict[str, Any]] | None:
    result = _load_dict(result_path)
    if not isinstance(result, dict):
        return None
    provenance = result.get("provenance", {})
    if not isinstance(provenance, dict):
        return None
    request_path = Path(str(provenance.get("search_request") or ""))
    if (
        not request_path.is_file()
        or request_path.parent.resolve() != RESULT_DIR.resolve()
        or provenance.get("search_request_sha256") != sha256_file(request_path)
    ):
        return None
    request_state = search_request_is_current(request_path)
    if request_state is None:
        return None
    request = request_state[0]
    if (
        str(result.get("concept_id") or "")
        != str(request.get("concept_id") or "")
        or str(result.get("format") or "")
        != str(request.get("format") or "")
        or result.get("status") != "READY_FOR_CANDIDATE_REVIEW"
    ):
        return None

    result_shots = result.get("shots", [])
    request_shots = request.get("shots", [])
    if not isinstance(result_shots, list) or not isinstance(request_shots, list):
        return None
    expected = {
        str(item.get("shot_id") or ""): str(
            item.get("shot_fingerprint") or ""
        )
        for item in request_shots
        if isinstance(item, dict)
    }
    actual = {
        str(item.get("shot_id") or ""): str(
            item.get("shot_fingerprint") or ""
        )
        for item in result_shots
        if isinstance(item, dict)
    }
    if not expected or expected != actual:
        return None
    return result, request_path, request


def prepare() -> dict[str, Any]:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    prepared = []
    current_request_paths: set[Path] = set()
    current_result_paths: set[Path] = set()

    board_paths = (
        sorted(STORYBOARD_DIR.glob("*.storyboard.json"))
        if STORYBOARD_DIR.exists()
        else []
    )
    for board_path in board_paths:
        if storyboard_is_current(board_path) is None:
            continue
        board = _load_dict(board_path)
        if not isinstance(board, dict):
            continue
        request = build_search_request(board, board_path)
        key = _key(
            str(board.get("concept_id") or ""),
            str(board.get("format") or ""),
        )
        request_path = RESULT_DIR / f"{key}.visual_search_request.json"
        atomic_write_json(request_path, request)
        current_request_paths.add(request_path.resolve())

        raw_path = RAW_DIR / f"{key}.visual_search_raw.json"
        result_path = RESULT_DIR / f"{key}.visual_search_results.json"
        raw_current = False
        if raw_path.exists():
            raw = _load_dict(raw_path)
            raw_current = isinstance(raw, dict) and raw_matches_request(
                request,
                raw,
            )
            if raw_current and isinstance(raw, dict):
                result = compile_results(request, request_path, raw)
                atomic_write_json(result_path, result)
                current_result_paths.add(result_path.resolve())
            elif result_path.exists():
                result_path.unlink()

        prepared.append(
            {
                "concept_id": board.get("concept_id"),
                "format": board.get("format"),
                "request": str(request_path),
                "raw_results_present": raw_path.exists(),
                "raw_results_current": raw_current,
            }
        )

    for stale in RESULT_DIR.glob("*.visual_search_request.json"):
        if stale.resolve() not in current_request_paths:
            stale.unlink()
    for stale in RESULT_DIR.glob("*.visual_search_results.json"):
        if stale.resolve() not in current_result_paths:
            stale.unlink()

    summary = snapshot()
    atomic_write_json(SUMMARY_FILE, summary)
    return summary

def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare storyboard-driven visual search")
    parser.add_argument("--mode", choices=("prepare",), required=True)
    parser.parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
