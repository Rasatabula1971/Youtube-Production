"""Build deterministic final-sound requirements from the current Slice 20 handoff.

Slice 21 does not call a sound provider, buy a licence, generate music/SFX,
render final video, upload, or publish. It only converts the human-approved
sound-design intent into stable requirements that can later be resolved by a
human-supplied licensed asset or an explicit human omission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from final_production_handoff import handoff_is_current
from visual_acquisition import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
HANDOFF_DIR = OUTPUT / "final_production_handoffs"
PLAN_DIR = OUTPUT / "final_sound_plans"
SUMMARY_FILE = OUTPUT / "final_sound_plan_summary.json"


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _requirement(
    *,
    segment_id: str,
    kind: str,
    index: int,
    direction: str,
    duck_under_narration: bool,
) -> dict[str, Any]:
    requirement_id = (
        f"{segment_id}:music"
        if kind == "MUSIC"
        else f"{segment_id}:sfx:{index:03d}"
    )
    base = {
        "requirement_id": requirement_id,
        "segment_id": segment_id,
        "kind": kind,
        "index": index,
        "direction": direction,
        "duck_under_narration": duck_under_narration,
        "resolution_policy": {
            "licensed_asset_allowed": True,
            "commercial_use_confirmation_required": True,
            "licence_reference_required": True,
            "explicit_omit_allowed": True,
            "omit_note_required": True,
            "app_provider_call_allowed": False,
        },
    }
    return {**base, "fingerprint": _fingerprint(base)}


def build_plan(
    handoff_path: Path,
    handoff: dict[str, Any],
) -> dict[str, Any]:
    current = handoff_is_current(handoff_path)
    if current is None or current != handoff:
        raise ValueError("STALE_FINAL_PRODUCTION_HANDOFF")
    if (
        handoff.get("status")
        != "READY_FOR_FINAL_SOUND_PROVIDER_OR_ASSET_REGISTRATION"
    ):
        raise ValueError("Final production handoff is not ready for sound planning")

    concept_id = str(handoff.get("concept_id") or "").strip()
    fmt = str(handoff.get("format") or "").strip()
    if not concept_id or not fmt:
        raise ValueError("Final production handoff identity is missing")

    requirements: list[dict[str, Any]] = []
    directions = handoff.get("sound_design_intent", [])
    if not isinstance(directions, list):
        raise ValueError("Final sound-design intent must be a list")

    seen_ids: set[str] = set()
    for item in directions:
        if not isinstance(item, dict):
            continue
        segment_id = str(item.get("segment_id") or "").strip()
        if not segment_id:
            raise ValueError("Final sound direction is missing segment_id")
        duck = bool(item.get("duck_under_narration", True))

        music = str(item.get("music_direction") or "").strip()
        if music:
            requirement = _requirement(
                segment_id=segment_id,
                kind="MUSIC",
                index=0,
                direction=music,
                duck_under_narration=duck,
            )
            if requirement["requirement_id"] in seen_ids:
                raise ValueError("Duplicate final sound requirement ID")
            seen_ids.add(str(requirement["requirement_id"]))
            requirements.append(requirement)

        sfx_values = item.get("sfx_direction", [])
        if sfx_values is None:
            sfx_values = []
        if not isinstance(sfx_values, list):
            raise ValueError("sfx_direction must be a list")
        for index, raw in enumerate(sfx_values, start=1):
            direction = str(raw or "").strip()
            if not direction:
                continue
            requirement = _requirement(
                segment_id=segment_id,
                kind="SFX",
                index=index,
                direction=direction,
                duck_under_narration=duck,
            )
            if requirement["requirement_id"] in seen_ids:
                raise ValueError("Duplicate final sound requirement ID")
            seen_ids.add(str(requirement["requirement_id"]))
            requirements.append(requirement)

    return {
        "artifact": "final_sound_plan",
        "concept_id": concept_id,
        "format": fmt,
        "status": (
            "WAITING_FOR_FINAL_SOUND_ASSETS"
            if requirements
            else "FINAL_SOUND_NOT_REQUIRED"
        ),
        "requirements": requirements,
        "requirements_count": len(requirements),
        "execution_policy": {
            "provider_neutral": True,
            "app_provider_call_authorized": False,
            "paid_execution_performed": False,
            "final_render_allowed": False,
            "upload_allowed": False,
            "publish_allowed": False,
        },
        "provenance": {
            "final_production_handoff": str(handoff_path.resolve()),
            "final_production_handoff_sha256": sha256_file(handoff_path),
        },
    }


def plan_is_current(path: Path) -> dict[str, Any] | None:
    if (
        not path.is_file()
        or path.parent.resolve() != PLAN_DIR.resolve()
    ):
        return None
    try:
        plan = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if (
        not isinstance(plan, dict)
        or plan.get("artifact") != "final_sound_plan"
        or plan.get("status")
        not in {"WAITING_FOR_FINAL_SOUND_ASSETS", "FINAL_SOUND_NOT_REQUIRED"}
    ):
        return None

    provenance = plan.get("provenance", {})
    if not isinstance(provenance, dict):
        return None
    handoff_path = Path(
        str(provenance.get("final_production_handoff") or "")
    )
    if (
        not handoff_path.is_file()
        or handoff_path.parent.resolve() != HANDOFF_DIR.resolve()
        or provenance.get("final_production_handoff_sha256")
        != sha256_file(handoff_path)
    ):
        return None

    handoff = handoff_is_current(handoff_path)
    if handoff is None:
        return None
    try:
        rebuilt = build_plan(handoff_path, handoff)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return plan if plan == rebuilt else None


def prepare() -> dict[str, Any]:
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    current_paths: set[Path] = set()
    items: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    handoff_paths = (
        sorted(HANDOFF_DIR.glob("*.final_production_handoff.json"))
        if HANDOFF_DIR.exists()
        else []
    )
    for handoff_path in handoff_paths:
        handoff = handoff_is_current(handoff_path)
        if handoff is None:
            continue
        if (
            handoff.get("status")
            != "READY_FOR_FINAL_SOUND_PROVIDER_OR_ASSET_REGISTRATION"
        ):
            continue
        try:
            plan = build_plan(handoff_path, handoff)
            key = _key(
                str(plan.get("concept_id") or ""),
                str(plan.get("format") or ""),
            )
            destination = PLAN_DIR / f"{key}.final_sound_plan.json"
            atomic_write_json(destination, plan)
            current_paths.add(destination.resolve())
            items.append(
                {
                    "concept_id": plan.get("concept_id"),
                    "format": plan.get("format"),
                    "status": plan.get("status"),
                    "requirements": plan.get("requirements_count"),
                    "plan_file": str(destination.resolve()),
                }
            )
        except Exception as exc:
            failures.append(
                {
                    "handoff": str(handoff_path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    for stale in PLAN_DIR.glob("*.final_sound_plan.json"):
        if stale.resolve() not in current_paths:
            stale.unlink()

    result = {
        "status": (
            "FINAL_SOUND_PLANS_READY"
            if items and not failures
            else "PARTIAL"
            if items
            else "FAILED"
            if failures
            else "WAITING_FOR_FINAL_PRODUCTION_HANDOFF"
        ),
        "prepared": len(items),
        "failed": len(failures),
        "paid_provider_calls": 0,
        "final_renders": 0,
        "items": items,
        "failures": failures,
    }
    atomic_write_json(SUMMARY_FILE, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare deterministic final sound requirements"
    )
    parser.add_argument("--mode", choices=("prepare",), required=True)
    parser.parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
