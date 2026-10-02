"""Zero-cost narration prototype preparation.

Creates a local preview manifest from Human-approved performance specs after the
pre-render engagement gate. This stage never calls a paid provider. A local TTS
renderer (Kokoro/Piper/etc.) may consume the manifest; when no renderer is
installed the workflow remains fail-closed at the preview-listen boundary.

Music/SFX entries are editorial suggestions only. They use placeholders/local
licensed assets and never trigger a paid asset call.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from typing import Any

from pipeline_integrity import atomic_write_json
from voice_performance import load_json, safe_slug, sha256_file
from voice_review import APPROVED_DIR

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"
ENGAGEMENT_DIR = OUTPUT_DIR / "pre_render_engagement"
MANIFEST_DIR = OUTPUT_DIR / "narration_preview_manifests"
SUMMARY_FILE = OUTPUT_DIR / "narration_preview_summary.json"


def _cue(purpose: str, index: int, total: int) -> dict[str, Any]:
    text = purpose.casefold()
    music = "neutral_bed"
    sfx: list[str] = []
    if index == 0:
        music = "opening_tension"
        sfx.append("optional_subtle_hook_impact")
    if any(term in text for term in ("problem", "tension", "stakes", "conflict")):
        music = "low_tension"
    if any(term in text for term in ("reveal", "solution", "answer", "payoff")):
        music = "payoff_lift"
        sfx.append("optional_subtle_reveal_accent")
    if index == total - 1:
        sfx.append("optional_music_resolve")
    return {
        "music_mood": music,
        "sfx_suggestions": sfx,
        "duck_under_narration": True,
        "editorial_only": True,
    }


def _engagement_passes(spec_path: Path) -> bool:
    matches = list(ENGAGEMENT_DIR.glob(f"{spec_path.stem}.engagement.json"))
    if len(matches) != 1:
        return False
    payload = load_json(matches[0])
    if not isinstance(payload, dict) or payload.get("status") != "PASS":
        return False
    provenance = payload.get("provenance", {})
    if not isinstance(provenance, dict):
        return False
    recorded = Path(str(provenance.get("approved_voice_spec") or "")).resolve()
    return bool(
        recorded == spec_path.resolve()
        and provenance.get("approved_voice_spec_sha256") == sha256_file(spec_path)
    )


def _manifest_path(concept_id: str, fmt: str) -> Path:
    key = f"{safe_slug(concept_id)}.{safe_slug(fmt)}"
    return MANIFEST_DIR / f"{key}.narration_preview.json"


def manifest_is_current(spec_path: Path, manifest_path: Path) -> bool:
    if not spec_path.is_file() or not manifest_path.is_file():
        return False
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        return False
    provenance = manifest.get("provenance", {})
    if not isinstance(provenance, dict):
        return False
    recorded = Path(str(provenance.get("approved_voice_spec") or "")).resolve()
    if recorded != spec_path.resolve():
        return False
    if provenance.get("approved_voice_spec_sha256") != sha256_file(spec_path):
        return False
    spec = load_json(spec_path)
    return bool(
        isinstance(spec, dict)
        and str(manifest.get("concept_id") or "") == str(spec.get("concept_id") or "")
        and str(manifest.get("format") or "") == str(spec.get("format") or "")
    )


def snapshot() -> dict[str, Any]:
    paths = (
        sorted(APPROVED_DIR.glob("*.approved_voice_spec.json"))
        if APPROVED_DIR.exists()
        else []
    )
    items: list[dict[str, Any]] = []
    waiting = 0
    stale = 0
    for spec_path in paths:
        if not _engagement_passes(spec_path):
            waiting += 1
            continue
        spec = load_json(spec_path)
        concept_id = str(spec.get("concept_id") or "").strip()
        fmt = str(spec.get("format") or "").strip()
        manifest_path = _manifest_path(concept_id, fmt)
        current = manifest_is_current(spec_path, manifest_path)
        stale += not current
        if current:
            items.append(
                {
                    "concept_id": concept_id,
                    "format": fmt,
                    "manifest": str(manifest_path),
                }
            )
    prepared = len(items)
    status = (
        "READY_FOR_FREE_PREVIEW_RENDER"
        if paths and waiting == 0 and stale == 0 and prepared == len(paths)
        else "WAITING_FOR_ENGAGEMENT_VALIDATION"
        if waiting
        else "STALE_PREVIEW_MANIFESTS"
        if paths
        else "WAITING_FOR_ENGAGEMENT_VALIDATION"
    )
    return {
        "status": status,
        "prepared": prepared,
        "waiting": waiting,
        "stale": stale,
        "items": items,
    }


def build_manifest(spec: dict[str, Any], spec_path: Path) -> dict[str, Any]:
    concept_id = str(spec.get("concept_id") or "").strip()
    fmt = str(spec.get("format") or "").strip()
    beats = spec.get("beats", [])
    directions = spec.get("directions", [])
    if not concept_id or not fmt or not isinstance(beats, list) or not beats:
        raise ValueError("Approved performance spec is incomplete")
    if not isinstance(directions, list) or len(directions) != len(beats):
        raise ValueError("Every preview beat requires a delivery direction")
    if spec.get("performance_gate", {}).get("status") != "PERFORMANCE_SPEC_APPROVED":
        raise ValueError("Human Performance Gate must be approved")

    segments: list[dict[str, Any]] = []
    for index, (beat, direction) in enumerate(zip(beats, directions, strict=True)):
        narration = str(beat.get("immutable_narration") or "").strip()
        if not narration:
            raise ValueError("Preview narration cannot be empty")
        segments.append({
            "segment_id": str(beat.get("beat_id") or index),
            "immutable_narration": narration,
            "delivery": {
                "emotion": direction.get("emotion"),
                "intensity": direction.get("intensity"),
                "speed": direction.get("speed"),
                "pause_before_ms": direction.get("pause_before_ms"),
                "pause_after_ms": direction.get("pause_after_ms"),
                "emphasis_terms": direction.get("emphasis_terms", []),
            },
            "sound_design": _cue(str(beat.get("purpose") or ""), index, len(beats)),
        })

    return {
        "artifact": "narration_preview_manifest",
        "concept_id": concept_id,
        "format": fmt,
        "title": spec.get("title"),
        "cost_policy": {
            "paid_calls_allowed": False,
            "paid_assets_allowed": False,
            "local_or_zero_cost_tts_only": True,
        },
        "renderer_preference": ["kokoro_local", "piper_local"],
        "renderer_note": (
            "Use an installed zero-cost local renderer. Do not fall through to a "
            "paid API when local rendering is unavailable."
        ),
        "segments": segments,
        "mix_policy": {
            "purpose": "story/tone/spacing preview, not final mastering",
            "music_and_sfx_are_suggestions": True,
            "asset_policy": "local, owned, public-domain, or verified compatible free licence",
            "silence_and_pause_plan_is_authoritative_for_preview": True,
        },
        "provenance": {
            "approved_voice_spec": str(spec_path.resolve()),
            "approved_voice_spec_sha256": sha256_file(spec_path),
        },
    }


def prepare() -> dict[str, Any]:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    paths = sorted(APPROVED_DIR.glob("*.approved_voice_spec.json")) if APPROVED_DIR.exists() else []
    items: list[dict[str, Any]] = []
    current: set[Path] = set()
    waiting = 0
    for spec_path in paths:
        if not _engagement_passes(spec_path):
            waiting += 1
            continue
        spec = load_json(spec_path)
        manifest = build_manifest(spec, spec_path)
        key = f"{safe_slug(manifest['concept_id'])}.{safe_slug(manifest['format'])}"
        dest = MANIFEST_DIR / f"{key}.narration_preview.json"
        atomic_write_json(dest, manifest)
        current.add(dest.resolve())
        items.append({"concept_id": manifest["concept_id"], "format": manifest["format"], "manifest": str(dest)})
    for stale in MANIFEST_DIR.glob("*.narration_preview.json"):
        if stale.resolve() not in current:
            stale.unlink()
    result = snapshot()
    atomic_write_json(SUMMARY_FILE, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare zero-cost narration prototypes")
    parser.add_argument("--mode", choices=("prepare",), required=True)
    parser.parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
