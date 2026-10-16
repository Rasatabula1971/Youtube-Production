import unittest

from experiment_01_discovery.experiment_01_5 import (
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
                "query_provenance": [{"topic": "brakes", "family": "failure_problem"}],
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
                "query_provenance": [{"topic": "brakes", "family": "failure_problem"}],
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


class GateArchiveTests(unittest.TestCase):
    """D-178: a rebuilt handoff archives the earlier human decision, never deletes it."""

    def test_rebuild_archives_decision_and_approved_set_with_their_study_set(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from experiment_01_discovery import experiment_01_5 as exp15

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "output"
            out15 = out / "experiment_01_5"
            out15.mkdir(parents=True)
            names = {
                "OUTPUT_DIR": out15,
                "PACKETS_FILE": out15 / "handoff_packets.json",
                "STUDY_SET_FILE": out15 / "study_set.json",
                "CSV_FILE": out15 / "handoff_candidates.csv",
                "SUMMARY_FILE": out15 / "summary.json",
                "HUMAN_DECISION_FILE": out15 / "human_opportunity_decision.json",
                "APPROVED_STUDY_SET_FILE": out15 / "approved_study_set.json",
                "ARCHIVE_ROOT": out / "archive",
            }
            names["STUDY_SET_FILE"].write_text('[{"video_id": "old"}]', encoding="utf-8")
            names["PACKETS_FILE"].write_text("[]", encoding="utf-8")
            names["HUMAN_DECISION_FILE"].write_text('{"decision": "APPROVE"}', encoding="utf-8")
            names["APPROVED_STUDY_SET_FILE"].write_text('[{"video_id": "old"}]', encoding="utf-8")
            patches = [patch.object(exp15, key, value) for key, value in names.items()]
            for p in patches:
                p.start()
                self.addCleanup(p.stop)

            exp15.write_outputs([], [{"video_id": "new"}], {}, {}, {})

            self.assertFalse(names["HUMAN_DECISION_FILE"].exists())
            self.assertFalse(names["APPROVED_STUDY_SET_FILE"].exists())
            [archived] = list(names["ARCHIVE_ROOT"].iterdir())
            self.assertTrue(archived.name.startswith("experiment_01_5_gate_"))
            self.assertEqual(json.loads((archived / "human_opportunity_decision.json").read_text())["decision"], "APPROVE")
            self.assertEqual(json.loads((archived / "approved_study_set.json").read_text()), [{"video_id": "old"}])
            self.assertEqual(json.loads((archived / "study_set.json").read_text()), [{"video_id": "old"}])
            self.assertEqual(json.loads(names["STUDY_SET_FILE"].read_text()), [{"video_id": "new"}])

            # Nothing to retire: nothing is archived.
            exp15.write_outputs([], [{"video_id": "newer"}], {}, {}, {})
            self.assertEqual(len(list(names["ARCHIVE_ROOT"].iterdir())), 1)
