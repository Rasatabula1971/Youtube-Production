"""Prepare zero-cost premium visual generation handoff requests.

Consumes the canonical Human Visual Spend Gate snapshot. Only shots explicitly
authorized in the complete current spend state are emitted.

This module NEVER calls an image/video provider and NEVER spends money.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json, safe_slug, sha256_file
from visual_gap_planner import gap_plan_is_current
from visual_spend_review import snapshot as visual_spend_snapshot

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
GAP_DIR = OUTPUT / "visual_gap_plans"
SPEND_DIR = OUTPUT / "visual_spend_reviews"
REQUEST_DIR = OUTPUT / "visual_generation_requests"
SUMMARY_FILE = OUTPUT / "visual_generation_handoff_summary.json"


def _key(concept_id: str, fmt: str, shot_id: str) -> str:
    return ".".join(
        [safe_slug(concept_id), safe_slug(fmt), safe_slug(shot_id)]
    )


def _request_path(concept_id: str, fmt: str, shot_id: str) -> Path:
    return REQUEST_DIR / (
        f"{_key(concept_id, fmt, shot_id)}.visual_generation_request.json"
    )


def _fingerprint(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _authorized_decisions(
    review: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    decisions = review.get("decisions", {})
    if not isinstance(decisions, dict):
        return []
    return [
        (str(shot_id), decision)
        for shot_id, decision in decisions.items()
        if isinstance(decision, dict)
        and decision.get("paid_generation_authorized") is True
        and str(decision.get("decision") or "") == "AUTHORIZE_GENERATION"
    ]


def _generation_brief(
    *,
    gap_plan_path: Path,
    gap_plan: dict[str, Any],
    spend_path: Path,
    spend_review: dict[str, Any],
    shot_id: str,
    decision: dict[str, Any],
) -> dict[str, Any]:
    if (
        spend_review.get("source_gap_plan")
        != str(gap_plan_path.resolve())
        or spend_review.get("source_gap_plan_sha256")
        != sha256_file(gap_plan_path)
        or str(spend_review.get("status") or "") != "COMPLETE"
    ):
        raise ValueError("STALE_VISUAL_SPEND_REVIEW")

    gap = next(
        (
            item
            for item in gap_plan.get("gaps", [])
            if isinstance(item, dict)
            and str(item.get("shot_id") or "") == shot_id
        ),
        None,
    )
    if gap is None:
        raise ValueError("Authorized shot is missing from current gap plan")
    if gap.get("premium_generation_recommended") is not True:
        raise ValueError(
            "Authorized shot is no longer a premium-generation gap"
        )

    try:
        max_cost = round(float(decision.get("max_cost_usd") or 0), 2)
    except (TypeError, ValueError) as exc:
        raise ValueError("Authorized generation cost is invalid") from exc
    if max_cost <= 0:
        raise ValueError(
            "Authorized generation request requires max_cost_usd > 0"
        )

    cinematic = (
        gap.get("cinematic_direction", {})
        if isinstance(gap.get("cinematic_direction"), dict)
        else {}
    )
    desired_visual = str(gap.get("desired_visual") or "").strip()
    story_purpose = str(gap.get("story_purpose") or "").strip()

    return {
        "artifact": "visual_generation_request",
        "status": "READY_FOR_PROVIDER_QUOTE_OR_RENDER",
        "concept_id": gap_plan.get("concept_id"),
        "format": gap_plan.get("format"),
        "shot_id": shot_id,
        "time_range": gap.get("time_range", {}),
        "story_purpose": story_purpose,
        "desired_visual": desired_visual,
        "generation_brief": {
            "subject_and_action": desired_visual,
            "narrative_intent": story_purpose,
            "camera_angle": cinematic.get("camera_angle"),
            "framing": cinematic.get("framing"),
            "camera_movement": cinematic.get("camera_movement"),
            "lens_feel": cinematic.get("lens_feel"),
            "lighting": cinematic.get("lighting"),
            "depth_of_field": cinematic.get("depth_of_field"),
            "motion_speed": cinematic.get("motion_speed"),
            "transition": cinematic.get("transition"),
            "continuity_notes": (
                "Match the approved storyboard timing and adjacent rough-cut "
                "visual language. Do not add unsupported factual details."
            ),
            "negative_constraints": [
                "Do not imitate a specific creator's distinctive footage or style.",
                "Do not add logos, watermarks, captions, UI, or text unless explicitly requested.",
                "Do not invent people, brands, locations, damage, danger, or mechanisms not supported by the approved story.",
                "Do not change the shot's narrative function merely to make it more spectacular.",
            ],
        },
        "provider_handoff": {
            "preferred_provider": "higgsfield",
            "provider_neutral_request": True,
            "provider_call_authorized": False,
            "quote_or_preview_only_until_execution_gate": True,
        },
        "spend_authorization": {
            "human_authorized": True,
            "max_cost_usd": max_cost,
            "authorization_note": str(decision.get("note") or ""),
            "execution_authorized": False,
        },
        "selection_policy": {
            "free_and_existing_sources_already_attempted": True,
            "premium_generation_is_last_resort": True,
            "human_must_choose_final_generated_asset": True,
        },
        "provenance": {
            "gap_plan": str(gap_plan_path.resolve()),
            "gap_plan_sha256": sha256_file(gap_plan_path),
            "visual_spend_review": str(spend_path.resolve()),
            "visual_spend_review_sha256": sha256_file(spend_path),
            "visual_spend_decision_sha256": _fingerprint(decision),
        },
    }


def prepare() -> dict[str, Any]:
    REQUEST_DIR.mkdir(parents=True, exist_ok=True)
    current_paths: set[Path] = set()
    items: list[dict[str, Any]] = []
    total_max_cost = 0.0

    spend_state = visual_spend_snapshot()
    if not spend_state.get("complete"):
        for stale in REQUEST_DIR.glob(
            "*.visual_generation_request.json"
        ):
            stale.unlink()
        summary = {
            "status": "WAITING_FOR_COMPLETE_VISUAL_SPEND_DECISIONS",
            "prepared": 0,
            "authorized_max_total_usd": 0.0,
            "provider_calls": 0,
            "paid_inference_executed": False,
            "items": [],
        }
        atomic_write_json(SUMMARY_FILE, summary)
        return summary

    for item in spend_state.get("items", []):
        if not isinstance(item, dict):
            continue
        decisions = item.get("decisions", {})
        if not isinstance(decisions, dict):
            continue
        authorized = _authorized_decisions({"decisions": decisions})
        if not authorized:
            continue

        gap_path = Path(str(item.get("gap_plan_file") or ""))
        spend_path = Path(str(item.get("spend_review_file") or ""))
        if (
            not gap_path.is_file()
            or gap_path.parent.resolve() != GAP_DIR.resolve()
            or not spend_path.is_file()
            or spend_path.parent.resolve() != SPEND_DIR.resolve()
            or item.get("gap_plan_sha256") != sha256_file(gap_path)
            or item.get("spend_review_sha256") != sha256_file(spend_path)
        ):
            raise ValueError("STALE_VISUAL_SPEND_REVIEW")

        gap_state = gap_plan_is_current(gap_path)
        if gap_state is None:
            raise ValueError("STALE_VISUAL_GAP_PLAN")
        gap_plan = gap_state[0]
        review = load_json(spend_path)
        if not isinstance(review, dict):
            raise ValueError("Visual spend review is malformed")

        for shot_id, decision in authorized:
            request = _generation_brief(
                gap_plan_path=gap_path,
                gap_plan=gap_plan,
                spend_path=spend_path,
                spend_review=review,
                shot_id=shot_id,
                decision=decision,
            )
            destination = _request_path(
                str(request.get("concept_id") or ""),
                str(request.get("format") or ""),
                shot_id,
            )
            atomic_write_json(destination, request)
            current_paths.add(destination.resolve())
            max_cost = float(
                request.get(
                    "spend_authorization",
                    {},
                ).get("max_cost_usd") or 0
            )
            total_max_cost += max_cost
            items.append(
                {
                    "concept_id": request.get("concept_id"),
                    "format": request.get("format"),
                    "shot_id": shot_id,
                    "preferred_provider": "higgsfield",
                    "max_cost_usd": round(max_cost, 2),
                    "request": str(destination),
                    "request_sha256": sha256_file(destination),
                }
            )

    for stale in REQUEST_DIR.glob("*.visual_generation_request.json"):
        if stale.resolve() not in current_paths:
            stale.unlink()

    expected_total = round(
        float(spend_state.get("authorized_max_total_usd") or 0),
        2,
    )
    prepared_total = round(total_max_cost, 2)
    if prepared_total != expected_total:
        raise ValueError(
            "VISUAL_GENERATION_HANDOFF_COST_MISMATCH"
        )

    summary = {
        "status": (
            "READY_FOR_PROVIDER_HANDOFF"
            if items
            else "NO_PAID_VISUAL_GENERATION_AUTHORIZED"
        ),
        "prepared": len(items),
        "authorized_max_total_usd": prepared_total,
        "provider_calls": 0,
        "paid_inference_executed": False,
        "items": items,
    }
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare premium visual generation handoff briefs"
    )
    parser.add_argument("--mode", choices=("prepare",), default="prepare")
    parser.parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
