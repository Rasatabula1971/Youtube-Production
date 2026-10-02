"""Plan unresolved visual gaps after Human Rough-Cut approval.

This module is deterministic and zero-spend. It never calls a paid provider and
never authorizes premium generation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
ROUGH = OUTPUT / "visual_rough_cuts"
REVIEWS = OUTPUT / "visual_rough_cut_reviews"
GAP = OUTPUT / "visual_gap_plans"
SUMMARY = OUTPUT / "visual_gap_plan_summary.json"


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _load_dict(path: Path) -> dict[str, Any] | None:
    try:
        value = load_json(path)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def build(
    rough: dict[str, Any],
    review: dict[str, Any],
    rough_path: Path,
    review_path: Path,
) -> dict[str, Any]:
    if rough.get("status") != "READY_FOR_HUMAN_ROUGH_CUT_GATE":
        raise ValueError("Rough cut is not current for gap planning")
    if (
        review.get("decision") != "APPROVE_WITH_GAPS"
        or review.get("approved_for_gap_planning") is not True
    ):
        raise ValueError("Rough cut is not approved for gap planning")
    if (
        str(review.get("source_rough_cut") or "")
        != str(rough_path.resolve())
        or review.get("source_rough_cut_sha256")
        != sha256_file(rough_path)
    ):
        raise ValueError("STALE_ROUGH_CUT_REVIEW")
    if (
        str(review.get("concept_id") or "")
        != str(rough.get("concept_id") or "")
        or str(review.get("format") or "")
        != str(rough.get("format") or "")
    ):
        raise ValueError("Rough cut/review identity mismatch")

    gaps: list[dict[str, Any]] = []
    for scene in rough.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        assignment = scene.get("visual_assignment", {})
        if (
            not isinstance(assignment, dict)
            or assignment.get("status") != "PLACEHOLDER"
        ):
            continue

        score = (
            scene.get("visual_value_score", {})
            if isinstance(scene.get("visual_value_score"), dict)
            else {}
        )
        try:
            total = int(score.get("total") or 0)
        except (TypeError, ValueError):
            total = 0
        hero = bool(scene.get("premium_generation_candidate")) and total >= 17
        gaps.append(
            {
                "shot_id": scene.get("shot_id"),
                "time_range": scene.get("time_range"),
                "story_purpose": scene.get("story_purpose"),
                "desired_visual": scene.get("desired_visual"),
                "cinematic_direction": scene.get("cinematic_direction", {}),
                "visual_value_score": score,
                "resolution_class": (
                    "D_HERO_GENERATION"
                    if hero
                    else "B_OR_C_EXISTING_TREATMENT_OR_BRIDGE"
                ),
                "generation_priority": "HIGH" if hero else "LOW",
                "premium_generation_recommended": hero,
                "premium_generation_authorized": False,
                "reason": assignment.get("reason"),
            }
        )

    gaps.sort(
        key=lambda item: int(
            item.get("visual_value_score", {}).get("total") or 0
        ),
        reverse=True,
    )
    hero_count = sum(
        gap["premium_generation_recommended"] is True
        for gap in gaps
    )
    return {
        "artifact": "visual_gap_plan",
        "concept_id": rough.get("concept_id"),
        "format": rough.get("format"),
        "status": "READY_FOR_VISUAL_GAP_REVIEW",
        "premium_generation_authorized": False,
        "gaps": gaps,
        "summary": {
            "unresolved": len(gaps),
            "hero_generation_candidates": hero_count,
        },
        "policy": {
            "retry_existing_or_treatment_before_paid_generation": True,
            "higgsfield_last_resort": True,
            "human_visual_spend_gate_required": True,
        },
        "provenance": {
            "rough_cut": str(rough_path.resolve()),
            "rough_cut_sha256": sha256_file(rough_path),
            "rough_cut_review": str(review_path.resolve()),
            "rough_cut_review_sha256": sha256_file(review_path),
        },
    }


def gap_plan_is_current(
    plan_path: Path,
) -> tuple[dict[str, Any], Path, Path] | None:
    plan = _load_dict(plan_path)
    if (
        not isinstance(plan, dict)
        or plan.get("artifact") != "visual_gap_plan"
        or plan.get("status") != "READY_FOR_VISUAL_GAP_REVIEW"
    ):
        return None

    provenance = plan.get("provenance", {})
    if not isinstance(provenance, dict):
        return None
    rough_path = Path(str(provenance.get("rough_cut") or ""))
    review_path = Path(str(provenance.get("rough_cut_review") or ""))
    if (
        not rough_path.is_file()
        or not review_path.is_file()
        or rough_path.parent.resolve() != ROUGH.resolve()
        or review_path.parent.resolve() != REVIEWS.resolve()
        or provenance.get("rough_cut_sha256") != sha256_file(rough_path)
        or provenance.get("rough_cut_review_sha256")
        != sha256_file(review_path)
    ):
        return None

    rough = _load_dict(rough_path)
    review = _load_dict(review_path)
    if not isinstance(rough, dict) or not isinstance(review, dict):
        return None
    try:
        expected = build(rough, review, rough_path, review_path)
    except ValueError:
        return None
    if plan != expected:
        return None
    return plan, rough_path, review_path


def snapshot() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    hero_total = 0
    if GAP.exists():
        for plan_path in sorted(GAP.glob("*.visual_gap_plan.json")):
            state = gap_plan_is_current(plan_path)
            if state is None:
                continue
            plan = state[0]
            summary = plan.get("summary", {})
            heroes = int(summary.get("hero_generation_candidates") or 0)
            hero_total += heroes
            items.append(
                {
                    "concept_id": plan.get("concept_id"),
                    "format": plan.get("format"),
                    "gap_plan": str(plan_path),
                    "gap_plan_sha256": sha256_file(plan_path),
                    "unresolved": int(summary.get("unresolved") or 0),
                    "hero_generation_candidates": heroes,
                }
            )

    return {
        "status": (
            "READY_FOR_VISUAL_SPEND_GATE"
            if hero_total > 0
            else "NO_PREMIUM_GENERATION_REQUIRED"
            if items
            else "WAITING_FOR_APPROVED_ROUGH_CUT"
        ),
        "prepared": len(items),
        "hero_generation_candidates": hero_total,
        "items": items,
        "premium_generation_authorized": False,
    }


def prepare() -> dict[str, Any]:
    GAP.mkdir(parents=True, exist_ok=True)
    current_paths: set[Path] = set()

    rough_paths = (
        sorted(ROUGH.glob("*.visual_rough_cut.json"))
        if ROUGH.exists()
        else []
    )
    for rough_path in rough_paths:
        rough = _load_dict(rough_path)
        if not isinstance(rough, dict):
            continue
        key = _key(
            str(rough.get("concept_id") or ""),
            str(rough.get("format") or ""),
        )
        review_path = REVIEWS / f"{key}.visual_rough_cut_review.json"
        review = _load_dict(review_path) if review_path.exists() else None
        if not isinstance(review, dict):
            continue
        try:
            plan = build(
                rough,
                review,
                rough_path,
                review_path,
            )
        except ValueError:
            continue

        destination = GAP / f"{key}.visual_gap_plan.json"
        atomic_write_json(destination, plan)
        current_paths.add(destination.resolve())

    for stale in GAP.glob("*.visual_gap_plan.json"):
        if stale.resolve() not in current_paths:
            stale.unlink()

    out = snapshot()
    atomic_write_json(SUMMARY, out)
    return out


def main() -> None:
    argparse.ArgumentParser().parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
