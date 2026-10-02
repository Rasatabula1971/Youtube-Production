"""Build a deterministic visual edit assembly plan.

This stage never downloads media, renders video, or calls a paid provider. It
converts the approved rough cut plus current gap/spend decisions into one
timeline contract that clearly identifies resolved assets and pending work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json, safe_slug, sha256_file
from visual_gap_planner import gap_plan_is_current

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


def _fingerprint(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _gap_fingerprint(gap: dict[str, Any]) -> str:
    return _fingerprint(gap)


def _assert_gap_current(
    rough_path: Path,
    review_path: Path,
    gap_path: Path,
) -> dict[str, Any]:
    state = gap_plan_is_current(gap_path)
    if state is None:
        raise ValueError("STALE_VISUAL_GAP_PLAN")
    gap, current_rough, current_review = state
    if (
        current_rough.resolve() != rough_path.resolve()
        or current_review.resolve() != review_path.resolve()
    ):
        raise ValueError("VISUAL_GAP_PLAN_BRANCH_MISMATCH")
    return gap


def _hero_gaps(gap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("shot_id") or ""): item
        for item in gap.get("gaps", [])
        if isinstance(item, dict)
        and item.get("premium_generation_recommended") is True
        and str(item.get("shot_id") or "")
    }


def _decision_cost(decision: dict[str, Any]) -> float:
    try:
        value = float(decision.get("max_cost_usd") or 0)
    except (TypeError, ValueError):
        return -1.0
    return value if math.isfinite(value) else -1.0


def _spend_decisions(
    gap_path: Path,
    gap: dict[str, Any],
    spend_path: Path,
) -> tuple[dict[str, Any], Path | None]:
    hero = _hero_gaps(gap)
    if not hero:
        return {}, None

    if not spend_path.is_file():
        raise ValueError("CURRENT_VISUAL_SPEND_REVIEW_REQUIRED")
    spend = load_json(spend_path)
    if not isinstance(spend, dict):
        raise ValueError("Visual spend review is malformed")
    if (
        spend.get("source_gap_plan") != str(gap_path.resolve())
        or spend.get("source_gap_plan_sha256") != sha256_file(gap_path)
        or str(spend.get("status") or "") != "COMPLETE"
    ):
        raise ValueError("STALE_OR_INCOMPLETE_VISUAL_SPEND_REVIEW")

    decisions = spend.get("decisions", {})
    if not isinstance(decisions, dict):
        raise ValueError("Visual spend decisions are malformed")

    current: dict[str, Any] = {}
    for shot_id, gap_item in hero.items():
        decision = decisions.get(shot_id)
        if not isinstance(decision, dict):
            raise ValueError("INCOMPLETE_VISUAL_SPEND_REVIEW")
        if decision.get("gap_fingerprint") != _gap_fingerprint(gap_item):
            raise ValueError("STALE_VISUAL_SPEND_DECISION")

        action = str(decision.get("decision") or "")
        paid = decision.get("paid_generation_authorized")
        cost = _decision_cost(decision)
        if action == "AUTHORIZE_GENERATION":
            valid = paid is True and cost > 0
        elif action == "KEEP_PLACEHOLDER":
            valid = paid is False and cost == 0
        elif action == "RETRY_EXISTING":
            valid = bool(
                paid is False
                and cost == 0
                and str(decision.get("note") or "").strip()
            )
        else:
            valid = False
        if not valid:
            raise ValueError("INVALID_VISUAL_SPEND_DECISION")
        current[shot_id] = decision

    if set(decisions) != set(hero):
        raise ValueError("VISUAL_SPEND_REVIEW_SHOT_SET_MISMATCH")
    return current, spend_path


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
    if not registry_path.is_file():
        return None
    record = load_json(registry_path)
    if (
        not isinstance(record, dict)
        or str(record.get("candidate_id") or "") != candidate_id
    ):
        return None

    provenance = record.get("provenance", {})
    asset_path = Path(str(record.get("asset_file") or ""))
    if not isinstance(provenance, dict):
        return None
    result_path = Path(str(provenance.get("search_result") or ""))
    review_path = Path(str(provenance.get("candidate_review") or ""))
    if (
        not result_path.is_file()
        or not review_path.is_file()
        or not asset_path.is_file()
        or provenance.get("search_result_sha256") != sha256_file(result_path)
        or provenance.get("candidate_review_sha256")
        != sha256_file(review_path)
        or record.get("asset_sha256") != sha256_file(asset_path)
    ):
        return None

    rights_source = str(provenance.get("rights_review") or "")
    if rights_source:
        rights_path = Path(rights_source)
        if (
            not rights_path.is_file()
            or provenance.get("rights_review_sha256")
            != sha256_file(rights_path)
        ):
            return None

    return {
        "asset_file": str(asset_path.resolve()),
        "asset_sha256": record.get("asset_sha256"),
        "license": record.get("license"),
        "creator": record.get("creator"),
        "source_url": record.get("source_url"),
        "acquisition_method": record.get("acquisition_method"),
        "registry_file": str(registry_path.resolve()),
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
    if not registry_path.is_file() or not generation_request_path.is_file():
        return None

    request = load_json(generation_request_path)
    record = load_json(registry_path)
    if not isinstance(request, dict) or not isinstance(record, dict):
        return None

    provenance = record.get("provenance", {})
    asset_path = Path(str(record.get("asset_file") or ""))
    authorization = request.get("spend_authorization", {})
    if (
        not isinstance(provenance, dict)
        or not isinstance(authorization, dict)
        or provenance.get("visual_generation_request_sha256")
        != sha256_file(generation_request_path)
        or not asset_path.is_file()
        or record.get("asset_sha256") != sha256_file(asset_path)
    ):
        return None

    try:
        actual_cost = round(float(record.get("actual_cost_usd") or 0), 2)
        max_cost = round(float(authorization.get("max_cost_usd") or 0), 2)
    except (TypeError, ValueError):
        return None
    if (
        not math.isfinite(actual_cost)
        or not math.isfinite(max_cost)
        or actual_cost < 0
        or max_cost <= 0
        or actual_cost > max_cost
    ):
        return None

    return {
        "status": "GENERATED_ASSET_READY",
        "asset_file": str(asset_path.resolve()),
        "asset_sha256": record.get("asset_sha256"),
        "provider": record.get("provider"),
        "provider_job_id": record.get("provider_job_id"),
        "actual_cost_usd": actual_cost,
        "registry_file": str(registry_path.resolve()),
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
    max_cost = _decision_cost(decision)
    if not request_path.is_file():
        return {
            "status": "PREMIUM_GENERATION_BRIEF_REQUIRED",
            "generation_request": None,
            "max_cost_usd": max_cost,
        }

    request = load_json(request_path)
    if not isinstance(request, dict):
        return {
            "status": "PREMIUM_GENERATION_BRIEF_STALE",
            "generation_request": str(request_path),
            "max_cost_usd": max_cost,
        }

    provenance = request.get("provenance", {})
    authorization = request.get("spend_authorization", {})
    current = bool(
        isinstance(provenance, dict)
        and isinstance(authorization, dict)
        and provenance.get("gap_plan_sha256") == sha256_file(gap_path)
        and provenance.get("visual_spend_review_sha256")
        == sha256_file(spend_path)
        and provenance.get("visual_spend_decision_sha256")
        == _fingerprint(decision)
        and authorization.get("human_authorized") is True
        and authorization.get("execution_authorized") is False
        and round(float(authorization.get("max_cost_usd") or 0), 2)
        == round(max_cost, 2)
    )
    if not current:
        return {
            "status": "PREMIUM_GENERATION_BRIEF_STALE",
            "generation_request": str(request_path),
            "max_cost_usd": max_cost,
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
            "generation_request": str(request_path.resolve()),
            "generation_request_sha256": sha256_file(request_path),
            "max_cost_usd": max_cost,
        }

    return {
        "status": "PREMIUM_GENERATION_PENDING",
        "generation_request": str(request_path.resolve()),
        "generation_request_sha256": sha256_file(request_path),
        "max_cost_usd": max_cost,
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
    if (
        not isinstance(review, dict)
        or review.get("decision") != "APPROVE_WITH_GAPS"
        or review.get("approved_for_gap_planning") is not True
        or review.get("source_rough_cut") != str(rough_path.resolve())
        or review.get("source_rough_cut_sha256")
        != sha256_file(rough_path)
    ):
        raise ValueError("Rough cut is not currently human-approved")

    gap = _assert_gap_current(rough_path, review_path, gap_path)
    concept_id = str(rough.get("concept_id") or "")
    fmt = str(rough.get("format") or "")
    if (
        str(gap.get("concept_id") or "") != concept_id
        or str(gap.get("format") or "") != fmt
    ):
        raise ValueError("Visual gap plan identity mismatch")

    base = _key(concept_id, fmt)
    spend_candidate = _spend_path(base)
    spend, spend_path = _spend_decisions(
        gap_path,
        gap,
        spend_candidate,
    )
    gap_by_shot = {
        str(item.get("shot_id") or ""): item
        for item in gap.get("gaps", [])
        if isinstance(item, dict)
    }

    timeline: list[dict[str, Any]] = []
    unresolved = 0
    premium_pending = 0
    local_asset_pending = 0
    retry_pending = 0

    for scene in rough.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        shot_id = str(scene.get("shot_id") or "")
        assignment = scene.get("visual_assignment", {})
        if not isinstance(assignment, dict):
            assignment = {}

        source_status = str(
            assignment.get("status") or "PLACEHOLDER"
        )
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
            "MANAGED_EXISTING_ASSET",
            "MANAGED_EDITORIAL_ASSET",
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
                slot["visual_status"] = (
                    "MANAGED_EDITORIAL_ASSET"
                    if source_status
                    in {
                        "MANAGED_EDITORIAL_ASSET",
                        "APPROVED_EDITORIAL_EXCERPT",
                    }
                    else "MANAGED_EXISTING_ASSET"
                )
                slot["asset"] = {
                    "candidate_id": candidate_id,
                    "reason": assignment.get("reason"),
                    **managed,
                }
            else:
                slot["visual_status"] = (
                    "MANUAL_EDITORIAL_ASSET_REQUIRED"
                    if source_status
                    in {
                        "MANAGED_EDITORIAL_ASSET",
                        "APPROVED_EDITORIAL_EXCERPT",
                    }
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
                and spend_path is not None
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
                if generation["status"] in {
                    "PREMIUM_GENERATION_BRIEF_REQUIRED",
                    "PREMIUM_GENERATION_BRIEF_STALE",
                    "PREMIUM_GENERATION_PENDING",
                }:
                    premium_pending += 1
            elif (
                premium
                and isinstance(decision, dict)
                and str(decision.get("decision") or "")
                == "KEEP_PLACEHOLDER"
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
                and str(decision.get("decision") or "")
                == "RETRY_EXISTING"
            ):
                slot["visual_status"] = "RETRY_EXISTING_REQUIRED"
                slot["retry_instruction"] = decision.get("note")
                retry_pending += 1
                unresolved += 1
            else:
                slot["visual_status"] = (
                    "EXISTING_TREATMENT_OR_BRIDGE_REQUIRED"
                )
                slot["placeholder_reason"] = (
                    assignment.get("reason")
                    or "Unresolved low-value visual gap."
                )
                unresolved += 1

        timeline.append(slot)

    status = (
        "WAITING_FOR_EXISTING_VISUAL_RETRY"
        if retry_pending
        else "WAITING_FOR_PREMIUM_GENERATED_ASSETS"
        if premium_pending
        else "WAITING_FOR_LOCAL_VISUAL_ASSETS"
        if local_asset_pending
        else "READY_FOR_EDIT_ASSEMBLY"
    )
    return {
        "artifact": "visual_assembly_plan",
        "concept_id": concept_id,
        "format": fmt,
        "status": status,
        "timeline": timeline,
        "summary": {
            "scenes": len(timeline),
            "premium_generation_pending": premium_pending,
            "local_asset_pending": local_asset_pending,
            "existing_retry_pending": retry_pending,
            "unresolved_nonpremium_or_placeholder": unresolved,
            "resolved_existing": sum(
                item.get("visual_status")
                in {
                    "MANAGED_EXISTING_ASSET",
                    "MANAGED_EDITORIAL_ASSET",
                }
                for item in timeline
            ),
        },
        "policy": {
            "edit_plan_only": True,
            "media_rendered": False,
            "paid_provider_called": False,
            "premium_asset_must_be_imported_before_final_render": True,
            "retry_existing_must_resolve_before_edit_preview": True,
        },
        "provenance": {
            "rough_cut": str(rough_path.resolve()),
            "rough_cut_sha256": sha256_file(rough_path),
            "rough_cut_review": str(review_path.resolve()),
            "rough_cut_review_sha256": sha256_file(review_path),
            "gap_plan": str(gap_path.resolve()),
            "gap_plan_sha256": sha256_file(gap_path),
            "spend_review": (
                str(spend_path.resolve())
                if spend_path is not None
                else None
            ),
            "spend_review_sha256": (
                sha256_file(spend_path)
                if spend_path is not None
                else None
            ),
        },
    }


def assembly_plan_is_current(
    plan_path: Path,
) -> dict[str, Any] | None:
    if not plan_path.is_file():
        return None
    plan = load_json(plan_path)
    if (
        not isinstance(plan, dict)
        or plan.get("artifact") != "visual_assembly_plan"
    ):
        return None

    provenance = plan.get("provenance", {})
    if not isinstance(provenance, dict):
        return None
    rough_path = Path(str(provenance.get("rough_cut") or ""))
    review_path = Path(str(provenance.get("rough_cut_review") or ""))
    gap_path = Path(str(provenance.get("gap_plan") or ""))
    if (
        not rough_path.is_file()
        or rough_path.parent.resolve() != ROUGH_DIR.resolve()
        or not review_path.is_file()
        or review_path.parent.resolve() != ROUGH_REVIEW_DIR.resolve()
        or not gap_path.is_file()
        or gap_path.parent.resolve() != GAP_DIR.resolve()
    ):
        return None

    rough = load_json(rough_path)
    if not isinstance(rough, dict):
        return None
    try:
        expected = build_plan(
            rough_path,
            rough,
            review_path,
            gap_path,
        )
    except ValueError:
        return None
    return plan if plan == expected else None


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
        if not isinstance(rough, dict):
            continue
        concept_id = str(rough.get("concept_id") or "")
        fmt = str(rough.get("format") or "")
        base = _key(concept_id, fmt)
        review_path = _review_path(base)
        gap_path = _gap_path(base)
        if not review_path.is_file() or not gap_path.is_file():
            continue

        plan = build_plan(
            rough_path,
            rough,
            review_path,
            gap_path,
        )
        destination = (
            ASSEMBLY_DIR / f"{base}.visual_assembly_plan.json"
        )
        atomic_write_json(destination, plan)
        current.add(destination.resolve())
        items.append(
            {
                "concept_id": concept_id,
                "format": fmt,
                "status": plan["status"],
                **plan["summary"],
                "assembly_plan": str(destination),
                "assembly_plan_sha256": sha256_file(destination),
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
        "waiting_for_existing_retry": sum(
            item["status"] == "WAITING_FOR_EXISTING_VISUAL_RETRY"
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
