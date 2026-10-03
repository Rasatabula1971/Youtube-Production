"""Human visual spend gate for current premium-generation gaps.

The gate records human decisions and hard spend ceilings only. It never calls a
paid provider.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json, sha256_file
from visual_gap_planner import gap_plan_is_current

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
GAPS = OUTPUT / "visual_gap_plans"
SPEND = OUTPUT / "visual_spend_reviews"
CONFIG = HERE / "visual_spend_config.json"

_SPEND_LOCK = threading.Lock()


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG)
    if not isinstance(config, dict):
        raise ValueError("Visual spend config must be a JSON object")

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

    if str(config.get("currency") or "").upper() != "USD":
        raise ValueError("Visual spend config currency must be USD")
    if config.get("human_authorization_required") is not True:
        raise ValueError(
            "Visual spend config must require explicit human authorization"
        )
    if config.get("paid_provider_calls_without_authorization") is not False:
        raise ValueError(
            "Visual spend config must forbid paid provider calls without authorization"
        )

    try:
        per_shot = float(config["per_shot_hard_cap_usd"])
        workflow = float(config["workflow_hard_cap_usd"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Visual spend caps must be numeric") from exc
    if (
        not math.isfinite(per_shot)
        or not math.isfinite(workflow)
        or per_shot <= 0
        or workflow <= 0
        or per_shot > workflow
    ):
        raise ValueError(
            "Visual spend caps must be finite, positive, and per-shot <= workflow"
        )

    return {
        **config,
        "currency": "USD",
        "per_shot_hard_cap_usd": per_shot,
        "workflow_hard_cap_usd": workflow,
        "human_authorization_required": True,
        "paid_provider_calls_without_authorization": False,
    }


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


def _decision_cost(decision: dict[str, Any]) -> float:
    try:
        value = float(decision.get("max_cost_usd") or 0)
    except (TypeError, ValueError):
        return 0.0
    return value if math.isfinite(value) and value > 0 else 0.0


def _decision_is_current(
    decision: dict[str, Any],
    gap: dict[str, Any],
    config: dict[str, Any],
) -> bool:
    if decision.get("gap_fingerprint") != _gap_fingerprint(gap):
        return False

    action = str(decision.get("decision") or "")
    paid = decision.get("paid_generation_authorized")
    cost = _decision_cost(decision)

    if action == "AUTHORIZE_GENERATION":
        return bool(
            paid is True
            and cost > 0
            and cost <= float(config["per_shot_hard_cap_usd"])
        )
    if action == "KEEP_PLACEHOLDER":
        return paid is False and cost == 0
    if action == "RETRY_EXISTING":
        return bool(
            paid is False
            and cost == 0
            and str(decision.get("note") or "").strip()
        )
    return False


def _authorized_total_for_review(review: dict[str, Any]) -> float:
    decisions = review.get("decisions", {})
    if not isinstance(decisions, dict):
        return 0.0
    return round(
        sum(
            _decision_cost(item)
            for item in decisions.values()
            if isinstance(item, dict)
            and item.get("paid_generation_authorized") is True
        ),
        2,
    )


def _reconcile(
    plan_path: Path,
    plan: dict[str, Any],
    stored: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    config = config or load_config()
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
        gap = hero_by_id.get(str(shot_id))
        if (
            gap is not None
            and isinstance(decision, dict)
            and _decision_is_current(decision, gap, config)
        ):
            current[str(shot_id)] = decision
        else:
            stale += 1

    decided = len(set(current).intersection(hero_by_id))
    authorized = sum(
        decision.get("paid_generation_authorized") is True
        for shot_id, decision in current.items()
        if shot_id in hero_by_id
    )
    review = {
        "artifact": "visual_spend_review",
        "concept_id": plan.get("concept_id"),
        "format": plan.get("format"),
        "source_gap_plan": str(plan_path.resolve()),
        "source_gap_plan_sha256": sha256_file(plan_path),
        "decisions": current,
        "authorized_max_total_usd": _authorized_total_for_review(
            {"decisions": current}
        ),
        "summary": {
            "required": len(hero_by_id),
            "decided": decided,
            "authorized": authorized,
        },
        "status": (
            "COMPLETE"
            if decided == len(hero_by_id)
            else "REVIEW_IN_PROGRESS"
        ),
    }
    return review, stale


def _current_plans() -> list[tuple[Path, dict[str, Any]]]:
    items: list[tuple[Path, dict[str, Any]]] = []
    if not GAPS.exists():
        return items
    for plan_path in sorted(GAPS.glob("*.visual_gap_plan.json")):
        state = gap_plan_is_current(plan_path)
        if state is not None:
            items.append((plan_path, state[0]))
    return items


def current_complete_review(
    plan_path: Path,
) -> tuple[dict[str, Any], Path] | None:
    state = gap_plan_is_current(plan_path)
    if state is None:
        return None
    plan = state[0]
    spend_path = _path(plan_path)
    if not spend_path.exists():
        return None

    stored = load_json(spend_path)
    if not isinstance(stored, dict):
        return None
    canonical, _ = _reconcile(
        plan_path,
        plan,
        stored,
        load_config(),
    )
    if stored != canonical or canonical.get("status") != "COMPLETE":
        return None
    return canonical, spend_path


def _other_authorized_total(
    exclude_plan_path: Path,
    config: dict[str, Any],
) -> float:
    total = 0.0
    for plan_path, plan in _current_plans():
        if plan_path.resolve() == exclude_plan_path.resolve():
            continue
        spend_path = _path(plan_path)
        if not spend_path.exists():
            continue
        stored = load_json(spend_path)
        if not isinstance(stored, dict):
            continue
        review, _ = _reconcile(
            plan_path,
            plan,
            stored,
            config,
        )
        total += _authorized_total_for_review(review)
    return round(total, 2)


def snapshot() -> dict[str, Any]:
    config = load_config()
    items: list[dict[str, Any]] = []
    hero_total = 0
    decided_total = 0
    authorized = 0
    stale_removed = 0
    authorized_max_total = 0.0
    current_spend_paths: set[Path] = set()

    current_plans = _current_plans()
    for plan_path, plan in current_plans:
        spend_path = _path(plan_path)
        current_spend_paths.add(spend_path.resolve())
        stored = (
            load_json(spend_path)
            if spend_path.exists()
            else {"decisions": {}}
        )
        review, stale = _reconcile(
            plan_path,
            plan,
            stored if isinstance(stored, dict) else {},
            config,
        )
        stale_removed += stale
        if spend_path.exists() and review != stored:
            atomic_write_json(spend_path, review)

        hero = _hero_gaps(plan)
        hero_ids = {
            str(gap.get("shot_id") or "")
            for gap in hero
            if str(gap.get("shot_id") or "")
        }
        decisions = {
            shot_id: decision
            for shot_id, decision in review["decisions"].items()
            if shot_id in hero_ids
        }
        hero_total += len(hero_ids)
        decided_total += len(decisions)
        authorized += sum(
            decision.get("paid_generation_authorized") is True
            for decision in decisions.values()
        )
        authorized_max_total += _authorized_total_for_review(
            {"decisions": decisions}
        )

        spend_exists = spend_path.exists()
        items.append(
            {
                "concept_id": plan.get("concept_id"),
                "format": plan.get("format"),
                "gap_plan_file": str(plan_path),
                "gap_plan_sha256": sha256_file(plan_path),
                "spend_review_file": (
                    str(spend_path) if spend_exists else None
                ),
                "spend_review_sha256": (
                    sha256_file(spend_path) if spend_exists else None
                ),
                "hero_candidates": hero,
                "decisions": decisions,
                "review_status": review.get("status"),
            }
        )

    if SPEND.exists():
        for stale_path in SPEND.glob("*.visual_spend_review.json"):
            if stale_path.resolve() not in current_spend_paths:
                stale_path.unlink()
                stale_removed += 1

    workflow_cap = float(config["workflow_hard_cap_usd"])
    authorized_max_total = round(authorized_max_total, 2)
    global_cap_valid = authorized_max_total <= workflow_cap
    complete = bool(items) and global_cap_valid and (
        hero_total == 0 or hero_total == decided_total
    )
    return {
        "status": (
            "WAITING_FOR_CURRENT_GAP_PLANS"
            if not items
            else "INVALID_VISUAL_SPEND_AUTHORIZATION"
            if not global_cap_valid
            else "NO_PREMIUM_GENERATION_REQUIRED"
            if hero_total == 0
            else "COMPLETE"
            if complete
            else "READY_FOR_VISUAL_SPEND_GATE"
        ),
        "complete": complete,
        "global_cap_valid": global_cap_valid,
        "hero_candidates": hero_total,
        "decided": decided_total,
        "authorized": authorized,
        "authorized_max_total_usd": authorized_max_total,
        "stale_removed": stale_removed,
        "currency": config["currency"],
        "per_shot_hard_cap_usd": config["per_shot_hard_cap_usd"],
        "workflow_hard_cap_usd": workflow_cap,
        "human_authorization_required": True,
        "paid_provider_calls_without_authorization": False,
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
    with _SPEND_LOCK:
        config = load_config()
        plan_path = Path(gap_plan_file)
        if (
            not plan_path.exists()
            or plan_path.parent.resolve() != GAPS.resolve()
        ):
            raise ValueError("Invalid gap plan")

        state = gap_plan_is_current(plan_path)
        if state is None:
            raise ValueError("STALE_VISUAL_GAP_PLAN")
        plan = state[0]

        decision = str(decision or "").strip().upper()
        if decision not in {
            "AUTHORIZE_GENERATION",
            "KEEP_PLACEHOLDER",
            "RETRY_EXISTING",
        }:
            raise ValueError("Unsupported visual spend decision")

        gap = next(
            (
                item
                for item in _hero_gaps(plan)
                if str(item.get("shot_id") or "") == shot_id
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

        try:
            requested_cost = float(max_cost_usd)
        except (TypeError, ValueError) as exc:
            raise ValueError("Visual authorization cost must be numeric") from exc
        if not math.isfinite(requested_cost):
            raise ValueError("Visual authorization cost must be finite")

        per_shot_cap = float(config["per_shot_hard_cap_usd"])
        workflow_cap = float(config["workflow_hard_cap_usd"])
        if decision == "AUTHORIZE_GENERATION":
            if requested_cost <= 0 or requested_cost > per_shot_cap:
                raise ValueError(
                    "Per-shot authorization must be > $0 and <= $"
                    + f"{per_shot_cap:.2f} USD"
                )

        spend_path = _path(plan_path)
        stored = (
            load_json(spend_path)
            if spend_path.exists()
            else {"decisions": {}}
        )
        current, _ = _reconcile(
            plan_path,
            plan,
            stored if isinstance(stored, dict) else {},
            config,
        )
        decisions = dict(current.get("decisions", {}))
        decisions[shot_id] = {
            "decision": decision,
            "max_cost_usd": (
                round(requested_cost, 2)
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
        review, _ = _reconcile(
            plan_path,
            plan,
            {"decisions": decisions},
            config,
        )

        branch_total = float(review["authorized_max_total_usd"])
        workflow_total = round(
            _other_authorized_total(plan_path, config) + branch_total,
            2,
        )
        if workflow_total > workflow_cap:
            raise ValueError(
                "Visual authorization total would exceed the configured $"
                + f"{workflow_cap:.2f} USD hard cap"
            )

        atomic_write_json(spend_path, review)
        return {
            **review,
            "authorized_workflow_total_usd": workflow_total,
        }


def main() -> None:
    print(json.dumps(snapshot(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
