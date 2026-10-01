"""Prepare a provider-neutral final production handoff.

This stage runs only after the structural edit direction is human-approved.
It validates that the approval, preview, edit manifest, narration and visual
assets are all current. It does not render, publish, call Higgsfield, or spend.

Final music/SFX remain descriptive intent until a commercial-safe provider or
licensed final audio asset path is explicitly connected.
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
APPROVED_EDIT_DIR = OUTPUT / "approved_edit_previews"
EDIT_RESULT_DIR = OUTPUT / "edit_preview_results"
HANDOFF_DIR = OUTPUT / "final_production_handoffs"
SOUND_DIR = OUTPUT / "approved_sound_design_briefs"
GENERATED_VISUAL_REGISTRY = OUTPUT / "generated_visual_asset_registry"
SUMMARY_FILE = OUTPUT / "final_production_handoff_summary.json"


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _current_approval(
    path: Path,
) -> tuple[dict[str, Any], Path, dict[str, Any], Path, dict[str, Any]]:
    approval = load_json(path)
    if approval.get("status") != "EDIT_DIRECTION_APPROVED":
        raise ValueError("Edit direction approval is invalid")

    result_path = Path(str(approval.get("source_preview_result") or ""))
    if (
        not result_path.exists()
        or result_path.parent.resolve() != EDIT_RESULT_DIR.resolve()
        or approval.get("source_preview_result_sha256")
        != sha256_file(result_path)
    ):
        raise ValueError("STALE_EDIT_DIRECTION_APPROVAL")

    result = load_json(result_path)
    provenance = result.get("provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError("Edit preview provenance is missing")
    manifest_path = Path(str(provenance.get("edit_manifest") or ""))
    if (
        not manifest_path.exists()
        or provenance.get("edit_manifest_sha256")
        != sha256_file(manifest_path)
    ):
        raise ValueError("STALE_EDIT_PREVIEW_RESULT")

    preview_path = Path(str(result.get("preview_file") or ""))
    if (
        not preview_path.exists()
        or result.get("preview_sha256") != sha256_file(preview_path)
    ):
        raise ValueError("Approved edit preview media is stale")

    manifest = load_json(manifest_path)
    if manifest.get("status") != "READY_FOR_LOCAL_PREVIEW_RENDER":
        raise ValueError("Current edit manifest is not valid")
    return approval, result_path, result, manifest_path, manifest


def _validate_final_visuals(
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    visuals: list[dict[str, Any]] = []
    blockers: list[str] = []
    for item in manifest.get("visual_track", []):
        if not isinstance(item, dict):
            continue
        shot_id = str(item.get("shot_id") or "")
        asset_value = str(item.get("asset_file") or "").strip()
        if item.get("preview_mode") != "ASSET" or not asset_value:
            blockers.append(f"{shot_id}:FINAL_VISUAL_ASSET_MISSING")
            continue
        asset_path = Path(asset_value)
        if (
            not asset_path.exists()
            or not asset_path.is_file()
            or item.get("asset_sha256") != sha256_file(asset_path)
        ):
            blockers.append(f"{shot_id}:FINAL_VISUAL_ASSET_STALE")
            continue
        visuals.append({
            "scene_index": item.get("scene_index"),
            "shot_id": shot_id,
            "beat_id": item.get("beat_id"),
            "start_seconds": item.get("start_seconds"),
            "end_seconds": item.get("end_seconds"),
            "duration_seconds": item.get("duration_seconds"),
            "story_purpose": item.get("story_purpose"),
            "cinematic_direction": item.get("cinematic_direction", {}),
            "asset_file": str(asset_path.resolve()),
            "asset_sha256": sha256_file(asset_path),
            "source_visual_status": item.get("source_visual_status"),
        })
    return visuals, blockers


def _validate_narration(
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    narration: list[dict[str, Any]] = []
    blockers: list[str] = []
    for item in manifest.get("narration_track", []):
        if not isinstance(item, dict):
            continue
        segment_id = str(item.get("segment_id") or "")
        path = Path(str(item.get("audio_file") or ""))
        if (
            not path.exists()
            or not path.is_file()
            or item.get("audio_sha256") != sha256_file(path)
        ):
            blockers.append(f"{segment_id}:NARRATION_AUDIO_STALE_OR_MISSING")
            continue
        narration.append({
            **item,
            "audio_file": str(path.resolve()),
            "audio_sha256": sha256_file(path),
        })
    if not narration:
        blockers.append("NO_CURRENT_NARRATION_AUDIO")
    return narration, blockers


def _visual_costs(concept_id: str, fmt: str) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    total = 0.0
    if GENERATED_VISUAL_REGISTRY.exists():
        for path in GENERATED_VISUAL_REGISTRY.glob(
            "*.generated_visual_asset.json"
        ):
            payload = load_json(path)
            if (
                str(payload.get("concept_id") or "") != concept_id
                or str(payload.get("format") or "") != fmt
            ):
                continue
            cost = round(float(payload.get("actual_cost_usd") or 0), 2)
            total += cost
            items.append({
                "shot_id": payload.get("shot_id"),
                "provider": payload.get("provider"),
                "actual_cost_usd": cost,
                "registry_file": str(path),
                "registry_sha256": sha256_file(path),
            })
    return {
        "currency": "USD",
        "generated_visual_actual_total_usd": round(total, 2),
        "items": items,
    }


def build_handoff(
    approval_path: Path,
) -> dict[str, Any]:
    (
        approval,
        result_path,
        result,
        manifest_path,
        manifest,
    ) = _current_approval(approval_path)

    concept_id = str(manifest.get("concept_id") or "")
    fmt = str(manifest.get("format") or "")
    visuals, visual_blockers = _validate_final_visuals(manifest)
    narration, narration_blockers = _validate_narration(manifest)
    blockers = visual_blockers + narration_blockers

    sound_path = SOUND_DIR / f"{_key(concept_id, fmt)}.sound_design_brief.json"
    sound_brief: dict[str, Any] | None = None
    if sound_path.exists():
        sound_brief = load_json(sound_path)
    else:
        blockers.append("APPROVED_SOUND_DESIGN_BRIEF_MISSING")

    # Sound design is intentionally still descriptive-only. A final licensed or
    # provider-rendered music/SFX layer has not yet been connected.
    blockers.append("FINAL_MUSIC_SFX_ASSETS_NOT_CONNECTED")

    return {
        "artifact": "final_production_handoff",
        "concept_id": concept_id,
        "format": fmt,
        "status": (
            "READY_FOR_FINAL_SOUND_PROVIDER_OR_ASSET_REGISTRATION"
            if blockers == ["FINAL_MUSIC_SFX_ASSETS_NOT_CONNECTED"]
            else "BLOCKED"
        ),
        "video_profile": manifest.get("video_profile", {}),
        "duration": manifest.get("duration", {}),
        "visual_track": visuals,
        "narration_track": narration,
        "sound_design_intent": (
            sound_brief.get("directions", [])
            if isinstance(sound_brief, dict)
            else []
        ),
        "provider_handoff": {
            "preferred_provider": "higgsfield",
            "provider_neutral": True,
            "provider_call_authorized": False,
            "paid_execution_performed": False,
            "sound_brief_is_instruction_only": True,
        },
        "costs": _visual_costs(concept_id, fmt),
        "blockers": blockers,
        "human_approval": {
            "edit_direction_approved": True,
            "placeholder_segments_at_approval": approval.get(
                "placeholder_segments_at_approval"
            ),
        },
        "provenance": {
            "approved_edit_preview": str(approval_path.resolve()),
            "approved_edit_preview_sha256": sha256_file(approval_path),
            "edit_preview_result": str(result_path.resolve()),
            "edit_preview_result_sha256": sha256_file(result_path),
            "edit_manifest": str(manifest_path.resolve()),
            "edit_manifest_sha256": sha256_file(manifest_path),
            "sound_design_brief": (
                str(sound_path.resolve()) if sound_path.exists() else None
            ),
            "sound_design_brief_sha256": (
                sha256_file(sound_path) if sound_path.exists() else None
            ),
        },
    }


def prepare() -> dict[str, Any]:
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    current: set[Path] = set()
    items: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    approvals = (
        sorted(APPROVED_EDIT_DIR.glob("*.approved_edit_preview.json"))
        if APPROVED_EDIT_DIR.exists()
        else []
    )
    for approval_path in approvals:
        try:
            handoff = build_handoff(approval_path)
            key = _key(
                str(handoff.get("concept_id") or ""),
                str(handoff.get("format") or ""),
            )
            destination = HANDOFF_DIR / f"{key}.final_production_handoff.json"
            atomic_write_json(destination, handoff)
            current.add(destination.resolve())
            items.append({
                "concept_id": handoff.get("concept_id"),
                "format": handoff.get("format"),
                "status": handoff.get("status"),
                "blockers": handoff.get("blockers", []),
                "handoff": str(destination),
            })
        except Exception as exc:
            failures.append({
                "approval": str(approval_path),
                "error_type": type(exc).__name__,
                "error": str(exc),
            })

    for stale in HANDOFF_DIR.glob("*.final_production_handoff.json"):
        if stale.resolve() not in current:
            stale.unlink()

    summary = {
        "status": (
            "FINAL_PRODUCTION_HANDOFFS_READY"
            if items and not failures
            else "PARTIAL"
            if items
            else "FAILED"
            if failures
            else "WAITING_FOR_APPROVED_EDIT_DIRECTION"
        ),
        "prepared": len(items),
        "failed": len(failures),
        "ready_for_final_sound": sum(
            item["status"]
            == "READY_FOR_FINAL_SOUND_PROVIDER_OR_ASSET_REGISTRATION"
            for item in items
        ),
        "blocked": sum(item["status"] == "BLOCKED" for item in items),
        "paid_provider_calls": 0,
        "items": items,
        "failures": failures,
    }
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare provider-neutral final production handoffs"
    )
    parser.add_argument("--mode", choices=("prepare",), required=True)
    parser.parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
