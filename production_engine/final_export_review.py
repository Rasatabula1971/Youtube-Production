"""Human Final Export Gate for Slice 22 local final render candidates.

Approval is bound to the exact current final render result and rendered bytes.
Rework decisions route the creative layer back without uploading or publishing.

When a finished edit has come back from Tesseract (D-144), that edit is the
candidate instead of the automated render: approval binds the edit's record
and bytes, and an approval of the automated render no longer counts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from final_render import RESULT_DIR, result_is_current
import tesseract_exchange
from visual_acquisition import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
REVIEW_DIR = OUTPUT / "final_export_reviews"
APPROVED_DIR = OUTPUT / "approved_final_exports"
REWORK_DIR = OUTPUT / "final_export_rework_requests"

DECISIONS = {
    "APPROVE_EXPORT",
    "RETURN_TO_VISUALS",
    "RETURN_TO_NARRATION",
    "RETURN_TO_SOUND",
    "RETURN_TO_EDITOR",
}


def candidate_is_current(path: Path) -> dict[str, Any] | None:
    """The automated render result or a returned edit, if still current."""
    if path.parent.resolve() == tesseract_exchange.RETURN_DIR.resolve():
        return tesseract_exchange.return_is_current(path)
    if path.parent.resolve() != RESULT_DIR.resolve():
        return None
    result = result_is_current(path)
    if result is None:
        return None
    returned = tesseract_exchange.current_return(
        str(result.get("concept_id") or ""), str(result.get("format") or "")
    )
    # A returned edit replaces the automated render as the candidate.
    return None if returned is not None else result


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _review_path(result: dict[str, Any]) -> Path:
    return REVIEW_DIR / (
        f"{_key(str(result.get('concept_id') or ''), str(result.get('format') or ''))}."
        "final_export_review.json"
    )


def _approval_path(result: dict[str, Any]) -> Path:
    return APPROVED_DIR / (
        f"{_key(str(result.get('concept_id') or ''), str(result.get('format') or ''))}."
        "approved_final_export.json"
    )


def _rework_path(result: dict[str, Any]) -> Path:
    return REWORK_DIR / (
        f"{_key(str(result.get('concept_id') or ''), str(result.get('format') or ''))}."
        "final_export_rework.json"
    )


def _current_review(
    result_path: Path,
    result: dict[str, Any],
) -> dict[str, Any] | None:
    path = _review_path(result)
    if not path.is_file():
        return None
    review = load_json(path)
    if (
        review.get("source_final_render_result_sha256")
        != sha256_file(result_path)
        or review.get("source_render_sha256")
        != result.get("render_sha256")
    ):
        return None
    return review


def approval_is_current(path: Path) -> dict[str, Any] | None:
    if (
        not path.is_file()
        or path.parent.resolve() != APPROVED_DIR.resolve()
    ):
        return None
    try:
        approval = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if (
        not isinstance(approval, dict)
        or approval.get("artifact") != "approved_final_export"
        or approval.get("status") != "FINAL_EXPORT_APPROVED"
    ):
        return None
    result_path = Path(
        str(approval.get("source_final_render_result") or "")
    )
    result = candidate_is_current(result_path)
    if (
        result is None
        or approval.get("source_final_render_result_sha256")
        != sha256_file(result_path)
        or approval.get("render_file") != result.get("render_file")
        or approval.get("render_sha256") != result.get("render_sha256")
    ):
        return None
    return approval


def snapshot() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    paths = (
        sorted(RESULT_DIR.glob("*.final_render_result.json"))
        if RESULT_DIR.exists()
        else []
    )
    for automated_path in paths:
        automated = result_is_current(automated_path)
        if automated is None:
            continue
        returned = tesseract_exchange.current_return(
            str(automated.get("concept_id") or ""),
            str(automated.get("format") or ""),
        )
        path, result = returned if returned is not None else (automated_path, automated)
        review = _current_review(path, result)
        approval_path = _approval_path(result)
        approval = (
            approval_is_current(approval_path)
            if approval_path.exists()
            else None
        )
        review_decision = (
            str(review.get("decision") or "PENDING")
            if isinstance(review, dict)
            else "PENDING"
        )
        if (
            review_decision == "APPROVE_EXPORT"
            and approval is None
        ):
            review_decision = "PENDING"

        items.append({
            "concept_id": result.get("concept_id"),
            "format": result.get("format"),
            "result_file": str(path.resolve()),
            "render_file": result.get("render_file"),
            "render_sha256": result.get("render_sha256"),
            "render_bytes": int(result.get("render_bytes") or 0),
            "duration_seconds": float(
                result.get("duration_seconds") or 0
            ),
            "sound_assets_mixed": int(
                automated.get("sound_assets_mixed") or 0
            ),
            "sound_omissions": int(
                automated.get("sound_omissions") or 0
            ),
            "source": "EDITOR" if returned is not None else "AUTOMATED",
            "automated_render_file": automated.get("render_file"),
            "editor_note": result.get("note") if returned is not None else None,
            "quality_checks": result.get("quality_checks") if returned is not None else None,
            "scene_changes": result.get("scene_changes") if returned is not None else None,
            "decision": review_decision,
            "note": (
                review.get("note", "")
                if isinstance(review, dict)
                else ""
            ),
            "export_approved": approval is not None,
            "approved_export_file": (
                str(approval_path.resolve())
                if approval is not None
                else None
            ),
        })

    pending = sum(item["decision"] == "PENDING" for item in items)
    approved = sum(bool(item["export_approved"]) for item in items)
    rework = sum(
        item["decision"] in {
            "RETURN_TO_VISUALS",
            "RETURN_TO_NARRATION",
            "RETURN_TO_SOUND",
            "RETURN_TO_EDITOR",
        }
        for item in items
    )
    return {
        "status": (
            "FINAL_EXPORT_APPROVED"
            if items and approved == len(items) and rework == 0
            else "COMPLETE"
            if items and pending == 0
            else "AWAITING_HUMAN_FINAL_EXPORT_REVIEW"
            if items
            else "WAITING_FOR_FINAL_RENDER"
        ),
        "complete": bool(items) and pending == 0,
        "total": len(items),
        "pending": pending,
        "approved": approved,
        "rework": rework,
        "upload_performed": False,
        "publish_performed": False,
        "items": items,
    }


def apply_action(
    *,
    result_file: str,
    decision: str,
    note: str,
) -> dict[str, Any]:
    path = Path(result_file).resolve()
    result = candidate_is_current(path)
    if result is None:
        raise ValueError("STALE_FINAL_RENDER_RESULT")
    value = str(decision or "").strip().upper()
    if value not in DECISIONS:
        raise ValueError("Unsupported Final Export Gate decision")
    clean_note = str(note or "").strip()
    if value != "APPROVE_EXPORT" and not clean_note:
        raise ValueError("Final export rework decisions require a note")

    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    review = {
        "artifact": "final_export_review",
        "concept_id": result.get("concept_id"),
        "format": result.get("format"),
        "decision": value,
        "note": clean_note,
        "source_final_render_result": str(path),
        "source_final_render_result_sha256": sha256_file(path),
        "source_render_sha256": result.get("render_sha256"),
    }
    atomic_write_json(_review_path(result), review)

    approval_path = _approval_path(result)
    rework_path = _rework_path(result)
    if value == "APPROVE_EXPORT":
        APPROVED_DIR.mkdir(parents=True, exist_ok=True)
        approval = {
            "artifact": "approved_final_export",
            "status": "FINAL_EXPORT_APPROVED",
            "concept_id": result.get("concept_id"),
            "format": result.get("format"),
            "render_file": result.get("render_file"),
            "render_sha256": result.get("render_sha256"),
            "render_bytes": result.get("render_bytes"),
            "source_final_render_result": str(path),
            "source_final_render_result_sha256": sha256_file(path),
            "upload_authorized": False,
            "publish_authorized": False,
        }
        atomic_write_json(approval_path, approval)
        if rework_path.exists():
            rework_path.unlink()
    else:
        REWORK_DIR.mkdir(parents=True, exist_ok=True)
        target = {
            "RETURN_TO_VISUALS": "FINAL_VISUALS",
            "RETURN_TO_NARRATION": "FINAL_NARRATION",
            "RETURN_TO_SOUND": "FINAL_SOUND",
            "RETURN_TO_EDITOR": "FINAL_EDIT",
        }[value]
        request = {
            "artifact": "final_export_rework_request",
            "status": "HUMAN_REWORK_REQUIRED",
            "concept_id": result.get("concept_id"),
            "format": result.get("format"),
            "target": target,
            "human_instruction": clean_note,
            "source_final_render_result": str(path),
            "source_final_render_result_sha256": sha256_file(path),
            "source_render_sha256": result.get("render_sha256"),
        }
        atomic_write_json(rework_path, request)
        if approval_path.exists():
            approval_path.unlink()

    return snapshot()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Human Final Export Gate"
    )
    parser.add_argument("--mode", choices=("status",), default="status")
    parser.parse_args()
    print(json.dumps(snapshot(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
