from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import visual_search_adapters as adapters


class VisualSearchAdapterTests(unittest.TestCase):
    def test_missing_keys_fail_closed_to_empty_results(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(adapters.pexels_videos("steelpan"), [])
            self.assertEqual(adapters.pixabay_videos("steelpan"), [])
            self.assertEqual(adapters.youtube_creator_discovery("steelpan"), [])

    def test_youtube_results_are_review_only(self) -> None:
        payload = {"items":[{"id":{"videoId":"abc"},"snippet":{"title":"Demo","channelTitle":"Creator","thumbnails":{"high":{"url":"https://img.test/a.jpg"}}}}]}
        with patch.dict(os.environ, {"YOUTUBE_API_KEY":"key"}, clear=True), patch.object(adapters, "_json", return_value=payload):
            result = adapters.youtube_creator_discovery("steelpan")[0]
        self.assertEqual(result["source_tier"], "EDITORIAL_EXCERPT")
        self.assertEqual(result["rights_status"], "DISCOVERY_ONLY")
        self.assertTrue(result["human_review_required"])

    def test_one_provider_failure_does_not_cancel_other_sources(self) -> None:
        with (
            patch.object(
                adapters,
                "pexels_videos",
                return_value=[{"candidate_id": "pexels-1"}],
            ),
            patch.object(
                adapters,
                "pixabay_videos",
                side_effect=TimeoutError("timed out"),
            ),
            patch.object(
                adapters,
                "youtube_creator_discovery",
                return_value=[{"candidate_id": "youtube-1"}],
            ),
        ):
            result = adapters.discover_with_diagnostics(
                "racing tyre",
                5,
            )

        self.assertFalse(result["paid_calls_allowed"])
        self.assertEqual(
            result["providers"]["pexels"][0]["candidate_id"],
            "pexels-1",
        )
        self.assertEqual(result["providers"]["pixabay"], [])
        self.assertEqual(result["errors"][0]["provider"], "pixabay")

    def test_invalid_provider_payload_is_isolated(self) -> None:
        candidates, error = adapters._safe_provider_call(
            "pexels",
            lambda: {"not": "a list"},
        )
        self.assertEqual(candidates, [])
        self.assertEqual(
            error["error_type"],
            "InvalidProviderResponse",
        )

    def test_discovery_rejects_unbounded_candidate_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 20"):
            adapters.discover_with_diagnostics("query", 1000)

    def test_pexels_normalizes_as_zero_cost_stock(self) -> None:
        payload={"videos":[{"id":1,"url":"https://pexels.test/1","duration":5,"user":{"name":"A"},"video_files":[{"link":"https://cdn.test/a.mp4"}],"video_pictures":[{"picture":"https://cdn.test/a.jpg"}]}]}
        with patch.dict(os.environ, {"PEXELS_API_KEY":"key"}, clear=True), patch.object(adapters, "_json", return_value=payload):
            result=adapters.pexels_videos("steelpan")[0]
        self.assertEqual(result["source_tier"], "FREE_COMMERCIAL_LICENSE")
        self.assertEqual(result["estimated_cost_usd"], 0.0)
        self.assertTrue(result["commercial_use_allowed"])


if __name__ == "__main__":
    unittest.main()
