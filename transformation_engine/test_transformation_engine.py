import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack

import transformation_engine as module
from transformation_engine import (
    build_concept_request,
    merge_candidate_files,
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
            "human_framing": {
                "hook_experience": {
                    "archetype": "EXPECTATION_VIOLATION",
                    "description": "A race car behaves normally, then the visible tyre condition suddenly looks destroyed."
                },
                "viewer_question": "How can a tyre look ruined so quickly and still be doing its job?",
                "psychological_pull": {
                    "primary_pull": "EXPECTATION_VIOLATION",
                    "viewer_expectation": "A healthy tyre should continue looking smooth and intact.",
                    "violation_or_tension": "The tyre surface rapidly looks torn up even during normal high-load use.",
                    "stakes": "The viewer cannot tell normal racing behaviour from actual tyre failure.",
                    "information_gap": "What physical process makes the surface look destroyed?",
                    "desired_resolution": "Understand what the visible surface change means and when it is actually a problem."
                },
                "explanation_payoff": "The viewer can distinguish dramatic-looking normal tyre behaviour from genuine failure by understanding the underlying mechanism.",
                "visual_opening_plan": {
                    "moments": [
                        {"visual": "Show a clean racing tyre before a hard run.", "purpose": "Establish the expected normal state."},
                        {"visual": "Cut to the same type of tyre with a visibly rough surface.", "purpose": "Create the visual contradiction."},
                        {"visual": "Freeze on the damaged-looking surface.", "purpose": "Hold the unanswered question before explaining it."}
                    ],
                    "opening_narration_intent": "This tyre looks destroyed after only a few laps. So why can that be normal?"
                },
                "drama": {
                    "capacity": 7,
                    "target": 5,
                    "source": "The tyre appears severely damaged even when the underlying process may be normal racing use.",
                    "constraint": "Do not imply the tyre is safe or failed until independent research verifies the actual condition.",
                    "hook_level": 6,
                    "story_curve": [6, 5, 7, 5],
                    "tempo_curve": [7, 4, 6, 5]
                }
            },
            "viewer_need_evidence": {
                "status": "INFERRED",
                "evidence_basis": [
                    "Replicated automotive mechanism evidence suggests this is a plausible viewer question."
                ],
                "rationale": "The viewer need is inferred from the studied content pattern, not directly observed in audience comments or search queries.",
            },
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

    def test_observed_viewer_need_requires_evidence_basis(self):
        request = build_concept_request(self.entry, self.config)
        concept = self.valid_concept()
        concept["viewer_need_evidence"]["status"] = "OBSERVED"
        concept["viewer_need_evidence"]["evidence_basis"] = []

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
                "OBSERVED viewer_need_evidence requires concrete evidence_basis"
                in error
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


    def test_cross_response_duplicate_concept_ids_are_namespaced_not_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requests = root / "requests"
            responses = root / "responses"
            requests.mkdir()
            responses.mkdir()

            validation_contract = module.validation_contract_sha256()
            for mechanism in ("m1", "m2"):
                request_path = requests / f"{mechanism}.concept_request.json"
                request_path.write_text(
                    json.dumps({"mechanism_id": mechanism}),
                    encoding="utf-8",
                )
                (responses / f"{mechanism}.json").write_text(
                    json.dumps(
                        {
                            "mechanism_id": mechanism,
                            "concepts": [
                                {
                                    "concept_id": "concept-1",
                                    "working_title": mechanism,
                                }
                            ],
                            "response_provenance": {
                                "request_sha256": module.sha256_file(request_path),
                                "validation_contract_sha256": validation_contract,
                            },
                        }
                    ),
                    encoding="utf-8",
                )

            with (
                patch.object(module, "REQUESTS_DIR", requests),
                patch.object(module, "RESPONSES_DIR", responses),
                patch.object(module, "load_config", return_value=self.config),
                patch.object(
                    module,
                    "validate_response",
                    side_effect=lambda response, request, config: {
                        "accepted": response["concepts"],
                        "rejected": [],
                    },
                ),
            ):
                accepted, rejected = merge_candidate_files()

        self.assertEqual(rejected, [])
        self.assertEqual(len(accepted), 2)
        self.assertEqual(
            {item["concept_id"] for item in accepted},
            {"concept-1", "m2--concept-1"},
        )
        renamed = next(item for item in accepted if item["concept_id"] != "concept-1")
        self.assertEqual(renamed["model_concept_id"], "concept-1")


    def test_apply_preserves_handoff_hash_so_next_prepare_invalidates_stale_outputs(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            output = root / "output"
            requests = output / "concept_requests"
            responses = output / "concept_responses"
            output.mkdir()
            requests.mkdir()
            responses.mkdir()
            handoff = root / "handoff.json"

            stack.enter_context(patch.object(module, "OUTPUT_DIR", output))
            stack.enter_context(patch.object(module, "REQUESTS_DIR", requests))
            stack.enter_context(patch.object(module, "RESPONSES_DIR", responses))
            stack.enter_context(
                patch.object(module, "CANDIDATES_FILE", output / "concept_candidates.json")
            )
            stack.enter_context(
                patch.object(module, "REJECTED_FILE", output / "rejected_concepts.json")
            )
            stack.enter_context(
                patch.object(module, "SUMMARY_FILE", output / "summary.json")
            )
            stack.enter_context(patch.object(module, "load_config", return_value={}))
            stack.enter_context(
                patch.object(
                    module,
                    "ready_entries",
                    side_effect=lambda payload, config: payload.get("entries", []),
                )
            )
            stack.enter_context(
                patch.object(
                    module,
                    "build_concept_request",
                    side_effect=lambda entry, config: {
                        "mechanism_id": entry["mechanism_id"]
                    },
                )
            )

            handoff.write_text(
                json.dumps({"entries": [{"mechanism_id": "m1", "label": "v1"}]}),
                encoding="utf-8",
            )
            first = run_prepare(handoff)
            module.run_apply()
            saved = json.loads(module.SUMMARY_FILE.read_text(encoding="utf-8"))
            self.assertEqual(saved["handoff_sha256"], first["handoff_sha256"])

            stale_names = [
                "concept_triage.json",
                "concept_candidates_triaged.json",
                "concept_gate_reviewed.json",
                "research_handoff.json",
                "concept_gate_ui_state.json",
            ]
            for name in stale_names:
                (output / name).write_text("{}", encoding="utf-8")

            handoff.write_text(
                json.dumps({"entries": [{"mechanism_id": "m1", "label": "v2"}]}),
                encoding="utf-8",
            )
            run_prepare(handoff)

            self.assertTrue(all(not (output / name).exists() for name in stale_names))

    def test_triage_waits_until_every_mechanism_contributes(self):
        # D-129: a resumable batch is not a complete stage. Five valid concepts
        # from m1 alone must not open triage while m2 has none.
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            output = Path(tmp)
            requests = output / "concept_requests"
            responses = output / "concept_responses"
            requests.mkdir()
            responses.mkdir()
            for name, value in {
                "OUTPUT_DIR": output,
                "REQUESTS_DIR": requests,
                "RESPONSES_DIR": responses,
                "CANDIDATES_FILE": output / "concept_candidates.json",
                "REJECTED_FILE": output / "rejected_concepts.json",
                "SUMMARY_FILE": output / "summary.json",
            }.items():
                stack.enter_context(patch.object(module, name, value))
            stack.enter_context(
                patch.object(module, "load_config", return_value={"minimum_candidates_for_triage": 5})
            )
            stack.enter_context(
                patch.object(
                    module,
                    "validate_response",
                    side_effect=lambda response, request, config: {
                        "accepted": [dict(item) for item in response["concepts"]],
                        "rejected": [],
                    },
                )
            )
            contract = module.validation_contract_sha256()

            def write_mechanism(mechanism_id, concepts):
                request = requests / f"{mechanism_id}.concept_request.json"
                request.write_text(json.dumps({"mechanism_id": mechanism_id}), encoding="utf-8")
                if concepts:
                    (responses / f"{mechanism_id}.json").write_text(
                        json.dumps({
                            "mechanism_id": mechanism_id,
                            "concepts": [{"concept_id": f"{mechanism_id}-c{i}"} for i in range(concepts)],
                            "response_provenance": {
                                "request_sha256": module.sha256_file(request),
                                "validation_contract_sha256": contract,
                            },
                        }),
                        encoding="utf-8",
                    )

            write_mechanism("m1", 5)
            write_mechanism("m2", 0)
            partial = module.run_apply()
            self.assertEqual(partial["status"], "INCOMPLETE_MECHANISM_COVERAGE")
            self.assertFalse(partial["ready_for_triage"])
            self.assertEqual(partial["missing_mechanism_ids"], ["m2"])

            write_mechanism("m2", 1)
            complete = module.run_apply()
            self.assertEqual(complete["status"], "CONCEPT_CANDIDATES_READY")
            self.assertTrue(complete["ready_for_triage"])


if __name__ == "__main__":
    unittest.main()
