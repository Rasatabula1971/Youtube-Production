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
from edit_manifest import manifest_is_current
from edit_preview_render import preview_result_is_current
from sound_design_brief import current_brief_for_branch
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
    if (
        not path.is_file()
        or path.parent.resolve() != APPROVED_EDIT_DIR.resolve()
    ):
        raise ValueError("STALE_EDIT_DIRECTION_APPROVAL")

    approval = load_json(path)
    if (
        approval.get("artifact") != "approved_edit_preview"
        or approval.get("status") != "EDIT_DIRECTION_APPROVED"
    ):
        raise ValueError("Edit direction approval is invalid")

    result_path = Path(str(approval.get("source_preview_result") or ""))
    if (
        not result_path.is_file()
        or result_path.parent.resolve() != EDIT_RESULT_DIR.resolve()
        or approval.get("source_preview_result_sha256")
        != sha256_file(result_path)
    ):
        raise ValueError("STALE_EDIT_DIRECTION_APPROVAL")

    current_result = preview_result_is_current(result_path)
    if current_result is None:
        raise ValueError("STALE_EDIT_PREVIEW_RESULT")
    result = current_result

    concept_id = str(result.get("concept_id") or "")
    fmt = str(result.get("format") or "")
    if (
        str(approval.get("concept_id") or "") != concept_id
        or str(approval.get("format") or "") != fmt
        or str(approval.get("preview_file") or "")
        != str(result.get("preview_file") or "")
        or int(approval.get("placeholder_segments_at_approval") or 0)
        != int(result.get("placeholder_segments") or 0)
    ):
        raise ValueError("STALE_EDIT_DIRECTION_APPROVAL")

    provenance = result.get("provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError("Edit preview provenance is missing")
    manifest_path = Path(str(provenance.get("edit_manifest") or ""))
    current_manifest = manifest_is_current(manifest_path)
    if (
        current_manifest is None
        or provenance.get("edit_manifest_sha256")
        != sha256_file(manifest_path)
    ):
        raise ValueError("STALE_EDIT_PREVIEW_RESULT")

    if (
        str(current_manifest.get("concept_id") or "") != concept_id
        or str(current_manifest.get("format") or "") != fmt
    ):
        raise ValueError("Edit preview branch identity is stale")

    return approval, result_path, result, manifest_path, current_manifest


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


def _visual_costs(
    concept_id: str,
    fmt: str,
    visuals: list[dict[str, Any]],
) -> dict[str, Any]:
    selected = {
        str(item.get("shot_id") or ""): item
        for item in visuals
        if isinstance(item, dict) and str(item.get("shot_id") or "")
    }
    items: list[dict[str, Any]] = []
    total = 0.0
    if GENERATED_VISUAL_REGISTRY.exists():
        for path in sorted(
            GENERATED_VISUAL_REGISTRY.glob("*.generated_visual_asset.json")
        ):
            payload = load_json(path)
            shot_id = str(payload.get("shot_id") or "")
            selected_item = selected.get(shot_id)
            if (
                str(payload.get("concept_id") or "") != concept_id
                or str(payload.get("format") or "") != fmt
                or payload.get("artifact") != "generated_visual_asset"
                or payload.get("status") != "REGISTERED_CURRENT"
                or selected_item is None
            ):
                continue

            asset_path = Path(str(payload.get("asset_file") or ""))
            selected_path = Path(str(selected_item.get("asset_file") or ""))
            if (
                not asset_path.is_file()
                or not selected_path.is_file()
                or asset_path.resolve() != selected_path.resolve()
                or payload.get("asset_sha256") != sha256_file(asset_path)
                or selected_item.get("asset_sha256") != sha256_file(asset_path)
            ):
                continue

            cost = round(float(payload.get("actual_cost_usd") or 0), 2)
            if cost < 0:
                raise ValueError("Generated visual actual cost cannot be negative")
            total += cost
            items.append({
                "shot_id": shot_id,
                "provider": payload.get("provider"),
                "actual_cost_usd": cost,
                "registry_file": str(path.resolve()),
                "registry_sha256": sha256_file(path),
                "asset_sha256": payload.get("asset_sha256"),
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

    sound_state = current_brief_for_branch(concept_id, fmt)
    sound_path: Path | None = None
    sound_brief: dict[str, Any] | None = None
    if sound_state is None:
        blockers.append("APPROVED_SOUND_DESIGN_BRIEF_MISSING_OR_STALE")
    else:
        sound_path, sound_brief = sound_state

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
        "costs": _visual_costs(concept_id, fmt, visuals),
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
                str(sound_path.resolve()) if sound_path is not None else None
            ),
            "sound_design_brief_sha256": (
                sha256_file(sound_path) if sound_path is not None else None
            ),
        },
    }


def handoff_is_current(path: Path) -> dict[str, Any] | None:
    if (
        not path.is_file()
        or path.parent.resolve() != HANDOFF_DIR.resolve()
    ):
        return None
    try:
        payload = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if (
        not isinstance(payload, dict)
        or payload.get("artifact") != "final_production_handoff"
        or payload.get("status")
        not in {
            "READY_FOR_FINAL_SOUND_PROVIDER_OR_ASSET_REGISTRATION",
            "BLOCKED",
        }
    ):
        return None

    provenance = payload.get("provenance", {})
    if not isinstance(provenance, dict):
        return None
    approval_path = Path(
        str(provenance.get("approved_edit_preview") or "")
    )
    if (
        not approval_path.is_file()
        or approval_path.parent.resolve() != APPROVED_EDIT_DIR.resolve()
        or provenance.get("approved_edit_preview_sha256")
        != sha256_file(approval_path)
    ):
        return None

    try:
        rebuilt = build_handoff(approval_path)
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        return None
    return payload if payload == rebuilt else None


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
