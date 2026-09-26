import unittest

from experiment_01_5 import (
    build_handoff_packets,
    build_study_set,
    evaluate_topic_evidence,
)


class Experiment015Tests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "minimum_topic_unique_channels": 3,
            "minimum_topic_velocity_samples": 3,
            "minimum_family_unique_channels": 2,
            "minimum_family_video_count": 2,
            "candidate_view_reference": 500000,
            "max_study_candidates": 4,
            "max_per_topic_format": 2,
            "max_per_channel": 1,
        }

    def test_topic_evidence_gate(self):
        ready, reasons = evaluate_topic_evidence(
            {
                "unique_channels": 3,
                "velocity_sample_count": 3,
                "age_matched_velocity_index": 1.5,
            },
            self.config,
        )
        self.assertTrue(ready)
        self.assertEqual(reasons, [])

        ready, reasons = evaluate_topic_evidence(
            {
                "unique_channels": 2,
                "velocity_sample_count": 3,
                "age_matched_velocity_index": 1.5,
            },
            self.config,
        )
        self.assertFalse(ready)
        self.assertIn("insufficient_topic_unique_channels", reasons)

    def test_pass_requires_topic_family_and_demand_evidence(self):
        candidates = [
            {
                "video_id": "v1",
                "youtube_url": "https://youtube.com/watch?v=v1",
                "title": "F1 Gearbox Explained",
                "channel_id": "c1",
                "channel_title": "Channel 1",
                "format_candidate": "long_form_candidate",
                "views": 1000000,
                "likes": 10000,
                "validated_topics": ["gearbox_transmission"],
                "query_provenance": [
                    {
                        "topic": "gearbox_transmission",
                        "family": "how_it_works",
                    }
                ],
            }
        ]
        topic_velocity = {
            "topics": {
                "gearbox_transmission": {
                    "by_format": {
                        "long_form_candidate": {
                            "unique_channels": 4,
                            "velocity_sample_count": 4,
                            "age_matched_velocity_index": 1.7,
                        }
                    }
                }
            }
        }
        expansion = {
            "topics": {
                "gearbox_transmission": {
                    "long_form_candidate": {
                        "how_it_works": {
                            "unique_channels": 3,
                            "video_count": 5,
                            "median_views": 900000,
                        }
                    }
                }
            }
        }

        packets = build_handoff_packets(
            candidates,
            topic_velocity,
            expansion,
            self.config,
        )
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0]["gate_status"], "PASS")
        self.assertEqual(packets[0]["replicated_families"], ["how_it_works"])

    def test_review_when_topic_ready_but_family_not_replicated(self):
        candidates = [
            {
                "video_id": "v1",
                "channel_id": "c1",
                "format_candidate": "short_candidate",
                "views": 900000,
                "validated_topics": ["brakes"],
                "query_provenance": [
                    {"topic": "brakes", "family": "failure_problem"}
                ],
            }
        ]
        topic_velocity = {
            "topics": {
                "brakes": {
                    "by_format": {
                        "short_candidate": {
                            "unique_channels": 3,
                            "velocity_sample_count": 3,
                            "age_matched_velocity_index": 1.2,
                        }
                    }
                }
            }
        }
        expansion = {
            "topics": {
                "brakes": {
                    "short_candidate": {
                        "failure_problem": {
                            "unique_channels": 1,
                            "video_count": 1,
                        }
                    }
                }
            }
        }

        packet = build_handoff_packets(
            candidates,
            topic_velocity,
            expansion,
            self.config,
        )[0]
        self.assertEqual(packet["gate_status"], "REVIEW")
        self.assertIn("no_replicated_depth_family", packet["gate_reasons"])

    def test_hold_when_topic_velocity_evidence_is_weak(self):
        candidates = [
            {
                "video_id": "v1",
                "channel_id": "c1",
                "format_candidate": "short_candidate",
                "views": 900000,
                "validated_topics": ["brakes"],
                "query_provenance": [
                    {"topic": "brakes", "family": "failure_problem"}
                ],
            }
        ]
        topic_velocity = {
            "topics": {
                "brakes": {
                    "by_format": {
                        "short_candidate": {
                            "unique_channels": 1,
                            "velocity_sample_count": 1,
                            "age_matched_velocity_index": 1.8,
                        }
                    }
                }
            }
        }
        expansion = {
            "topics": {
                "brakes": {
                    "short_candidate": {
                        "failure_problem": {
                            "unique_channels": 3,
                            "video_count": 5,
                        }
                    }
                }
            }
        }

        packet = build_handoff_packets(
            candidates,
            topic_velocity,
            expansion,
            self.config,
        )[0]
        self.assertEqual(packet["gate_status"], "HOLD")

    def test_study_set_enforces_channel_and_topic_caps(self):
        packets = [
            {
                "gate_status": "PASS",
                "video_id": "v1",
                "channel_id": "same",
                "topic": "gearbox_transmission",
                "format_candidate": "long_form_candidate",
                "views": 2000000,
                "primary_metric": {"value": 2.0},
            },
            {
                "gate_status": "PASS",
                "video_id": "v2",
                "channel_id": "same",
                "topic": "gearbox_transmission",
                "format_candidate": "long_form_candidate",
                "views": 1500000,
                "primary_metric": {"value": 1.9},
            },
            {
                "gate_status": "PASS",
                "video_id": "v3",
                "channel_id": "other",
                "topic": "brakes",
                "format_candidate": "short_candidate",
                "views": 1000000,
                "primary_metric": {"value": 1.5},
            },
        ]

        selected = build_study_set(packets, self.config)

        self.assertEqual([row["video_id"] for row in selected], ["v1", "v3"])


if __name__ == "__main__":
    unittest.main()
