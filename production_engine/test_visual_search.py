from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import visual_search


class VisualSearchTests(unittest.TestCase):
    def test_verified_free_candidate_is_eligible(self) -> None:
        candidate = visual_search.normalize_candidate({
            "candidate_id":"free-1","source_tier":"FREE_COMMERCIAL_LICENSE",
            "rights_status":"VERIFIED","commercial_use_allowed":True,
            "source_url":"https://example.test/free","estimated_cost_usd":0,
        }, "shot-001")
        self.assertEqual(candidate["state"], "ELIGIBLE")

    def test_creator_excerpt_requires_human_review_even_if_downloadable(self) -> None:
        candidate = visual_search.normalize_candidate({
            "candidate_id":"creator-1","source_tier":"EDITORIAL_EXCERPT",
            "rights_status":"UNKNOWN","commercial_use_allowed":None,
            "source_url":"https://example.test/video","creator":"Creator",
        }, "shot-001")
        self.assertEqual(candidate["state"], "HUMAN_REVIEW_REQUIRED")
        self.assertEqual(candidate["reason"], "CREATOR_EXCERPT_RIGHTS_CONTEXT_REVIEW")

    def test_unknown_rights_are_blocked(self) -> None:
        candidate = visual_search.normalize_candidate({
            "source_tier":"FREE_COMMERCIAL_LICENSE","rights_status":"UNKNOWN",
            "commercial_use_allowed":True,"source_url":"https://example.test/a",
        }, "shot-001")
        self.assertEqual(candidate["state"], "BLOCKED")

    def test_search_request_never_allows_paid_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"board.json"; p.write_text("{}",encoding="utf-8")
            board={"concept_id":"c1","format":"shorts","status":"READY_FOR_VISUAL_SEARCH","cards":[{"shot_id":"shot-001","beat_id":"b1","time_range":{},"desired_visual":"hammer strike","search_terms":["hammer strike"],"cinematic_direction":{},"premium_generation_candidate":True,"source_strategy":{"selected_candidate_id":None,"creator_excerpt_allowed_only_after_human_rights_context_review":True}}]}
            request=visual_search.build_search_request(board,p)
        self.assertFalse(request["policy"]["paid_generation_calls_allowed"])
        self.assertTrue(request["policy"]["search_existing_before_generation"])


if __name__ == "__main__":
    unittest.main()
