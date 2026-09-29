from __future__ import annotations

import json
from pathlib import Path

import pytest

from production_engine.visual_acquisition import (
    build_manifest,
    candidate_state,
    load_config,
    route_manifest,
    route_requirement,
)


def approved_plan() -> dict:
    return {
        "concept_id": "concept-1",
        "format_gate": {"status": "READY_FOR_PRODUCTION_ENGINE"},
        "package": {
            "title": "Wet Tyres",
            "one_sentence_promise": "Explain why tyres lose grip in rain.",
            "expected_payoff": "Understand the grip limit.",
        },
        "branches": [
            {
                "format": "long_form",
                "duration_intent_seconds": 600,
                "beats": [
                    {
                        "beat_id": "lf001",
                        "purpose": "Show the risk.",
                        "treatment": "A car approaches standing water at speed.",
                        "claim_ids": ["claim-1"],
                        "source_section_ids": ["section-1"],
                    },
                    {
                        "beat_id": "lf002",
                        "purpose": "Explain the mechanism.",
                        "treatment": "Show water leaving the tyre contact patch.",
                        "claim_ids": ["claim-2"],
                        "source_section_ids": ["section-2"],
                    },
                ],
            }
        ],
    }


def write_plan(tmp_path: Path, plan: dict) -> Path:
    path = tmp_path / "concept-1.approved_format_plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def candidate(
    candidate_id: str,
    tier: str,
    *,
    cost: float = 0.0,
    rights_status: str = "VERIFIED",
    commercial: bool = True,
) -> dict:
    return {
        "candidate_id": candidate_id,
        "source_tier": tier,
        "estimated_cost_usd": cost,
        "rights_status": rights_status,
        "commercial_use_allowed": commercial,
        "source_url": f"https://example.test/{candidate_id}",
    }


def test_build_manifest_requires_accepted_format_gate(tmp_path: Path) -> None:
    config = load_config()
    plan = approved_plan()
    plan["format_gate"]["status"] = "FORMAT_REWORK_REQUIRED"
    path = write_plan(tmp_path, plan)

    with pytest.raises(ValueError, match="READY_FOR_PRODUCTION_ENGINE"):
        build_manifest(plan, path, plan["branches"][0], config)


def test_build_manifest_creates_one_requirement_per_beat(tmp_path: Path) -> None:
    config = load_config()
    plan = approved_plan()
    path = write_plan(tmp_path, plan)

    manifest = build_manifest(plan, path, plan["branches"][0], config)

    assert manifest["concept_id"] == "concept-1"
    assert manifest["format"] == "long_form"
    assert len(manifest["requirements"]) == 2
    assert manifest["requirements"][0]["beat_id"] == "lf001"
    assert manifest["requirements"][0]["routing"]["next_source_tier"] == "OWN_LIBRARY"
    assert manifest["manifest_provenance"]["approved_format_plan_sha256"]


def test_verified_free_asset_beats_paid_ai() -> None:
    config = load_config()
    requirement = {
        "attempted_source_tiers": [],
        "candidates": [
            candidate(
                "ai-1",
                "CHEAP_AI",
                cost=1.25,
                rights_status="PROVIDER_LICENSED",
            ),
            candidate("stock-1", "FREE_COMMERCIAL_LICENSE"),
        ],
    }

    decision = route_requirement(
        requirement,
        config,
        remaining_budget_usd=10.0,
    )

    assert decision["status"] == "SELECTED"
    assert decision["selected_candidate_id"] == "stock-1"
    assert decision["estimated_paid_cost_usd"] == 0.0


