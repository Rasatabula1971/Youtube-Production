"""Build a deterministic visual edit assembly plan.

This stage never downloads media, renders video, or calls a paid provider.
It converts the approved rough-cut + gap/spend decisions into one timeline
contract that clearly identifies which shots are resolved and which remain
pending.
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
ROUGH_DIR = OUTPUT / "visual_rough_cuts"
ROUGH_REVIEW_DIR = OUTPUT / "visual_rough_cut_reviews"
GAP_DIR = OUTPUT / "visual_gap_plans"
SPEND_DIR = OUTPUT / "visual_spend_reviews"
GEN_REQUEST_DIR = OUTPUT / "visual_generation_requests"
GENERATED_REGISTRY_DIR = OUTPUT / "generated_visual_asset_registry"
MANAGED_REGISTRY_DIR = OUTPUT / "managed_visual_asset_registry"
ASSEMBLY_DIR = OUTPUT / "visual_assembly_plans"
SUMMARY_FILE = OUTPUT / "visual_assembly_plan_summary.json"


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _review_path(base: str) -> Path:
    return ROUGH_REVIEW_DIR / f"{base}.visual_rough_cut_review.json"


def _gap_path(base: str) -> Path:
    return GAP_DIR / f"{base}.visual_gap_plan.json"


def _spend_path(base: str) -> Path:
    return SPEND_DIR / f"{base}.visual_spend_review.json"


def _generation_request(
    concept_id: str,
    fmt: str,
    shot_id: str,
) -> Path:
    return GEN_REQUEST_DIR / (
        f"{safe_slug(concept_id)}.{safe_slug(fmt)}."
        f"{safe_slug(shot_id)}.visual_generation_request.json"
    )


def _assert_gap_current(
    rough_path: Path,
    review_path: Path,
    gap_path: Path,
) -> dict[str, Any]:
    if not review_path.exists() or not gap_path.exists():
        raise ValueError("Current rough-cut review and gap plan are required")
    gap = load_json(gap_path)
    provenance = gap.get("provenance", {})
    if (
        not isinstance(provenance, dict)
        or provenance.get("rough_cut_sha256") != sha256_file(rough_path)
        or provenance.get("rough_cut_review_sha256")
        != sha256_file(review_path)
    ):
        raise ValueError("STALE_VISUAL_GAP_PLAN")
    return gap


def _spend_decisions(
    gap_path: Path,
    spend_path: Path,
) -> dict[str, Any]:
    if not spend_path.exists():
        return {}
    spend = load_json(spend_path)
    if (
        spend.get("source_gap_plan_sha256") != sha256_file(gap_path)
        or str(spend.get("status") or "") != "COMPLETE"
    ):
        raise ValueError("STALE_OR_INCOMPLETE_VISUAL_SPEND_REVIEW")
    decisions = spend.get("decisions", {})
    return decisions if isinstance(decisions, dict) else {}


def _managed_asset_record(
    concept_id: str,
    fmt: str,
    shot_id: str,
    candidate_id: str,
) -> dict[str, Any] | None:
    registry_path = MANAGED_REGISTRY_DIR / (
        f"{safe_slug(concept_id)}.{safe_slug(fmt)}."
        f"{safe_slug(shot_id)}.managed_visual_asset.json"
    )
    if not registry_path.exists():
        return None
    record = load_json(registry_path)
    if str(record.get("candidate_id") or "") != candidate_id:
        return None
    provenance = record.get("provenance", {})
    asset_path = Path(str(record.get("asset_file") or ""))
    if not isinstance(provenance, dict):
        return None
    result_path = Path(str(provenance.get("search_result") or ""))
    review_path = Path(str(provenance.get("candidate_review") or ""))
    if (
        not result_path.exists()
        or not review_path.exists()
        or not asset_path.exists()
        or provenance.get("search_result_sha256") != sha256_file(result_path)
        or provenance.get("candidate_review_sha256") != sha256_file(review_path)
        or record.get("asset_sha256") != sha256_file(asset_path)
    ):
        return None
    rights_source = str(provenance.get("rights_review") or "")
    if rights_source:
        rights_path = Path(rights_source)
        if (
            not rights_path.exists()
            or provenance.get("rights_review_sha256")
            != sha256_file(rights_path)
        ):
            return None
    return {
        "asset_file": str(asset_path),
        "asset_sha256": record.get("asset_sha256"),
        "license": record.get("license"),
        "creator": record.get("creator"),
        "source_url": record.get("source_url"),
        "acquisition_method": record.get("acquisition_method"),
        "registry_file": str(registry_path),
        "registry_sha256": sha256_file(registry_path),
    }


def _generated_asset_record(
    concept_id: str,
    fmt: str,
    shot_id: str,
    generation_request_path: Path,
) -> dict[str, Any] | None:
    registry_path = GENERATED_REGISTRY_DIR / (
        f"{safe_slug(concept_id)}.{safe_slug(fmt)}."
        f"{safe_slug(shot_id)}.generated_visual_asset.json"
    )
    if not registry_path.exists() or not generation_request_path.exists():
        return None
    record = load_json(registry_path)
    provenance = record.get("provenance", {})
    asset_path = Path(str(record.get("asset_file") or ""))
    if (
        not isinstance(provenance, dict)
        or provenance.get("visual_generation_request_sha256")
        != sha256_file(generation_request_path)
        or not asset_path.exists()
        or record.get("asset_sha256") != sha256_file(asset_path)
    ):
        return None
    return {
        "status": "GENERATED_ASSET_READY",
        "asset_file": str(asset_path),
        "asset_sha256": record.get("asset_sha256"),
        "provider": record.get("provider"),
        "provider_job_id": record.get("provider_job_id"),
        "actual_cost_usd": float(record.get("actual_cost_usd") or 0),
        "registry_file": str(registry_path),
        "registry_sha256": sha256_file(registry_path),
    }


def _generation_slot(
    *,
    concept_id: str,
    fmt: str,
    shot_id: str,
    gap_path: Path,
    spend_path: Path,
    decision: dict[str, Any],
) -> dict[str, Any]:
    request_path = _generation_request(concept_id, fmt, shot_id)
    if not request_path.exists():
        return {
            "status": "PREMIUM_GENERATION_BRIEF_REQUIRED",
            "generation_request": None,
            "max_cost_usd": float(decision.get("max_cost_usd") or 0),
        }

    request = load_json(request_path)
    provenance = request.get("provenance", {})
    authorization = request.get("spend_authorization", {})
    current = bool(
        isinstance(provenance, dict)
        and isinstance(authorization, dict)
        and provenance.get("gap_plan_sha256") == sha256_file(gap_path)
        and spend_path.exists()
        and provenance.get("visual_spend_review_sha256")
        == sha256_file(spend_path)
        and authorization.get("human_authorized") is True
        and authorization.get("execution_authorized") is False
        and round(float(authorization.get("max_cost_usd") or 0), 2)
        == round(float(decision.get("max_cost_usd") or 0), 2)
    )
    if not current:
        return {
            "status": "PREMIUM_GENERATION_BRIEF_STALE",
            "generation_request": str(request_path),
            "max_cost_usd": float(decision.get("max_cost_usd") or 0),
        }

    generated = _generated_asset_record(
        concept_id,
        fmt,
        shot_id,
        request_path,
    )
    if generated is not None:
        return {
            **generated,
            "generation_request": str(request_path),
            "generation_request_sha256": sha256_file(request_path),
            "max_cost_usd": float(decision.get("max_cost_usd") or 0),
        }

    return {
        "status": "PREMIUM_GENERATION_PENDING",
        "generation_request": str(request_path),
        "generation_request_sha256": sha256_file(request_path),
        "max_cost_usd": float(decision.get("max_cost_usd") or 0),
        "preferred_provider": (
            request.get("provider_handoff", {}).get("preferred_provider")
            if isinstance(request.get("provider_handoff"), dict)
            else None
        ),
    }


def build_plan(
    rough_path: Path,
    rough: dict[str, Any],
    review_path: Path,
    gap_path: Path,
) -> dict[str, Any]:
    if str(rough.get("status") or "") != "READY_FOR_HUMAN_ROUGH_CUT_GATE":
        raise ValueError("Rough cut is not ready for assembly planning")

    review = load_json(review_path)
    if review.get("approved_for_gap_planning") is not True:
        raise ValueError("Rough cut is not human-approved")

    gap = _assert_gap_current(rough_path, review_path, gap_path)
    concept_id = str(rough.get("concept_id") or "")
    fmt = str(rough.get("format") or "")
    base = _key(concept_id, fmt)
    spend_path = _spend_path(base)
    spend = _spend_decisions(gap_path, spend_path)
    gap_by_shot = {
        str(item.get("shot_id") or ""): item
        for item in gap.get("gaps", [])
        if isinstance(item, dict)
    }

    timeline: list[dict[str, Any]] = []
    unresolved = 0
    premium_pending = 0
    local_asset_pending = 0

    for scene in rough.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        shot_id = str(scene.get("shot_id") or "")
        assignment = scene.get("visual_assignment", {})
        if not isinstance(assignment, dict):
            assignment = {}

        source_status = str(assignment.get("status") or "PLACEHOLDER")
        slot: dict[str, Any] = {
            "scene_index": scene.get("scene_index"),
            "shot_id": shot_id,
            "beat_id": scene.get("beat_id"),
            "time_range": scene.get("time_range", {}),
            "story_purpose": scene.get("story_purpose"),
            "desired_visual": scene.get("desired_visual"),
            "cinematic_direction": scene.get("cinematic_direction", {}),
        }

        if source_status in {
            "APPROVED_EXISTING_ASSET",
            "APPROVED_EDITORIAL_EXCERPT",
        }:
            candidate_id = str(assignment.get("candidate_id") or "")
            managed = _managed_asset_record(
                concept_id,
                fmt,
                shot_id,
                candidate_id,
            )
            if managed is not None:
                slot["visual_status"] = source_status
                slot["asset"] = {
                    "candidate_id": candidate_id,
                    "reason": assignment.get("reason"),
                    **managed,
                }
            else:
                slot["visual_status"] = (
                    "MANUAL_EDITORIAL_ASSET_REQUIRED"
                    if source_status == "APPROVED_EDITORIAL_EXCERPT"
                    else "LOCAL_APPROVED_ASSET_REQUIRED"
                )
                slot["asset"] = {
                    "candidate_id": candidate_id,
                    "source_url": assignment.get("source_url"),
                    "reason": assignment.get("reason"),
                }
                local_asset_pending += 1
        else:
            gap_item = gap_by_shot.get(shot_id, {})
            decision = spend.get(shot_id, {})
            premium = bool(
                isinstance(gap_item, dict)
                and gap_item.get("premium_generation_recommended") is True
            )
            if (
                premium
                and isinstance(decision, dict)
                and decision.get("paid_generation_authorized") is True
                and str(decision.get("decision") or "")
                == "AUTHORIZE_GENERATION"
            ):
                generation = _generation_slot(
                    concept_id=concept_id,
                    fmt=fmt,
                    shot_id=shot_id,
                    gap_path=gap_path,
                    spend_path=spend_path,
                    decision=decision,
                )
                slot["visual_status"] = generation["status"]
                slot["generation"] = generation
                if generation["status"] == "PREMIUM_GENERATION_PENDING":
                    premium_pending += 1
            elif (
                premium
                and isinstance(decision, dict)
                and str(decision.get("decision") or "") == "KEEP_PLACEHOLDER"
            ):
                slot["visual_status"] = "PLACEHOLDER_APPROVED"
                slot["placeholder_reason"] = (
                    decision.get("note")
                    or assignment.get("reason")
                    or "Human chose not to spend on this shot."
                )
                unresolved += 1
            elif (
                premium
                and isinstance(decision, dict)
                and str(decision.get("decision") or "") == "RETRY_EXISTING"
            ):
                slot["visual_status"] = "RETRY_EXISTING_REQUIRED"
                slot["retry_instruction"] = decision.get("note")
                unresolved += 1
            else:
                slot["visual_status"] = "EXISTING_TREATMENT_OR_BRIDGE_REQUIRED"
                slot["placeholder_reason"] = (
                    assignment.get("reason") or "Unresolved low-value visual gap."
                )
                unresolved += 1

        timeline.append(slot)

    return {
        "artifact": "visual_assembly_plan",
        "concept_id": concept_id,
        "format": fmt,
        "status": (
            "WAITING_FOR_PREMIUM_GENERATED_ASSETS"
            if premium_pending
            else "WAITING_FOR_LOCAL_VISUAL_ASSETS"
            if local_asset_pending
            else "READY_FOR_EDIT_ASSEMBLY"
        ),
        "timeline": timeline,
        "summary": {
            "scenes": len(timeline),
            "premium_generation_pending": premium_pending,
            "local_asset_pending": local_asset_pending,
            "unresolved_nonpremium_or_placeholder": unresolved,
            "resolved_existing": sum(
                item.get("visual_status")
                in {
                    "APPROVED_EXISTING_ASSET",
                    "APPROVED_EDITORIAL_EXCERPT",
                }
                for item in timeline
            ),
        },
        "policy": {
            "edit_plan_only": True,
            "media_rendered": False,
            "paid_provider_called": False,
            "premium_asset_must_be_imported_before_final_render": True,
        },
        "provenance": {
            "rough_cut": str(rough_path.resolve()),
            "rough_cut_sha256": sha256_file(rough_path),
            "rough_cut_review": str(review_path.resolve()),
            "rough_cut_review_sha256": sha256_file(review_path),
            "gap_plan": str(gap_path.resolve()),
            "gap_plan_sha256": sha256_file(gap_path),
            "spend_review": (
                str(spend_path.resolve()) if spend_path.exists() else None
            ),
            "spend_review_sha256": (
                sha256_file(spend_path) if spend_path.exists() else None
            ),
        },
    }


def prepare() -> dict[str, Any]:
    ASSEMBLY_DIR.mkdir(parents=True, exist_ok=True)
    current: set[Path] = set()
    items: list[dict[str, Any]] = []

    rough_paths = (
        sorted(ROUGH_DIR.glob("*.visual_rough_cut.json"))
        if ROUGH_DIR.exists()
        else []
    )
    for rough_path in rough_paths:
        rough = load_json(rough_path)
        concept_id = str(rough.get("concept_id") or "")
        fmt = str(rough.get("format") or "")
        base = _key(concept_id, fmt)
        review_path = _review_path(base)
        gap_path = _gap_path(base)
        if not review_path.exists() or not gap_path.exists():
            continue

        plan = build_plan(
            rough_path,
            rough,
            review_path,
            gap_path,
        )
        dest = ASSEMBLY_DIR / f"{base}.visual_assembly_plan.json"
        atomic_write_json(dest, plan)
        current.add(dest.resolve())
        items.append(
            {
                "concept_id": concept_id,
                "format": fmt,
                "status": plan["status"],
                **plan["summary"],
                "assembly_plan": str(dest),
            }
        )

    for stale in ASSEMBLY_DIR.glob("*.visual_assembly_plan.json"):
        if stale.resolve() not in current:
            stale.unlink()

    summary = {
        "status": (
            "ASSEMBLY_PLANS_READY"
            if items
            else "WAITING_FOR_APPROVED_VISUAL_GAP_PLANS"
        ),
        "prepared": len(items),
        "waiting_for_premium_assets": sum(
            item["status"] == "WAITING_FOR_PREMIUM_GENERATED_ASSETS"
            for item in items
        ),
        "waiting_for_local_assets": sum(
            item["status"] == "WAITING_FOR_LOCAL_VISUAL_ASSETS"
            for item in items
        ),
        "ready_for_edit_assembly": sum(
            item["status"] == "READY_FOR_EDIT_ASSEMBLY"
            for item in items
        ),
        "provider_calls": 0,
        "media_rendered": False,
        "items": items,
    }
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare deterministic visual edit assembly plans"
    )
    parser.add_argument("--mode", choices=("prepare",), default="prepare")
    parser.parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
