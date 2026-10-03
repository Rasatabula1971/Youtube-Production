from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import visual_generation_handoff as handoff


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class VisualGenerationHandoffTests(unittest.TestCase):
    def gap_plan(self) -> dict:
        return {
            "artifact": "visual_gap_plan",
            "concept_id": "c1",
            "format": "short",
            "gaps": [
                {
                    "shot_id": "shot-001",
                    "time_range": {"start_seconds": 0, "end_seconds": 3},
                    "story_purpose": "hook",
                    "desired_visual": (
                        "Airliner tire touches down with visible deformation."
                    ),
                    "cinematic_direction": {
                        "camera_angle": "low",
                        "framing": "close_up",
                        "camera_movement": "controlled_push_in",
                        "lens_feel": "35mm",
                        "lighting": "directional_high_contrast",
                        "depth_of_field": "shallow",
                        "motion_speed": "slow_motion_on_impact",
                        "transition": "hard_cut",
                    },
                    "premium_generation_recommended": True,
                },
                {
                    "shot_id": "shot-002",
                    "story_purpose": "supporting_explanation",
                    "desired_visual": "Tire cutaway.",
                    "cinematic_direction": {},
                    "premium_generation_recommended": False,
                },
            ],
        }

    def decision(self) -> dict:
        return {
            "decision": "AUTHORIZE_GENERATION",
            "paid_generation_authorized": True,
            "max_cost_usd": 2.5,
            "note": (
                "Worth paying for if free search cannot deliver the landing impact."
            ),
        }

    def spend_review(
        self,
        gap_path: Path,
        decision: dict | None = None,
    ) -> dict:
        current = decision or self.decision()
        return {
            "artifact": "visual_spend_review",
            "status": "COMPLETE",
            "concept_id": "c1",
            "format": "short",
            "source_gap_plan": str(gap_path.resolve()),
            "source_gap_plan_sha256": handoff.sha256_file(gap_path),
            "decisions": {"shot-001": current},
        }

    def spend_snapshot(
        self,
        gap_path: Path,
        spend_path: Path,
        decision: dict,
    ) -> dict:
        return {
            "status": "COMPLETE",
            "complete": True,
            "global_cap_valid": True,
            "hero_candidates": 1,
            "authorized": 1,
            "authorized_max_total_usd": 2.5,
            "items": [
                {
                    "concept_id": "c1",
                    "format": "short",
                    "gap_plan_file": str(gap_path),
                    "gap_plan_sha256": handoff.sha256_file(gap_path),
                    "spend_review_file": str(spend_path),
                    "spend_review_sha256": handoff.sha256_file(spend_path),
                    "decisions": {"shot-001": decision},
                }
            ],
        }

    def test_prepare_emits_only_explicitly_authorized_hero_shot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gaps = root / "gaps"
            spend = root / "spend"
            requests = root / "requests"
            summary = root / "summary.json"
            gap_payload = self.gap_plan()
            gap_path = write_json(
                gaps / "c1.short.visual_gap_plan.json",
                gap_payload,
            )
            decision = self.decision()
            spend_path = write_json(
                spend / "c1.short.visual_spend_review.json",
                self.spend_review(gap_path, decision),
            )
            snapshot = self.spend_snapshot(
                gap_path,
                spend_path,
                decision,
            )

            with (
                patch.object(handoff, "GAP_DIR", gaps),
                patch.object(handoff, "SPEND_DIR", spend),
                patch.object(handoff, "REQUEST_DIR", requests),
                patch.object(handoff, "SUMMARY_FILE", summary),
                patch.object(
                    handoff,
                    "visual_spend_snapshot",
                    return_value=snapshot,
                ),
                patch.object(
                    handoff,
                    "gap_plan_is_current",
                    return_value=(gap_payload, Path("rough"), Path("review")),
                ),
            ):
                result = handoff.prepare()
                files = list(
                    requests.glob("*.visual_generation_request.json")
                )
                request = json.loads(
                    files[0].read_text(encoding="utf-8")
                )

        self.assertEqual(result["status"], "READY_FOR_PROVIDER_HANDOFF")
        self.assertEqual(result["prepared"], 1)
        self.assertEqual(len(files), 1)
        self.assertEqual(request["shot_id"], "shot-001")
        self.assertEqual(
            request["provider_handoff"]["preferred_provider"],
            "higgsfield",
        )
        self.assertTrue(
            request["provider_handoff"]["provider_neutral_request"]
        )
        self.assertFalse(
            request["provider_handoff"]["provider_call_authorized"]
        )
        self.assertFalse(
            request["spend_authorization"]["execution_authorized"]
        )
        self.assertEqual(
            request["spend_authorization"]["max_cost_usd"],
            2.5,
        )
        self.assertEqual(
            request["provenance"]["visual_spend_decision_sha256"],
            handoff._fingerprint(decision),
        )
        self.assertEqual(result["provider_calls"], 0)
        self.assertFalse(result["paid_inference_executed"])

    def test_stale_spend_review_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gaps = root / "gaps"
            spend = root / "spend"
            requests = root / "requests"
            summary = root / "summary.json"
            gap_payload = self.gap_plan()
            gap_path = write_json(
                gaps / "c1.short.visual_gap_plan.json",
                gap_payload,
            )
            decision = self.decision()
            review = self.spend_review(gap_path, decision)
            review["source_gap_plan_sha256"] = "stale"
            spend_path = write_json(
                spend / "c1.short.visual_spend_review.json",
                review,
            )
            snapshot = self.spend_snapshot(
                gap_path,
                spend_path,
                decision,
            )

            with (
                patch.object(handoff, "GAP_DIR", gaps),
                patch.object(handoff, "SPEND_DIR", spend),
                patch.object(handoff, "REQUEST_DIR", requests),
                patch.object(handoff, "SUMMARY_FILE", summary),
                patch.object(
                    handoff,
                    "visual_spend_snapshot",
                    return_value=snapshot,
                ),
                patch.object(
                    handoff,
                    "gap_plan_is_current",
                    return_value=(gap_payload, Path("rough"), Path("review")),
                ),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "STALE_VISUAL_SPEND_REVIEW",
                ):
                    handoff.prepare()

    def test_incomplete_spend_state_prunes_old_generation_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requests = root / "requests"
            summary = root / "summary.json"
            stale = write_json(
                requests / "old.visual_generation_request.json",
                {"artifact": "visual_generation_request"},
            )

            with (
                patch.object(handoff, "REQUEST_DIR", requests),
                patch.object(handoff, "SUMMARY_FILE", summary),
                patch.object(
                    handoff,
                    "visual_spend_snapshot",
                    return_value={
                        "status": "READY_FOR_VISUAL_SPEND_GATE",
                        "complete": False,
                        "items": [],
                    },
                ),
            ):
                result = handoff.prepare()

        self.assertEqual(
            result["status"],
            "WAITING_FOR_COMPLETE_VISUAL_SPEND_DECISIONS",
        )
        self.assertEqual(result["prepared"], 0)
        self.assertFalse(stale.exists())

    def test_no_authorized_spend_prunes_old_generation_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requests = root / "requests"
            summary = root / "summary.json"
            stale = write_json(
                requests / "old.visual_generation_request.json",
                {"artifact": "visual_generation_request"},
            )
            with (
                patch.object(handoff, "REQUEST_DIR", requests),
                patch.object(handoff, "SUMMARY_FILE", summary),
                patch.object(
                    handoff,
                    "visual_spend_snapshot",
                    return_value={
                        "status": "NO_PREMIUM_GENERATION_REQUIRED",
                        "complete": True,
                        "global_cap_valid": True,
                        "authorized_max_total_usd": 0,
                        "items": [],
                    },
                ),
            ):
                result = handoff.prepare()

        self.assertEqual(
            result["status"],
            "NO_PAID_VISUAL_GENERATION_AUTHORIZED",
        )
        self.assertEqual(result["prepared"], 0)
        self.assertFalse(stale.exists())


if __name__ == "__main__":
    unittest.main()
