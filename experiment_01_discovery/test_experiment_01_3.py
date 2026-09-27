import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import experiment_01_3 as exp13

from experiment_01_3 import (
    aggregate_age_matched_velocity,
    calculate_age_window,
    classify_topic_relevance,
    confidence_from_unique_channels,
    topic_channel_confidence,
    restore_checkpoint_state,
    search_job_key,
)


class Experiment013Tests(unittest.TestCase):
    def test_age_window_120_plus_minus_15(self):
        observed = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
        window = calculate_age_window(observed, 120, 15)

        self.assertEqual(window["minimum_age_days"], 105)
        self.assertEqual(window["maximum_age_days"], 135)
        self.assertEqual(window["published_after"], "2026-05-14T12:00:00Z")
        self.assertEqual(window["published_before"], "2026-06-13T12:00:00Z")

    def test_rocketdyne_f1_engine_is_not_formula_1_context(self):
        result = classify_topic_relevance(
            "Why Can't We Remake the Rocketdyne F-1 Engine? Apollo Saturn V",
            ["engine"],
            ["f1", "formula 1", "motorsport"],
        )
        self.assertEqual(result["topic_relevance"], "OFF_TOPIC")
        self.assertEqual(result["topic_relevance_reason"], "missing_motorsport_context_in_title")

    def test_formula_1_gearbox_is_on_topic(self):
        result = classify_topic_relevance(
            "The Insane Genius of a Formula 1 Gearbox",
            ["gearbox", "transmission"],
            ["f1", "formula 1", "motorsport"],
        )
        self.assertEqual(result["topic_relevance"], "ON_TOPIC")


    def test_sim_racing_title_does_not_become_steering_topic(self):
        result = classify_topic_relevance(
            "ULTRA REALISTIC F1 2026 - Charles Leclerc Ferrari Monaco GP",
            ["steering"],
            ["f1", "formula 1", "motorsport"],
            ["sim racing", "simracing", "gameplay"],
        )
        self.assertEqual(result["topic_relevance"], "OFF_TOPIC")
        self.assertEqual(result["topic_relevance_reason"], "missing_topic_term_in_title")

    def test_corvette_short_does_not_become_aerodynamics_topic(self):
        result = classify_topic_relevance(
            "Corvette takes a 90° turn at full speed. #formula1 #f1 #shorts",
            ["aerodynamic", "aerodynamics", "aero", "downforce"],
            ["f1", "formula 1", "motorsport"],
        )
        self.assertEqual(result["topic_relevance"], "OFF_TOPIC")
        self.assertEqual(result["topic_relevance_reason"], "missing_topic_term_in_title")

    def test_description_terms_cannot_rescue_title_only_validation(self):
        result = classify_topic_relevance(
            "How Engineers Spent a Century Solving the Clutch",
            ["gearbox", "transmission", "engine", "turbo"],
            ["f1", "formula 1", "motorsport"],
        )
        self.assertEqual(result["topic_relevance"], "OFF_TOPIC")
        self.assertEqual(result["topic_relevance_reason"], "missing_topic_term_in_title")

    def test_excluded_sim_racing_title_is_rejected_even_with_topic_term(self):
        result = classify_topic_relevance(
            "F1 Steering Setup for Sim Racing",
            ["steering"],
            ["f1", "formula 1", "motorsport"],
            ["sim racing", "simracing", "gameplay"],
        )
        self.assertEqual(result["topic_relevance"], "OFF_TOPIC")
        self.assertEqual(result["topic_relevance_reason"], "excluded_title_term")

    def test_topic_channel_confidence_uses_unique_channels(self):
        self.assertEqual(topic_channel_confidence(0), "INSUFFICIENT")
        self.assertEqual(topic_channel_confidence(2), "LOW")
        self.assertEqual(topic_channel_confidence(4), "MODERATE")
        self.assertEqual(topic_channel_confidence(5), "STRONG")
        self.assertEqual(
            confidence_from_unique_channels(5),
            "STRONG",
        )


    def test_search_job_key_separates_phase_and_window(self):
        strict = {
            "published_after": "2026-05-14T00:00:00Z",
            "published_before": "2026-06-13T00:00:00Z",
        }
        wide = {
            "published_after": "2026-04-29T00:00:00Z",
            "published_before": "2026-06-28T00:00:00Z",
        }
        base = dict(
            topic_name="brakes",
            query="F1 brakes engineering",
            format_target="long_form_candidate",
            video_duration="medium",
            order="viewCount",
        )

        key_a = search_job_key(search_phase="strict", age_window=strict, **base)
        key_b = search_job_key(search_phase="expanded", age_window=wide, **base)

        self.assertNotEqual(key_a, key_b)

    def test_restore_checkpoint_state_rehydrates_sets(self):
        checkpoint = {
            "discovered": {"video-a": ["brakes", "steering"]},
            "matches": {"video-a": [{"target_topic": "brakes"}]},
            "audit": [{"target_topic": "brakes"}],
            "completed_search_jobs": ["job-1"],
        }

        discovered, matches, audit, completed = restore_checkpoint_state(checkpoint)

        self.assertEqual(discovered["video-a"], {"brakes", "steering"})
        self.assertEqual(matches["video-a"][0]["target_topic"], "brakes")
        self.assertEqual(
            matches["video-a"][0]["discovery_backend"],
            "youtube_api_v3",
        )
        self.assertEqual(audit[0]["target_topic"], "brakes")
        self.assertEqual(
            audit[0]["discovery_backend"],
            "youtube_api_v3",
        )
        self.assertEqual(completed, {"job-1"})



    def test_yt_dlp_pool_uses_supported_base_and_year_hint_queries(self):
        base_result = {
            "results": [
                {
                    "video_id": "base-only",
                    "title": "Base result",
                    "upload_date": "20260520",
                    "duration_seconds": 120,
                    "view_count": 800000,
                },
                {
                    "video_id": "shared",
                    "title": "Shared result",
                    "upload_date": "20260521",
                    "duration_seconds": 300,
                    "view_count": 900000,
                },
            ]
        }
        year_result = {
            "results": [
                {
                    "video_id": "shared",
                    "title": "Shared result",
                    "upload_date": "20260521",
                    "duration_seconds": 300,
                    "view_count": 900000,
                },
                {
                    "video_id": "year-only",
                    "title": "Year result",
                    "upload_date": "20260522",
                    "duration_seconds": 500,
                    "view_count": 1000000,
                },
            ]
        }
        cache = {}
        window = {
            "published_after": "2026-05-14T00:00:00Z",
            "published_before": "2026-06-13T23:59:59Z",
        }

        with patch.object(
            exp13,
            "search_youtube",
            side_effect=[base_result, year_result],
        ) as search:
            first = exp13._yt_dlp_pool(
                "F1 brakes engineering",
                window,
                cache,
            )
            second = exp13._yt_dlp_pool(
                "F1 brakes engineering",
                window,
                cache,
            )

        self.assertEqual(search.call_count, 2)
        self.assertEqual(
            search.call_args_list[0].args[0],
            "F1 brakes engineering",
        )
        self.assertEqual(
            search.call_args_list[1].args[0],
            "F1 brakes engineering 2026",
        )
        self.assertEqual(
            search.call_args_list[0].kwargs["strategy"],
            "relevance",
        )
        self.assertEqual(
            search.call_args_list[1].kwargs["strategy"],
            "relevance",
        )
        self.assertEqual(
            search.call_args_list[0].kwargs["limit"],
            exp13.YT_DLP_RELEVANCE_POOL,
        )
        self.assertEqual(
            {item["video_id"] for item in first},
            {"base-only", "shared", "year-only"},
        )
        shared = next(
            item for item in first
            if item["video_id"] == "shared"
        )
        self.assertEqual(
            shared["discovery_queries"],
            [
                "F1 brakes engineering",
                "F1 brakes engineering 2026",
            ],
        )
        self.assertEqual(first, second)


    def test_yt_dlp_ids_prefilter_age_format_and_views(self):
        pool = [
            {
                "video_id": "keep",
                "upload_date": "20260520",
                "duration_seconds": 120,
                "view_count": 800000,
            },
            {
                "video_id": "wrong-age",
                "upload_date": "20260720",
                "duration_seconds": 120,
                "view_count": 800000,
            },
            {
                "video_id": "wrong-format",
                "upload_date": "20260520",
                "duration_seconds": 600,
                "view_count": 800000,
            },
            {
                "video_id": "low-views",
                "upload_date": "20260520",
                "duration_seconds": 120,
                "view_count": 100000,
            },
        ]
        window = {
            "published_after": "2026-05-14T00:00:00Z",
            "published_before": "2026-06-13T23:59:59Z",
        }

        with patch.object(
            exp13,
            "_yt_dlp_pool",
            return_value=pool,
        ):
            ids = exp13._yt_dlp_ids(
                "F1 brakes engineering",
                window,
                "short_candidate",
                "short",
                500000,
                {},
            )

        self.assertEqual(ids, ["keep"])

    def test_yt_dlp_duration_branches_do_not_overlap(self):
        pool = [
            {
                "video_id": "short",
                "upload_date": "20260520",
                "duration_seconds": 180,
                "view_count": 800000,
            },
            {
                "video_id": "medium-low",
                "upload_date": "20260520",
                "duration_seconds": 181,
                "view_count": 800000,
            },
            {
                "video_id": "medium-high",
                "upload_date": "20260520",
                "duration_seconds": 1200,
                "view_count": 800000,
            },
            {
                "video_id": "long",
                "upload_date": "20260520",
                "duration_seconds": 1201,
                "view_count": 800000,
            },
        ]
        window = {
            "published_after": "2026-05-14T00:00:00Z",
            "published_before": "2026-06-13T23:59:59Z",
        }

        with patch.object(
            exp13,
            "_yt_dlp_pool",
            return_value=pool,
        ):
            medium = exp13._yt_dlp_ids(
                "F1 brakes engineering",
                window,
                "long_form_candidate",
                "medium",
                500000,
                {},
            )
            long_form = exp13._yt_dlp_ids(
                "F1 brakes engineering",
                window,
                "long_form_candidate",
                "long",
                500000,
                {},
            )

        self.assertEqual(medium, ["medium-low", "medium-high"])
        self.assertEqual(long_form, ["long"])

    def test_expanded_query_families_add_new_discovery_queries(self):
        topic = {
            "queries": ["F1 brakes engineering"],
            "expansion_queries": ["F1 brakes explained"],
            "short_expansion_queries": ["F1 brakes #shorts"],
        }

        self.assertEqual(
            exp13._topic_queries(
                topic,
                search_phase="strict",
                format_target="short_candidate",
            ),
            ["F1 brakes engineering"],
        )
        self.assertEqual(
            exp13._topic_queries(
                topic,
                search_phase="expanded",
                format_target="long_form_candidate",
            ),
            ["F1 brakes explained"],
        )
        self.assertEqual(
            exp13._topic_queries(
                topic,
                search_phase="expanded",
                format_target="short_candidate",
            ),
            ["F1 brakes explained", "F1 brakes #shorts"],
        )

    def test_velocity_history_reads_archived_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = (
                root
                / "archive"
                / "experiment_01_3_20260926T190000Z"
            )
            archive.mkdir(parents=True)
            archived_snapshot = archive / "video_snapshots.jsonl"
            archived_snapshot.write_text(
                json.dumps(
                    {
                        "video_id": "video-a",
                        "observed_at": "2026-09-26T17:00:00+00:00",
                        "views": 1000,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            current = root / "current.jsonl"
            persistent = root / "persistent.jsonl"
            persistent.write_text(
                json.dumps(
                    {
                        "video_id": "video-a",
                        "observed_at": "2026-09-26T18:00:00+00:00",
                        "views": 1100,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with (
                patch.object(exp13, "OUTPUT_ROOT", root),
                patch.object(exp13, "SNAPSHOT_FILE", current),
                patch.object(
                    exp13,
                    "PERSISTENT_SNAPSHOT_FILE",
                    persistent,
                ),
            ):
                history = exp13.load_velocity_history()

        self.assertEqual(
            [item["views"] for item in history["video-a"]],
            [1000, 1100],
        )

    def test_auto_discovery_falls_back_to_yt_dlp_when_api_unavailable(self):
        config = {
            "minimum_views": 500000,
            "search_orders": ["viewCount"],
            "search_profiles": {
                "short_candidate": ["short"],
            },
            "topics": [
                {
                    "topic": "brakes",
                    "queries": ["F1 brakes engineering"],
                }
            ],
        }
        window = {
            "published_after": "2026-05-14T00:00:00Z",
            "published_before": "2026-06-13T00:00:00Z",
        }

        with (
            patch.object(
                exp13,
                "api_get",
                side_effect=SystemExit("quota"),
            ),
            patch.object(
                exp13,
                "youtube_health",
                return_value={
                    "ready": True,
                    "active_backend": "yt-dlp",
                },
            ),
            patch.object(
                exp13,
                "_yt_dlp_ids",
                return_value=["video-a"],
            ),
        ):
            (
                discovered,
                matches,
                audit,
                completed,
                calls,
                status,
            ) = exp13.discover(
                config,
                "api-key",
                window,
                60,
                None,
                None,
                discovery_backend="auto",
            )

        self.assertEqual(status, "COMPLETE")
        self.assertEqual(calls, 0)
        self.assertEqual(
            discovered["video-a"],
            {"brakes"},
        )
        self.assertEqual(
            audit[0]["discovery_backend"],
            "agent_reach_yt_dlp",
        )
        self.assertEqual(
            matches["video-a"][0]["backend_search_strategy"],
            "ytsearch_relevance+year_hint",
        )
        self.assertEqual(len(completed), 1)


    def test_auto_mode_uses_fallback_when_api_budget_is_zero(self):
        config = {
            "minimum_views": 500000,
            "search_orders": ["viewCount"],
            "search_profiles": {
                "short_candidate": ["short"],
            },
            "topics": [
                {
                    "topic": "brakes",
                    "queries": ["F1 brakes engineering"],
                }
            ],
        }
        window = {
            "published_after": "2026-05-14T00:00:00Z",
            "published_before": "2026-06-13T00:00:00Z",
        }

        with (
            patch.object(
                exp13,
                "api_get",
            ) as api,
            patch.object(
                exp13,
                "youtube_health",
                return_value={
                    "ready": True,
                    "active_backend": "yt-dlp",
                },
            ),
            patch.object(
                exp13,
                "_yt_dlp_ids",
                return_value=["video-a"],
            ),
        ):
            result = exp13.discover(
                config,
                "api-key",
                window,
                0,
                None,
                None,
                discovery_backend="auto",
            )

        api.assert_not_called()
        self.assertEqual(result[-1], "COMPLETE")
        self.assertEqual(
            result[2][0]["discovery_backend"],
            "agent_reach_yt_dlp",
        )

    def test_api_only_mode_does_not_fall_back(self):
        config = {
            "minimum_views": 500000,
            "search_orders": ["viewCount"],
            "search_profiles": {
                "short_candidate": ["short"],
            },
            "topics": [
                {
                    "topic": "brakes",
                    "queries": ["F1 brakes engineering"],
                }
            ],
        }
        window = {
            "published_after": "2026-05-14T00:00:00Z",
            "published_before": "2026-06-13T00:00:00Z",
        }

        with (
            patch.object(
                exp13,
                "api_get",
                side_effect=SystemExit("quota"),
            ),
            patch.object(
                exp13,
                "_yt_dlp_ids",
            ) as fallback,
        ):
            result = exp13.discover(
                config,
                "api-key",
                window,
                60,
                None,
                None,
                discovery_backend="youtube_api",
            )

        self.assertEqual(
            result[-1],
            "YOUTUBE_API_UNAVAILABLE",
        )
        fallback.assert_not_called()

    def test_shorts_and_long_form_use_separate_velocity_baselines(self):
        rows = [
            {
                "video_id": "long-a",
                "channel_id": "c1",
                "validated_topics": ["gearbox_transmission"],
                "topic_relevance": "ON_TOPIC",
                "format_candidate": "long_form_candidate",
                "age_days": 120,
                "views": 2_000_000,
                "current_views_per_day": 10_000,
                "outlier_ratio": 5,
                "outlier_reliability": "TRUSTED",
            },
            {
                "video_id": "long-b",
                "channel_id": "c2",
                "validated_topics": ["brakes"],
                "topic_relevance": "ON_TOPIC",
                "format_candidate": "long_form_candidate",
                "age_days": 121,
                "views": 1_500_000,
                "current_views_per_day": 2_000,
                "outlier_ratio": 3,
                "outlier_reliability": "TRUSTED",
            },
            {
                "video_id": "short-a",
                "channel_id": "c3",
                "validated_topics": ["brakes"],
                "topic_relevance": "ON_TOPIC",
                "format_candidate": "short_candidate",
                "age_days": 118,
                "views": 6_000_000,
                "current_views_per_day": 50_000,
                "outlier_ratio": 10,
                "outlier_reliability": "TRUSTED",
            },
        ]
        niches = {
            "gearbox_transmission": "automotive_racing",
            "brakes": "automotive_racing",
        }

        result = aggregate_age_matched_velocity(rows, niches)

        self.assertEqual(
            result[
                "cohort_median_current_views_per_day_by_niche_format"
            ]["automotive_racing"]["long_form_candidate"],
            6000.0,
        )
        self.assertEqual(
            result[
                "cohort_median_current_views_per_day_by_niche_format"
            ]["automotive_racing"]["short_candidate"],
            50000.0,
        )
        self.assertEqual(
            result["topics"]["gearbox_transmission"]["by_format"]["long_form_candidate"][
                "age_matched_velocity_index"
            ],
            1.667,
        )
        self.assertEqual(
            result["topics"]["gearbox_transmission"]["by_format"]["long_form_candidate"][
                "topic_channel_confidence"
            ],
            "LOW",
        )

    def test_velocity_denominator_never_pools_across_niches(self):
        rows = [
            {
                "video_id": "auto-a",
                "channel_id": "auto-1",
                "validated_topics": ["gearbox_transmission"],
                "topic_relevance": "ON_TOPIC",
                "format_candidate": "short_candidate",
                "age_days": 120,
                "views": 2_000_000,
                "current_views_per_day": 1_000,
                "outlier_ratio": 5,
                "outlier_reliability": "TRUSTED",
            },
            {
                "video_id": "auto-b",
                "channel_id": "auto-2",
                "validated_topics": ["brakes"],
                "topic_relevance": "ON_TOPIC",
                "format_candidate": "short_candidate",
                "age_days": 121,
                "views": 2_000_000,
                "current_views_per_day": 3_000,
                "outlier_ratio": 5,
                "outlier_reliability": "TRUSTED",
            },
            {
                "video_id": "finance-a",
                "channel_id": "finance-1",
                "validated_topics": ["credit_cards"],
                "topic_relevance": "ON_TOPIC",
                "format_candidate": "short_candidate",
                "age_days": 119,
                "views": 2_000_000,
                "current_views_per_day": 100_000,
                "outlier_ratio": 5,
                "outlier_reliability": "TRUSTED",
            },
            {
                "video_id": "finance-b",
                "channel_id": "finance-2",
                "validated_topics": ["saving"],
                "topic_relevance": "ON_TOPIC",
                "format_candidate": "short_candidate",
                "age_days": 122,
                "views": 2_000_000,
                "current_views_per_day": 300_000,
                "outlier_ratio": 5,
                "outlier_reliability": "TRUSTED",
            },
        ]
        niches = {
            "gearbox_transmission": "automotive_racing",
            "brakes": "automotive_racing",
            "credit_cards": "personal_finance",
            "saving": "personal_finance",
        }

        result = aggregate_age_matched_velocity(rows, niches)

        baselines = result[
            "cohort_median_current_views_per_day_by_niche_format"
        ]
        self.assertEqual(
            baselines["automotive_racing"]["short_candidate"],
            2000.0,
        )
        self.assertEqual(
            baselines["personal_finance"]["short_candidate"],
            200000.0,
        )
        self.assertEqual(
            result["topics"]["gearbox_transmission"]["by_format"]["short_candidate"][
                "age_matched_velocity_index"
            ],
            0.5,
        )
        self.assertEqual(
            result["topics"]["credit_cards"]["by_format"]["short_candidate"][
                "age_matched_velocity_index"
            ],
            0.5,
        )
        self.assertEqual(
            result["cohort_median_current_views_per_day_by_format"],
            {},
        )


if __name__ == "__main__":
    unittest.main()
