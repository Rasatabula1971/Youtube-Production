from __future__ import annotations

import json
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

    def test_selected_asset_without_current_managed_file_is_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board_path = root / "board.json"
            review_path = root / "review.json"
            board_path.write_text("{}", encoding="utf-8")
            review_path.write_text("{}", encoding="utf-8")
            card = {
                "shot_id": "shot-001",
                "beat_id": "b1",
                "time_range": {"start_seconds": 0, "end_seconds": 2},
                "story_purpose": "hook",
                "desired_visual": "impact",
                "cinematic_direction": {},
            }
            board = {
                "concept_id": "c1",
                "format": "shorts",
                "status": "READY_FOR_VISUAL_SEARCH",
                "cards": [card],
            }
            review = {
                "concept_id": "c1",
                "format": "shorts",
                "status": "READY_FOR_ROUGH_CUT",
                "decisions": {
                    "shot-001": {
                        "status": "SELECTED",
                        "candidate_id": "free-1",
                        "candidate_source_url": "https://example.test/free-1",
                        "candidate_fingerprint": "candidate-fp",
                        "shot_fingerprint": visual_rough_cut.shot_fingerprint(card),
                    }
                },
            }
            rough = visual_rough_cut.build(
                board,
                review,
                None,
                board_path,
                review_path,
            )

        assignment = rough["scenes"][0]["visual_assignment"]
        self.assertEqual(assignment["status"], "PLACEHOLDER")
        self.assertEqual(
            assignment["reason"],
            "SELECTED_ASSET_NOT_ACQUIRED_CURRENT",
        )

    def test_current_managed_asset_fills_rough_cut_with_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board_path = root / "board.json"
            review_path = root / "review.json"
            result_path = root / "result.json"
            asset_path = root / "asset.mp4"
            registry_path = root / "registry.json"
            for path in (board_path, review_path, result_path):
                path.write_text("{}", encoding="utf-8")
            asset_path.write_bytes(b"managed-asset")

            card = {
                "shot_id": "shot-001",
                "beat_id": "b1",
                "time_range": {"start_seconds": 0, "end_seconds": 2},
                "story_purpose": "hook",
                "desired_visual": "impact",
                "cinematic_direction": {},
            }
            decision = {
                "status": "SELECTED",
                "candidate_id": "free-1",
                "candidate_source_url": "https://example.test/free-1",
                "candidate_fingerprint": "candidate-fp",
                "shot_fingerprint": visual_rough_cut.shot_fingerprint(card),
            }
            board = {
                "concept_id": "c1",
                "format": "shorts",
                "status": "READY_FOR_VISUAL_SEARCH",
                "cards": [card],
            }
            review = {
                "concept_id": "c1",
                "format": "shorts",
                "status": "READY_FOR_ROUGH_CUT",
                "decisions": {"shot-001": decision},
            }
            record = {
                "candidate_id": "free-1",
                "candidate_fingerprint": "candidate-fp",
                "asset_file": str(asset_path),
                "asset_sha256": visual_rough_cut.sha256_file(asset_path),
                "provenance": {
                    "search_result": str(result_path),
                    "search_result_sha256": visual_rough_cut.sha256_file(result_path),
                    "candidate_review": str(review_path),
                    "candidate_review_sha256": visual_rough_cut.sha256_file(review_path),
                },
            }
            registry_path.write_text(json.dumps(record), encoding="utf-8")

            rough = visual_rough_cut.build(
                board,
                review,
                None,
                board_path,
                review_path,
                managed_assets={
                    "shot-001": (registry_path, record),
                },
            )

        assignment = rough["scenes"][0]["visual_assignment"]
        self.assertEqual(
            assignment["status"],
            "MANAGED_EXISTING_ASSET",
        )
        self.assertEqual(
            assignment["asset_sha256"],
            record["asset_sha256"],
        )
        self.assertIn(
            "shot-001",
            rough["provenance"]["managed_asset_registry"],
        )

    def test_approved_editorial_without_local_file_remains_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board_path = root / "board.json"
            review_path = root / "review.json"
            rights_path = root / "rights.json"
            for path in (board_path, review_path, rights_path):
                path.write_text("{}", encoding="utf-8")

            card = {
                "shot_id": "shot-001",
                "beat_id": "b1",
                "time_range": {"start_seconds": 0, "end_seconds": 2},
                "story_purpose": "hook",
                "desired_visual": "creator event",
                "cinematic_direction": {},
            }
            board = {
                "concept_id": "c1",
                "format": "shorts",
                "status": "READY_FOR_VISUAL_SEARCH",
                "cards": [card],
            }
            review = {
                "concept_id": "c1",
                "format": "shorts",
                "status": "READY_FOR_ROUGH_CUT",
                "decisions": {
                    "shot-001": {
                        "status": "SELECTED_PENDING_RIGHTS_CONTEXT_GATE",
                        "candidate_id": "creator-1",
                        "candidate_source_url": "https://example.test/creator",
                        "candidate_fingerprint": "candidate-fp",
                        "shot_fingerprint": visual_rough_cut.shot_fingerprint(card),
                    }
                },
            }
            rights = {
                "decisions": {
                    "shot-001": {
                        "approved_for_rough_cut": True,
                    }
                }
            }
            rough = visual_rough_cut.build(
                board,
                review,
                rights,
                board_path,
                review_path,
                rights_path,
            )

        assignment = rough["scenes"][0]["visual_assignment"]
        self.assertEqual(assignment["status"], "PLACEHOLDER")
        self.assertEqual(
            assignment["reason"],
            "EDITORIAL_ASSET_REQUIRES_MANUAL_SUPPLY",
        )

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
