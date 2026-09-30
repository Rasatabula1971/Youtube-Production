"""Build a zero/low-cost visual rough-cut timeline before premium generation.

Consumes narration timing maps and visual acquisition manifests. It never calls
a paid visual provider. Selected verified free/owned assets are used when
available; otherwise the timeline carries explicit placeholders for human review.
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
ROUGH_DIR = OUTPUT_DIR / "visual_rough_cuts"
SUMMARY_FILE = OUTPUT_DIR / "visual_rough_cut_summary.json"


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def build_rough_cut(timing: dict[str, Any], visual: dict[str, Any], timing_path: Path, visual_path: Path) -> dict[str, Any]:
    if timing.get("status") != "READY_FOR_ROUGH_CUT":
        raise ValueError("Narration timing map is not ready for rough cut")
    if timing.get("concept_id") != visual.get("concept_id") or timing.get("format") != visual.get("format"):
        raise ValueError("Timing map and visual manifest identity mismatch")

    requirements = {str(item.get("beat_id")): item for item in visual.get("requirements", []) if isinstance(item, dict)}
    scenes = []
    for index, segment in enumerate(timing.get("segments", [])):
        segment_id = str(segment.get("segment_id") or "")
        requirement = requirements.get(segment_id)
        if requirement is None:
            # Format/voice beat IDs should normally align. Preserve a visible
            # placeholder rather than inventing or purchasing a visual.
            assignment = {"status": "PLACEHOLDER", "reason": "NO_MATCHING_VISUAL_REQUIREMENT", "candidate_id": None}
            purpose = None
            treatment = None
        else:
            routing = requirement.get("routing", {})
            selected = routing.get("selected_candidate_id") if isinstance(routing, dict) else None
            assignment = {
                "status": "FREE_OR_VERIFIED_ASSET" if selected else "PLACEHOLDER",
                "reason": routing.get("reason") if isinstance(routing, dict) else "ACQUISITION_REQUIRED",
                "candidate_id": selected,
            }
            purpose = requirement.get("narrative_purpose")
            treatment = requirement.get("visual_treatment")
        scenes.append({
            "scene_index": index,
            "segment_id": segment_id,
            "start_seconds": segment.get("audio_start_seconds"),
            "end_seconds": segment.get("audio_end_seconds"),
            "timeline_end_seconds": segment.get("timeline_end_seconds"),
            "narrative_purpose": purpose,
            "visual_treatment": treatment,
            "visual_assignment": assignment,
        })

    placeholders = sum(scene["visual_assignment"]["status"] == "PLACEHOLDER" for scene in scenes)
    return {
        "artifact": "visual_rough_cut_manifest",
        "concept_id": timing.get("concept_id"),
        "format": timing.get("format"),
        "status": "READY_FOR_HUMAN_ROUGH_CUT_GATE",
        "premium_generation_allowed": False,
        "timeline_duration_seconds": timing.get("total_duration_seconds"),
        "scenes": scenes,
        "summary": {"scenes": len(scenes), "placeholders": placeholders},
        "gate_policy": {
            "human_review_required_before_premium_visual_generation": True,
            "rough_cut_may_contain_placeholders": True,
            "paid_visual_calls_allowed": False,
        },
        "provenance": {
            "narration_timing_map": str(timing_path.resolve()),
            "narration_timing_map_sha256": sha256_file(timing_path),
            "visual_manifest": str(visual_path.resolve()),
            "visual_manifest_sha256": sha256_file(visual_path),
        },
    }


def prepare() -> dict[str, Any]:
    ROUGH_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for timing_path in sorted(TIMING_DIR.glob("*.narration_timing_map.json")) if TIMING_DIR.exists() else []:
        timing = load_json(timing_path)
        key = _key(str(timing.get("concept_id") or ""), str(timing.get("format") or ""))
        visual_path = VISUAL_DIR / f"{key}.visual_manifest.json"
        if not visual_path.exists():
            continue
        rough = build_rough_cut(timing, load_json(visual_path), timing_path, visual_path)
        destination = ROUGH_DIR / f"{key}.visual_rough_cut.json"
        atomic_write_json(destination, rough)
        items.append({"concept_id": rough["concept_id"], "format": rough["format"], "rough_cut": str(destination), "placeholders": rough["summary"]["placeholders"]})
    result = {
        "status": "READY_FOR_HUMAN_ROUGH_CUT_GATE" if items else "WAITING_FOR_AUDIO_AND_VISUAL_MANIFESTS",
        "prepared": len(items),
        "items": items,
        "paid_visual_calls_allowed": False,
    }
    atomic_write_json(SUMMARY_FILE, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare visual rough-cut manifests")
    parser.add_argument("--mode", choices=("prepare",), required=True)
    parser.parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
