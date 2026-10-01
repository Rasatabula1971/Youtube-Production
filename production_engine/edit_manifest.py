"""Build a deterministic local edit manifest for free preview rendering.

The manifest combines:
- narration Audio-QC + real timing map,
- current visual assembly plan,
- approved descriptive sound-design intent.

It does not generate music/SFX, call paid providers, or publish media.
Missing visual assets remain explicit preview placeholders.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
ASSEMBLY_DIR = OUTPUT / "visual_assembly_plans"
QC_DIR = OUTPUT / "narration_audio_qc"
TIMING_DIR = OUTPUT / "narration_timing_maps"
SOUND_DIR = OUTPUT / "approved_sound_design_briefs"
EDIT_DIR = OUTPUT / "edit_manifests"
SUMMARY_FILE = OUTPUT / "edit_manifest_summary.json"


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _video_profile(fmt: str) -> dict[str, Any]:
    if fmt == "short":
        return {
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "aspect_ratio": "9:16",
        }
    return {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "aspect_ratio": "16:9",
    }


def _narration_track(
    qc: dict[str, Any],
    timing: dict[str, Any],
) -> list[dict[str, Any]]:
    if qc.get("status") != "PASS":
        raise ValueError("Narration Audio QC must PASS before edit manifest")
    if timing.get("status") != "READY_FOR_ROUGH_CUT":
        raise ValueError("Narration timing map is not ready")
    if qc.get("concept_id") != timing.get("concept_id") or qc.get(
        "format"
    ) != timing.get("format"):
        raise ValueError("Narration QC/timing identity mismatch")

    checks = {
        str(item.get("segment_id") or ""): item
        for item in qc.get("checks", [])
        if isinstance(item, dict)
    }
    track: list[dict[str, Any]] = []
    for timing_item in timing.get("segments", []):
        if not isinstance(timing_item, dict):
            continue
        segment_id = str(timing_item.get("segment_id") or "")
        check = checks.get(segment_id)
        if not isinstance(check, dict) or check.get("status") != "PASS":
            raise ValueError(
                f"Narration segment {segment_id} is missing current PASS QC"
            )
        audio_path = Path(str(check.get("audio_file") or ""))
        if not audio_path.exists() or not audio_path.is_file():
            raise ValueError(
                f"Narration segment {segment_id} audio file is missing"
            )
        track.append({
            "segment_id": segment_id,
            "audio_file": str(audio_path.resolve()),
            "audio_sha256": sha256_file(audio_path),
            "audio_start_seconds": float(
                timing_item.get("audio_start_seconds") or 0
            ),
            "audio_end_seconds": float(
                timing_item.get("audio_end_seconds") or 0
            ),
            "timeline_end_seconds": float(
                timing_item.get("timeline_end_seconds") or 0
            ),
            "pause_before_seconds": float(
                timing_item.get("pause_before_seconds") or 0
            ),
            "pause_after_seconds": float(
                timing_item.get("pause_after_seconds") or 0
            ),
        })
    if not track:
        raise ValueError("Narration track contains no current audio segments")
    return track


def _visual_track(assembly: dict[str, Any]) -> list[dict[str, Any]]:
    timeline = assembly.get("timeline", [])
    if not isinstance(timeline, list) or not timeline:
        raise ValueError("Visual assembly plan contains no timeline scenes")

    out: list[dict[str, Any]] = []
    for item in timeline:
        if not isinstance(item, dict):
            continue
        visual_status = str(item.get("visual_status") or "")
        asset_file: str | None = None
        asset_sha256: str | None = None

        asset = item.get("asset", {})
        generation = item.get("generation", {})
        if isinstance(asset, dict) and asset.get("asset_file"):
            path = Path(str(asset["asset_file"]))
            if path.exists() and path.is_file():
                asset_file = str(path.resolve())
                asset_sha256 = sha256_file(path)
        if (
            visual_status == "GENERATED_ASSET_READY"
            and isinstance(generation, dict)
            and generation.get("asset_file")
        ):
            path = Path(str(generation["asset_file"]))
            if path.exists() and path.is_file():
                asset_file = str(path.resolve())
                asset_sha256 = sha256_file(path)

        time_range = (
            item.get("time_range", {})
            if isinstance(item.get("time_range"), dict)
            else {}
        )
        start = float(time_range.get("start_seconds") or 0)
        end = float(time_range.get("end_seconds") or start)
        if end <= start:
            raise ValueError(
                f"Visual shot {item.get('shot_id')} has invalid time range"
            )

        out.append({
            "scene_index": item.get("scene_index"),
            "shot_id": item.get("shot_id"),
            "beat_id": item.get("beat_id"),
            "start_seconds": start,
            "end_seconds": end,
            "duration_seconds": end - start,
            "story_purpose": item.get("story_purpose"),
            "desired_visual": item.get("desired_visual"),
            "cinematic_direction": item.get("cinematic_direction", {}),
            "source_visual_status": visual_status,
            "preview_mode": (
                "ASSET"
                if asset_file
                else "PLACEHOLDER"
            ),
            "asset_file": asset_file,
            "asset_sha256": asset_sha256,
            "placeholder_reason": (
                None
                if asset_file
                else visual_status or "VISUAL_ASSET_NOT_LOCAL"
            ),
        })
    return out


def _sound_directions(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = load_json(path)
    directions = payload.get("directions", [])
    return [
        item
        for item in directions
        if isinstance(item, dict)
    ] if isinstance(directions, list) else []


def build_manifest(
    *,
    assembly_path: Path,
    assembly: dict[str, Any],
    qc_path: Path,
    qc: dict[str, Any],
    timing_path: Path,
    timing: dict[str, Any],
    sound_path: Path,
) -> dict[str, Any]:
    concept_id = str(assembly.get("concept_id") or "")
    fmt = str(assembly.get("format") or "")
    if not concept_id or not fmt:
        raise ValueError("Visual assembly identity is missing")
    if (
        str(qc.get("concept_id") or "") != concept_id
        or str(qc.get("format") or "") != fmt
        or str(timing.get("concept_id") or "") != concept_id
        or str(timing.get("format") or "") != fmt
    ):
        raise ValueError("Edit inputs do not describe the same branch")

    narration = _narration_track(qc, timing)
    visuals = _visual_track(assembly)
    narration_duration = float(
        timing.get("total_duration_seconds") or 0
    )
    visual_duration = max(
        (float(item["end_seconds"]) for item in visuals),
        default=0.0,
    )
    preview_duration = max(narration_duration, visual_duration)
    placeholders = sum(
        item["preview_mode"] == "PLACEHOLDER"
        for item in visuals
    )

    return {
        "artifact": "edit_manifest",
        "concept_id": concept_id,
        "format": fmt,
        "status": "READY_FOR_LOCAL_PREVIEW_RENDER",
        "render_purpose": "HUMAN_STRUCTURAL_EDIT_PREVIEW",
        "video_profile": _video_profile(fmt),
        "duration": {
            "narration_seconds": narration_duration,
            "visual_timeline_seconds": visual_duration,
            "preview_seconds": preview_duration,
        },
        "narration_track": narration,
        "visual_track": visuals,
        "sound_design_intent": _sound_directions(sound_path),
        "preview_policy": {
            "placeholders_allowed": True,
            "placeholder_count": placeholders,
            "premium_provider_calls_allowed": False,
            "music_or_sfx_generation_allowed": False,
            "publish_ready": False,
            "human_edit_preview_gate_required": True,
        },
        "provenance": {
            "visual_assembly_plan": str(assembly_path.resolve()),
            "visual_assembly_plan_sha256": sha256_file(assembly_path),
            "narration_audio_qc": str(qc_path.resolve()),
            "narration_audio_qc_sha256": sha256_file(qc_path),
            "narration_timing_map": str(timing_path.resolve()),
            "narration_timing_map_sha256": sha256_file(timing_path),
            "sound_design_brief": (
                str(sound_path.resolve()) if sound_path.exists() else None
            ),
            "sound_design_brief_sha256": (
                sha256_file(sound_path) if sound_path.exists() else None
            ),
        },
    }


def prepare() -> dict[str, Any]:
    EDIT_DIR.mkdir(parents=True, exist_ok=True)
    current: set[Path] = set()
    items: list[dict[str, Any]] = []

    assembly_paths = (
        sorted(ASSEMBLY_DIR.glob("*.visual_assembly_plan.json"))
        if ASSEMBLY_DIR.exists()
        else []
    )
    for assembly_path in assembly_paths:
        assembly = load_json(assembly_path)
        concept_id = str(assembly.get("concept_id") or "")
        fmt = str(assembly.get("format") or "")
        key = _key(concept_id, fmt)

        qc_path = QC_DIR / f"{key}.narration_audio_qc.json"
        timing_path = TIMING_DIR / f"{key}.narration_timing_map.json"
        sound_path = SOUND_DIR / f"{key}.sound_design_brief.json"
        if not qc_path.exists() or not timing_path.exists():
            continue
        qc = load_json(qc_path)
        timing = load_json(timing_path)

        manifest = build_manifest(
            assembly_path=assembly_path,
            assembly=assembly,
            qc_path=qc_path,
            qc=qc,
            timing_path=timing_path,
            timing=timing,
            sound_path=sound_path,
        )
        destination = EDIT_DIR / f"{key}.edit_manifest.json"
        atomic_write_json(destination, manifest)
        current.add(destination.resolve())
        items.append({
            "concept_id": concept_id,
            "format": fmt,
            "manifest": str(destination),
            "placeholder_count": manifest["preview_policy"][
                "placeholder_count"
            ],
            "preview_seconds": manifest["duration"][
                "preview_seconds"
            ],
        })

    for stale in EDIT_DIR.glob("*.edit_manifest.json"):
        if stale.resolve() not in current:
            stale.unlink()

    summary = {
        "status": (
            "EDIT_MANIFESTS_READY"
            if items
            else "WAITING_FOR_CURRENT_AUDIO_AND_VISUAL_ASSEMBLY"
        ),
        "prepared": len(items),
        "items": items,
        "paid_provider_calls": 0,
        "media_rendered": False,
    }
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare deterministic local edit preview manifests"
    )
    parser.add_argument("--mode", choices=("prepare",), required=True)
    parser.parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
