from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from experiment_01_discovery.market_intelligence import (
    VELOCITY_NEGATIVE_ADJUSTMENT,
    VELOCITY_NO_PRIOR,
    VELOCITY_VALID,
    aggregate_topic_evidence,
    append_snapshots,
    build_query_competition_profile,
    calculate_snapshot_velocity,
    enrich_query_profiles_with_evidence,
    load_snapshot_history,
)


class QueryProfileTests(unittest.TestCase):
    def test_profile_describes_channel_concentration_and_scale(self) -> None:
        details = {
            "a": {
                "snippet": {
                    "channelId": "c1",
                    "publishedAt": "2026-09-01T00:00:00Z",
                },
                "statistics": {"viewCount": "1000"},
            },
            "b": {
                "snippet": {
                    "channelId": "c1",
                    "publishedAt": "2026-08-01T00:00:00Z",
                },
                "statistics": {"viewCount": "3000"},
            },
            "c": {
                "snippet": {
                    "channelId": "c2",
                    "publishedAt": "2024-01-01T00:00:00Z",
                },
                "statistics": {"viewCount": "5000"},
            },
        }
        channels = {
            "c1": {"statistics": {"subscriberCount": "2000000"}},
            "c2": {"statistics": {"subscriberCount": "100000"}},
        }
        profile = build_query_competition_profile(
            query="F1 engineering",
            video_ids=["a", "b", "c"],
            details=details,
            channels=channels,
            now=datetime(2026, 9, 25, tzinfo=timezone.utc),
        )
        self.assertEqual(profile["unique_channels"], 2)
        self.assertEqual(profile["top_channel_share"], 0.6667)
        self.assertEqual(profile["median_views"], 3000.0)
        self.assertEqual(profile["large_channel_share"], 0.6667)
        self.assertEqual(profile["recent_result_share"], 0.6667)

    def test_evidence_is_attached_without_score(self) -> None:
        profiles = [
            {
                "niche": "automotive_racing",
                "query": "F1 engineering",
            }
        ]
        rows = [
            {
                "query_matches": [
                    {
                        "niche": "automotive_racing",
                        "query": "F1 engineering",
                        "rank": 1,
                    }
                ],
                "relevance": "ON_INTENT",
                "outlier_reliability": "TRUSTED",
                "outlier_ratio": 5.0,
            },
            {
                "query_matches": [
                    {
                        "niche": "automotive_racing",
                        "query": "F1 engineering",
                        "rank": 2,
                    }
                ],
                "relevance": "OFF_INTENT",
                "outlier_reliability": "CAUTION",
                "outlier_ratio": 1500.0,
            },
        ]
        result = enrich_query_profiles_with_evidence(profiles, rows)[0]
        self.assertEqual(result["analyzed_500k_plus"], 2)
        self.assertEqual(result["on_intent_500k_plus"], 1)
        self.assertEqual(result["off_intent_500k_plus"], 1)
        self.assertEqual(result["median_trusted_outlier_ratio"], 5.0)
        self.assertNotIn("score", result)


class VelocityTests(unittest.TestCase):
    def test_first_observation_has_no_velocity(self) -> None:
        result = calculate_snapshot_velocity(
            video_id="v1",
            current_views=1000,
            observed_at="2026-09-25T12:00:00+00:00",
            history={},
        )
        self.assertEqual(result["velocity_status"], VELOCITY_NO_PRIOR)
        self.assertIsNone(result["current_views_per_day"])

    def test_uses_latest_snapshot_old_enough(self) -> None:
        history = {
            "v1": [
                {
                    "video_id": "v1",
                    "observed_at": "2026-09-24T12:00:00+00:00",
                    "views": 1000,
                },
                {
                    "video_id": "v1",
                    "observed_at": "2026-09-25T11:30:00+00:00",
                    "views": 1500,
                },
            ]
        }
        result = calculate_snapshot_velocity(
            video_id="v1",
            current_views=2200,
            observed_at="2026-09-25T12:00:00+00:00",
            history=history,
            minimum_interval_hours=1.0,
        )
        self.assertEqual(result["velocity_status"], VELOCITY_VALID)
        self.assertEqual(result["velocity_previous_views"], 1000)
        self.assertEqual(result["view_delta_since_snapshot"], 1200)
        self.assertEqual(result["current_views_per_hour"], 50.0)

    def test_negative_adjustment_is_preserved_but_not_called_velocity(self) -> None:
        history = {
            "v1": [
                {
                    "video_id": "v1",
                    "observed_at": "2026-09-24T12:00:00+00:00",
                    "views": 1200,
                }
            ]
        }
        result = calculate_snapshot_velocity(
            video_id="v1",
            current_views=1000,
            observed_at="2026-09-25T12:00:00+00:00",
            history=history,
        )
        self.assertEqual(
            result["velocity_status"],
            VELOCITY_NEGATIVE_ADJUSTMENT,
        )
        self.assertEqual(result["view_delta_since_snapshot"], -200)
        self.assertIsNone(result["current_views_per_hour"])

    def test_snapshot_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshots.jsonl"
            append_snapshots(
                path,
                [{"video_id": "v1", "views": 1000}],
                "2026-09-25T12:00:00+00:00",
            )
            history = load_snapshot_history(path)
            self.assertEqual(history["v1"][0]["views"], 1000)


class TopicAggregationTests(unittest.TestCase):
    def test_topics_keep_formats_separate(self) -> None:
        rows = [
            {
                "topic": "unused",
                "topics": ["brakes"],
                "relevance": "ON_INTENT",
                "format_candidate": "short_candidate",
                "views": 1000,
                "channel_id": "c1",
                "outlier_ratio": 10.0,
                "outlier_reliability": "TRUSTED",
                "current_views_per_day": 100.0,
            },
            {
                "topics": ["brakes"],
                "relevance": "ON_INTENT",
                "format_candidate": "long_form_candidate",
                "views": 3000,
                "channel_id": "c2",
                "outlier_ratio": 4.0,
                "outlier_reliability": "TRUSTED",
                "current_views_per_day": None,
            },
            {
                "topics": ["brakes"],
                "relevance": "OFF_INTENT",
                "format_candidate": "short_candidate",
                "views": 999999,
                "channel_id": "junk",
                "outlier_ratio": 500.0,
                "outlier_reliability": "TRUSTED",
                "current_views_per_day": 99999.0,
            },
        ]
        evidence = aggregate_topic_evidence(rows)
        self.assertEqual(evidence["brakes"]["overall"]["video_count"], 2)
        self.assertIn("short_candidate", evidence["brakes"]["by_format"])
        self.assertIn("long_form_candidate", evidence["brakes"]["by_format"])
        self.assertEqual(
            evidence["brakes"]["overall"]["median_views"],
            2000.0,
        )


if __name__ == "__main__":
    unittest.main()
