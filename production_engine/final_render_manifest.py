"""Build a rebuild-current manifest for the local Slice 22 final render.

The manifest binds the current Slice 20 final-production handoff to every
current Slice 21 sound resolution. It performs no rendering, upload, or publish
action.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from final_production_handoff import HANDOFF_DIR, handoff_is_current
from final_sound_plan import PLAN_DIR, plan_is_current
from final_sound_asset_import import REGISTRY_DIR, resolution_is_current
from visual_acquisition import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
MANIFEST_DIR = OUTPUT / "final_render_manifests"
SUMMARY_FILE = OUTPUT / "final_render_manifest_summary.json"

MUSIC_VOLUME_DUCKED = 0.18
MUSIC_VOLUME_OPEN = 0.28
SFX_VOLUME = 0.45
SFX_STAGGER_SECONDS = 0.5


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _current_resolution_map(
    plan: dict[str, Any],
) -> dict[str, tuple[Path, dict[str, Any]]]:
    out: dict[str, tuple[Path, dict[str, Any]]] = {}
    if not REGISTRY_DIR.exists():
        return out
    for path in sorted(REGISTRY_DIR.glob("*.final_sound_resolution.json")):
        payload = resolution_is_current(path)
        if payload is None:
            continue
        if (
            str(payload.get("concept_id") or "")
            != str(plan.get("concept_id") or "")
            or str(payload.get("format") or "")
            != str(plan.get("format") or "")
        ):
            continue
        requirement_id = str(payload.get("requirement_id") or "")
        if not requirement_id:
            continue
        if requirement_id in out:
            raise ValueError(
                f"Duplicate current final sound resolution: {requirement_id}"
            )
        out[requirement_id] = (path, payload)
    return out


def _segment_map(
    handoff: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in handoff.get("narration_track", []):
        if not isinstance(item, dict):
            continue
        segment_id = str(item.get("segment_id") or "")
        if not segment_id or segment_id in out:
            raise ValueError("Final narration segment IDs must be unique")
        out[segment_id] = item
    if not out:
        raise ValueError("Final handoff has no narration timing")
    return out


def _sound_track(
    *,
    plan: dict[str, Any],
    handoff: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    resolutions = _current_resolution_map(plan)
    segments = _segment_map(handoff)
    sound_track: list[dict[str, Any]] = []
    omitted: list[dict[str, Any]] = []

    requirements = [
        item
        for item in plan.get("requirements", [])
        if isinstance(item, dict)
    ]
    if len(resolutions) != len(requirements):
        raise ValueError("FINAL_SOUND_RESOLUTIONS_INCOMPLETE_OR_STALE")

    for requirement in requirements:
        requirement_id = str(requirement.get("requirement_id") or "")
        current = resolutions.get(requirement_id)
        if current is None:
            raise ValueError(
                f"Missing current final sound resolution: {requirement_id}"
            )
        resolution_path, resolution = current
        if (
            resolution.get("requirement_fingerprint")
            != requirement.get("fingerprint")
        ):
            raise ValueError("STALE_FINAL_SOUND_RESOLUTION")

        segment_id = str(requirement.get("segment_id") or "")
        narration = segments.get(segment_id)
        if narration is None:
            raise ValueError(
                f"Sound requirement references unknown segment: {segment_id}"
            )

        if resolution.get("status") == "OMITTED_BY_HUMAN":
            omitted.append({
                "requirement_id": requirement_id,
                "segment_id": segment_id,
                "kind": requirement.get("kind"),
                "human_note": resolution.get("note"),
                "resolution_file": str(resolution_path.resolve()),
                "resolution_sha256": sha256_file(resolution_path),
            })
            continue

        asset_path = Path(str(resolution.get("asset_file") or ""))
        if not asset_path.is_file():
            raise ValueError("Current final sound asset is missing")

        segment_start = float(
            narration.get("audio_start_seconds") or 0
        )
        segment_end = float(
            narration.get("timeline_end_seconds")
            or narration.get("audio_end_seconds")
            or segment_start
        )
        if segment_end <= segment_start:
            raise ValueError(
                f"Narration segment {segment_id} has invalid timing"
            )

        kind = str(requirement.get("kind") or "")
        index = int(requirement.get("index") or 0)
        if kind == "MUSIC":
            start = segment_start
            end = segment_end
            loop_to_fill = True
            volume = (
                MUSIC_VOLUME_DUCKED
                if requirement.get("duck_under_narration", True)
                else MUSIC_VOLUME_OPEN
            )
        elif kind == "SFX":
            available = max(0.0, segment_end - segment_start - 0.05)
            offset = min(
                max(0, index - 1) * SFX_STAGGER_SECONDS,
                available,
            )
            start = segment_start + offset
            end = segment_end
            loop_to_fill = False
            volume = SFX_VOLUME
        else:
            raise ValueError(f"Unsupported final sound kind: {kind}")

        sound_track.append({
            "requirement_id": requirement_id,
            "requirement_fingerprint": requirement.get("fingerprint"),
            "segment_id": segment_id,
            "kind": kind,
            "direction": requirement.get("direction"),
            "start_seconds": start,
            "end_seconds": end,
            "max_duration_seconds": max(0.0, end - start),
            "loop_to_fill": loop_to_fill,
            "volume": volume,
            "duck_under_narration": bool(
                requirement.get("duck_under_narration", True)
            ),
            "asset_file": str(asset_path.resolve()),
            "asset_sha256": sha256_file(asset_path),
            "rights": resolution.get("rights"),
            "cost": resolution.get("cost"),
            "resolution_file": str(resolution_path.resolve()),
            "resolution_sha256": sha256_file(resolution_path),
        })

    return sound_track, omitted


def build_manifest(
    plan_path: Path,
    plan: dict[str, Any],
) -> dict[str, Any]:
    current_plan = plan_is_current(plan_path)
    if current_plan is None or current_plan != plan:
        raise ValueError("STALE_FINAL_SOUND_PLAN")

    provenance = plan.get("provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError("Final sound plan provenance is missing")
    handoff_path = Path(
        str(provenance.get("final_production_handoff") or "")
    )
    handoff = handoff_is_current(handoff_path)
    if (
        handoff is None
        or handoff_path.parent.resolve() != HANDOFF_DIR.resolve()
        or provenance.get("final_production_handoff_sha256")
        != sha256_file(handoff_path)
    ):
        raise ValueError("STALE_FINAL_PRODUCTION_HANDOFF")

    concept_id = str(plan.get("concept_id") or "")
    fmt = str(plan.get("format") or "")
    if (
        str(handoff.get("concept_id") or "") != concept_id
        or str(handoff.get("format") or "") != fmt
    ):
        raise ValueError("Final render inputs describe different branches")

    visuals = [
        dict(item)
        for item in handoff.get("visual_track", [])
        if isinstance(item, dict)
    ]
    narration = [
        dict(item)
        for item in handoff.get("narration_track", [])
        if isinstance(item, dict)
    ]
    if not visuals or not narration:
        raise ValueError("Final render requires visual and narration tracks")
    for item in visuals:
        path = Path(str(item.get("asset_file") or ""))
        if (
            not path.is_file()
            or item.get("asset_sha256") != sha256_file(path)
        ):
            raise ValueError("STALE_FINAL_VISUAL_ASSET")
    for item in narration:
        path = Path(str(item.get("audio_file") or ""))
        if (
            not path.is_file()
            or item.get("audio_sha256") != sha256_file(path)
        ):
            raise ValueError("STALE_FINAL_NARRATION_AUDIO")

    sound_track, omitted = _sound_track(plan=plan, handoff=handoff)
    duration = handoff.get("duration", {})
    total = float(
        duration.get("preview_seconds")
        or duration.get("visual_timeline_seconds")
        or duration.get("narration_seconds")
        or 0
    )
    if total <= 0:
        raise ValueError("Final render duration must be positive")

    return {
        "artifact": "final_render_manifest",
        "concept_id": concept_id,
        "format": fmt,
        "status": "READY_FOR_LOCAL_FINAL_RENDER",
        "video_profile": handoff.get("video_profile", {}),
        "duration_seconds": total,
        "visual_track": visuals,
        "narration_track": narration,
        "sound_track": sound_track,
        "omitted_sound_requirements": omitted,
        "mix_policy": {
            "narration_volume": 1.0,
            "music_volume_ducked": MUSIC_VOLUME_DUCKED,
            "music_volume_open": MUSIC_VOLUME_OPEN,
            "sfx_volume": SFX_VOLUME,
            "sfx_stagger_seconds": SFX_STAGGER_SECONDS,
            "final_limiter": 0.95,
            "dynamic_sidechain_ducking": False,
            "note": (
                "Slice 22 uses conservative fixed music attenuation under "
                "narration. Human final-export review may return sound for rework."
            ),
        },
        "render_policy": {
            "local_ffmpeg_only": True,
            "placeholders_allowed": False,
            "paid_provider_calls": 0,
            "upload_allowed": False,
            "publish_allowed": False,
            "human_final_export_gate_required": True,
        },
        "provenance": {
            "final_sound_plan": str(plan_path.resolve()),
            "final_sound_plan_sha256": sha256_file(plan_path),
            "final_production_handoff": str(handoff_path.resolve()),
            "final_production_handoff_sha256": sha256_file(handoff_path),
            "sound_resolutions": [
                {
                    "requirement_id": item["requirement_id"],
                    "resolution_file": item["resolution_file"],
                    "resolution_sha256": item["resolution_sha256"],
                    "asset_sha256": item["asset_sha256"],
                }
                for item in sound_track
            ] + [
                {
                    "requirement_id": item["requirement_id"],
                    "resolution_file": item["resolution_file"],
                    "resolution_sha256": item["resolution_sha256"],
                    "asset_sha256": None,
                }
                for item in omitted
            ],
        },
    }


def manifest_is_current(path: Path) -> dict[str, Any] | None:
    if (
        not path.is_file()
        or path.parent.resolve() != MANIFEST_DIR.resolve()
    ):
        return None
    try:
        manifest = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if (
        not isinstance(manifest, dict)
        or manifest.get("artifact") != "final_render_manifest"
        or manifest.get("status") != "READY_FOR_LOCAL_FINAL_RENDER"
    ):
        return None
    provenance = manifest.get("provenance", {})
    if not isinstance(provenance, dict):
        return None
    plan_path = Path(str(provenance.get("final_sound_plan") or ""))
    if (
        not plan_path.is_file()
        or plan_path.parent.resolve() != PLAN_DIR.resolve()
        or provenance.get("final_sound_plan_sha256")
        != sha256_file(plan_path)
    ):
        return None
    plan = plan_is_current(plan_path)
    if plan is None:
        return None
    try:
        rebuilt = build_manifest(plan_path, plan)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return manifest if manifest == rebuilt else None


def prepare() -> dict[str, Any]:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    current_paths: set[Path] = set()
    items: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for plan_path in (
        sorted(PLAN_DIR.glob("*.final_sound_plan.json"))
        if PLAN_DIR.exists()
        else []
    ):
        plan = plan_is_current(plan_path)
        if plan is None:
            continue
        try:
            manifest = build_manifest(plan_path, plan)
            key = _key(
                str(manifest.get("concept_id") or ""),
                str(manifest.get("format") or ""),
            )
            destination = MANIFEST_DIR / f"{key}.final_render_manifest.json"
            atomic_write_json(destination, manifest)
            current_paths.add(destination.resolve())
            items.append({
                "concept_id": manifest.get("concept_id"),
                "format": manifest.get("format"),
                "manifest_file": str(destination.resolve()),
                "manifest_sha256": sha256_file(destination),
                "sound_assets": len(manifest.get("sound_track", [])),
                "sound_omissions": len(
                    manifest.get("omitted_sound_requirements", [])
                ),
            })
        except Exception as exc:
            failures.append({
                "plan": str(plan_path),
                "error_type": type(exc).__name__,
                "error": str(exc),
            })

    for stale in MANIFEST_DIR.glob("*.final_render_manifest.json"):
        if stale.resolve() not in current_paths:
            stale.unlink()

    result = {
        "status": (
            "FINAL_RENDER_MANIFESTS_READY"
            if items and not failures
            else "PARTIAL"
            if items
            else "FAILED"
            if failures
            else "WAITING_FOR_FINAL_SOUND_ASSETS"
        ),
        "prepared": len(items),
        "failed": len(failures),
        "items": items,
        "paid_provider_calls": 0,
        "media_rendered": False,
    }
    atomic_write_json(SUMMARY_FILE, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare rebuild-current local final render manifests"
    )
    parser.add_argument("--mode", choices=("prepare",), required=True)
    parser.parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
