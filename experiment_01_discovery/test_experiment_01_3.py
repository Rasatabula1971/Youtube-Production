import unittest
from datetime import datetime, timezone

from experiment_01_3 import (
    aggregate_age_matched_velocity,
    calculate_age_window,
    classify_topic_relevance,
    confidence_from_unique_channels,
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

    def test_confidence_uses_unique_channels(self):
        self.assertEqual(confidence_from_unique_channels(0), "INSUFFICIENT")
        self.assertEqual(confidence_from_unique_channels(2), "LOW")
        self.assertEqual(confidence_from_unique_channels(4), "MODERATE")
        self.assertEqual(confidence_from_unique_channels(5), "STRONG")

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

        result = aggregate_age_matched_velocity(rows)

        self.assertEqual(
            result["cohort_median_current_views_per_day_by_format"]["long_form_candidate"],
            6000.0,
        )
        self.assertEqual(
            result["cohort_median_current_views_per_day_by_format"]["short_candidate"],
            50000.0,
        )
        self.assertEqual(
            result["topics"]["gearbox_transmission"]["by_format"]["long_form_candidate"][
                "age_matched_velocity_index"
            ],
            1.667,
        )


if __name__ == "__main__":
    unittest.main()
