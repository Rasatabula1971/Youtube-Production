import unittest

from experiment_01_discovery.experiment_01_4 import (
    allocate_search_budget,
    build_plan,
    classify_depth_readiness,
)


class Experiment014Tests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "minimum_unique_channels": 3,
            "minimum_velocity_samples": 3,
            "maximum_plan_searches": 5,
            "search_order": "viewCount",
            "lookback_days": 1825,
            "motorsport_context_terms": ["f1", "formula 1"],
            "exclude_title_terms": ["sim racing"],
            "duration_filters": {
                "short_candidate": ["short"],
                "long_form_candidate": ["medium", "long"],
            },
            "topic_definitions": {
                "gearbox_transmission": {
                    "query_root": "F1 gearbox",
                    "match_terms": ["gearbox"],
                    "niche": "automotive_racing",
                },
                "brakes": {
                    "query_root": "F1 brakes",
                    "match_terms": ["brakes"],
                    "niche": "automotive_racing",
                },
            },
            "query_families": [
                {"family": "how_it_works", "template": "{root} how it works"},
                {"family": "failure_problem", "template": "{root} failure problem"},
            ],
        }

    def test_depth_readiness_requires_channels_velocity_and_index(self):
        ready = classify_depth_readiness(
            {
                "unique_channels": 3,
                "velocity_sample_count": 3,
                "age_matched_velocity_index": 1.4,
            },
            minimum_unique_channels=3,
            minimum_velocity_samples=3,
        )
        self.assertTrue(ready["depth_ready"])

        not_ready = classify_depth_readiness(
            {
                "unique_channels": 2,
                "velocity_sample_count": 3,
                "age_matched_velocity_index": 1.4,
            },
            minimum_unique_channels=3,
            minimum_velocity_samples=3,
        )
        self.assertFalse(not_ready["depth_ready"])
        self.assertIn("insufficient_unique_channels", not_ready["readiness_reasons"])

    def test_long_form_generates_medium_and_long_tasks(self):
        tasks = allocate_search_budget(
            [
                {
                    "topic": "gearbox_transmission",
                    "format_candidate": "long_form_candidate",
                    "unique_channels": 4,
                    "velocity_sample_count": 4,
                    "age_matched_velocity_index": 1.5,
                }
            ],
            self.config,
            10,
        )
        self.assertEqual(len(tasks), 4)
        self.assertEqual(
            {task["video_duration_filter"] for task in tasks},
            {"medium", "long"},
        )

    def test_budget_allocator_round_robins_cells(self):
        cells = [
            {
                "topic": "gearbox_transmission",
                "format_candidate": "long_form_candidate",
                "unique_channels": 5,
                "velocity_sample_count": 5,
                "age_matched_velocity_index": 2.0,
            },
            {
                "topic": "brakes",
                "format_candidate": "short_candidate",
                "unique_channels": 4,
                "velocity_sample_count": 4,
                "age_matched_velocity_index": 1.5,
            },
        ]
        tasks = allocate_search_budget(cells, self.config, 3)
        self.assertEqual(len(tasks), 3)
        self.assertEqual(tasks[0]["topic"], "gearbox_transmission")
        self.assertEqual(tasks[1]["topic"], "brakes")

    def test_plan_waits_when_01_3_has_no_velocity(self):
        topic_velocity = {
            "topics": {
                "gearbox_transmission": {
                    "by_format": {
                        "long_form_candidate": {
                            "unique_channels": 4,
                            "velocity_sample_count": 0,
                            "age_matched_velocity_index": None,
                            "niche": "automotive_racing",
                            "topic_channel_confidence": "MODERATE",
                        }
                    }
                }
            }
        }
        plan = build_plan(
            topic_velocity,
            {"cohort_id": "test", "mode": "discover"},
            self.config,
        )
        self.assertEqual(plan["status"], "WAITING_FOR_01_3_EVIDENCE")
        self.assertEqual(plan["search_tasks"], [])

    def test_plan_becomes_ready_with_replicated_velocity(self):
        topic_velocity = {
            "topics": {
                "gearbox_transmission": {
                    "by_format": {
                        "long_form_candidate": {
                            "unique_channels": 4,
                            "velocity_sample_count": 4,
                            "age_matched_velocity_index": 1.8,
                            "niche": "automotive_racing",
                            "topic_channel_confidence": "MODERATE",
                            "median_current_views_per_day": 12000,
                        }
                    }
                }
            }
        }
        plan = build_plan(
            topic_velocity,
            {"cohort_id": "test", "mode": "refresh"},
            self.config,
        )
        self.assertEqual(plan["status"], "READY")
        self.assertGreater(len(plan["search_tasks"]), 0)
        self.assertEqual(
            plan["ready_cells"][0]["niche"],
            "automotive_racing",
        )
        self.assertEqual(
            plan["ready_cells"][0]["topic_channel_confidence"],
            "MODERATE",
        )
        self.assertEqual(
            plan["search_tasks"][0]["niche"],
            "automotive_racing",
        )


if __name__ == "__main__":
    unittest.main()


class SecondNicheTests(unittest.TestCase):
    """D-178: per-niche context words and niche-limited query families."""

    def setUp(self):
        from experiment_01_discovery import experiment_01_4 as exp14

        self.exp14 = exp14
        self.config = exp14.load_config()

    def test_rules_family_is_asked_only_of_motorsport_topics(self):
        def families(topic, niche):
            cell = {"topic": topic, "niche": niche, "format_candidate": "long_form_candidate"}
            return sorted({task["family"] for task in self.exp14.build_tasks_for_cell(cell, self.config)})

        everything = sorted(f["family"] for f in self.config["query_families"])
        self.assertEqual(families("brakes", "automotive_racing"), everything)
        self.assertNotIn("rules_loopholes", families("microwave_oven", "everyday_science"))
        self.assertEqual(len(families("microwave_oven", "everyday_science")), len(everything) - 1)

    def test_every_topic_has_context_words_for_its_niche(self):
        from experiment_01_discovery.experiment_01_3 import context_terms_for

        for topic, definition in self.config["topic_definitions"].items():
            self.assertTrue(context_terms_for(self.config, definition["niche"]), topic)
        self.assertEqual(len(self.config["topic_definitions"]), 16)
