"""Build the commercial-safe Sound Design Brief after free prototype approval.

This module copies no generated reference audio. It transfers descriptive intent
only: timing intent, mood, SFX descriptions, ducking, and transition direction.
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
APPROVED_DIR = OUTPUT_DIR / "approved_narration_previews"
PREVIEW_DIR = OUTPUT_DIR / "narration_preview_manifests"
BRIEF_DIR = OUTPUT_DIR / "approved_sound_design_briefs"
SUMMARY_FILE = OUTPUT_DIR / "sound_design_brief_summary.json"


def build_brief(approval: dict[str, Any], manifest: dict[str, Any], approval_path: Path) -> dict[str, Any]:
    directions = []
    for segment in manifest.get("segments", []):
        sound = segment.get("sound_design", {})
        directions.append({
            "segment_id": segment.get("segment_id"),
            "music_direction": sound.get("music_mood"),
            "sfx_direction": list(sound.get("sfx_suggestions", [])),
            "duck_under_narration": bool(sound.get("duck_under_narration", True)),
            "pause_before_ms": segment.get("delivery", {}).get("pause_before_ms"),
            "pause_after_ms": segment.get("delivery", {}).get("pause_after_ms"),
        })
    return {
        "artifact": "approved_sound_design_brief",
        "concept_id": manifest.get("concept_id"),
        "format": manifest.get("format"),
        "human_preview_decision": approval.get("decision"),
        "directions": directions,
        "provider_handoff_policy": {
            "descriptive_instructions_only": True,
            "prototype_audio_attached": False,
            "audiogen_output_attached": False,
            "musicgen_output_attached": False,
        },
        "provenance": {
            "preview_approval": str(approval_path.resolve()),
            "preview_approval_sha256": sha256_file(approval_path),
        },
    }


def prepare() -> dict[str, Any]:
    BRIEF_DIR.mkdir(parents=True, exist_ok=True)
    approvals = sorted(APPROVED_DIR.glob("*.approved_preview.json")) if APPROVED_DIR.exists() else []
    items = []
    for approval_path in approvals:
        approval = load_json(approval_path)
        if approval.get("decision") != "APPROVE_FINAL":
            continue
        concept_id = str(approval.get("concept_id") or "")
        fmt = str(approval.get("format") or "")
        key = f"{safe_slug(concept_id)}.{safe_slug(fmt)}"
        manifest_path = PREVIEW_DIR / f"{key}.narration_preview.json"
        if not manifest_path.exists():
            continue
        manifest = load_json(manifest_path)
        brief = build_brief(approval, manifest, approval_path)
        destination = BRIEF_DIR / f"{key}.sound_design_brief.json"
        atomic_write_json(destination, brief)
        items.append({"concept_id": concept_id, "format": fmt, "brief": str(destination)})
    result = {
        "status": "READY_FOR_FINAL_PROVIDER_HANDOFF" if items else "WAITING_FOR_APPROVED_FREE_PREVIEW",
        "prepared": len(items),
        "items": items,
        "prototype_media_copied": False,
    }
    atomic_write_json(SUMMARY_FILE, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build approved Sound Design Brief")
    parser.add_argument("--mode", choices=("prepare",), required=True)
    parser.parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
