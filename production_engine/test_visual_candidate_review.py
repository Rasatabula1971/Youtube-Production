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


def current_request_state(path: Path):
    if not path.exists():
        return None
    return (json.loads(path.read_text(encoding="utf-8")), Path("board"))


def current_result_state(path: Path):
    if not path.exists():
        return None
    return (
        json.loads(path.read_text(encoding="utf-8")),
        Path("request"),
        {},
    )


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
        request_path = results / "c1.short.visual_search_request.json"
        request_path.write_text(
            json.dumps(
                {
                    "artifact": "visual_search_request",
                    "concept_id": "c1",
                    "format": "short",
                    "status": "SEARCH_REQUIRED",
                    "shots": [
                        {
                            "shot_id": item["shot_id"],
                            "shot_fingerprint": item["shot_fingerprint"],
                        }
                        for item in shots
                    ],
                }
            ),
            encoding="utf-8",
        )
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
                patch.object(
                    review,
                    "search_request_is_current",
                    side_effect=current_request_state,
                ),
                patch.object(
                    review,
                    "search_result_is_current",
                    side_effect=current_result_state,
                ),
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

    def test_editorial_candidate_routes_to_rights_even_if_state_is_tampered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results, storyboards, reviews = self.paths(root)
            current = card("shot-001", "creator crash clip")
            self.write_board(storyboards, [current])
            shot = result_shot(current, "creator-1")
            shot["candidates"][0].update(
                {
                    "source_tier": "EDITORIAL_EXCERPT",
                    "rights_status": "DISCOVERY_ONLY",
                    "commercial_use_allowed": None,
                    "human_review_required": True,
                    "state": "ELIGIBLE",
                }
            )
            shot["eligible"] = 0
            shot["human_review_required"] = 1
            result_path = self.write_results(results, [shot])

            with (
                patch.object(review, "RESULT_DIR", results),
                patch.object(review, "STORYBOARD_DIR", storyboards),
                patch.object(review, "REVIEW_DIR", reviews),
                patch.object(
                    review,
                    "search_result_is_current",
                    side_effect=current_result_state,
                ),
            ):
                saved = review.apply_action(
                    result_file=str(result_path),
                    shot_id="shot-001",
                    action="SELECT",
                    candidate_id="creator-1",
                )

            decision = saved["decisions"]["shot-001"]
            self.assertEqual(
                decision["status"],
                "SELECTED_PENDING_RIGHTS_CONTEXT_GATE",
            )
            self.assertEqual(
                decision["rights_route"],
                "HUMAN_RIGHTS_CONTEXT_GATE",
            )

    def test_unverified_candidate_cannot_fake_auto_reuse_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results, storyboards, reviews = self.paths(root)
            current = card("shot-001", "unknown stock clip")
            self.write_board(storyboards, [current])
            shot = result_shot(current, "candidate-1")
            shot["candidates"][0].update(
                {
                    "rights_status": "UNKNOWN",
                    "commercial_use_allowed": True,
                    "state": "ELIGIBLE",
                }
            )
            result_path = self.write_results(results, [shot])

            with (
                patch.object(review, "RESULT_DIR", results),
                patch.object(review, "STORYBOARD_DIR", storyboards),
                patch.object(review, "REVIEW_DIR", reviews),
                patch.object(
                    review,
                    "search_result_is_current",
                    side_effect=current_result_state,
                ),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "not eligible for automatic reuse",
                ):
                    review.apply_action(
                        result_file=str(result_path),
                        shot_id="shot-001",
                        action="SELECT",
                        candidate_id="candidate-1",
                    )

    def test_unknown_discovery_only_source_cannot_use_rights_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results, storyboards, reviews = self.paths(root)
            current = card("shot-001", "unknown discovery clip")
            self.write_board(storyboards, [current])
            shot = result_shot(current, "unknown-1")
            shot["candidates"][0].update(
                {
                    "source_tier": "UNKNOWN",
                    "rights_status": "DISCOVERY_ONLY",
                    "commercial_use_allowed": None,
                    "human_review_required": True,
                    "state": "HUMAN_REVIEW_REQUIRED",
                }
            )
            result_path = self.write_results(results, [shot])

            with (
                patch.object(review, "RESULT_DIR", results),
                patch.object(review, "STORYBOARD_DIR", storyboards),
                patch.object(review, "REVIEW_DIR", reviews),
                patch.object(
                    review,
                    "search_result_is_current",
                    side_effect=current_result_state,
                ),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "unsupported source tier",
                ):
                    review.apply_action(
                        result_file=str(result_path),
                        shot_id="shot-001",
                        action="SELECT",
                        candidate_id="unknown-1",
                    )

    def test_stale_result_provenance_blocks_candidate_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results, storyboards, reviews = self.paths(root)
            current = card("shot-001", "impact")
            self.write_board(storyboards, [current])
            result_path = self.write_results(
                results,
                [result_shot(current, "candidate-1")],
            )
            with (
                patch.object(review, "RESULT_DIR", results),
                patch.object(review, "STORYBOARD_DIR", storyboards),
                patch.object(review, "REVIEW_DIR", reviews),
                patch.object(
                    review,
                    "search_result_is_current",
                    return_value=None,
                ),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "not bound to the current request",
                ):
                    review.apply_action(
                        result_file=str(result_path),
                        shot_id="shot-001",
                        action="SELECT",
                        candidate_id="candidate-1",
                    )

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
                patch.object(
                    review,
                    "search_request_is_current",
                    side_effect=current_request_state,
                ),
                patch.object(
                    review,
                    "search_result_is_current",
                    side_effect=current_result_state,
                ),
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
