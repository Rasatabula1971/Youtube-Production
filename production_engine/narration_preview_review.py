"""Human gate for the zero-cost narration/audio prototype.

The operator listens to the free draft before any paid narration quote or spend
decision is allowed.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from typing import Any

from pipeline_integrity import atomic_write_json
from voice_performance import load_json, safe_slug, sha256_file
from voice_review import APPROVED_DIR as APPROVED_VOICE_DIR

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"
PREVIEW_DIR = OUTPUT_DIR / "narration_preview_manifests"
RENDER_DIR = OUTPUT_DIR / "narration_preview_audio"
RESPONSES_DIR = OUTPUT_DIR / "narration_preview_review_responses"
APPROVED_DIR = OUTPUT_DIR / "approved_narration_previews"
SUMMARY_FILE = OUTPUT_DIR / "narration_preview_gate_summary.json"
REVIEWER_ENV = "YOUTUBE_REVIEWER_ID"

DECISIONS = {"APPROVE_FINAL", "REWORK_PERFORMANCE", "REWORK_SCRIPT", "REWORK_MUSIC_SFX"}


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _render_metadata_path(audio_path: Path) -> Path:
    return audio_path.with_suffix(".meta.json")


def _current_manifest(manifest_path: Path) -> dict[str, Any] | None:
    if not manifest_path.is_file():
        return None
    try:
        manifest = load_json(manifest_path)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(manifest, dict):
        return None
    concept_id = str(manifest.get("concept_id") or "").strip()
    fmt = str(manifest.get("format") or "").strip()
    if not concept_id or not fmt:
        return None
    spec_path = APPROVED_VOICE_DIR / f"{_key(concept_id, fmt)}.approved_voice_spec.json"
    if not spec_path.is_file():
        return None
    provenance = manifest.get("provenance", {})
    if not isinstance(provenance, dict):
        return None
    recorded = Path(str(provenance.get("approved_voice_spec") or "")).resolve()
    if recorded != spec_path.resolve():
        return None
    if provenance.get("approved_voice_spec_sha256") != sha256_file(spec_path):
        return None
    try:
        spec = load_json(spec_path)
    except (OSError, json.JSONDecodeError):
        return None
    gate = spec.get("performance_gate", {}) if isinstance(spec, dict) else {}
    if not isinstance(gate, dict) or gate.get("status") != "PERFORMANCE_SPEC_APPROVED":
        return None
    if (
        str(spec.get("concept_id") or "").strip() != concept_id
        or str(spec.get("format") or "").strip() != fmt
    ):
        return None
    return manifest


def current_render(
    manifest_path: Path,
    audio_path: Path,
) -> dict[str, Any] | None:
    if _current_manifest(manifest_path) is None:
        return None
    metadata_path = _render_metadata_path(audio_path)
    if (
        not manifest_path.exists()
        or not audio_path.exists()
        or not metadata_path.exists()
    ):
        return None
    try:
        metadata = load_json(metadata_path)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(metadata, dict):
        return None
    if metadata.get("manifest_sha256") != sha256_file(manifest_path):
        return None
    if metadata.get("audio_sha256") != sha256_file(audio_path):
        return None
    return metadata


def snapshot() -> dict[str, Any]:
    manifests = sorted(PREVIEW_DIR.glob("*.narration_preview.json")) if PREVIEW_DIR.exists() else []
    items: list[dict[str, Any]] = []
    accepted = 0
    pending = 0
    for path in manifests:
        manifest = load_json(path)
        key = _key(str(manifest.get("concept_id") or ""), str(manifest.get("format") or ""))
        audio = RENDER_DIR / f"{key}.preview.wav"
        response_path = RESPONSES_DIR / f"{key}.preview_review.json"
        try:
            response = load_json(response_path) if response_path.exists() else {}
        except (OSError, json.JSONDecodeError):
            response = {}
        render_metadata = current_render(path, audio)
        response_current = (
            isinstance(response, dict)
            and render_metadata is not None
            and response.get("preview_manifest_sha256") == sha256_file(path)
            and response.get("preview_audio_sha256")
            == render_metadata.get("audio_sha256")
        )
        approved = bool(
            response_current and response.get("decision") == "APPROVE_FINAL"
        )
        if approved:
            accepted += 1
        else:
            pending += 1
        items.append({
            "concept_id": manifest.get("concept_id"),
            "format": manifest.get("format"),
            "audio_ready": render_metadata is not None,
            "audio": str(audio) if render_metadata is not None else None,
            "decision": (
                response.get("decision", "PENDING")
                if response_current
                else "PENDING"
            ),
            "approved_for_paid_quote": approved,
            "manifest": str(path),
            "manifest_sha256": sha256_file(path),
            "audio_sha256": (
                render_metadata.get("audio_sha256")
                if render_metadata is not None
                else None
            ),
        })
    return {
        "status": "APPROVED_FOR_PAID_QUOTE" if items and accepted == len(items) else "AWAITING_FREE_PREVIEW" if items else "WAITING_FOR_PREVIEW_MANIFESTS",
        "complete": bool(items) and accepted == len(items),
        "accepted": accepted,
        "pending": pending,
        "items": items,
    }


def apply_action(*, concept_id: str, format: str, decision: str, note: str = "") -> dict[str, Any]:
    decision = decision.strip().upper()
    if decision not in DECISIONS:
        raise ValueError("Invalid preview decision")
    key = _key(concept_id, format)
    manifest_path = PREVIEW_DIR / f"{key}.narration_preview.json"
    audio_path = RENDER_DIR / f"{key}.preview.wav"
    if not manifest_path.exists():
        raise ValueError("Preview manifest not found")
    manifest = _current_manifest(manifest_path)
    if manifest is None:
        raise ValueError("Preview manifest is stale against the current approved Voice Performance spec")
    render_metadata = current_render(manifest_path, audio_path)
    if decision == "APPROVE_FINAL" and render_metadata is None:
        raise ValueError(
            "Cannot approve final rendering before listening artifact exists "
            "for the current preview manifest"
        )
    if decision != "APPROVE_FINAL" and not note.strip():
        raise ValueError("Rework decisions require a note")
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "concept_id": concept_id,
        "format": format,
        "reviewer": os.getenv(REVIEWER_ENV, "local-operator"),
        "decision": decision,
        "note": note.strip(),
        "preview_manifest_sha256": sha256_file(manifest_path),
        "approved_voice_spec_sha256": manifest.get("provenance", {}).get(
            "approved_voice_spec_sha256"
        ),
        "preview_audio": (
            str(audio_path) if render_metadata is not None else None
        ),
        "preview_audio_sha256": (
            render_metadata.get("audio_sha256")
            if render_metadata is not None
            else None
        ),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_json(RESPONSES_DIR / f"{key}.preview_review.json", payload)
    approved_path = APPROVED_DIR / f"{key}.approved_preview.json"
    if decision == "APPROVE_FINAL":
        APPROVED_DIR.mkdir(parents=True, exist_ok=True)
        atomic_write_json(approved_path, payload)
    elif approved_path.exists():
        approved_path.unlink()
    result = snapshot()
    atomic_write_json(SUMMARY_FILE, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Free narration prototype review")
    parser.add_argument("--mode", choices=("status",), required=True)
    parser.parse_args()
    print(json.dumps(snapshot(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
