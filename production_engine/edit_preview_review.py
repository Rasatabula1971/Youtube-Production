"""Human gate for local structural edit previews.

Approvals are bound to the exact preview result hash. Replacing narration,
visual assets, assembly, or the rendered preview makes the approval stale.

Rework decisions are recorded as explicit routing requests; this module does
not silently mutate upstream creative artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from edit_preview_render import preview_result_is_current
from visual_acquisition import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
RESULT_DIR = OUTPUT / "edit_preview_results"
REVIEW_DIR = OUTPUT / "edit_preview_reviews"
APPROVED_DIR = OUTPUT / "approved_edit_previews"
REWORK_DIR = OUTPUT / "edit_preview_rework_requests"

DECISIONS = {
    "APPROVE_EDIT_DIRECTION",
    "RETURN_TO_VISUALS",
    "RETURN_TO_NARRATION",
    "RETURN_TO_SOUND",
}


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _current_result(path: Path) -> dict[str, Any]:
    result = preview_result_is_current(path)
    if result is None:
        raise ValueError("STALE_EDIT_PREVIEW_RESULT")
    return result


def _review_path(result: dict[str, Any]) -> Path:
    return REVIEW_DIR / (
        f"{_key(str(result.get('concept_id') or ''), str(result.get('format') or ''))}."
        "edit_preview_review.json"
    )


def _approval_path(result: dict[str, Any]) -> Path:
    return APPROVED_DIR / (
        f"{_key(str(result.get('concept_id') or ''), str(result.get('format') or ''))}."
        "approved_edit_preview.json"
    )


def _rework_path(result: dict[str, Any]) -> Path:
    return REWORK_DIR / (
        f"{_key(str(result.get('concept_id') or ''), str(result.get('format') or ''))}."
        "edit_preview_rework.json"
    )


def _current_review(
    result_path: Path,
    result: dict[str, Any],
) -> dict[str, Any] | None:
    path = _review_path(result)
    if not path.exists():
        return None
    review = load_json(path)
    if (
        review.get("source_preview_result_sha256")
        != sha256_file(result_path)
    ):
        return None
    return review


def snapshot() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    paths = (
        sorted(RESULT_DIR.glob("*.edit_preview_result.json"))
        if RESULT_DIR.exists()
        else []
    )
    for path in paths:
        try:
            result = _current_result(path)
        except ValueError:
            continue
        review = _current_review(path, result)
        items.append({
            "concept_id": result.get("concept_id"),
            "format": result.get("format"),
            "result_file": str(path),
            "preview_file": result.get("preview_file"),
            "placeholder_segments": int(
                result.get("placeholder_segments") or 0
            ),
            "duration_seconds": float(
                result.get("duration_seconds") or 0
            ),
            "decision": (
                review.get("decision")
                if isinstance(review, dict)
                else "PENDING"
            ),
            "note": (
                review.get("note", "")
                if isinstance(review, dict)
                else ""
            ),
            "complete": bool(review),
        })

    pending = sum(item["decision"] == "PENDING" for item in items)
    approved = sum(
        item["decision"] == "APPROVE_EDIT_DIRECTION"
        for item in items
    )
    rework = sum(
        item["decision"] in {
            "RETURN_TO_VISUALS",
            "RETURN_TO_NARRATION",
            "RETURN_TO_SOUND",
        }
        for item in items
    )
    return {
        "status": (
            "COMPLETE"
            if items and pending == 0
            else "AWAITING_HUMAN_DECISION"
            if items
            else "WAITING_FOR_EDIT_PREVIEWS"
        ),
        "complete": bool(items) and pending == 0,
        "total": len(items),
        "pending": pending,
        "approved": approved,
        "rework": rework,
        "items": items,
    }


def apply_action(
    *,
    result_file: str,
    decision: str,
    note: str,
) -> dict[str, Any]:
    path = Path(result_file).resolve()
    result = _current_result(path)
    value = str(decision or "").strip().upper()
    if value not in DECISIONS:
        raise ValueError("Unsupported Edit Preview Gate decision")
    clean_note = str(note or "").strip()
    if value != "APPROVE_EDIT_DIRECTION" and not clean_note:
        raise ValueError("Return/rework decisions require a note")

    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    review = {
        "artifact": "edit_preview_review",
        "concept_id": result.get("concept_id"),
        "format": result.get("format"),
        "decision": value,
        "note": clean_note,
        "source_preview_result": str(path),
        "source_preview_result_sha256": sha256_file(path),
        "source_preview_sha256": result.get("preview_sha256"),
    }
    atomic_write_json(_review_path(result), review)

    approval_path = _approval_path(result)
    rework_path = _rework_path(result)
    if value == "APPROVE_EDIT_DIRECTION":
        APPROVED_DIR.mkdir(parents=True, exist_ok=True)
        approval = {
            "artifact": "approved_edit_preview",
            "status": "EDIT_DIRECTION_APPROVED",
            "concept_id": result.get("concept_id"),
            "format": result.get("format"),
            "preview_file": result.get("preview_file"),
            "placeholder_segments_at_approval": int(
                result.get("placeholder_segments") or 0
            ),
            "source_preview_result": str(path),
            "source_preview_result_sha256": sha256_file(path),
        }
        atomic_write_json(approval_path, approval)
        if rework_path.exists():
            rework_path.unlink()
    else:
        REWORK_DIR.mkdir(parents=True, exist_ok=True)
        target = {
            "RETURN_TO_VISUALS": "VISUALS_STORYBOARD",
            "RETURN_TO_NARRATION": "NARRATION_PERFORMANCE",
            "RETURN_TO_SOUND": "SOUND_DESIGN",
        }[value]
        request = {
            "artifact": "edit_preview_rework_request",
            "status": "HUMAN_REWORK_REQUIRED",
            "concept_id": result.get("concept_id"),
            "format": result.get("format"),
            "target": target,
            "human_instruction": clean_note,
            "source_preview_result": str(path),
            "source_preview_result_sha256": sha256_file(path),
        }
        atomic_write_json(rework_path, request)
        if approval_path.exists():
            approval_path.unlink()

    return snapshot()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Human Edit Preview Gate"
    )
    parser.add_argument("--mode", choices=("status",), default="status")
    parser.parse_args()
    print(json.dumps(snapshot(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
