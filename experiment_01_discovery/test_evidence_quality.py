from __future__ import annotations

import unittest

from experiment_01_discovery.evidence_quality import (
    RELIABILITY_CAUTION,
    RELIABILITY_TRUSTED,
    RELIABILITY_UNAVAILABLE,
    RELEVANCE_ADJACENT,
    RELEVANCE_OFF_INTENT,
    RELEVANCE_ON_INTENT,
    classify_outlier_reliability,
    classify_relevance,
    classify_themes,
)


PROFILE = {
    "exclude_terms": [
        "gta",
        "gameplay",
        "gaming",
        "remote control",
        "rc car",
        "toy car",
    ],
    "strong_terms": [
        "engineering",
        "engineer",
        "technology",
        "gearbox",
        "brake",
        "brakes",
        "tire",
        "tires",
        "steering",
        "engine",
        "aerodynamic",
        "aero",
        "downforce",
        "suspension",
        "power unit",
        "pit stop",
    ],
    "context_terms": [
        "f1",
        "formula 1",
        "formula e",
        "motorsport",
        "race car",
        "racecar",
        "racing",
        "track",
        "driver",
        "engineer",
        "mechanic",
        "mechanics",
    ],
    "theme_rules": {
        "hidden_mechanisms": [
            "how",
            "works",
            "explained",
            "why",
        ],
        "comparisons": [
            " vs ",
            "versus",
            "comparison",
        ],
        "rules_loopholes": [
            "banned",
            "cheat",
            "cheated",
            "legal",
            "rule",
        ],
    },
}


class RelevanceTests(unittest.TestCase):
    def test_gta_gameplay_is_off_intent(self) -> None:
        result = classify_relevance(
            "MY FERRARI RACECAR EXPLODE IN RACE | GTA V GAMEPLAY #144",
            PROFILE,
        )
        self.assertEqual(
            result["relevance"],
            RELEVANCE_OFF_INTENT,
        )
        self.assertIn(
            "excluded_term",
            result["relevance_reason"],
        )

    def test_f1_gearbox_is_on_intent(self) -> None:
        result = classify_relevance(
            "The Insane Genius of a Formula 1 Gearbox",
            PROFILE,
        )
        self.assertEqual(
            result["relevance"],
            RELEVANCE_ON_INTENT,
        )
        self.assertIn(
            "gearbox",
            result["relevance_matches"],
        )

    def test_f1_drag_race_is_adjacent(self) -> None:
        result = classify_relevance(
            "Drone vs F1 Car Drag Race",
            PROFILE,
        )
        self.assertEqual(
            result["relevance"],
            RELEVANCE_ADJACENT,
        )

    def test_f1_tires_are_on_intent(self) -> None:
        result = classify_relevance(
            "F1 Tires Explained",
            PROFILE,
        )
        self.assertEqual(
            result["relevance"],
            RELEVANCE_ON_INTENT,
        )


    def test_mechanic_vibe_clip_is_adjacent_not_on_intent(self) -> None:
        result = classify_relevance(
            "McLaren Mechanic has unlimited Aura",
            PROFILE,
        )
        self.assertEqual(
            result["relevance"],
            RELEVANCE_ADJACENT,
        )

    def test_themes_are_multi_label(self) -> None:
        themes = classify_themes(
            "Why F1 vs F2 Brakes Work Differently",
            PROFILE["theme_rules"],
        )
        self.assertIn("hidden_mechanisms", themes)
        self.assertIn("comparisons", themes)


class ReliabilityTests(unittest.TestCase):
    def test_strong_clean_ratio_is_trusted(self) -> None:
        result = classify_outlier_reliability(
            outlier_ratio=26.53,
            baseline_confidence="strong_sample",
            baseline_warning="",
        )
        self.assertEqual(
            result["outlier_reliability"],
            RELIABILITY_TRUSTED,
        )

    def test_small_baseline_is_caution(self) -> None:
        result = classify_outlier_reliability(
            outlier_ratio=10440.15,
            baseline_confidence="strong_sample",
            baseline_warning="small_channel_baseline",
        )
        self.assertEqual(
            result["outlier_reliability"],
            RELIABILITY_CAUTION,
        )
        self.assertIn(
            "small_channel_baseline",
            result["outlier_reliability_reason"],
        )

    def test_extreme_ratio_alone_is_caution(self) -> None:
        result = classify_outlier_reliability(
            outlier_ratio=1200.0,
            baseline_confidence="strong_sample",
            baseline_warning="",
        )
        self.assertEqual(
            result["outlier_reliability"],
            RELIABILITY_CAUTION,
        )
        self.assertIn(
            "extreme_outlier_ratio",
            result["outlier_reliability_reason"],
        )

    def test_missing_ratio_is_unavailable(self) -> None:
        result = classify_outlier_reliability(
            outlier_ratio=None,
            baseline_confidence="no_baseline",
            baseline_warning="small_baseline_sample",
        )
        self.assertEqual(
            result["outlier_reliability"],
            RELIABILITY_UNAVAILABLE,
        )


if __name__ == "__main__":
    unittest.main()
