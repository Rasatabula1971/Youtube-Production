import unittest

from transformation_engine import (
    build_concept_request,
    ready_entries,
    validate_response,
)


class TransformationEngineTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "concepts_per_mechanism": 5,
            "allowed_format_intents": [
                "long_form",
                "short",
                "either",
            ],
            "require_ready_handoff": True,
            "minimum_research_questions": 2,
        }
        self.entry = {
            "mechanism_id": "curiosity_gap",
            "label": "Creates a specific unanswered question.",
            "pattern_state": "HUMAN_CONFIRMED_PATTERN",
            "handoff_status": "READY_FOR_TRANSFORMATION_ENGINE",
            "replication": {
                "video_ids": ["source1", "source2"],
                "unique_channels": 2,
            },
            "scope": {
                "topics": ["gearbox", "brakes"],
                "formats": ["long_form_candidate"],
            },
            "transferable_descriptions": [
                {"description": "Open with a concrete unanswered question."}
            ],
            "observed_examples": [],
            "source_specific_elements_to_avoid": [
                {"element": "Exact gearbox wording."}
            ],
            "existing_transformation_directions": [],
        }

    def valid_concept(self):
        return {
            "concept_id": "curiosity_gap-001",
            "working_title": "Why Racing Brakes Behave Backwards",
            "premise": "Investigate a counterintuitive brake design constraint.",
            "audience_promise": "Explain the hidden engineering reason.",
            "format_intent": "long_form",
            "mechanism_application": "Lead with one concrete unanswered engineering question.",
            "transformation_method": "Uses a different system, research path, and explanation.",
            "research_questions": [
                "What thermal limits drive the design?",
                "Which rules constrain the brake system?",
            ],
            "source_specific_elements_used": [],
            "source_dependency_test": {
                "passes": True,
                "source_assets_required": False,
                "rationale": "The concept is independently researchable.",
            },
        }

    def test_only_ready_entries_are_used(self):
        blocked = dict(self.entry)
        blocked["handoff_status"] = "REQUIRES_HUMAN_REVIEW"

        result = ready_entries(
            {"entries": [self.entry, blocked]},
            self.config,
        )

        self.assertEqual(len(result), 1)

    def test_request_preserves_mechanism_context_without_ranking(self):
        request = build_concept_request(self.entry, self.config)

        self.assertEqual(
            request["mechanism_id"],
            "curiosity_gap",
        )
        self.assertEqual(request["concept_count_requested"], 5)
        self.assertNotIn("score", request)
        self.assertNotIn("rank", request)

    def test_valid_concept_passes(self):
        request = build_concept_request(self.entry, self.config)
        response = {
            "mechanism_id": "curiosity_gap",
            "concepts": [self.valid_concept()],
        }

        result = validate_response(
            response,
            request,
            self.config,
        )

        self.assertEqual(len(result["accepted"]), 1)
        self.assertEqual(len(result["rejected"]), 0)

    def test_source_dependent_concept_is_rejected(self):
        request = build_concept_request(self.entry, self.config)
        concept = self.valid_concept()
        concept["source_dependency_test"]["passes"] = False

        result = validate_response(
            {
                "mechanism_id": "curiosity_gap",
                "concepts": [concept],
            },
            request,
            self.config,
        )

        self.assertEqual(len(result["accepted"]), 0)
        self.assertTrue(
            any(
                "passes must be true" in error
                for error in result["rejected"][0]["errors"]
            )
        )

    def test_source_specific_usage_is_rejected(self):
        request = build_concept_request(self.entry, self.config)
        concept = self.valid_concept()
        concept["source_specific_elements_used"] = [
            "Exact gearbox wording."
        ]

        result = validate_response(
            {
                "mechanism_id": "curiosity_gap",
                "concepts": [concept],
            },
            request,
            self.config,
        )

        self.assertEqual(len(result["accepted"]), 0)

    def test_direct_source_video_id_reference_is_rejected(self):
        request = build_concept_request(self.entry, self.config)
        concept = self.valid_concept()
        concept["premise"] += " Inspired directly by source1."

        result = validate_response(
            {
                "mechanism_id": "curiosity_gap",
                "concepts": [concept],
            },
            request,
            self.config,
        )

        self.assertEqual(len(result["accepted"]), 0)

    def test_research_questions_are_required(self):
        request = build_concept_request(self.entry, self.config)
        concept = self.valid_concept()
        concept["research_questions"] = ["Only one?"]

        result = validate_response(
            {
                "mechanism_id": "curiosity_gap",
                "concepts": [concept],
            },
            request,
            self.config,
        )

        self.assertEqual(len(result["accepted"]), 0)


if __name__ == "__main__":
    unittest.main()
