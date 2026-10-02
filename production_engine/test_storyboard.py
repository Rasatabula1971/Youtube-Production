from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import storyboard


class StoryboardTests(unittest.TestCase):
    def _paths(self, root: Path) -> tuple[Path, Path]:
        t, v = root / "timing.json", root / "visual.json"
        t.write_text("{}", encoding="utf-8"); v.write_text("{}", encoding="utf-8")
        return t, v

    def test_high_value_unfilled_hook_becomes_candidate_not_authorized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t, v = self._paths(Path(tmp))
            timing = {"concept_id":"c1","format":"shorts","status":"READY_FOR_ROUGH_CUT","segments":[{"segment_id":"b1","audio_start_seconds":0.0,"audio_end_seconds":3.0}]}
            visual = {"concept_id":"c1","format":"shorts","requirements":[{"beat_id":"b1","narrative_purpose":"hook","visual_treatment":"dramatic steel impact","routing":{"selected_candidate_id":None}}]}
            result = storyboard.build_storyboard(timing, visual, t, v)
        card = result["cards"][0]
        self.assertTrue(card["premium_generation_candidate"])
        self.assertFalse(card["premium_generation_authorized"])
        self.assertTrue(card["source_strategy"]["search_existing_first"])

    def test_existing_asset_prevents_premium_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t, v = self._paths(Path(tmp))
            timing = {"concept_id":"c1","format":"long_form","status":"READY_FOR_ROUGH_CUT","segments":[{"segment_id":"b1","audio_start_seconds":0.0,"audio_end_seconds":5.0}]}
            visual = {"concept_id":"c1","format":"long_form","requirements":[{"beat_id":"b1","narrative_purpose":"climax","visual_treatment":"wide reveal","routing":{"selected_candidate_id":"archive-1"}}]}
            result = storyboard.build_storyboard(timing, visual, t, v)
        self.assertFalse(result["cards"][0]["premium_generation_candidate"])

    def test_storyboard_rejects_timing_and_visual_beat_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t, v = self._paths(Path(tmp))
            timing = {
                "concept_id": "c1",
                "format": "shorts",
                "status": "READY_FOR_ROUGH_CUT",
                "segments": [
                    {
                        "segment_id": "b1",
                        "audio_start_seconds": 0.0,
                        "audio_end_seconds": 3.0,
                    }
                ],
            }
            visual = {
                "concept_id": "c1",
                "format": "shorts",
                "requirements": [
                    {
                        "beat_id": "different",
                        "narrative_purpose": "hook",
                        "visual_treatment": "impact",
                        "routing": {"selected_candidate_id": None},
                    }
                ],
            }
            with self.assertRaisesRegex(ValueError, "exactly match"):
                storyboard.build_storyboard(timing, visual, t, v)

    def test_changed_timing_hash_makes_storyboard_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            timings = root / "timings"
            visuals = root / "visuals"
            boards = root / "boards"
            timings.mkdir()
            visuals.mkdir()
            boards.mkdir()
            timing_path = timings / "c1.shorts.narration_timing_map.json"
            visual_path = visuals / "c1.shorts.visual_manifest.json"
            timing = {
                "concept_id": "c1",
                "format": "shorts",
                "status": "READY_FOR_ROUGH_CUT",
                "segments": [
                    {
                        "segment_id": "b1",
                        "audio_start_seconds": 0.0,
                        "audio_end_seconds": 3.0,
                    }
                ],
            }
            timing_path.write_text(json.dumps(timing), encoding="utf-8")
            visual = {
                "concept_id": "c1",
                "format": "shorts",
                "requirements": [
                    {
                        "beat_id": "b1",
                        "narrative_purpose": "hook",
                        "visual_treatment": "impact",
                        "routing": {"selected_candidate_id": None},
                    }
                ],
                "manifest_provenance": {
                    "narration_timing_map_sha256": storyboard.sha256_file(
                        timing_path
                    )
                },
            }
            visual_path.write_text(json.dumps(visual), encoding="utf-8")
            with (
                patch.object(storyboard, "TIMING_DIR", timings),
                patch.object(storyboard, "VISUAL_DIR", visuals),
                patch.object(storyboard, "STORYBOARD_DIR", boards),
                patch.object(
                    storyboard,
                    "SUMMARY_FILE",
                    root / "summary.json",
                ),
            ):
                prepared = storyboard.prepare()
                board_path = boards / "c1.shorts.storyboard.json"
                self.assertEqual(prepared["status"], "READY_FOR_VISUAL_SEARCH")
                self.assertIsNotNone(
                    storyboard.storyboard_is_current(board_path)
                )
                timing["segments"][0]["audio_end_seconds"] = 4.0
                timing_path.write_text(json.dumps(timing), encoding="utf-8")
                self.assertIsNone(
                    storyboard.storyboard_is_current(board_path)
                )

    def test_creator_excerpt_is_never_auto_approved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t, v = self._paths(Path(tmp))
            timing = {"concept_id":"c1","format":"long_form","status":"READY_FOR_ROUGH_CUT","segments":[{"segment_id":"b1","audio_start_seconds":0.0,"audio_end_seconds":5.0}]}
            visual = {"concept_id":"c1","format":"long_form","requirements":[{"beat_id":"b1","narrative_purpose":"supporting_explanation","visual_treatment":"creator demonstration","routing":{"selected_candidate_id":None}}]}
            result = storyboard.build_storyboard(timing, visual, t, v)
        self.assertTrue(result["cards"][0]["source_strategy"]["creator_excerpt_allowed_only_after_human_rights_context_review"])


if __name__ == "__main__":
    unittest.main()
