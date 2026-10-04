"""Human Final Audio Gate: approve the exact paid narration before visuals use it (D-137).

The Narration Preview Gate approves the free local preview and the Spend Gate
approves the quote. The paid provider's returned audio then passed only the
automatic Audio QC (duration, silence, clipping, missing files), and visual
planning started from it without anyone listening. The vision requires the
exact final audio to be approved by a human.

This gate sits after Audio QC passes. Per video (concept + format) the human
listens to every returned segment and decides:

  APPROVE_FINAL_AUDIO  the audio is the narration of this video
  REWORK_SEGMENTS      named segments must be re-recorded (note required);
                       the next provider return replaces the audio
  REJECT_AUDIO         the return is unusable (note required)

An approval is bound to the hashes of the QC report and the timing map, so a
new provider return, a re-run of QC or any edit returns the video to PENDING.
Every decision is appended to an append-only history (D-133).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import append_jsonl, atomic_write_json, read_jsonl
from narration_audio_qc import QC_DIR, TIMING_DIR
from narration_audio_qc import snapshot as audio_qc_snapshot
from narration_render import OUTPUT_DIR, artifact_key, load_json, sha256_file

APPROVED_DIR = OUTPUT_DIR / "approved_final_narration"
HISTORY_FILE = OUTPUT_DIR / "final_narration_history.jsonl"
DECISIONS = {"APPROVE_FINAL_AUDIO", "REWORK_SEGMENTS", "REJECT_AUDIO"}
REVIEWER_ENV = "YOUTUBE_REVIEWER_ID"
DEFAULT_REVIEWER = "local-operator"


def reviewer() -> str:
    return os.getenv(REVIEWER_ENV, DEFAULT_REVIEWER).strip() or DEFAULT_REVIEWER


def _approved_path(concept_id: str, fmt: str) -> Path:
    return APPROVED_DIR / f"{artifact_key(concept_id, fmt)}.approved_final_narration.json"


def _binding(concept_id: str, fmt: str) -> dict[str, str] | None:
    key = artifact_key(concept_id, fmt)
    qc_path = QC_DIR / f"{key}.narration_audio_qc.json"
    timing_path = TIMING_DIR / f"{key}.narration_timing_map.json"
    if not qc_path.exists() or not timing_path.exists():
        return None
    return {
        "audio_qc_sha256": sha256_file(qc_path),
        "timing_map_sha256": sha256_file(timing_path),
    }


def _history(concept_id: str, fmt: str) -> list[dict[str, Any]]:
    return [
        event
        for event in read_jsonl(HISTORY_FILE)
        if event.get("concept_id") == concept_id and event.get("format") == fmt
    ]


def _segments(concept_id: str, fmt: str) -> list[dict[str, Any]]:
    key = artifact_key(concept_id, fmt)
    qc = load_json(QC_DIR / f"{key}.narration_audio_qc.json")
    timing = load_json(TIMING_DIR / f"{key}.narration_timing_map.json")
    windows = {str(s.get("segment_id")): s for s in timing.get("segments", []) if isinstance(s, dict)}
    rows = []
    for check in qc.get("checks", []):
        if not isinstance(check, dict):
            continue
        segment_id = str(check.get("segment_id") or "")
        window = windows.get(segment_id, {})
        rows.append(
            {
                "segment_id": segment_id,
                "attempt": check.get("attempt"),
                "expected_duration_seconds": check.get("expected_duration_seconds"),
                "actual_duration_seconds": check.get("actual_duration_seconds"),
                "audio_start_seconds": window.get("audio_start_seconds"),
                "audio_end_seconds": window.get("audio_end_seconds"),
            }
        )
    return rows


def decision_for(concept_id: str, fmt: str) -> tuple[str, dict[str, Any]]:
    """Current decision for a video, bound to the current QC and timing map."""
    binding = _binding(concept_id, fmt)
    if binding is None:
        return "PENDING", {}
    approved = _approved_path(concept_id, fmt)
    if approved.exists():
        record = load_json(approved)
        if record.get("binding") == binding:
            return "APPROVE_FINAL_AUDIO", record
    for event in reversed(_history(concept_id, fmt)):
        if event.get("binding") != binding:
            break
        if event.get("decision") in {"REWORK_SEGMENTS", "REJECT_AUDIO"}:
            return str(event["decision"]), event
        break
    return "PENDING", {}


def is_approved(concept_id: str, fmt: str) -> bool:
    return decision_for(concept_id, fmt)[0] == "APPROVE_FINAL_AUDIO"


def snapshot() -> dict[str, Any]:
    qc = audio_qc_snapshot()
    items = []
    for row in qc.get("items", []):
        if row.get("status") != "PASS":
            continue
        concept_id, fmt = str(row["concept_id"]), str(row["format"])
        decision, record = decision_for(concept_id, fmt)
        items.append(
            {
                "video_id": f"{concept_id}:{fmt}",
                "concept_id": concept_id,
                "format": fmt,
                "segments": _segments(concept_id, fmt),
                "decision": decision,
                "note": record.get("note", ""),
                "rework_segment_ids": record.get("rework_segment_ids", []),
                "reviewer": record.get("reviewer"),
                "reviewed_at": record.get("reviewed_at"),
                "history": _history(concept_id, fmt),
            }
        )
    expected = int(qc.get("passed") or 0) if qc.get("status") == "PASS" else 0
    approved = sum(item["decision"] == "APPROVE_FINAL_AUDIO" for item in items)
    complete = bool(items) and expected == len(items) and approved == len(items)
    return {
        "status": (
            "WAITING_FOR_AUDIO_QC"
            if not items
            else "FINAL_AUDIO_APPROVED"
            if complete
            else "AWAITING_HUMAN_FINAL_AUDIO"
        ),
        "complete": complete,
        "pending": sum(item["decision"] == "PENDING" for item in items),
        "approved": approved,
        "items": items,
    }


def apply_action(
    *,
    concept_id: str,
    format: str,
    decision: str,
    note: str | None = None,
    segment_ids: Any = None,
) -> dict[str, Any]:
    concept_id, fmt = str(concept_id or "").strip(), str(format or "").strip()
    value = str(decision or "").strip().upper()
    if value not in DECISIONS:
        raise ValueError("Decision must be APPROVE_FINAL_AUDIO, REWORK_SEGMENTS or REJECT_AUDIO")
    item = next(
        (row for row in snapshot()["items"] if row["concept_id"] == concept_id and row["format"] == fmt),
        None,
    )
    if item is None:
        raise ValueError("No QC-passed narration to review for this video")
    binding = _binding(concept_id, fmt)
    clean_note = str(note or "").strip()
    known = {segment["segment_id"] for segment in item["segments"]}
    chosen = [str(x) for x in (segment_ids or []) if str(x)]
    if value != "APPROVE_FINAL_AUDIO" and not clean_note:
        raise ValueError("Rework and Reject need a note saying what is wrong")
    if value == "REWORK_SEGMENTS":
        if not chosen:
            raise ValueError("Rework needs at least one segment to re-record")
        unknown = sorted(set(chosen) - known)
        if unknown:
            raise ValueError("Unknown segment(s): " + ", ".join(unknown))
    record = {
        "artifact": "final_narration_decision",
        "concept_id": concept_id,
        "format": fmt,
        "decision": value,
        "note": clean_note,
        "rework_segment_ids": chosen if value == "REWORK_SEGMENTS" else [],
        "reviewer": reviewer(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "binding": binding,
        "binding_sha256": hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest(),
    }
    approved = _approved_path(concept_id, fmt)
    if value == "APPROVE_FINAL_AUDIO":
        atomic_write_json(approved, record)
    elif approved.exists():
        approved.unlink()
    append_jsonl(HISTORY_FILE, {"recorded_at": record["reviewed_at"], "gate": "final_audio", **record})
    return snapshot()


def audio_file_path(concept_id: str, fmt: str, segment_id: str) -> Path:
    """The QC-checked audio file of one segment, for listening in the UI."""
    key = artifact_key(str(concept_id), str(fmt))
    qc_path = QC_DIR / f"{key}.narration_audio_qc.json"
    if not qc_path.exists():
        raise ValueError("No audio QC for this video")
    check = next(
        (c for c in load_json(qc_path).get("checks", []) if str(c.get("segment_id")) == str(segment_id)),
        None,
    )
    if check is None:
        raise ValueError("Unknown segment")
    path = Path(str(check.get("audio_file") or "")).resolve()
    managed = (OUTPUT_DIR / "narration_audio").resolve()
    if managed not in path.parents or not path.is_file():
        raise ValueError("Audio file is not a managed narration file")
    return path
