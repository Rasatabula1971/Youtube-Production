from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import visual_rough_cut_review as review


class VisualRoughCutReviewTests(unittest.TestCase):
    def test_approval_is_bound_to_exact_rough_cut(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rough_dir = root / "rough"
            review_dir = root / "reviews"
            rough_dir.mkdir()
            review_dir.mkdir()
            rough_path = rough_dir / "c1.short.visual_rough_cut.json"
            rough_path.write_text(
                json.dumps(
                    {
                        "artifact": "visual_rough_cut",
                        "concept_id": "c1",
                        "format": "short",
                        "summary": {"unresolved_visual_gaps": 1},
                        "scenes": [{"shot_id": "shot-001"}],
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(review, "ROUGH", rough_dir),
                patch.object(review, "REVIEW", review_dir),
            ):
                saved = review.apply_action(
                    rough_cut_file=str(rough_path),
                    decision="APPROVE_WITH_GAPS",
                )
                current = review.snapshot()
                rough = json.loads(rough_path.read_text(encoding="utf-8"))
                rough["scenes"].append({"shot_id": "shot-002"})
                rough_path.write_text(json.dumps(rough), encoding="utf-8")
                stale = review.snapshot()

            self.assertTrue(saved["approved_for_gap_planning"])
            self.assertTrue(current["complete"])
            self.assertEqual(current["accepted"], 1)
            self.assertFalse(stale["complete"])
            self.assertEqual(stale["pending"], 1)
            self.assertIsNone(stale["items"][0]["decision"])

    def test_rework_requires_instruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rough_dir = root / "rough"
            review_dir = root / "reviews"
            rough_dir.mkdir()
            review_dir.mkdir()
            rough_path = rough_dir / "c1.short.visual_rough_cut.json"
            rough_path.write_text(
                json.dumps(
                    {
                        "concept_id": "c1",
                        "format": "short",
                        "summary": {},
                        "scenes": [],
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(review, "ROUGH", rough_dir),
                patch.object(review, "REVIEW", review_dir),
                self.assertRaisesRegex(ValueError, "requires a note"),
            ):
                review.apply_action(
                    rough_cut_file=str(rough_path),
                    decision="REWORK_VISUAL",
                    note="",
                )


if __name__ == "__main__":
    unittest.main()
