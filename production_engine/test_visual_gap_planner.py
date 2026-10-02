from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import visual_gap_planner as gap


class VisualGapPlannerTests(unittest.TestCase):
    def fixture(self, root: Path):
        rough_dir = root / "rough"
        review_dir = root / "reviews"
        gap_dir = root / "gaps"
        rough_dir.mkdir()
        review_dir.mkdir()
        gap_dir.mkdir()

        rough_path = rough_dir / "c1.short.visual_rough_cut.json"
        rough = {
            "artifact": "visual_rough_cut_manifest",
            "concept_id": "c1",
            "format": "short",
            "status": "READY_FOR_HUMAN_ROUGH_CUT_GATE",
            "scenes": [
                {
                    "shot_id": "shot-001",
                    "time_range": {"start_seconds": 0, "end_seconds": 2},
                    "story_purpose": "hook",
                    "desired_visual": "hero impact",
                    "cinematic_direction": {"framing": "close"},
                    "visual_value_score": {"total": 19},
                    "premium_generation_candidate": True,
                    "visual_assignment": {
                        "status": "PLACEHOLDER",
                        "reason": "NEEDS_BETTER_VISUAL",
                    },
                }
            ],
        }
        rough_path.write_text(json.dumps(rough), encoding="utf-8")

        review_path = review_dir / "c1.short.visual_rough_cut_review.json"
        review = {
            "artifact": "visual_rough_cut_review",
            "concept_id": "c1",
            "format": "short",
            "decision": "APPROVE_WITH_GAPS",
            "approved_for_gap_planning": True,
            "source_rough_cut": str(rough_path.resolve()),
            "source_rough_cut_sha256": gap.sha256_file(rough_path),
        }
        review_path.write_text(json.dumps(review), encoding="utf-8")
        return rough_dir, review_dir, gap_dir, rough_path, review_path

    def test_gap_plan_becomes_stale_when_rough_cut_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rough_dir, review_dir, gap_dir, rough_path, _ = self.fixture(root)
            summary = root / "summary.json"
            with (
                patch.object(gap, "ROUGH", rough_dir),
                patch.object(gap, "REVIEWS", review_dir),
                patch.object(gap, "GAP", gap_dir),
                patch.object(gap, "SUMMARY", summary),
            ):
                prepared = gap.prepare()
                plan_path = gap_dir / "c1.short.visual_gap_plan.json"
                self.assertEqual(
                    prepared["status"],
                    "READY_FOR_VISUAL_SPEND_GATE",
                )
                self.assertIsNotNone(gap.gap_plan_is_current(plan_path))

                rough = json.loads(rough_path.read_text(encoding="utf-8"))
                rough["scenes"][0]["desired_visual"] = "changed hero"
                rough_path.write_text(json.dumps(rough), encoding="utf-8")
                self.assertIsNone(gap.gap_plan_is_current(plan_path))

    def test_rework_decision_prunes_old_gap_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rough_dir, review_dir, gap_dir, _, review_path = self.fixture(root)
            summary = root / "summary.json"
            with (
                patch.object(gap, "ROUGH", rough_dir),
                patch.object(gap, "REVIEWS", review_dir),
                patch.object(gap, "GAP", gap_dir),
                patch.object(gap, "SUMMARY", summary),
            ):
                gap.prepare()
                plan_path = gap_dir / "c1.short.visual_gap_plan.json"
                self.assertTrue(plan_path.exists())

                review = json.loads(review_path.read_text(encoding="utf-8"))
                review["decision"] = "REWORK_VISUAL"
                review["approved_for_gap_planning"] = False
                review_path.write_text(json.dumps(review), encoding="utf-8")
                state = gap.prepare()

            self.assertFalse(plan_path.exists())
            self.assertEqual(
                state["status"],
                "WAITING_FOR_APPROVED_ROUGH_CUT",
            )


if __name__ == "__main__":
    unittest.main()
