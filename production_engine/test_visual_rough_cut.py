from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import visual_rough_cut


class VisualRoughCutTests(unittest.TestCase):
    def test_rough_cut_never_unlocks_premium_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            timing_path = root / "timing.json"
            visual_path = root / "visual.json"
            timing_path.write_text("{}", encoding="utf-8")
            visual_path.write_text("{}", encoding="utf-8")
            timing = {
                "concept_id": "c1", "format": "shorts", "status": "READY_FOR_ROUGH_CUT",
                "total_duration_seconds": 4.0,
                "segments": [{"segment_id": "b1", "audio_start_seconds": 0.0, "audio_end_seconds": 4.0, "timeline_end_seconds": 4.0}],
            }
            visual = {
                "concept_id": "c1", "format": "shorts",
                "requirements": [{"beat_id": "b1", "narrative_purpose": "hook", "visual_treatment": "close-up", "routing": {"status": "ACQUISITION_REQUIRED", "selected_candidate_id": None}}],
            }
            result = visual_rough_cut.build_rough_cut(timing, visual, timing_path, visual_path)
        self.assertEqual(result["status"], "READY_FOR_HUMAN_ROUGH_CUT_GATE")
        self.assertFalse(result["premium_generation_allowed"])
        self.assertFalse(result["gate_policy"]["paid_visual_calls_allowed"])
        self.assertEqual(result["scenes"][0]["visual_assignment"]["status"], "PLACEHOLDER")

    def test_selected_verified_asset_can_fill_rough_cut(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            timing_path = root / "timing.json"; visual_path = root / "visual.json"
            timing_path.write_text("{}", encoding="utf-8"); visual_path.write_text("{}", encoding="utf-8")
            timing = {"concept_id": "c1", "format": "long_form", "status": "READY_FOR_ROUGH_CUT", "total_duration_seconds": 2.0, "segments": [{"segment_id": "b1", "audio_start_seconds": 0.0, "audio_end_seconds": 2.0, "timeline_end_seconds": 2.0}]}
            visual = {"concept_id": "c1", "format": "long_form", "requirements": [{"beat_id": "b1", "narrative_purpose": "setup", "visual_treatment": "archive", "routing": {"status": "SELECTED", "selected_candidate_id": "free-1", "reason": "VERIFIED_RIGHTS"}}]}
            result = visual_rough_cut.build_rough_cut(timing, visual, timing_path, visual_path)
        self.assertEqual(result["scenes"][0]["visual_assignment"]["status"], "FREE_OR_VERIFIED_ASSET")


if __name__ == "__main__":
    unittest.main()