def test_editorial_excerpt_requires_review_before_later_paid_tier() -> None:
    config = load_config()
    requirement = {
        "attempted_source_tiers": [],
        "candidates": [
            candidate("excerpt-1", "EDITORIAL_EXCERPT"),
            candidate(
                "ai-1",
                "CHEAP_AI",
                cost=1.0,
                rights_status="PROVIDER_LICENSED",
            ),
        ],
    }

    decision = route_requirement(
        requirement,
        config,
        remaining_budget_usd=10.0,
    )

    assert decision["status"] == "HUMAN_REVIEW_REQUIRED"
    assert decision["review_candidate_id"] == "excerpt-1"
    assert decision["selected_candidate_id"] is None


def test_clip_length_never_converts_excerpt_to_auto_eligible() -> None:
    config = load_config()
    short_excerpt = candidate("excerpt-1", "EDITORIAL_EXCERPT")
    short_excerpt["duration_seconds"] = 1.0

    state, reason = candidate_state(
        short_excerpt,
        config,
        remaining_budget_usd=10.0,
    )

    assert config["never_treat_clip_duration_as_permission"] is True
    assert state == "HUMAN_REVIEW_REQUIRED"
    assert reason == "RIGHTS_OR_CONTEXT_REVIEW"


def test_unverified_free_asset_is_blocked() -> None:
    config = load_config()
    unverified = candidate(
        "stock-1",
        "FREE_COMMERCIAL_LICENSE",
        rights_status="UNKNOWN",
    )

    state, reason = candidate_state(
        unverified,
        config,
        remaining_budget_usd=10.0,
    )

    assert state == "BLOCKED"
    assert reason == "RIGHTS_NOT_VERIFIED"


def test_paid_candidate_over_remaining_budget_is_blocked() -> None:
    config = load_config()
    paid = candidate(
        "ai-1",
        "CHEAP_AI",
        cost=2.0,
        rights_status="PROVIDER_LICENSED",
    )

    state, reason = candidate_state(
        paid,
        config,
        remaining_budget_usd=1.5,
    )

    assert state == "BLOCKED"
    assert reason == "PAID_VISUAL_HARD_CAP"


def test_route_manifest_tracks_paid_spend_without_exceeding_cap(
    tmp_path: Path,
) -> None:
    config = load_config()
    plan = approved_plan()
    path = write_plan(tmp_path, plan)
    manifest = build_manifest(plan, path, plan["branches"][0], config)

    for index, requirement in enumerate(manifest["requirements"], start=1):
        requirement["candidates"] = [
            candidate(
                f"ai-{index}",
                "CHEAP_AI",
                cost=4.0,
                rights_status="PROVIDER_LICENSED",
            )
        ]
        requirement["attempted_source_tiers"] = [
            "OWN_LIBRARY",
            "FREE_COMMERCIAL_LICENSE",
            "PUBLIC_DOMAIN",
            "CREATIVE_COMMONS_ALLOWED",
            "EDITORIAL_EXCERPT",
            "MOTION_GRAPHIC",
        ]

    routed = route_manifest(manifest, config, verify_provenance=False)

    summary = routed["routing_summary"]
    assert summary["estimated_paid_cost_usd"] == 8.0
    assert summary["within_target"] is False
    assert summary["within_hard_cap"] is True
    assert summary["status"] == "ROUTED"


def test_hard_cap_prevents_second_paid_selection(tmp_path: Path) -> None:
    config = load_config()
    plan = approved_plan()
    path = write_plan(tmp_path, plan)
    manifest = build_manifest(plan, path, plan["branches"][0], config)

    for index, requirement in enumerate(manifest["requirements"], start=1):
        requirement["candidates"] = [
            candidate(
                f"premium-{index}",
                "HIGGSFIELD_PREMIUM",
                cost=6.0,
                rights_status="PROVIDER_LICENSED",
            )
        ]

    routed = route_manifest(manifest, config, verify_provenance=False)

    statuses = [item["routing"]["status"] for item in routed["requirements"]]
    assert statuses == ["SELECTED", "ACQUISITION_REQUIRED"]
    assert routed["routing_summary"]["estimated_paid_cost_usd"] == 6.0
    assert routed["routing_summary"]["within_hard_cap"] is True
