from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from production_engine import visual_acquisition
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


class VisualAcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config()

    def test_build_manifest_requires_accepted_format_gate(self) -> None:
        plan = approved_plan()
        plan["format_gate"]["status"] = "FORMAT_REWORK_REQUIRED"
        with tempfile.TemporaryDirectory() as directory:
            path = write_plan(Path(directory), plan)
            with self.assertRaisesRegex(
                ValueError,
                "READY_FOR_PRODUCTION_ENGINE",
            ):
                build_manifest(
                    plan,
                    path,
                    plan["branches"][0],
                    self.config,
                )

    def test_build_manifest_creates_one_requirement_per_beat(self) -> None:
        plan = approved_plan()
        with tempfile.TemporaryDirectory() as directory:
            path = write_plan(Path(directory), plan)
            manifest = build_manifest(
                plan,
                path,
                plan["branches"][0],
                self.config,
            )

        self.assertEqual(manifest["concept_id"], "concept-1")
        self.assertEqual(manifest["format"], "long_form")
        self.assertEqual(len(manifest["requirements"]), 2)
        self.assertEqual(manifest["requirements"][0]["beat_id"], "lf001")
        self.assertEqual(
            manifest["requirements"][0]["routing"]["next_source_tier"],
            "OWN_LIBRARY",
        )
        self.assertTrue(
            manifest["manifest_provenance"]["approved_format_plan_sha256"]
        )

    def test_prepare_binds_manifest_to_current_narration_timing(self) -> None:
        plan = approved_plan()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            approved = root / "approved"
            timings = root / "timings"
            manifests = root / "manifests"
            approved.mkdir()
            timings.mkdir()
            manifests.mkdir()
            plan_path = write_plan(approved, plan)
            timing_path = (
                timings
                / "concept-1.long_form.narration_timing_map.json"
            )
            timing_path.write_text(
                json.dumps(
                    {
                        "concept_id": "concept-1",
                        "format": "long_form",
                        "status": "READY_FOR_ROUGH_CUT",
                        "segments": [],
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(visual_acquisition, "TIMING_DIR", timings),
                patch.object(visual_acquisition, "MANIFESTS_DIR", manifests),
                patch.object(
                    visual_acquisition,
                    "SUMMARY_FILE",
                    root / "summary.json",
                ),
                patch.object(visual_acquisition, "OUTPUT_DIR", root),
            ):
                result = visual_acquisition.run_prepare(
                    approved,
                    self.config,
                )

            self.assertEqual(result["status"], "VISUAL_MANIFESTS_READY")
            manifest_path = (
                manifests
                / "concept-1.long_form.visual_manifest.json"
            )
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            provenance = manifest["manifest_provenance"]
            self.assertEqual(
                provenance["narration_timing_map_sha256"],
                visual_acquisition.sha256_file(timing_path),
            )
            self.assertEqual(
                provenance["narration_timing_map"],
                str(timing_path.resolve()),
            )

    def test_verified_free_asset_beats_paid_ai(self) -> None:
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
            self.config,
            remaining_budget_usd=10.0,
        )

        self.assertEqual(decision["status"], "SELECTED")
        self.assertEqual(decision["selected_candidate_id"], "stock-1")
        self.assertEqual(decision["estimated_paid_cost_usd"], 0.0)

    def test_editorial_excerpt_requires_review_before_paid_tier(self) -> None:
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
            self.config,
            remaining_budget_usd=10.0,
        )

        self.assertEqual(decision["status"], "HUMAN_REVIEW_REQUIRED")
        self.assertEqual(decision["review_candidate_id"], "excerpt-1")
        self.assertIsNone(decision["selected_candidate_id"])

    def test_clip_length_never_auto_approves_excerpt(self) -> None:
        short_excerpt = candidate("excerpt-1", "EDITORIAL_EXCERPT")
        short_excerpt["duration_seconds"] = 1.0

        state, reason = candidate_state(
            short_excerpt,
            self.config,
            remaining_budget_usd=10.0,
        )

        self.assertTrue(
            self.config["never_treat_clip_duration_as_permission"]
        )
        self.assertEqual(state, "HUMAN_REVIEW_REQUIRED")
        self.assertEqual(reason, "RIGHTS_OR_CONTEXT_REVIEW")

    def test_unverified_free_asset_is_blocked(self) -> None:
        unverified = candidate(
            "stock-1",
            "FREE_COMMERCIAL_LICENSE",
            rights_status="UNKNOWN",
        )

        state, reason = candidate_state(
            unverified,
            self.config,
            remaining_budget_usd=10.0,
        )

        self.assertEqual(state, "BLOCKED")
        self.assertEqual(reason, "RIGHTS_NOT_VERIFIED")

    def test_paid_candidate_over_remaining_budget_is_blocked(self) -> None:
        paid = candidate(
            "ai-1",
            "CHEAP_AI",
            cost=2.0,
            rights_status="PROVIDER_LICENSED",
        )

        state, reason = candidate_state(
            paid,
            self.config,
            remaining_budget_usd=1.5,
        )

        self.assertEqual(state, "BLOCKED")
        self.assertEqual(reason, "PAID_VISUAL_HARD_CAP")

    def test_route_manifest_tracks_paid_spend(self) -> None:
        plan = approved_plan()
        with tempfile.TemporaryDirectory() as directory:
            path = write_plan(Path(directory), plan)
            manifest = build_manifest(
                plan,
                path,
                plan["branches"][0],
                self.config,
            )

        for index, requirement in enumerate(
            manifest["requirements"],
            start=1,
        ):
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

        routed = route_manifest(
            manifest,
            self.config,
            verify_provenance=False,
        )

        summary = routed["routing_summary"]
        self.assertEqual(summary["estimated_paid_cost_usd"], 8.0)
        self.assertFalse(summary["within_target"])
        self.assertTrue(summary["within_hard_cap"])
        self.assertEqual(summary["status"], "ROUTED")

    def test_hard_cap_prevents_second_paid_selection(self) -> None:
        plan = approved_plan()
        with tempfile.TemporaryDirectory() as directory:
            path = write_plan(Path(directory), plan)
            manifest = build_manifest(
                plan,
                path,
                plan["branches"][0],
                self.config,
            )

        for index, requirement in enumerate(
            manifest["requirements"],
            start=1,
        ):
            requirement["candidates"] = [
                candidate(
                    f"premium-{index}",
                    "HIGGSFIELD_PREMIUM",
                    cost=6.0,
                    rights_status="PROVIDER_LICENSED",
                )
            ]

        routed = route_manifest(
            manifest,
            self.config,
            verify_provenance=False,
        )

        statuses = [
            item["routing"]["status"]
            for item in routed["requirements"]
        ]
        self.assertEqual(
            statuses,
            ["SELECTED", "ACQUISITION_REQUIRED"],
        )
        self.assertEqual(
            routed["routing_summary"]["estimated_paid_cost_usd"],
            6.0,
        )
        self.assertTrue(
            routed["routing_summary"]["within_hard_cap"]
        )


if __name__ == "__main__":
    unittest.main()
