from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import visual_search
import visual_search_acquire


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
        self.assertTrue(request["shots"][0]["shot_fingerprint"])


    def test_search_request_becomes_stale_when_storyboard_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            board_path = root / "c1.shorts.storyboard.json"
            request_path = root / "c1.shorts.visual_search_request.json"
            board = {
                "concept_id": "c1",
                "format": "shorts",
                "status": "READY_FOR_VISUAL_SEARCH",
                "cards": [
                    {
                        "shot_id": "shot-001",
                        "beat_id": "b1",
                        "time_range": {},
                        "desired_visual": "impact",
                        "search_terms": ["impact"],
                        "cinematic_direction": {},
                        "premium_generation_candidate": False,
                        "source_strategy": {
                            "selected_candidate_id": None,
                            "creator_excerpt_allowed_only_after_human_rights_context_review": True,
                        },
                    }
                ],
            }
            board_path.write_text(json.dumps(board), encoding="utf-8")
            request = visual_search.build_search_request(
                board,
                board_path,
            )
            request_path.write_text(json.dumps(request), encoding="utf-8")
            with patch.object(
                visual_search,
                "storyboard_is_current",
                return_value=(board, Path("timing"), Path("visual")),
            ):
                self.assertIsNotNone(
                    visual_search.search_request_is_current(request_path)
                )
                board["cards"][0]["desired_visual"] = "changed impact"
                board_path.write_text(json.dumps(board), encoding="utf-8")
                self.assertIsNone(
                    visual_search.search_request_is_current(request_path)
                )

    def test_acquire_reuses_unchanged_raw_shot_and_searches_changed_shot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / "results"
            raw_dir = root / "raw"
            results.mkdir()
            raw_dir.mkdir()

            request_path = results / "c1.short.visual_search_request.json"
            request = {
                "artifact": "visual_search_request",
                "concept_id": "c1",
                "format": "short",
                "status": "SEARCH_REQUIRED",
                "shots": [
                    {
                        "shot_id": "s1",
                        "shot_fingerprint": "fp-current-1",
                        "search_terms": ["wing bend"],
                        "max_candidates_per_source": 5,
                    },
                    {
                        "shot_id": "s2",
                        "shot_fingerprint": "fp-current-2",
                        "search_terms": ["landing gear"],
                        "max_candidates_per_source": 5,
                    },
                ],
            }
            request_path.write_text(json.dumps(request), encoding="utf-8")
            raw_path = raw_dir / "c1.short.visual_search_raw.json"
            raw_path.write_text(
                json.dumps(
                    {
                        "concept_id": "c1",
                        "format": "short",
                        "shot_fingerprints": {
                            "s1": "fp-current-1",
                            "s2": "fp-old-2",
                        },
                        "provider_errors": {},
                        "shots": {
                            "s1": [{"candidate_id": "old-s1"}],
                            "s2": [{"candidate_id": "old-s2"}],
                        },
                    }
                ),
                encoding="utf-8",
            )

            discovered = {
                "providers": {
                    "free": [
                        {
                            "candidate_id": "new-s2",
                            "source_tier": "FREE_COMMERCIAL_LICENSE",
                            "rights_status": "VERIFIED",
                            "commercial_use_allowed": True,
                            "source_url": "https://example.test/new-s2",
                        }
                    ]
                },
                "errors": [],
            }

            def current_request(path):
                return (request, Path("board")) if path == request_path else None

            with (
                patch.object(visual_search_acquire, "RESULT_DIR", results),
                patch.object(visual_search_acquire, "RAW_DIR", raw_dir),
                patch.object(
                    visual_search_acquire,
                    "SUMMARY_FILE",
                    root / "summary.json",
                ),
                patch.object(
                    visual_search_acquire,
                    "search_request_is_current",
                    side_effect=current_request,
                ),
                patch.object(
                    visual_search_acquire,
                    "search_result_is_current",
                    return_value=({}, request_path, request),
                ),
                patch.object(
                    visual_search_acquire,
                    "discover_with_diagnostics",
                    return_value=discovered,
                ) as discover,
            ):
                result = visual_search_acquire.acquire()

            updated = json.loads(raw_path.read_text(encoding="utf-8"))
            self.assertEqual(result["processed"], 1)
            self.assertEqual(result["items"][0]["shots_reused"], 1)
            self.assertEqual(result["items"][0]["shots_searched"], 1)
            self.assertEqual(discover.call_count, 1)
            self.assertEqual(updated["shots"]["s1"][0]["candidate_id"], "old-s1")
            self.assertEqual(updated["shots"]["s2"][0]["candidate_id"], "new-s2")
            self.assertEqual(
                updated["shot_fingerprints"]["s2"],
                "fp-current-2",
            )

    def test_stale_search_request_never_calls_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / "results"
            raw_dir = root / "raw"
            results.mkdir()
            raw_dir.mkdir()
            request_path = results / "stale.visual_search_request.json"
            request_path.write_text("{}", encoding="utf-8")

            with (
                patch.object(visual_search_acquire, "RESULT_DIR", results),
                patch.object(visual_search_acquire, "RAW_DIR", raw_dir),
                patch.object(
                    visual_search_acquire,
                    "SUMMARY_FILE",
                    root / "summary.json",
                ),
                patch.object(
                    visual_search_acquire,
                    "search_request_is_current",
                    return_value=None,
                ),
                patch.object(
                    visual_search_acquire,
                    "discover_with_diagnostics",
                ) as discover,
            ):
                result = visual_search_acquire.acquire()

            discover.assert_not_called()
            self.assertEqual(result["stale_requests_skipped"], 1)

    def test_provider_error_does_not_discard_other_provider_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / "results"
            raw_dir = root / "raw"
            results.mkdir()
            raw_dir.mkdir()
            request_path = results / "c1.short.visual_search_request.json"
            request = {
                "artifact": "visual_search_request",
                "concept_id": "c1",
                "format": "short",
                "status": "SEARCH_REQUIRED",
                "shots": [
                    {
                        "shot_id": "s1",
                        "shot_fingerprint": "fp1",
                        "search_terms": ["impact"],
                        "max_candidates_per_source": 5,
                    }
                ],
            }
            request_path.write_text(json.dumps(request), encoding="utf-8")
            discovery = {
                "providers": {
                    "pexels": [
                        {
                            "candidate_id": "free-1",
                            "source_tier": "FREE_COMMERCIAL_LICENSE",
                            "rights_status": "VERIFIED",
                            "commercial_use_allowed": True,
                            "source_url": "https://example.test/free-1",
                        }
                    ],
                    "pixabay": [],
                },
                "errors": [
                    {
                        "provider": "pixabay",
                        "error_type": "TimeoutError",
                        "error": "timed out",
                    }
                ],
            }

            with (
                patch.object(visual_search_acquire, "RESULT_DIR", results),
                patch.object(visual_search_acquire, "RAW_DIR", raw_dir),
                patch.object(
                    visual_search_acquire,
                    "SUMMARY_FILE",
                    root / "summary.json",
                ),
                patch.object(
                    visual_search_acquire,
                    "search_request_is_current",
                    return_value=(request, Path("board")),
                ),
                patch.object(
                    visual_search_acquire,
                    "search_result_is_current",
                    return_value=({}, request_path, request),
                ),
                patch.object(
                    visual_search_acquire,
                    "discover_with_diagnostics",
                    return_value=discovery,
                ),
            ):
                result = visual_search_acquire.acquire()

            compiled_path = (
                results / "c1.short.visual_search_results.json"
            )
            compiled = json.loads(
                compiled_path.read_text(encoding="utf-8")
            )
            self.assertEqual(result["provider_errors"], 1)
            self.assertEqual(
                compiled["shots"][0]["candidates"][0]["candidate_id"],
                "free-1",
            )
            self.assertEqual(
                compiled["shots"][0]["provider_errors"][0]["provider"],
                "pixabay",
            )



if __name__ == "__main__":
    unittest.main()
