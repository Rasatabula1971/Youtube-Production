"""Deterministic storyboard and cinematic shot specification layer.

Turns narration timing + visual requirements into search-first storyboard cards.
Premium generation is only recommended for high-value gaps; this module never
calls an image/video provider or authorizes spend.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"
TIMING_DIR = OUTPUT_DIR / "narration_timing_maps"
VISUAL_DIR = OUTPUT_DIR / "visual_manifests"
STORYBOARD_DIR = OUTPUT_DIR / "storyboards"
SUMMARY_FILE = OUTPUT_DIR / "storyboard_summary.json"

EXCITING_PURPOSES = {"hook", "reveal", "payoff", "climax", "transformation", "stakes", "conflict"}


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _score(purpose: str, has_asset: bool, index: int, total: int) -> dict[str, int]:
    p = purpose.lower()
    story = 5 if p in EXCITING_PURPOSES else 3
    emotional = 5 if p in {"hook", "stakes", "conflict", "climax", "payoff"} else 3
    uniqueness = 4 if p in {"transformation", "reveal", "climax"} else 2
    sourcing_gap = 0 if has_asset else 5
    opening_bonus = 2 if index == 0 else 0
    total_score = story + emotional + uniqueness + sourcing_gap + opening_bonus
    return {"story_importance": story, "emotional_intensity": emotional, "uniqueness": uniqueness, "sourcing_gap": sourcing_gap, "opening_bonus": opening_bonus, "total": total_score}


def _cinematic_spec(purpose: str, score: int) -> dict[str, Any]:
    p = purpose.lower()
    if p in {"hook", "stakes", "conflict"}:
        angle, framing, movement, lens = "low_or_eye_level", "close_up_to_medium", "controlled_push_in", "35mm"
        lighting = "directional_high_contrast"
    elif p in {"reveal", "payoff", "climax", "transformation"}:
        angle, framing, movement, lens = "dynamic_reveal_angle", "detail_to_wide_reveal", "pull_back_or_orbit", "24-35mm"
        lighting = "cinematic_subject_separation"
    else:
        angle, framing, movement, lens = "natural_eye_level", "medium_or_wide", "static_or_slow_tracking", "35-50mm"
        lighting = "naturalistic"
    return {
        "camera_angle": angle,
        "framing": framing,
        "camera_movement": movement,
        "lens_feel": lens,
        "lighting": lighting,
        "depth_of_field": "shallow_when_subject_isolation_helps",
        "motion_speed": "normal_with_slow_motion_only_on_meaningful_impact",
        "transition": "cut_on_narration_or_action",
        "premium_prompt_detail_required": score >= 17,
    }


def build_storyboard(timing: dict[str, Any], visual: dict[str, Any], timing_path: Path, visual_path: Path) -> dict[str, Any]:
    if timing.get("status") != "READY_FOR_ROUGH_CUT":
        raise ValueError("Narration timing map is not ready")
    if (timing.get("concept_id"), timing.get("format")) != (visual.get("concept_id"), visual.get("format")):
        raise ValueError("Storyboard inputs do not identify the same branch")
    requirements = visual.get("requirements", [])
    segments = timing.get("segments", [])
    if not isinstance(requirements, list) or not isinstance(segments, list) or not segments:
        raise ValueError("Storyboard inputs require visual requirements and timing segments")
    reqs = {
        str(item.get("beat_id") or ""): item
        for item in requirements
        if isinstance(item, dict)
    }
    segment_ids = [
        str(item.get("segment_id") or "")
        for item in segments
        if isinstance(item, dict)
    ]
    if (
        len(segment_ids) != len(segments)
        or any(not item for item in segment_ids)
        or len(set(segment_ids)) != len(segment_ids)
        or set(segment_ids) != set(reqs)
    ):
        raise ValueError(
            "Narration timing segments must exactly match visual requirement beat IDs"
        )
    cards: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        beat_id = str(segment.get("segment_id") or "")
        req = reqs.get(beat_id, {})
        routing = req.get("routing", {}) if isinstance(req, dict) else {}
        selected = routing.get("selected_candidate_id") if isinstance(routing, dict) else None
        purpose = str(req.get("narrative_purpose") or "supporting_explanation")
        score = _score(purpose, bool(selected), index, len(segments))
        premium_candidate = not selected and score["total"] >= 17
        treatment = str(req.get("visual_treatment") or "")
        cards.append({
            "shot_id": f"shot-{index + 1:03d}",
            "beat_id": beat_id,
            "time_range": {"start_seconds": segment.get("audio_start_seconds"), "end_seconds": segment.get("audio_end_seconds")},
            "story_purpose": purpose,
            "desired_visual": treatment,
            "search_terms": [term for term in [treatment, purpose] if term],
            "source_strategy": {
                "search_existing_first": True,
                "selected_candidate_id": selected,
                "creator_excerpt_allowed_only_after_human_rights_context_review": True,
                "premium_generation_is_last_resort": True,
            },
            "visual_value_score": score,
            "cinematic_direction": _cinematic_spec(purpose, score["total"]),
            "premium_generation_candidate": premium_candidate,
            "premium_generation_authorized": False,
            "premium_reason": "HIGH_VALUE_UNFILLED_VISUAL_GAP" if premium_candidate else None,
        })
    return {
        "artifact": "production_storyboard",
        "concept_id": timing.get("concept_id"),
        "format": timing.get("format"),
        "status": "READY_FOR_VISUAL_SEARCH",
        "premium_generation_authorized": False,
        "cards": cards,
        "summary": {
            "shots": len(cards),
            "existing_assets": sum(bool(c["source_strategy"]["selected_candidate_id"]) for c in cards),
            "premium_candidates": sum(c["premium_generation_candidate"] for c in cards),
        },
        "policy": {
            "storyboard_before_asset_search": True,
            "existing_and_reusable_visuals_preferred": True,
            "creator_excerpts_require_human_rights_context_review": True,
            "premium_generation_only_for_justified_gaps": True,
            "no_fixed_premium_shot_quota": True,
        },
        "provenance": {
            "narration_timing_map": str(timing_path.resolve()),
            "narration_timing_map_sha256": sha256_file(timing_path),
            "visual_manifest": str(visual_path.resolve()),
            "visual_manifest_sha256": sha256_file(visual_path),
        },
    }


def _load_dict(path: Path) -> dict[str, Any] | None:
    try:
        value = load_json(path)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def storyboard_is_current(
    board_path: Path,
) -> tuple[dict[str, Any], Path, Path] | None:
    board = _load_dict(board_path)
    if not isinstance(board, dict) or board.get("status") != "READY_FOR_VISUAL_SEARCH":
        return None
    provenance = board.get("provenance", {})
    if not isinstance(provenance, dict):
        return None
    timing_path = Path(str(provenance.get("narration_timing_map") or ""))
    visual_path = Path(str(provenance.get("visual_manifest") or ""))
    if not timing_path.is_file() or not visual_path.is_file():
        return None
    if (
        provenance.get("narration_timing_map_sha256") != sha256_file(timing_path)
        or provenance.get("visual_manifest_sha256") != sha256_file(visual_path)
    ):
        return None
    timing = _load_dict(timing_path)
    visual = _load_dict(visual_path)
    if not isinstance(timing, dict) or not isinstance(visual, dict):
        return None
    if timing.get("status") != "READY_FOR_ROUGH_CUT":
        return None
    visual_provenance = visual.get("manifest_provenance", {})
    if (
        not isinstance(visual_provenance, dict)
        or visual_provenance.get("narration_timing_map_sha256")
        != sha256_file(timing_path)
    ):
        return None
    identity = (
        str(board.get("concept_id") or ""),
        str(board.get("format") or ""),
    )
    if identity != (
        str(timing.get("concept_id") or ""),
        str(timing.get("format") or ""),
    ) or identity != (
        str(visual.get("concept_id") or ""),
        str(visual.get("format") or ""),
    ):
        return None
    return board, timing_path, visual_path


def snapshot() -> dict[str, Any]:
    paths = (
        sorted(STORYBOARD_DIR.glob("*.storyboard.json"))
        if STORYBOARD_DIR.exists()
        else []
    )
    items: list[dict[str, Any]] = []
    stale = 0
    for path in paths:
        state = storyboard_is_current(path)
        if state is None:
            stale += 1
            continue
        board, _timing, _visual = state
        items.append(
            {
                "concept_id": board.get("concept_id"),
                "format": board.get("format"),
                "storyboard": str(path),
                **board.get("summary", {}),
            }
        )
    return {
        "status": (
            "READY_FOR_VISUAL_SEARCH"
            if items and stale == 0
            else "STALE_STORYBOARDS"
            if stale
            else "WAITING_FOR_AUDIO_AND_VISUAL_MANIFESTS"
        ),
        "prepared": len(items),
        "stale": stale,
        "items": items,
        "premium_generation_authorized": False,
    }


def prepare() -> dict[str, Any]:
    STORYBOARD_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    current: set[Path] = set()
    timing_paths = (
        sorted(TIMING_DIR.glob("*.narration_timing_map.json"))
        if TIMING_DIR.exists()
        else []
    )
    for timing_path in timing_paths:
        timing = _load_dict(timing_path)
        if not isinstance(timing, dict):
            continue
        key = _key(
            str(timing.get("concept_id") or ""),
            str(timing.get("format") or ""),
        )
        visual_path = VISUAL_DIR / f"{key}.visual_manifest.json"
        visual = _load_dict(visual_path)
        if not isinstance(visual, dict):
            continue
        provenance = visual.get("manifest_provenance", {})
        if (
            not isinstance(provenance, dict)
            or provenance.get("narration_timing_map_sha256")
            != sha256_file(timing_path)
        ):
            continue
        board = build_storyboard(
            timing,
            visual,
            timing_path,
            visual_path,
        )
        path = STORYBOARD_DIR / f"{key}.storyboard.json"
        atomic_write_json(path, board)
        current.add(path.resolve())
        items.append(
            {
                "concept_id": board["concept_id"],
                "format": board["format"],
                "storyboard": str(path),
                **board["summary"],
            }
        )

    for stale in STORYBOARD_DIR.glob("*.storyboard.json"):
        if stale.resolve() not in current:
            stale.unlink()

    summary = snapshot()
    atomic_write_json(SUMMARY_FILE, summary)
    return summary

def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare production storyboards")
    parser.add_argument("--mode", choices=("prepare",), required=True)
    parser.parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
