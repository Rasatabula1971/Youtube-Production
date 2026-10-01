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
                    "desired_visual": "Airliner tire touches down with visible deformation.",
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

    def spend_review(self, gap_path: Path) -> dict:
        return {
            "artifact": "visual_spend_review",
            "status": "COMPLETE",
            "concept_id": "c1",
            "format": "short",
            "source_gap_plan": str(gap_path.resolve()),
            "source_gap_plan_sha256": handoff.sha256_file(gap_path),
            "decisions": {
                "shot-001": {
                    "decision": "AUTHORIZE_GENERATION",
                    "paid_generation_authorized": True,
                    "max_cost_usd": 2.5,
                    "note": "Worth paying for if free search cannot deliver the landing impact.",
                },
                "shot-002": {
                    "decision": "KEEP_PLACEHOLDER",
                    "paid_generation_authorized": False,
                    "max_cost_usd": 0,
                    "note": "",
                },
            },
        }

    def test_prepare_emits_only_explicitly_authorized_hero_shot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gaps = root / "gaps"
            spend = root / "spend"
            requests = root / "requests"
            summary = root / "summary.json"
            gap_path = write_json(gaps / "c1.short.visual_gap_plan.json", self.gap_plan())
            spend_path = write_json(
                spend / "c1.short.visual_spend_review.json",
                self.spend_review(gap_path),
            )

            with (
                patch.object(handoff, "GAP_DIR", gaps),
                patch.object(handoff, "SPEND_DIR", spend),
                patch.object(handoff, "REQUEST_DIR", requests),
                patch.object(handoff, "SUMMARY_FILE", summary),
            ):
                result = handoff.prepare()
                files = list(requests.glob("*.visual_generation_request.json"))
                request = json.loads(files[0].read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "READY_FOR_PROVIDER_HANDOFF")
        self.assertEqual(result["prepared"], 1)
        self.assertEqual(len(files), 1)
        self.assertEqual(request["shot_id"], "shot-001")
        self.assertEqual(request["provider_handoff"]["preferred_provider"], "higgsfield")
        self.assertTrue(request["provider_handoff"]["provider_neutral_request"])
        self.assertFalse(request["provider_handoff"]["provider_call_authorized"])
        self.assertFalse(request["spend_authorization"]["execution_authorized"])
        self.assertEqual(request["spend_authorization"]["max_cost_usd"], 2.5)
        self.assertEqual(request["generation_brief"]["camera_angle"], "low")
        self.assertEqual(result["provider_calls"], 0)
        self.assertFalse(result["paid_inference_executed"])
        self.assertTrue(spend_path.exists())

    def test_stale_spend_review_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gaps = root / "gaps"
            spend = root / "spend"
            requests = root / "requests"
            summary = root / "summary.json"
            gap_path = write_json(gaps / "c1.short.visual_gap_plan.json", self.gap_plan())
            review = self.spend_review(gap_path)
            review["source_gap_plan_sha256"] = "stale"
            write_json(spend / "c1.short.visual_spend_review.json", review)

            with (
                patch.object(handoff, "GAP_DIR", gaps),
                patch.object(handoff, "SPEND_DIR", spend),
                patch.object(handoff, "REQUEST_DIR", requests),
                patch.object(handoff, "SUMMARY_FILE", summary),
            ):
                with self.assertRaisesRegex(ValueError, "STALE_VISUAL_SPEND_REVIEW"):
                    handoff.prepare()

    def test_old_generation_requests_are_removed_when_authorization_disappears(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gaps = root / "gaps"
            spend = root / "spend"
            requests = root / "requests"
            summary = root / "summary.json"
            gap_path = write_json(gaps / "c1.short.visual_gap_plan.json", self.gap_plan())
            review = self.spend_review(gap_path)
            review["decisions"]["shot-001"] = {
                "decision": "KEEP_PLACEHOLDER",
                "paid_generation_authorized": False,
                "max_cost_usd": 0,
            }
            write_json(spend / "c1.short.visual_spend_review.json", review)
            stale = write_json(
                requests / "old.visual_generation_request.json",
                {"artifact": "visual_generation_request"},
            )

            with (
                patch.object(handoff, "GAP_DIR", gaps),
                patch.object(handoff, "SPEND_DIR", spend),
                patch.object(handoff, "REQUEST_DIR", requests),
                patch.object(handoff, "SUMMARY_FILE", summary),
            ):
                result = handoff.prepare()

        self.assertEqual(result["status"], "NO_PAID_VISUAL_GENERATION_AUTHORIZED")
        self.assertEqual(result["prepared"], 0)
        self.assertFalse(stale.exists())


if __name__ == "__main__":
    unittest.main()
