import unittest

from analysis_execute import (
    build_analysis_request,
    merge_analysis_response,
    objective_metrics,
)


class AnalysisExecutionTests(unittest.TestCase):
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
            "mechanism_taxonomy": {
                "curiosity_gap": "Curiosity",
                "hidden_mechanism": "Hidden mechanism",
            },
            "causal_warning_phrases": [
                "made it viral",
                "caused the views",
            ],
            "analysis_execution": {
                "opening_window_seconds": 30,
                "max_evidence_items_per_dimension": 10,
                "max_observation_chars": 500,
            },
        }

    def profile(self):
        return {
            "schema_version": "2.0",
            "experiment_id": "02",
            "study_id": "h1",
            "video_id": "v1",
            "source": {
                "channel_id": "c1",
                "channel_title": "Channel",
            },
            "source_inputs": {},
            "evidence": [
                {
                    "evidence_id": "metadata.title",
                    "type": "metadata",
                    "locator": "video title",
                    "observation": "Why F1 Gearboxes Are So Strange",
                },
                {
                    "evidence_id": "transcript.t000000000_000005000_0001",
                    "type": "transcript",
                    "locator": "00:00:00.000-00:00:05.000",
                    "observation": "Why does an F1 gearbox need eight gears?",
                },
                {
                    "evidence_id": "transcript.t000005000_000010000_0002",
                    "type": "transcript",
                    "locator": "00:00:05.000-00:00:10.000",
                    "observation": "The answer starts inside the casing.",
                },
                {
                    "evidence_id": "opportunity.01_5",
                    "type": "opportunity_evidence",
                    "locator": "handoff",
                    "observation": "Selection context only.",
                },
            ],
            "analysis": {
                "packaging": {"findings": [], "notes": ""},
                "opening_hook": {"findings": [], "notes": ""},
            },
            "working_hypotheses": [],
            "transfer": {
                "transferable_mechanisms": [],
                "source_specific_elements": [],
                "transformation_opportunities": [],
            },
        }

    def test_request_filters_evidence_by_dimension(self):
        request = build_analysis_request(self.profile(), self.config)

        packaging_ids = set(
            request["dimensions"]["packaging"]["evidence_refs"]
        )
        hook_ids = set(
            request["dimensions"]["opening_hook"]["evidence_refs"]
        )

        self.assertEqual(packaging_ids, {"metadata.title"})
        self.assertEqual(
            hook_ids,
            {
                "transcript.t000000000_000005000_0001",
                "transcript.t000005000_000010000_0002",
            },
        )


    def test_request_uses_single_compact_evidence_library(self):
        request = build_analysis_request(self.profile(), self.config)

        self.assertIn("evidence_library", request)
        self.assertIn("metadata.title", request["evidence_library"])
        self.assertNotIn("opportunity.01_5", request["evidence_library"])
        self.assertNotIn("evidence", request["dimensions"]["packaging"])

    def test_audience_promise_keeps_title_when_transcript_is_large(self):
        profile = self.profile()
        for index in range(20):
            start = 10 + index
            end = start + 1
            profile["evidence"].append(
                {
                    "evidence_id": f"transcript.extra{index}",
                    "type": "transcript",
                    "locator": f"00:00:{start:02d}.000-00:00:{end:02d}.000",
                    "observation": f"Transcript segment {index}",
                }
            )

        config = dict(self.config)
        config["required_dimensions"] = ["audience_promise"]
        config["dimension_evidence_types"] = {
            "audience_promise": ["metadata", "transcript"]
        }
        config["analysis_execution"] = {
            "opening_window_seconds": 30,
            "max_evidence_items_per_dimension": 3,
            "max_observation_chars": 500,
        }

        request = build_analysis_request(profile, config)
        refs = request["dimensions"]["audience_promise"]["evidence_refs"]

        self.assertIn("metadata.title", refs)
        self.assertEqual(len(refs), 3)

    def test_objective_metrics_count_timestamped_transcript(self):
        metrics = objective_metrics(
            self.profile(),
            opening_window_seconds=30,
        )

        self.assertEqual(metrics["transcript_segment_count"], 2)
        self.assertEqual(metrics["timestamped_transcript_span_seconds"], 10.0)
        self.assertEqual(metrics["transcript_segments_per_minute"], 12.0)

    def test_supported_finding_is_merged(self):
        response = {
            "video_id": "v1",
            "analysis": {
                "packaging": {
                    "findings": [
                        {
                            "finding": "The title is phrased as a specific question.",
                            "mechanism_ids": ["curiosity_gap"],
                            "evidence_refs": ["metadata.title"],
                            "confidence": "MODERATE",
                        }
                    ]
                },
                "opening_hook": {"findings": []},
            },
            "working_hypotheses": [],
            "transfer": {},
        }

        merged, report = merge_analysis_response(
            self.profile(),
            response,
            self.config,
        )

        self.assertEqual(
            len(merged["analysis"]["packaging"]["findings"]),
            1,
        )
        self.assertEqual(report["accepted_findings"], 1)
        self.assertEqual(report["routed_to_hypotheses"], 0)

    def test_missing_evidence_routes_finding_to_hypothesis(self):
        response = {
            "video_id": "v1",
            "analysis": {
                "packaging": {"findings": []},
                "opening_hook": {
                    "findings": [
                        {
                            "finding": "The opening uses a curiosity gap.",
                            "mechanism_ids": ["curiosity_gap"],
                            "evidence_refs": [],
                            "confidence": "MODERATE",
                        }
                    ]
                },
            },
            "working_hypotheses": [],
            "transfer": {},
        }

        merged, report = merge_analysis_response(
            self.profile(),
            response,
            self.config,
        )

        self.assertEqual(
            merged["analysis"]["opening_hook"]["findings"],
            [],
        )
        self.assertEqual(len(merged["working_hypotheses"]), 1)
        self.assertEqual(report["routed_to_hypotheses"], 1)

    def test_causal_claim_routes_to_hypothesis(self):
        response = {
            "video_id": "v1",
            "analysis": {
                "packaging": {"findings": []},
                "opening_hook": {
                    "findings": [
                        {
                            "finding": "This question made it viral.",
                            "mechanism_ids": ["curiosity_gap"],
                            "evidence_refs": [
                                "transcript.t000000000_000005000_0001"
                            ],
                            "confidence": "LOW",
                        }
                    ]
                },
            },
            "working_hypotheses": [],
            "transfer": {},
        }

        merged, report = merge_analysis_response(
            self.profile(),
            response,
            self.config,
        )

        self.assertEqual(
            merged["analysis"]["opening_hook"]["findings"],
            [],
        )
        self.assertEqual(len(merged["working_hypotheses"]), 1)
        self.assertEqual(report["routed_to_hypotheses"], 1)

    def test_response_video_id_must_match(self):
        response = {
            "video_id": "wrong",
            "analysis": {},
            "working_hypotheses": [],
            "transfer": {},
        }

        with self.assertRaises(ValueError):
            merge_analysis_response(
                self.profile(),
                response,
                self.config,
            )


    def test_partial_response_preserves_omitted_dimension(self):
        profile = self.profile()
        profile["analysis"]["packaging"]["findings"] = [
            {
                "finding": "Existing packaging finding.",
                "mechanism_ids": [],
                "evidence_refs": ["metadata.title"],
                "confidence": "LOW",
            }
        ]

        response = {
            "video_id": "v1",
            "analysis": {
                "opening_hook": {
                    "findings": [
                        {
                            "finding": "The opening asks a direct question.",
                            "mechanism_ids": ["curiosity_gap"],
                            "evidence_refs": [
                                "transcript.t000000000_000005000_0001"
                            ],
                            "confidence": "MODERATE",
                        }
                    ]
                }
            },
            "working_hypotheses": [],
            "transfer": {},
        }

        merged, _ = merge_analysis_response(
            profile,
            response,
            self.config,
        )

        self.assertEqual(
            merged["analysis"]["packaging"]["findings"][0]["finding"],
            "Existing packaging finding.",
        )
        self.assertEqual(
            len(merged["analysis"]["opening_hook"]["findings"]),
            1,
        )

    def test_reapplying_same_hypothesis_does_not_duplicate_it(self):
        response = {
            "video_id": "v1",
            "analysis": {
                "opening_hook": {
                    "findings": [
                        {
                            "finding": "This question made it viral.",
                            "mechanism_ids": ["curiosity_gap"],
                            "evidence_refs": [
                                "transcript.t000000000_000005000_0001"
                            ],
                            "confidence": "LOW",
                        }
                    ]
                }
            },
            "working_hypotheses": [],
            "transfer": {},
        }

        first, _ = merge_analysis_response(
            self.profile(),
            response,
            self.config,
        )
        second, _ = merge_analysis_response(
            first,
            response,
            self.config,
        )

        self.assertEqual(len(second["working_hypotheses"]), 1)

    def test_failed_source_dependency_test_routes_to_hypothesis(self):
        response = {
            "video_id": "v1",
            "analysis": {
                "packaging": {"findings": []},
                "opening_hook": {"findings": []},
            },
            "working_hypotheses": [],
            "transfer": {
                "transformation_opportunities": [
                    {
                        "mechanism_id": "hidden_mechanism",
                        "new_direction": "Use the exact source animation with new narration.",
                        "evidence_refs": [
                            "transcript.t000005000_000010000_0002"
                        ],
                        "source_dependency_test": {
                            "passes": false,
                            "rationale": "The idea depends on the source animation.",
                        },
                    }
                ]
            },
        }

        merged, report = merge_analysis_response(
            self.profile(),
            response,
            self.config,
        )

        self.assertEqual(
            merged["transfer"]["transformation_opportunities"],
            [],
        )
        self.assertEqual(len(merged["working_hypotheses"]), 1)
        self.assertEqual(report["routed_to_hypotheses"], 1)


if __name__ == "__main__":
    unittest.main()
