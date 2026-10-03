import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from visual_gap_planner import build as build_gaps
from visual_rough_cut import build, sha256_file
from visual_search import shot_fingerprint


def editorial_board() -> dict:
    return {
        "status": "READY_FOR_VISUAL_SEARCH",
        "concept_id": "c",
        "format": "long",
        "cards": [
            {
                "shot_id": "s1",
                "beat_id": "b1",
                "time_range": {},
                "story_purpose": "hook",
                "desired_visual": "x",
                "cinematic_direction": {},
                "visual_value_score": {"total": 20},
                "premium_generation_candidate": True,
            }
        ],
    }


def editorial_review(board: dict) -> dict:
    return {
        "status": "READY_FOR_ROUGH_CUT",
        "concept_id": "c",
        "format": "long",
        "decisions": {
            "s1": {
                "status": "SELECTED_PENDING_RIGHTS_CONTEXT_GATE",
                "candidate_id": "e1",
                "candidate_source_url": "https://example.test",
                "shot_fingerprint": shot_fingerprint(board["cards"][0]),
            }
        },
    }


class VisualPostReviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_editorial_excerpt_stays_placeholder_without_rights_gate(self):
        board = editorial_board()
        review = editorial_review(board)
        bp = self.root / "b.json"
        rp = self.root / "r.json"
        bp.write_text("{}", encoding="utf-8")
        rp.write_text("{}", encoding="utf-8")
        rough = build(board, review, None, bp, rp)
        self.assertEqual(rough["scenes"][0]["visual_assignment"]["status"], "PLACEHOLDER")

    def test_rights_approved_editorial_excerpt_can_enter_rough_cut(self):
        # Since Slice 16 an approved excerpt enters the rough cut only as a
        # current managed local file registered after the rights gate.
        board = editorial_board()
        review = editorial_review(board)
        rights = {"decisions": {"s1": {"approved_for_rough_cut": True}}}
        bp = self.root / "b.json"
        rp = self.root / "r.json"
        rights_path = self.root / "rights.json"
        result_path = self.root / "result.json"
        asset_path = self.root / "excerpt.mp4"
        registry_path = self.root / "registry.json"
        for path in (bp, rp, rights_path, result_path):
            path.write_text("{}", encoding="utf-8")
        asset_path.write_bytes(b"editorial-excerpt")
        record = {
            "candidate_id": "e1",
            "asset_file": str(asset_path),
            "asset_sha256": sha256_file(asset_path),
            "provenance": {
                "search_result": str(result_path),
                "search_result_sha256": sha256_file(result_path),
                "candidate_review": str(rp),
                "candidate_review_sha256": sha256_file(rp),
                "rights_review": str(rights_path),
                "rights_review_sha256": sha256_file(rights_path),
            },
        }
        registry_path.write_text(json.dumps(record), encoding="utf-8")
        rough = build(
            board,
            review,
            rights,
            bp,
            rp,
            rights_path,
            managed_assets={"s1": (registry_path, record)},
        )
        assignment = rough["scenes"][0]["visual_assignment"]
        self.assertEqual(assignment["status"], "MANAGED_EDITORIAL_ASSET")
        self.assertEqual(assignment["asset_sha256"], record["asset_sha256"])

    def test_gap_planner_keeps_paid_generation_locked(self):
        rough = {
            "status": "READY_FOR_HUMAN_ROUGH_CUT_GATE",
            "concept_id": "c",
            "format": "long",
            "scenes": [
                {
                    "shot_id": "s1",
                    "time_range": {},
                    "story_purpose": "hook",
                    "desired_visual": "hero",
                    "cinematic_direction": {"camera_movement": "push_in"},
                    "visual_value_score": {"total": 20},
                    "premium_generation_candidate": True,
                    "visual_assignment": {"status": "PLACEHOLDER", "reason": "gap"},
                }
            ],
        }
        rp = self.root / "rough.json"
        reviewp = self.root / "review.json"
        rp.write_text("rough", encoding="utf-8")
        reviewp.write_text("review", encoding="utf-8")
        review = {
            "concept_id": "c",
            "format": "long",
            "decision": "APPROVE_WITH_GAPS",
            "approved_for_gap_planning": True,
            "source_rough_cut": str(rp.resolve()),
            "source_rough_cut_sha256": hashlib.sha256(b"rough").hexdigest(),
        }
        plan = build_gaps(rough, review, rp, reviewp)
        self.assertEqual(plan["gaps"][0]["resolution_class"], "D_HERO_GENERATION")
        self.assertIs(plan["gaps"][0]["premium_generation_authorized"], False)


if __name__ == "__main__":
    unittest.main()
