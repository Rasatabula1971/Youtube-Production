"""Human Visual Plan Gate: approve the complete visual plan before paid narration (D-138).

Vision: the complete visual plan is approved before money is spent. Until now
the visual manifest and storyboard were built only after the paid narration
had been quoted, authorized, returned and QC-checked, because they took their
timing from the returned audio. Nothing approved the plan as a whole.

This gate runs after the free narration preview is approved and before the
Narration Spend Gate. Per video it builds the complete plan from the approved
format plan (the same requirements the visual manifest uses) and times each
shot from the approved free preview's per-beat audio:

  * every shot in order: beat, purpose, visual treatment, claims, and its
    window in the preview timeline;
  * the visual source route each shot will try, first tier first;
  * the per-video budget (D-136) the visuals will draw on.

APPROVE_VISUAL_PLAN binds the approval to the approved format plan, the
approved preview audio and the plan content. REWORK_VISUAL_PLAN records a note
and holds the spend until the format plan is reworked. The server refuses to
authorize narration spend for a video whose plan is not approved.

After the paid narration returns and is approved (D-137), the storyboard is
retimed to the real audio as before; its shots are the approved plan's beats.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import append_jsonl, atomic_write_json, read_jsonl
import video_budget
from narration_preview_render import SEGMENT_AUDIO_DIR
from narration_preview_review import APPROVED_DIR as APPROVED_PREVIEW_DIR
from narration_preview_review import PREVIEW_DIR
from visual_acquisition import (
    APPROVED_FORMAT_DIR,
    OUTPUT_DIR,
    build_manifest,
    load_config,
    load_json,
    safe_slug,
    sha256_file,
)

APPROVED_DIR = OUTPUT_DIR / "approved_visual_plans"
HISTORY_FILE = OUTPUT_DIR / "visual_plan_history.jsonl"
DECISIONS = {"APPROVE_VISUAL_PLAN", "REWORK_VISUAL_PLAN"}
REVIEWER_ENV = "YOUTUBE_REVIEWER_ID"
DEFAULT_REVIEWER = "local-operator"


def reviewer() -> str:
    return os.getenv(REVIEWER_ENV, DEFAULT_REVIEWER).strip() or DEFAULT_REVIEWER


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _wav_seconds(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate()
            return round(handle.getnframes() / rate, 3) if rate else None
    except (OSError, wave.Error, EOFError):
        return None


def _approved_previews() -> dict[str, dict[str, Any]]:
    """Approved free previews keyed by concept.format slug."""
    found: dict[str, dict[str, Any]] = {}
    if not APPROVED_PREVIEW_DIR.exists():
        return found
    for path in sorted(APPROVED_PREVIEW_DIR.glob("*.approved_preview.json")):
        payload = load_json(path)
        if isinstance(payload, dict) and payload.get("decision") == "APPROVE_FINAL":
            found[path.name[: -len(".approved_preview.json")]] = payload
    return found


def _preview_timing(key: str) -> dict[str, dict[str, Any]]:
    """Per-beat windows in the approved preview timeline, from its segment WAVs."""
    manifest_path = PREVIEW_DIR / f"{key}.narration_preview.json"
    if not manifest_path.exists():
        return {}
    segments = load_json(manifest_path).get("segments", [])
    cursor = 0.0
    windows: dict[str, dict[str, Any]] = {}
    for index, segment in enumerate(segments if isinstance(segments, list) else []):
        if not isinstance(segment, dict):
            continue
        segment_id = str(segment.get("segment_id") or index)
        wav = SEGMENT_AUDIO_DIR / f"{safe_slug(key)}.{index:03d}.{safe_slug(segment_id)}.segment.wav"
        seconds = _wav_seconds(wav)
        start = cursor
        if seconds is not None:
            cursor += seconds
        windows[segment_id] = {
            "preview_start_seconds": round(start, 3) if seconds is not None else None,
            "preview_end_seconds": round(cursor, 3) if seconds is not None else None,
            "preview_seconds": seconds,
        }
    return windows


def _format_plans() -> list[tuple[Path, dict[str, Any]]]:
    if not APPROVED_FORMAT_DIR.exists():
        return []
    plans = []
    for path in sorted(APPROVED_FORMAT_DIR.glob("*.approved_format_plan.json")):
        payload = load_json(path)
        if isinstance(payload, dict):
            plans.append((path, payload))
    return plans


def build_plans() -> list[dict[str, Any]]:
    """The complete visual plan for every video whose free preview is approved."""
    previews = _approved_previews()
    config = load_config()
    plans = []
    for path, format_plan in _format_plans():
        for branch in format_plan.get("branches", []) or []:
            if not isinstance(branch, dict):
                continue
            concept_id = str(format_plan.get("concept_id") or "")
            fmt = str(branch.get("format") or "")
            key = _key(concept_id, fmt)
            preview = previews.get(key)
            if preview is None:
                continue
            try:
                manifest = build_manifest(format_plan, path, branch, config)
            except ValueError as exc:
                plans.append({"concept_id": concept_id, "format": fmt, "key": key, "error": str(exc)})
                continue
            windows = _preview_timing(key)
            shots = []
            for requirement in manifest["requirements"]:
                window = windows.get(str(requirement["beat_id"]), {})
                shots.append(
                    {
                        "beat_id": requirement["beat_id"],
                        "narrative_purpose": requirement["narrative_purpose"],
                        "visual_treatment": requirement["visual_treatment"],
                        "claim_ids": requirement["claim_ids"],
                        "first_source_tier": (requirement["route_policy"] or [None])[0],
                        **window,
                    }
                )
            plan = {
                "artifact": "visual_plan",
                "concept_id": concept_id,
                "format": fmt,
                "key": key,
                "video_id": video_budget.video_id(concept_id, fmt),
                "duration_intent_seconds": manifest["duration_intent_seconds"],
                "preview_total_seconds": max(
                    (s.get("preview_end_seconds") or 0 for s in shots), default=0
                ),
                "untimed_shots": sum(s.get("preview_seconds") is None for s in shots),
                "preferred_source_order": manifest["preferred_source_order"],
                "cost_policy": manifest["cost_policy"],
                "shots": shots,
                "provenance": {
                    "approved_format_plan": str(path),
                    "approved_format_plan_sha256": sha256_file(path),
                    "approved_preview_audio_sha256": preview.get("preview_audio_sha256"),
                },
            }
            plan["plan_sha256"] = hashlib.sha256(
                json.dumps(plan, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            plans.append(plan)
    return plans


def _approved_path(key: str) -> Path:
    return APPROVED_DIR / f"{key}.approved_visual_plan.json"


def _history(key: str) -> list[dict[str, Any]]:
    return [event for event in read_jsonl(HISTORY_FILE) if event.get("key") == key]


def _decision(plan: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    approved = _approved_path(plan["key"])
    if approved.exists():
        record = load_json(approved)
        if record.get("plan_sha256") == plan.get("plan_sha256"):
            return "APPROVE_VISUAL_PLAN", record
    history = _history(plan["key"])
    if history and history[-1].get("plan_sha256") == plan.get("plan_sha256"):
        if history[-1].get("decision") == "REWORK_VISUAL_PLAN":
            return "REWORK_VISUAL_PLAN", history[-1]
    return "PENDING", {}


def snapshot() -> dict[str, Any]:
    items = []
    for plan in build_plans():
        if "error" in plan:
            items.append({**plan, "decision": "BLOCKED"})
            continue
        decision, record = _decision(plan)
        try:
            budget = video_budget.summary(plan["video_id"], ledger=video_budget.ledger_in(OUTPUT_DIR))
        except (OSError, ValueError):
            budget = {}
        items.append(
            {
                **plan,
                "decision": decision,
                "note": record.get("note", ""),
                "reviewer": record.get("reviewer"),
                "reviewed_at": record.get("reviewed_at"),
                "budget": budget,
                "history": _history(plan["key"]),
            }
        )
    approved = sum(item["decision"] == "APPROVE_VISUAL_PLAN" for item in items)
    return {
        "status": (
            "WAITING_FOR_APPROVED_PREVIEW"
            if not items
            else "VISUAL_PLANS_APPROVED"
            if approved == len(items)
            else "AWAITING_HUMAN_VISUAL_PLAN"
        ),
        "complete": bool(items) and approved == len(items),
        "pending": sum(item["decision"] == "PENDING" for item in items),
        "rework": sum(item["decision"] == "REWORK_VISUAL_PLAN" for item in items),
        "approved": approved,
        "items": items,
    }


def is_approved(concept_id: str, fmt: str) -> bool:
    key = _key(str(concept_id), str(fmt))
    plan = next((p for p in build_plans() if p.get("key") == key and "error" not in p), None)
    return plan is not None and _decision(plan)[0] == "APPROVE_VISUAL_PLAN"


def apply_action(*, concept_id: str, format: str, decision: str, note: str | None = None) -> dict[str, Any]:
    value = str(decision or "").strip().upper()
    if value not in DECISIONS:
        raise ValueError("Decision must be APPROVE_VISUAL_PLAN or REWORK_VISUAL_PLAN")
    key = _key(str(concept_id or "").strip(), str(format or "").strip())
    plan = next((p for p in build_plans() if p.get("key") == key), None)
    if plan is None:
        raise ValueError("No visual plan for this video: approve its free narration preview first")
    if "error" in plan:
        raise ValueError("The visual plan cannot be built: " + plan["error"])
    clean_note = str(note or "").strip()
    if value == "REWORK_VISUAL_PLAN" and not clean_note:
        raise ValueError("Rework needs a note saying what the plan must change")
    record = {
        "artifact": "visual_plan_decision",
        "key": key,
        "concept_id": plan["concept_id"],
        "format": plan["format"],
        "decision": value,
        "note": clean_note,
        "reviewer": reviewer(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "plan_sha256": plan["plan_sha256"],
    }
    approved = _approved_path(key)
    if value == "APPROVE_VISUAL_PLAN":
        atomic_write_json(approved, {**record, "plan": plan})
    elif approved.exists():
        approved.unlink()
    append_jsonl(HISTORY_FILE, {"recorded_at": record["reviewed_at"], "gate": "visual_plan", **record})
    return snapshot()
