from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import visual_candidate_review as review
from visual_search import shot_fingerprint


def card(shot_id: str, desired: str) -> dict:
    return {
        "shot_id": shot_id,
        "beat_id": shot_id.replace("shot", "beat"),
        "time_range": {"start_seconds": 0, "end_seconds": 2},
        "story_purpose": "hook",
        "desired_visual": desired,
        "search_terms": [desired],
        "source_strategy": {
            "selected_candidate_id": None,
            "creator_excerpt_allowed_only_after_human_rights_context_review": True,
        },
        "cinematic_direction": {"camera_angle": "eye"},
        "premium_generation_candidate": False,
    }


def result_shot(current_card: dict, candidate_id: str) -> dict:
    return {
        "shot_id": current_card["shot_id"],
        "creative_version": int(current_card.get("creative_version") or 1),
        "shot_fingerprint": shot_fingerprint(current_card),
        "candidates": [
            {
                "candidate_id": candidate_id,
                "shot_id": current_card["shot_id"],
                "source_tier": "FREE_COMMERCIAL_LICENSE",
                "source_url": f"https://example.test/{candidate_id}",
                "rights_status": "VERIFIED",
                "commercial_use_allowed": True,
                "state": "ELIGIBLE",
                "estimated_cost_usd": 0.0,
            }
        ],
        "eligible": 1,
        "human_review_required": 0,
        "search_gap": False,
        "premium_generation_candidate": False,
    }


class VisualCandidateReviewTests(unittest.TestCase):
    def paths(self, root: Path):
        results = root / "results"
        storyboards = root / "storyboards"
        reviews = root / "reviews"
        results.mkdir()
        storyboards.mkdir()
        reviews.mkdir()
        return results, storyboards, reviews

    def write_board(
        self,
        storyboards: Path,
        cards: list[dict],
    ) -> Path:
        path = storyboards / "c1.short.storyboard.json"
        path.write_text(
            json.dumps(
                {
                    "concept_id": "c1",
                    "format": "short",
                    "status": "READY_FOR_VISUAL_SEARCH",
                    "cards": cards,
                }
            ),
            encoding="utf-8",
        )
        return path

    def write_results(
        self,
        results: Path,
        shots: list[dict],
    ) -> Path:
        path = results / "c1.short.visual_search_results.json"
        path.write_text(
            json.dumps(
                {
                    "artifact": "visual_search_results",
                    "concept_id": "c1",
                    "format": "short",
                    "status": "READY_FOR_CANDIDATE_REVIEW",
                    "shots": shots,
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_storyboard_change_blocks_old_visual_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results, storyboards, reviews = self.paths(root)
            first = card("shot-001", "old visual")
            board_path = self.write_board(storyboards, [first])
            result_path = self.write_results(
                results,
                [result_shot(first, "candidate-1")],
            )
            with (
                patch.object(review, "RESULT_DIR", results),
                patch.object(review, "STORYBOARD_DIR", storyboards),
                patch.object(review, "REVIEW_DIR", reviews),
            ):
                accepted = review.apply_action(
                    result_file=str(result_path),
                    shot_id="shot-001",
                    action="SELECT",
                    candidate_id="candidate-1",
                )
                self.assertEqual(
                    accepted["decisions"]["shot-001"]["status"],
                    "SELECTED",
                )

                changed = card("shot-001", "new visual")
                board_path.write_text(
                    json.dumps(
                        {
                            "concept_id": "c1",
                            "format": "short",
                            "status": "READY_FOR_VISUAL_SEARCH",
                            "cards": [changed],
                        }
                    ),
                    encoding="utf-8",
                )
                snapshot = review.snapshot()
                with self.assertRaisesRegex(
                    ValueError,
                    "re-search is required",
                ):
                    review.apply_action(
                        result_file=str(result_path),
                        shot_id="shot-001",
                        action="SELECT",
                        candidate_id="candidate-1",
                    )

            self.assertEqual(snapshot["status"], "VISUAL_SEARCH_STALE")
            self.assertEqual(snapshot["stale_shots"], 1)
            self.assertEqual(snapshot["packets"][0]["decisions"], {})

    def test_unchanged_shot_decision_survives_other_shot_result_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results, storyboards, reviews = self.paths(root)
            shot_one = card("shot-001", "wing bend")
            shot_two = card("shot-002", "landing gear")
            self.write_board(storyboards, [shot_one, shot_two])
            result_path = self.write_results(
                results,
                [
                    result_shot(shot_one, "candidate-1"),
                    result_shot(shot_two, "candidate-2"),
                ],
            )
            with (
                patch.object(review, "RESULT_DIR", results),
                patch.object(review, "STORYBOARD_DIR", storyboards),
                patch.object(review, "REVIEW_DIR", reviews),
            ):
                review.apply_action(
                    result_file=str(result_path),
                    shot_id="shot-001",
                    action="SELECT",
                    candidate_id="candidate-1",
                )

                refreshed = json.loads(
                    result_path.read_text(encoding="utf-8")
                )
                refreshed["shots"][1] = result_shot(
                    shot_two,
                    "candidate-2-new",
                )
                result_path.write_text(
                    json.dumps(refreshed),
                    encoding="utf-8",
                )
                snapshot = review.snapshot()

            decisions = snapshot["packets"][0]["decisions"]
            self.assertIn("shot-001", decisions)
            self.assertNotIn("shot-002", decisions)
            self.assertEqual(
                decisions["shot-001"]["candidate_id"],
                "candidate-1",
            )


if __name__ == "__main__":
    unittest.main()
