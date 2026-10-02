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
from narration_preview_review import (
    RENDER_DIR as PREVIEW_RENDER_DIR,
    current_render as current_preview_render,
)

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"
APPROVED_DIR = OUTPUT_DIR / "approved_narration_previews"
PREVIEW_DIR = OUTPUT_DIR / "narration_preview_manifests"
BRIEF_DIR = OUTPUT_DIR / "approved_sound_design_briefs"
SUMMARY_FILE = OUTPUT_DIR / "sound_design_brief_summary.json"


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _load_dict(path: Path) -> dict[str, Any] | None:
    try:
        value = load_json(path)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def current_preview_approval(
    approval_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path] | None:
    approval = _load_dict(approval_path)
    if not isinstance(approval, dict) or approval.get("decision") != "APPROVE_FINAL":
        return None
    concept_id = str(approval.get("concept_id") or "").strip()
    fmt = str(approval.get("format") or "").strip()
    if not concept_id or not fmt:
        return None
    key = _key(concept_id, fmt)
    manifest_path = PREVIEW_DIR / f"{key}.narration_preview.json"
    audio_path = PREVIEW_RENDER_DIR / f"{key}.preview.wav"
    manifest = _load_dict(manifest_path)
    if not isinstance(manifest, dict):
        return None
    if (
        str(manifest.get("concept_id") or "").strip() != concept_id
        or str(manifest.get("format") or "").strip() != fmt
    ):
        return None
    render_metadata = current_preview_render(manifest_path, audio_path)
    if render_metadata is None:
        return None
    provenance = manifest.get("provenance", {})
    if not isinstance(provenance, dict):
        return None
    if (
        approval.get("preview_manifest_sha256") != sha256_file(manifest_path)
        or approval.get("preview_audio_sha256")
        != render_metadata.get("audio_sha256")
        or approval.get("approved_voice_spec_sha256")
        != provenance.get("approved_voice_spec_sha256")
    ):
        return None
    return approval, manifest, render_metadata, manifest_path


def current_brief_for_branch(
    concept_id: str,
    fmt: str,
) -> tuple[Path, dict[str, Any]] | None:
    key = _key(concept_id, fmt)
    approval_path = APPROVED_DIR / f"{key}.approved_preview.json"
    current = current_preview_approval(approval_path)
    if current is None:
        return None
    approval, _manifest, render_metadata, manifest_path = current
    brief_path = BRIEF_DIR / f"{key}.sound_design_brief.json"
    brief = _load_dict(brief_path)
    if not isinstance(brief, dict):
        return None
    provenance = brief.get("provenance", {})
    if not isinstance(provenance, dict):
        return None
    if (
        provenance.get("preview_approval_sha256") != sha256_file(approval_path)
        or provenance.get("preview_manifest_sha256") != sha256_file(manifest_path)
        or provenance.get("preview_audio_sha256")
        != render_metadata.get("audio_sha256")
        or provenance.get("approved_voice_spec_sha256")
        != approval.get("approved_voice_spec_sha256")
    ):
        return None
    if (
        str(brief.get("concept_id") or "").strip() != concept_id
        or str(brief.get("format") or "").strip() != fmt
    ):
        return None
    return brief_path, brief


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
            "preview_manifest_sha256": approval.get("preview_manifest_sha256"),
            "preview_audio_sha256": approval.get("preview_audio_sha256"),
            "approved_voice_spec_sha256": approval.get(
                "approved_voice_spec_sha256"
            ),
        },
    }


def snapshot() -> dict[str, Any]:
    approvals = (
        sorted(APPROVED_DIR.glob("*.approved_preview.json"))
        if APPROVED_DIR.exists()
        else []
    )
    expected = 0
    current = 0
    stale_approvals = 0
    items: list[dict[str, Any]] = []
    for approval_path in approvals:
        approval_state = current_preview_approval(approval_path)
        if approval_state is None:
            stale_approvals += 1
            continue
        approval, _manifest, _render_metadata, _manifest_path = approval_state
        concept_id = str(approval.get("concept_id") or "").strip()
        fmt = str(approval.get("format") or "").strip()
        expected += 1
        brief_state = current_brief_for_branch(concept_id, fmt)
        if brief_state is None:
            continue
        brief_path, _brief = brief_state
        current += 1
        items.append(
            {
                "concept_id": concept_id,
                "format": fmt,
                "brief": str(brief_path),
            }
        )

    status = (
        "READY_FOR_FINAL_PROVIDER_HANDOFF"
        if expected > 0 and current == expected and stale_approvals == 0
        else "STALE_SOUND_DESIGN_BRIEF"
        if expected > 0 or stale_approvals > 0
        else "WAITING_FOR_APPROVED_FREE_PREVIEW"
    )
    return {
        "status": status,
        "prepared": current,
        "expected": expected,
        "stale_approvals": stale_approvals,
        "items": items,
        "prototype_media_copied": False,
    }


def prepare() -> dict[str, Any]:
    BRIEF_DIR.mkdir(parents=True, exist_ok=True)
    approvals = (
        sorted(APPROVED_DIR.glob("*.approved_preview.json"))
        if APPROVED_DIR.exists()
        else []
    )
    current_paths: set[Path] = set()
    for approval_path in approvals:
        approval_state = current_preview_approval(approval_path)
        if approval_state is None:
            continue
        approval, manifest, _render_metadata, _manifest_path = approval_state
        concept_id = str(approval.get("concept_id") or "").strip()
        fmt = str(approval.get("format") or "").strip()
        key = _key(concept_id, fmt)
        brief = build_brief(approval, manifest, approval_path)
        destination = BRIEF_DIR / f"{key}.sound_design_brief.json"
        atomic_write_json(destination, brief)
        current_paths.add(destination.resolve())

    for stale in BRIEF_DIR.glob("*.sound_design_brief.json"):
        if stale.resolve() not in current_paths:
            stale.unlink()

    result = snapshot()
    atomic_write_json(SUMMARY_FILE, result)
    return result

def main() -> None:
    parser = argparse.ArgumentParser(description="Build approved Sound Design Brief")
    parser.add_argument("--mode", choices=("prepare",), required=True)
    parser.parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
