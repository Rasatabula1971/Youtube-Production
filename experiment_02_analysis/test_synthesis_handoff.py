import unittest

from synthesis_handoff import (
    build_mechanism_library,
    build_transformation_handoff,
    mechanism_state,
)


class SynthesisHandoffTests(unittest.TestCase):
    def setUp(self):
        self.experiment_config = {
            "required_dimensions": ["opening_hook"],
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
                "opening_hook": [
                    "transcript",
                    "opening_frame",
                    "visual_note",
                    "audio_note",
                ]
            },
            "mechanism_taxonomy": {
                "curiosity_gap": "Creates an unanswered question.",
                "hidden_mechanism": "Reveals an internal mechanism.",
            },
            "minimum_replication_videos": 2,
            "minimum_replication_channels": 2,
            "causal_warning_phrases": ["made it viral"],
        }
        self.synthesis_config = {
            "max_observed_examples_per_mechanism": 12,
            "max_transfer_descriptions_per_mechanism": 12,
            "max_transformation_directions_per_mechanism": 12,
            "require_human_review_for_ready": True,
        }

    def profile(
        self,
        video_id,
        channel_id,
        *,
        reviewed=False,
        topic="gearbox",
        fmt="long_form_candidate",
        mechanism="curiosity_gap",
    ):
        return {
            "schema_version": "2.0",
            "experiment_id": "02",
            "video_id": video_id,
            "source": {
                "channel_id": channel_id,
                "channel_title": channel_id,
                "topic": topic,
                "format_candidate": fmt,
            },
            "evidence": [
                {
                    "evidence_id": "transcript.open",
                    "type": "transcript",
                    "locator": "00:00:00.000-00:00:05.000",
                    "observation": "Opening asks a direct question.",
                }
            ],
            "analysis": {
                "opening_hook": {
                    "findings": [
                        {
                            "finding": "The opening asks a direct question.",
                            "mechanism_ids": [mechanism],
                            "evidence_refs": ["transcript.open"],
                            "confidence": "MODERATE",
                        }
                    ],
                    "notes": "",
                }
            },
            "working_hypotheses": [],
            "transfer": {
                "transferable_mechanisms": [
                    {
                        "description": "Use a concrete unanswered question.",
                        "mechanism_ids": [mechanism],
                        "evidence_refs": ["transcript.open"],
                        "confidence": "MODERATE",
                    }
                ],
                "source_specific_elements": [
                    {
                        "element": "Exact gearbox wording.",
                        "evidence_refs": ["transcript.open"],
                        "confidence": "MODERATE",
                    }
                ],
                "transformation_opportunities": [
                    {
                        "mechanism_id": mechanism,
                        "new_direction": "Apply the question structure to brakes.",
                        "evidence_refs": ["transcript.open"],
                        "source_dependency_test": {
                            "passes": True,
                            "rationale": "The mechanism survives without source wording.",
                        },
                    }
                ],
            },
            "review": {"completed": reviewed},
        }

    def test_replicated_two_videos_two_channels_is_draft_without_review(self):
        library = build_mechanism_library(
            [self.profile("v1", "c1"), self.profile("v2", "c2")],
            self.experiment_config,
            self.synthesis_config,
        )
        mechanism = library["mechanisms"][0]
        self.assertEqual(mechanism["state"], "MODEL_SYNTHESIS_DRAFT")
        self.assertEqual(mechanism["replication"]["video_count"], 2)
        self.assertEqual(mechanism["replication"]["unique_channels"], 2)

    def test_human_reviewed_replication_is_confirmed(self):
        library = build_mechanism_library(
            [
                self.profile("v1", "c1", reviewed=True),
                self.profile("v2", "c2", reviewed=True),
            ],
            self.experiment_config,
            self.synthesis_config,
        )
        self.assertEqual(
            library["mechanisms"][0]["state"],
            "HUMAN_CONFIRMED_PATTERN",
        )

    def test_same_channel_does_not_meet_replication_gate(self):
        library = build_mechanism_library(
            [self.profile("v1", "same"), self.profile("v2", "same")],
            self.experiment_config,
            self.synthesis_config,
        )
        self.assertEqual(
            library["mechanisms"][0]["state"],
            "SINGLE_SOURCE_OBSERVATION",
        )

    def test_cross_topic_and_cross_format_scope_are_descriptive(self):
        library = build_mechanism_library(
            [
                self.profile("v1", "c1", topic="gearbox", fmt="long_form_candidate"),
                self.profile("v2", "c2", topic="brakes", fmt="short_candidate"),
            ],
            self.experiment_config,
            self.synthesis_config,
        )
        scope = library["mechanisms"][0]["scope"]
        self.assertEqual(scope["topic_scope"], "CROSS_TOPIC")
        self.assertEqual(scope["format_scope"], "CROSS_FORMAT")

    def test_failed_source_dependency_direction_is_excluded(self):
        first = self.profile("v1", "c1")
        first["transfer"]["transformation_opportunities"][0][
            "source_dependency_test"
        ]["passes"] = False
        library = build_mechanism_library(
            [first, self.profile("v2", "c2")],
            self.experiment_config,
            self.synthesis_config,
        )
        directions = library["mechanisms"][0][
            "accepted_transformation_directions"
        ]
        self.assertEqual(len(directions), 1)
        self.assertEqual(directions[0]["video_id"], "v2")

    def test_handoff_requires_review_for_model_draft(self):
        library = build_mechanism_library(
            [self.profile("v1", "c1"), self.profile("v2", "c2")],
            self.experiment_config,
            self.synthesis_config,
        )
        handoff = build_transformation_handoff(
            library,
            self.synthesis_config,
        )
        self.assertEqual(
            handoff["status"],
            "DRAFT_REQUIRES_HUMAN_REVIEW",
        )
        self.assertEqual(
            handoff["entries"][0]["handoff_status"],
            "REQUIRES_HUMAN_REVIEW",
        )

    def test_handoff_ready_after_human_confirmed_replication(self):
        library = build_mechanism_library(
            [
                self.profile("v1", "c1", reviewed=True),
                self.profile("v2", "c2", reviewed=True),
            ],
            self.experiment_config,
            self.synthesis_config,
        )
        handoff = build_transformation_handoff(
            library,
            self.synthesis_config,
        )
        self.assertEqual(
            handoff["status"],
            "READY_FOR_TRANSFORMATION_ENGINE",
        )

    def test_mechanism_state_is_not_a_score(self):
        state = mechanism_state(
            video_count=10,
            channel_count=10,
            reviewed_video_count=0,
            reviewed_channel_count=0,
            minimum_videos=2,
            minimum_channels=2,
        )
        self.assertEqual(state, "MODEL_SYNTHESIS_DRAFT")


if __name__ == "__main__":
    unittest.main()
