"""Human visual spend gate for premium-generation gaps."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
GAPS = OUTPUT / "visual_gap_plans"
SPEND = OUTPUT / "visual_spend_reviews"
CONFIG = HERE / "visual_spend_config.json"


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG)
    required = {
        "currency",
        "per_shot_hard_cap_usd",
        "workflow_hard_cap_usd",
        "human_authorization_required",
        "paid_provider_calls_without_authorization",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(
            "Visual spend config is missing: " + ", ".join(missing)
        )
    return config


def _path(plan_path: Path) -> Path:
    SPEND.mkdir(parents=True, exist_ok=True)
    return SPEND / plan_path.name.replace(
        ".visual_gap_plan.json",
        ".visual_spend_review.json",
    )


def _gap_fingerprint(gap: dict[str, Any]) -> str:
    encoded = json.dumps(
        gap,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _hero_gaps(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        gap
        for gap in plan.get("gaps", [])
        if isinstance(gap, dict)
        and gap.get("premium_generation_recommended") is True
    ]


def _reconcile(
    plan_path: Path,
    plan: dict[str, Any],
    stored: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    hero_by_id = {
        str(gap.get("shot_id") or ""): gap
        for gap in _hero_gaps(plan)
        if str(gap.get("shot_id") or "")
    }
    prior = (
        stored.get("decisions", {})
        if isinstance(stored, dict)
        and isinstance(stored.get("decisions"), dict)
        else {}
    )
    current: dict[str, Any] = {}
    stale = 0
    for shot_id, decision in prior.items():
        gap = hero_by_id.get(shot_id)
        if (
            gap is not None
            and isinstance(decision, dict)
            and decision.get("gap_fingerprint") == _gap_fingerprint(gap)
        ):
            current[shot_id] = decision
        else:
            stale += 1
    review = {
        "artifact": "visual_spend_review",
        "concept_id": plan.get("concept_id"),
        "format": plan.get("format"),
        "source_gap_plan": str(plan_path.resolve()),
        "source_gap_plan_sha256": sha256_file(plan_path),
        "decisions": current,
    }
    return review, stale


def snapshot() -> dict[str, Any]:
    config = load_config()
    items: list[dict[str, Any]] = []
    hero_total = 0
    decided_total = 0
    authorized = 0
    stale_removed = 0
    authorized_max_total = 0.0

    paths = (
        sorted(GAPS.glob("*.visual_gap_plan.json"))
        if GAPS.exists()
        else []
    )
    for plan_path in paths:
        plan = load_json(plan_path)
        spend_path = _path(plan_path)
        stored = (
            load_json(spend_path)
            if spend_path.exists()
            else {"decisions": {}}
        )
        review, stale = _reconcile(plan_path, plan, stored)
        stale_removed += stale
        if spend_path.exists() and review != stored:
            atomic_write_json(spend_path, review)

        hero = _hero_gaps(plan)
        hero_ids = {
            str(gap.get("shot_id") or "")
            for gap in hero
        }
        decisions = {
            shot_id: decision
            for shot_id, decision in review["decisions"].items()
            if shot_id in hero_ids
        }
        hero_total += len(hero)
        decided_total += len(decisions)
        authorized += sum(
            decision.get("paid_generation_authorized") is True
            for decision in decisions.values()
        )
        authorized_max_total += sum(
            float(decision.get("max_cost_usd") or 0)
            for decision in decisions.values()
        )
        items.append(
            {
                "concept_id": plan.get("concept_id"),
                "format": plan.get("format"),
                "gap_plan_file": str(plan_path),
                "gap_plan_sha256": sha256_file(plan_path),
                "hero_candidates": hero,
                "decisions": decisions,
            }
        )

    complete = hero_total == 0 or hero_total == decided_total
    return {
        "status": (
            "NO_PREMIUM_GENERATION_REQUIRED"
            if hero_total == 0
            else "COMPLETE"
            if complete
            else "READY_FOR_VISUAL_SPEND_GATE"
        ),
        "complete": complete,
        "hero_candidates": hero_total,
        "decided": decided_total,
        "authorized": authorized,
        "authorized_max_total_usd": round(authorized_max_total, 2),
        "stale_removed": stale_removed,
        "currency": config["currency"],
        "per_shot_hard_cap_usd": float(
            config["per_shot_hard_cap_usd"]
        ),
        "workflow_hard_cap_usd": float(
            config["workflow_hard_cap_usd"]
        ),
        "human_authorization_required": bool(
            config["human_authorization_required"]
        ),
        "items": items,
    }


def apply_action(
    *,
    gap_plan_file: str,
    shot_id: str,
    decision: str,
    max_cost_usd: float = 0,
    note: str = "",
) -> dict[str, Any]:
    config = load_config()
    plan_path = Path(gap_plan_file)
    if (
        not plan_path.exists()
        or plan_path.parent.resolve() != GAPS.resolve()
    ):
        raise ValueError("Invalid gap plan")

    decision = str(decision or "").strip().upper()
    if decision not in {
        "AUTHORIZE_GENERATION",
        "KEEP_PLACEHOLDER",
        "RETRY_EXISTING",
    }:
        raise ValueError("Unsupported visual spend decision")

    plan = load_json(plan_path)
    gap = next(
        (
            item
            for item in _hero_gaps(plan)
            if str(item.get("shot_id")) == shot_id
        ),
        None,
    )
    if gap is None:
        raise ValueError(
            "Shot is not a premium-generation candidate in the current gap plan"
        )
    if decision == "RETRY_EXISTING" and not note.strip():
        raise ValueError(
            "Retry existing requires a human instruction for the new search"
        )

    per_shot_cap = float(config["per_shot_hard_cap_usd"])
    workflow_cap = float(config["workflow_hard_cap_usd"])
    if decision == "AUTHORIZE_GENERATION":
        if not bool(config["human_authorization_required"]):
            raise ValueError(
                "Visual spend config must require explicit human authorization"
            )
        if max_cost_usd <= 0 or max_cost_usd > per_shot_cap:
            raise ValueError(
                "Per-shot authorization must be > $0 and <= "
                f"${per_shot_cap:.2f} USD"
            )

    spend_path = _path(plan_path)
    stored = (
        load_json(spend_path)
        if spend_path.exists()
        else {"decisions": {}}
    )
    review, _ = _reconcile(plan_path, plan, stored)
    review["decisions"][shot_id] = {
        "decision": decision,
        "max_cost_usd": (
            round(float(max_cost_usd), 2)
            if decision == "AUTHORIZE_GENERATION"
            else 0
        ),
        "note": note.strip(),
        "paid_generation_authorized": (
            decision == "AUTHORIZE_GENERATION"
        ),
        "gap_fingerprint": _gap_fingerprint(gap),
        "cinematic_direction": gap.get("cinematic_direction", {}),
        "desired_visual": gap.get("desired_visual"),
    }
    authorized_total = round(
        sum(
            float(item.get("max_cost_usd") or 0)
            for item in review["decisions"].values()
        ),
        2,
    )
    if authorized_total > workflow_cap:
        raise ValueError(
            "Visual authorization total would exceed the configured "
            f"${workflow_cap:.2f} USD hard cap"
        )
    review["authorized_max_total_usd"] = authorized_total
    hero_ids = {
        str(item.get("shot_id") or "")
        for item in _hero_gaps(plan)
    }
    decided = len(
        set(review["decisions"]).intersection(hero_ids)
    )
    review["summary"] = {
        "required": len(hero_ids),
        "decided": decided,
        "authorized": sum(
            item.get("paid_generation_authorized") is True
            for shot, item in review["decisions"].items()
            if shot in hero_ids
        ),
    }
    review["status"] = (
        "COMPLETE"
        if decided == len(hero_ids)
        else "REVIEW_IN_PROGRESS"
    )
    atomic_write_json(spend_path, review)
    return review


def main() -> None:
    print(json.dumps(snapshot(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
