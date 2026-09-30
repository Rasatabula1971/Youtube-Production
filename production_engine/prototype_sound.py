"""Prepare reference-only music and SFX prompts for the free audio prototype.

AudioCraft AudioGen/MusicGen may be used locally for research/reference. Their
generated media is quarantined under prototype_reference and MUST NOT enter a
final/export directory. Only descriptive sound-design instructions may cross the
human listen gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from voice_performance import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"
PREVIEW_DIR = OUTPUT_DIR / "narration_preview_manifests"
REFERENCE_DIR = OUTPUT_DIR / "prototype_reference" / "sound"
PLAN_DIR = OUTPUT_DIR / "prototype_sound_plans"
SUMMARY_FILE = OUTPUT_DIR / "prototype_sound_summary.json"


def build_plan(manifest: dict[str, Any], source: Path) -> dict[str, Any]:
    segments: list[dict[str, Any]] = []
    for segment in manifest.get("segments", []):
        sound = segment.get("sound_design", {})
        mood = str(sound.get("music_mood") or "neutral_bed").replace("_", " ")
        sfx = [str(value).replace("_", " ") for value in sound.get("sfx_suggestions", [])]
        segments.append({
            "segment_id": segment.get("segment_id"),
            "music_reference_prompt": (
                f"Instrumental underscore reference: {mood}; support narration, no vocals, "
                "leave speech intelligible, demonstrate mood only."
            ),
            "sfx_reference_prompts": [
                f"Sound-effect reference: {item}; subtle, short, narration-safe." for item in sfx
            ],
            "duck_under_narration": bool(sound.get("duck_under_narration", True)),
        })
    return {
        "artifact": "prototype_sound_reference_plan",
        "concept_id": manifest.get("concept_id"),
        "format": manifest.get("format"),
        "reference_only": True,
        "commercial_final_use_allowed": False,
        "final_export_allowed": False,
        "generator_preferences": {
            "music": "audiocraft_musicgen_local",
            "sfx": "audiocraft_audiogen_local",
        },
        "segments": segments,
        "quarantine_directory": str(REFERENCE_DIR.resolve()),
        "boundary": (
            "Generated reference media never crosses into final production. "
            "Only human-approved descriptive sound-design instructions may cross."
        ),
        "provenance": {
            "preview_manifest": str(source.resolve()),
            "preview_manifest_sha256": sha256_file(source),
        },
    }


def prepare() -> dict[str, Any]:
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    paths = sorted(PREVIEW_DIR.glob("*.narration_preview.json")) if PREVIEW_DIR.exists() else []
    items = []
    for source in paths:
        manifest = load_json(source)
        plan = build_plan(manifest, source)
        key = f"{safe_slug(str(plan['concept_id']))}.{safe_slug(str(plan['format']))}"
        destination = PLAN_DIR / f"{key}.sound_reference_plan.json"
        atomic_write_json(destination, plan)
        items.append({"concept_id": plan["concept_id"], "format": plan["format"], "plan": str(destination)})
    result = {
        "status": "READY_FOR_REFERENCE_SOUND_GENERATION" if items else "WAITING_FOR_PREVIEW_MANIFESTS",
        "prepared": len(items),
        "items": items,
        "reference_media_directory": str(REFERENCE_DIR),
        "paid_calls_allowed": False,
    }
    atomic_write_json(SUMMARY_FILE, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare reference-only prototype sound plans")
    parser.add_argument("--mode", choices=("prepare",), required=True)
    parser.parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
