import unittest

from experiment_02 import (
    aggregate_profiles,
    build_profile_from_study_item,
    prepare_work_packets,
    validate_profile,
)


class Experiment02Tests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "required_dimensions": [
                "packaging",
                "opening_hook",
            ],
            "allowed_confidence": ["LOW", "MODERATE", "HIGH"],
            "evidence_types": [
                "metadata",
                "transcript",
                "thumbnail",
                "opening_frame",
                "visual_note",
                "timing_note",
                "audio_note",
                "opportunity_evidence",
            ],
            "dimension_evidence_types": {
                "packaging": ["metadata", "thumbnail", "opening_frame"],
                "opening_hook": [
                    "transcript",
                    "opening_frame",
                    "visual_note",
                    "audio_note",
                ],
            },
            "minimum_replication_videos": 2,
            "minimum_replication_channels": 2,
            "mechanism_taxonomy": {
                "curiosity_gap": "Curiosity",
                "hidden_mechanism": "Hidden mechanism",
            },
            "causal_warning_phrases": [
                "made it viral",
                "caused the views",
            ],
        }

    def base_profile(self, video_id="v1", channel_id="c1"):
        return {
            "schema_version": "2.0",
            "experiment_id": "02",
            "study_id": video_id,
            "video_id": video_id,
            "source": {
                "channel_id": channel_id,
            },
            "evidence": [
                {
                    "evidence_id": "metadata.title",
                    "type": "metadata",
                    "observation": "Why F1 Gearboxes Are Strange",
                },
                {
                    "evidence_id": "transcript.0_10",
                    "type": "transcript",
                    "locator": "00:00-00:10",
                    "observation": "The opening poses the central question.",
                },
            ],
            "analysis": {
                "packaging": {"findings": []},
                "opening_hook": {"findings": []},
            },
            "working_hypotheses": [],
            "transfer": {
                "transferable_mechanisms": [],
                "source_specific_elements": [],
                "transformation_opportunities": [],
            },
        }

    def test_prepare_is_offline_and_creates_empty_profile(self):
        study = [
            {
                "handoff_id": "h1",
                "video_id": "v1",
                "title": "F1 Gearbox",
                "channel_id": "c1",
                "channel_title": "Channel",
                "topic": "gearbox_transmission",
                "format_candidate": "long_form_candidate",
                "views": 1000000,
                "primary_metric": {"value": 1.5},
                "replicated_families": ["how_it_works"],
            }
        ]
        packets = prepare_work_packets(study, self.config)
        profile = build_profile_from_study_item(study[0], self.config)

        self.assertEqual(len(packets), 1)
        self.assertEqual(profile["source_inputs"]["transcript"]["status"], "NOT_PROVIDED")
        self.assertEqual(profile["analysis"]["packaging"]["findings"], [])

    def test_supported_finding_requires_evidence(self):
        profile = self.base_profile()
        profile["analysis"]["packaging"]["findings"] = [
            {
                "finding": "The title creates a curiosity gap.",
                "mechanism_ids": ["curiosity_gap"],
                "evidence_refs": [],
                "confidence": "MODERATE",
            }
        ]

        report = validate_profile(profile, self.config)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("evidence_refs" in error for error in report["errors"])
        )

    def test_dimension_requires_appropriate_evidence_type(self):
        profile = self.base_profile()
        profile["analysis"]["opening_hook"]["findings"] = [
            {
                "finding": "The opening asks a question.",
                "mechanism_ids": ["curiosity_gap"],
                "evidence_refs": ["metadata.title"],
                "confidence": "MODERATE",
            }
        ]

        report = validate_profile(profile, self.config)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("do not support this dimension" in error for error in report["errors"])
        )

    def test_causal_language_is_warning_not_supported_fact(self):
        profile = self.base_profile()
        profile["analysis"]["opening_hook"]["findings"] = [
            {
                "finding": "This hook made it viral.",
                "mechanism_ids": ["curiosity_gap"],
                "evidence_refs": ["transcript.0_10"],
                "confidence": "LOW",
            }
        ]

        report = validate_profile(profile, self.config)
        self.assertTrue(report["valid"])
        self.assertEqual(len(report["warnings"]), 1)

    def test_transformation_requires_source_dependency_test(self):
        profile = self.base_profile()
        profile["transfer"]["transformation_opportunities"] = [
            {
                "mechanism_id": "hidden_mechanism",
                "new_direction": "Explain a different hidden mechanism.",
                "evidence_refs": ["transcript.0_10"],
                "source_dependency_test": {},
            }
        ]

        report = validate_profile(profile, self.config)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("source_dependency_test.passes" in error for error in report["errors"])
        )

    def test_cross_video_replication_requires_independent_channels(self):
        first = self.base_profile("v1", "c1")
        second = self.base_profile("v2", "c2")

        for profile in (first, second):
            profile["analysis"]["opening_hook"]["findings"] = [
                {
                    "finding": "The opening creates an unanswered question.",
                    "mechanism_ids": ["curiosity_gap"],
                    "evidence_refs": ["transcript.0_10"],
                    "confidence": "MODERATE",
                }
            ]

        result = aggregate_profiles([first, second], self.config)
        pattern = result["patterns"][0]

        self.assertEqual(pattern["mechanism_id"], "curiosity_gap")
        self.assertEqual(pattern["status"], "REPLICATED_PATTERN")
        self.assertEqual(pattern["unique_channels"], 2)


if __name__ == "__main__":
    unittest.main()
