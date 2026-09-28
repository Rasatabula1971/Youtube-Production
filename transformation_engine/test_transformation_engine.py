import json
import tempfile
import unittest
from pathlib import Path

import transformation_engine as module
from transformation_engine import (
    build_concept_request,
    ready_entries,
    run_prepare,
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
            "viewer_problem": "Why do racing brakes behave poorly in conditions that suit road brakes?",
            "viewer_moment": "Trying to understand a counterintuitive race-car engineering tradeoff.",
            "desired_outcome": "Understand the thermal constraint and why the obvious road-car solution fails.",
            "content_gap": {
                "hypothesis": "Existing explanations may describe hot brakes without connecting temperature to the design tradeoff.",
                "evidence_status": "HYPOTHESIS",
                "evidence_basis": [],
            },
            "channel_fit": {
                "status": "FIT",
                "rationale": "Matches the channel's automotive engineering and mechanism-explainer direction.",
            },
            "title_clarity_test": {
                "options": [
                    "Why Racing Brakes Behave Backwards",
                    "Why F1 Brakes Hate Normal Temperatures",
                    "The Brake Problem Road Cars Never Face",
                ],
                "result": "PASS",
                "rationale": "Three distinct titles express the same clear viewer problem and payoff.",
            },
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

    def test_prepare_binds_requests_to_handoff_and_invalidates_stale_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoff = root / "handoff.json"
            output = root / "output"
            requests = output / "concept_requests"
            responses = output / "concept_responses"
            output.mkdir()
            requests.mkdir()
            responses.mkdir()

            payload = {
                "status": "READY_FOR_TRANSFORMATION_ENGINE",
                "entries": [self.entry],
            }
            handoff.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )

            old_output = module.OUTPUT_DIR
            old_requests = module.REQUESTS_DIR
            old_responses = module.RESPONSES_DIR
            old_candidates = module.CANDIDATES_FILE
            old_rejected = module.REJECTED_FILE
            old_summary = module.SUMMARY_FILE
            try:
                module.OUTPUT_DIR = output
                module.REQUESTS_DIR = requests
                module.RESPONSES_DIR = responses
                module.CANDIDATES_FILE = output / "concept_candidates.json"
                module.REJECTED_FILE = output / "rejected_concepts.json"
                module.SUMMARY_FILE = output / "summary.json"

                first = run_prepare(handoff)
                request_path = requests / "curiosity_gap.concept_request.json"
                request = json.loads(request_path.read_text(encoding="utf-8"))
                first_hash = request["request_provenance"]["handoff_sha256"]
                self.assertEqual(
                    first_hash,
                    module.sha256_file(handoff),
                )

                (output / "concept_gate_ui_state.json").write_text(
                    json.dumps({"status": "COMPLETE"}),
                    encoding="utf-8",
                )

                payload["entries"][0]["label"] = "Changed mechanism label"
                handoff.write_text(
                    json.dumps(payload),
                    encoding="utf-8",
                )
                second = run_prepare(handoff)

                self.assertNotEqual(
                    first["handoff_sha256"],
                    second["handoff_sha256"],
                )
                self.assertFalse((output / "concept_gate_ui_state.json").exists())
            finally:
                module.OUTPUT_DIR = old_output
                module.REQUESTS_DIR = old_requests
                module.RESPONSES_DIR = old_responses
                module.CANDIDATES_FILE = old_candidates
                module.REJECTED_FILE = old_rejected
                module.SUMMARY_FILE = old_summary

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

    def test_missing_viewer_problem_is_rejected(self):
        request = build_concept_request(self.entry, self.config)
        concept = self.valid_concept()
        concept["viewer_problem"] = ""

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
                "viewer_problem is required" in error
                for error in result["rejected"][0]["errors"]
            )
        )

    def test_supported_gap_requires_evidence_basis(self):
        request = build_concept_request(self.entry, self.config)
        concept = self.valid_concept()
        concept["content_gap"]["evidence_status"] = "SUPPORTED"
        concept["content_gap"]["evidence_basis"] = []

        result = validate_response(
            {
                "mechanism_id": "curiosity_gap",
                "concepts": [concept],
            },
            request,
            self.config,
        )

        self.assertEqual(len(result["accepted"]), 0)

    def test_title_clarity_requires_three_options(self):
        request = build_concept_request(self.entry, self.config)
        concept = self.valid_concept()
        concept["title_clarity_test"]["options"] = ["One", "Two"]

        result = validate_response(
            {
                "mechanism_id": "curiosity_gap",
                "concepts": [concept],
            },
            request,
            self.config,
        )

        self.assertEqual(len(result["accepted"]), 0)

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
        concept["source_specific_elements_used"] = ["Exact gearbox wording."]

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
