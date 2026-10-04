from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import concept_model_runner as runner

import transformation_engine as engine


class ConceptModelRunnerTests(unittest.TestCase):
    def request(self):
        return {
            "request_type": "transformation_concept_generation",
            "mechanism_id": "curiosity_gap",
            "mechanism_label": "Curiosity gap",
            "pattern_state": "HUMAN_CONFIRMED_PATTERN",
            "replication": {
                "video_ids": ["source1", "source2"],
                "unique_channels": 2,
            },
            "scope": {"topics": ["tyres"], "formats": ["short_candidate"]},
            "transferable_descriptions": [
                {"description": "Open with a concrete unanswered question."}
            ],
            "observed_examples": [],
            "viewer_need_signal_context": [],
            "source_specific_elements_to_avoid": [{"element": "Exact source wording."}],
            "existing_transformation_directions": [],
            "source_video_ids": ["source1", "source2"],
            "concept_count_requested": 5,
            "allowed_format_intents": ["long_form", "short", "either"],
            "instructions": [],
            "response_schema": {},
        }

    def valid_concept(self):
        return {
            "concept_id": "curiosity_gap-001",
            "working_title": "Why Racing Tyres Look Ruined So Fast",
            "premise": "Explain why visible tyre damage can reflect normal high-load use.",
            "audience_promise": "Reveal the engineering reason the surface looks destroyed.",
            "viewer_problem": "Why do racing tyres look damaged after only a short run?",
            "viewer_moment": "Watching race footage and noticing shredded-looking tyre surfaces.",
            "desired_outcome": "Understand what the visible tyre surface changes mean.",
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
                "status": "HYPOTHESIS",
                "evidence_basis": [],
                "rationale": "No direct audience-question evidence is present in this test request.",
            },
            "content_gap": {
                "hypothesis": "Many clips show the visual effect without explaining the mechanism.",
                "evidence_status": "HYPOTHESIS",
                "evidence_basis": [],
            },
            "channel_fit": {
                "status": "REVIEW",
                "rationale": "The concept fits an automotive engineering explainer direction but needs channel confirmation.",
            },
            "title_clarity_test": {
                "options": [
                    "Why Racing Tyres Look Ruined So Fast",
                    "Why F1 Tyres Look Destroyed After a Race",
                    "The Tyre Damage That Is Not Really Damage",
                ],
                "result": "PASS",
                "rationale": "Three clear framings express the same viewer question.",
            },
            "format_intent": "short",
            "mechanism_application": "Lead with the surprising visual question before revealing the mechanism.",
            "transformation_method": "Use independent tyre-engineering research and a new explanation path.",
            "research_questions": [
                "What physical process creates the visible tyre surface change?",
                "Which tyre operating conditions make it more pronounced?",
            ],
            "source_specific_elements_used": [],
            "source_dependency_test": {
                "passes": True,
                "source_assets_required": False,
                "rationale": "The explanation can be researched and produced independently.",
            },
        }

    def runner_config(self):
        return {
            "adapter": "fair_subprocess",
            "fair": {
                "quality_level": "standard",
                "max_attempts": 3,
                "max_unanswered_attempts": 6,
                "max_verification_attempts": 1,
                "timeout_seconds": 45,
                "cross_check_required": False,
                "max_output_tokens": 8192,
                "cache_mode": "bypass",
                "priority": "P2",
                "client_id": "test",
                "confirmed_free_providers": [],
            },
            "runner": {
                "max_prompt_chars": 95000,
                "subprocess_timeout_seconds": 30,
                "max_requests_per_batch": 4,
            },
        }

    def test_schema_locks_mechanism_and_source_independence(self):
        schema = runner.response_schema(self.request())
        self.assertEqual(
            schema["properties"]["mechanism_id"]["const"],
            "curiosity_gap",
        )
        need_evidence = schema["properties"]["concepts"]["items"]["properties"][
            "viewer_need_evidence"
        ]["properties"]
        self.assertIn("OBSERVED", need_evidence["status"]["enum"])
        self.assertIn("INFERRED", need_evidence["status"]["enum"])
        self.assertIn("HYPOTHESIS", need_evidence["status"]["enum"])
        dependency = schema["properties"]["concepts"]["items"]["properties"][
            "source_dependency_test"
        ]["properties"]
        self.assertTrue(dependency["passes"]["const"])
        self.assertFalse(dependency["source_assets_required"]["const"])

    def test_prompt_explicitly_forbids_ranking_and_copying(self):
        prompt = runner.build_prompt(
            self.request(),
            maximum_chars=95000,
        )
        self.assertIn("Do not rank or score concepts", prompt)
        self.assertIn("not rewrites of the source videos", prompt)
        self.assertIn("viewer_need_evidence.status", prompt)
        self.assertIn("OBSERVED", prompt)

    def test_rework_schema_targets_one_stable_concept(self):
        request = self.request()
        original = self.valid_concept()
        request.update(
            {
                "human_rework_note": "Make the hook more human and less technical.",
                "human_rework_concept_id": original["concept_id"],
                "human_rework_original_concept": original,
                "human_rework_original_concepts": [
                    original,
                    {
                        **original,
                        "concept_id": "curiosity_gap-002",
                        "working_title": "Keep This Sibling",
                    },
                ],
            }
        )
        schema = runner.response_schema(request)
        concepts = schema["properties"]["concepts"]
        concept_id = concepts["items"]["properties"]["concept_id"]

        self.assertEqual(concepts["maxItems"], 1)
        self.assertEqual(concept_id["const"], original["concept_id"])

    def test_rework_prompt_marks_human_instruction_authoritative(self):
        request = self.request()
        request.update(
            {
                "human_rework_note": "Make the hook about what an ordinary viewer notices.",
                "human_rework_concept_id": self.valid_concept()["concept_id"],
            }
        )
        prompt = runner.build_prompt(request, maximum_chars=95000)

        self.assertIn("AUTHORITATIVE human instruction", prompt)
        self.assertIn("exactly one revised concept", prompt)
        self.assertIn("same concept_id", prompt)
        self.assertIn("ordinary viewer notices", prompt)

    def test_rework_merge_replaces_only_target_concept(self):
        target = self.valid_concept()
        sibling = {
            **self.valid_concept(),
            "concept_id": "curiosity_gap-002",
            "working_title": "Keep This Sibling",
        }
        request = self.request()
        request.update(
            {
                "human_rework_note": "Raise the human tension.",
                "human_rework_concept_id": target["concept_id"],
                "human_rework_original_concepts": [target, sibling],
            }
        )
        replacement = {
            **target,
            "working_title": "The Tire Shouldn't Look Like This",
        }
        merged = runner._merge_human_rework_response(
            request,
            {
                "mechanism_id": "curiosity_gap",
                "concepts": [replacement],
            },
        )

        self.assertEqual(len(merged["concepts"]), 2)
        self.assertEqual(
            merged["concepts"][0]["working_title"],
            "The Tire Shouldn't Look Like This",
        )
        self.assertEqual(
            merged["concepts"][1]["working_title"],
            "Keep This Sibling",
        )

    @patch("concept_model_runner.resolve_fair_paths")
    @patch("concept_model_runner.call_fair_bridge")
    def test_valid_free_response_is_written_with_request_hash(
        self,
        call_bridge,
        resolve_paths,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request_path = root / "curiosity_gap.concept_request.json"
            request_path.write_text(
                json.dumps(self.request()),
                encoding="utf-8",
            )
            resolve_paths.return_value = {
                "repo": root,
                "env_file": root / ".env",
                "python": root / "python.exe",
            }
            call_bridge.return_value = {
                "status": "ACCEPTED",
                "output": json.dumps(
                    {
                        "mechanism_id": "curiosity_gap",
                        "concepts": [self.valid_concept()],
                    }
                ),
                "paid_inference_executed": False,
                "provider_id": "kilo_free",
                "model_id": "free-model",
                "request_id": "req-1",
                "attempts": [],
            }

            old_runs = runner.MODEL_RUNS_DIR
            old_raw = runner.RAW_OUTPUTS_DIR
            old_responses = runner.RESPONSES_DIR
            try:
                runner.MODEL_RUNS_DIR = root / "runs"
                runner.RAW_OUTPUTS_DIR = root / "raw"
                runner.RESPONSES_DIR = root / "responses"
                result = runner.run_one(
                    request_path,
                    force=False,
                    runner_config=self.runner_config(),
                )
                response = json.loads(
                    (runner.RESPONSES_DIR / "curiosity_gap.json").read_text(
                        encoding="utf-8"
                    )
                )
                expected_request_hash = engine.sha256_file(request_path)
            finally:
                runner.MODEL_RUNS_DIR = old_runs
                runner.RAW_OUTPUTS_DIR = old_raw
                runner.RESPONSES_DIR = old_responses

        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(result["structurally_accepted"], 1)
        self.assertEqual(
            response["response_provenance"]["request_sha256"],
            expected_request_hash,
        )
        self.assertEqual(
            response["response_provenance"]["validation_contract_sha256"],
            engine.validation_contract_sha256(),
        )

    @patch("analysis_model_runner.call_direct_gemini_backup")
    @patch("analysis_model_runner.direct_gemini_available", return_value=True)
    @patch("concept_model_runner.resolve_fair_paths")
    @patch("concept_model_runner.call_fair_bridge")
    def test_all_rejected_batch_is_reported_not_repaired_by_gemini(
        self,
        call_bridge,
        resolve_paths,
        _direct_available,
        call_repair,
    ):
        # D-129: direct Gemini replaces exhausted free capacity only; it never
        # "repairs" output that failed deterministic validation.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request_path = root / "curiosity_gap.concept_request.json"
            request_path.write_text(json.dumps(self.request()), encoding="utf-8")
            resolve_paths.return_value = {
                "repo": root,
                "env_file": root / ".env",
                "python": root / "python.exe",
            }
            invalid = self.valid_concept()
            invalid["research_questions"] = []
            call_bridge.return_value = {
                "status": "ACCEPTED",
                "output": json.dumps({
                    "mechanism_id": "curiosity_gap",
                    "concepts": [invalid],
                }),
                "paid_inference_executed": False,
                "provider_id": "direct_gemini_backup",
                "model_id": "gemini-test",
                "request_id": "req-initial",
                "direct_backup_used": True,
                "direct_backup_free_tier_only": True,
                "direct_backup_may_bill": False,
                "billing_authorization": "USER_APPROVED_DIRECT_GEMINI_BACKUP",
                "attempts": [],
            }
            call_repair.return_value = {
                "status": "ACCEPTED",
                "output": json.dumps({
                    "mechanism_id": "curiosity_gap",
                    "concepts": [self.valid_concept()],
                }),
                "paid_inference_executed": None,
                "provider_id": "direct_gemini_backup",
                "model_id": "gemini-test",
                "request_id": "req-repair",
                "direct_backup_used": True,
                "direct_backup_free_tier_only": True,
                "direct_backup_may_bill": False,
                "billing_authorization": "USER_APPROVED_DIRECT_GEMINI_BACKUP",
                "attempts": [],
            }

            old_runs = runner.MODEL_RUNS_DIR
            old_raw = runner.RAW_OUTPUTS_DIR
            old_responses = runner.RESPONSES_DIR
            try:
                runner.MODEL_RUNS_DIR = root / "runs"
                runner.RAW_OUTPUTS_DIR = root / "raw"
                runner.RESPONSES_DIR = root / "responses"
                result = runner.run_one(
                    request_path,
                    force=True,
                    runner_config=self.runner_config(),
                )
            finally:
                runner.MODEL_RUNS_DIR = old_runs
                runner.RAW_OUTPUTS_DIR = old_raw
                runner.RESPONSES_DIR = old_responses

        self.assertNotEqual(result["status"], "VALIDATED")
        self.assertEqual(result["structurally_accepted"], 0)
        self.assertFalse(result["validation_repair_attempted"])
        self.assertTrue(result["initial_validation_rejection_summary"])
        call_repair.assert_not_called()

    @patch("concept_model_runner.resolve_fair_paths")
    @patch("concept_model_runner.call_fair_bridge")
    def test_old_validation_contract_forces_regeneration(
        self,
        call_bridge,
        resolve_paths,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request_path = root / "curiosity_gap.concept_request.json"
            request_path.write_text(
                json.dumps(self.request()),
                encoding="utf-8",
            )
            request_hash = engine.sha256_file(request_path)
            runs = root / "runs"
            responses = root / "responses"
            raw = root / "raw"
            runs.mkdir()
            responses.mkdir()
            raw.mkdir()
            (runs / "curiosity_gap.model_run.json").write_text(
                json.dumps(
                    {
                        "status": "VALIDATED",
                        "request_sha256": request_hash,
                        "validation_contract_sha256": "old-contract",
                    }
                ),
                encoding="utf-8",
            )
            (responses / "curiosity_gap.json").write_text(
                json.dumps(
                    {
                        "mechanism_id": "curiosity_gap",
                        "concepts": [self.valid_concept()],
                        "response_provenance": {
                            "request_sha256": request_hash,
                            "validation_contract_sha256": "old-contract",
                        },
                    }
                ),
                encoding="utf-8",
            )
            resolve_paths.return_value = {
                "repo": root,
                "env_file": root / ".env",
                "python": root / "python.exe",
            }
            call_bridge.return_value = {
                "status": "ACCEPTED",
                "output": json.dumps(
                    {
                        "mechanism_id": "curiosity_gap",
                        "concepts": [self.valid_concept()],
                    }
                ),
                "paid_inference_executed": False,
                "provider_id": "kilo_free",
                "model_id": "free-model",
                "request_id": "req-regenerated",
                "attempts": [],
            }

            old_runs = runner.MODEL_RUNS_DIR
            old_raw = runner.RAW_OUTPUTS_DIR
            old_responses = runner.RESPONSES_DIR
            try:
                runner.MODEL_RUNS_DIR = runs
                runner.RAW_OUTPUTS_DIR = raw
                runner.RESPONSES_DIR = responses
                result = runner.run_one(
                    request_path,
                    force=False,
                    runner_config=self.runner_config(),
                )
            finally:
                runner.MODEL_RUNS_DIR = old_runs
                runner.RAW_OUTPUTS_DIR = old_raw
                runner.RESPONSES_DIR = old_responses

        self.assertEqual(result["status"], "VALIDATED")
        call_bridge.assert_called_once()

    @patch("concept_model_runner.run_apply")
    @patch("concept_model_runner.run_one")
    def test_merge_ready_overrides_partial_provider_batch(
        self,
        run_one,
        run_apply,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            requests = Path(tmp)
            for index in range(5):
                (requests / f"m{index}.concept_request.json").write_text(
                    json.dumps({"mechanism_id": f"m{index}"}),
                    encoding="utf-8",
                )
            run_one.side_effect = [
                {"status": "VALIDATED", "mechanism_id": f"m{index}"}
                for index in range(4)
            ]
            run_apply.return_value = {
                "status": "CONCEPT_CANDIDATES_READY",
                "accepted_concepts": 4,
            }

            result = runner.run_batch(
                requests,
                force=False,
                maximum_requests=None,
                config=self.runner_config(),
            )

        self.assertEqual(result["status"], "CONCEPT_CANDIDATES_READY")
        self.assertEqual(result["provider_batch_status"], "BATCH_PROGRESS")
        self.assertEqual(result["model_runs_invoked"], 4)
        self.assertEqual(run_one.call_count, 4)

    @patch("concept_model_runner.run_apply")
    @patch("concept_model_runner.run_one")
    def test_clean_batch_limit_still_reports_progress_without_ready_pool(
        self,
        run_one,
        run_apply,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            requests = Path(tmp)
            for index in range(5):
                (requests / f"m{index}.concept_request.json").write_text(
                    json.dumps({"mechanism_id": f"m{index}"}),
                    encoding="utf-8",
                )
            run_one.side_effect = [
                {"status": "VALIDATED", "mechanism_id": f"m{index}"}
                for index in range(4)
            ]
            run_apply.return_value = {
                "status": "INSUFFICIENT_CONCEPT_CANDIDATES",
                "accepted_concepts": 3,
            }

            result = runner.run_batch(
                requests,
                force=False,
                maximum_requests=None,
                config=self.runner_config(),
            )

        self.assertEqual(result["status"], "BATCH_PROGRESS")
        self.assertEqual(result["provider_batch_status"], "BATCH_PROGRESS")

    @patch("concept_model_runner.run_apply")
    @patch("concept_model_runner.run_one")
    def test_mixed_success_and_escalation_reports_batch_progress(
        self,
        run_one,
        run_apply,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            requests = Path(tmp)
            for index in range(5):
                (requests / f"m{index}.concept_request.json").write_text(
                    json.dumps({"mechanism_id": f"m{index}"}),
                    encoding="utf-8",
                )
            run_one.side_effect = [
                {"status": "VALIDATED", "mechanism_id": "m0"},
                {"status": "MODEL_ESCALATION_REQUIRED", "mechanism_id": "m1"},
                {"status": "VALIDATED", "mechanism_id": "m2"},
                {"status": "MODEL_ESCALATION_REQUIRED", "mechanism_id": "m3"},
            ]
            run_apply.return_value = {
                "status": "INSUFFICIENT_CONCEPT_CANDIDATES",
                "accepted_concepts": 2,
            }

            result = runner.run_batch(
                requests,
                force=False,
                maximum_requests=None,
                config=self.runner_config(),
            )

        self.assertEqual(result["status"], "BATCH_PROGRESS")
        self.assertEqual(result["provider_batch_status"], "BATCH_PROGRESS")
        self.assertEqual(result["model_runs_invoked"], 4)
        self.assertEqual(run_one.call_count, 4)

    @patch("concept_model_runner.run_apply")
    @patch("concept_model_runner.run_one")
    def test_cached_successes_do_not_mask_provider_stall(
        self,
        run_one,
        run_apply,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            requests = Path(tmp)
            for index in range(5):
                (requests / f"m{index}.concept_request.json").write_text(
                    json.dumps({"mechanism_id": f"m{index}"}),
                    encoding="utf-8",
                )
            run_one.side_effect = [
                {"status": "SKIPPED_ALREADY_VALIDATED", "mechanism_id": "m0"},
                {"status": "MODEL_ESCALATION_REQUIRED", "mechanism_id": "m1"},
                {"status": "SKIPPED_ALREADY_VALIDATED", "mechanism_id": "m2"},
                {"status": "SKIPPED_ALREADY_VALIDATED", "mechanism_id": "m3"},
                {"status": "SKIPPED_ALREADY_VALIDATED", "mechanism_id": "m4"},
            ]
            run_apply.return_value = {
                "status": "INSUFFICIENT_CONCEPT_CANDIDATES",
                "accepted_concepts": 4,
            }

            result = runner.run_batch(
                requests,
                force=False,
                maximum_requests=None,
                config=self.runner_config(),
            )

        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["provider_batch_status"], "PARTIAL")
        self.assertEqual(result["model_runs_invoked"], 1)
        self.assertEqual(run_one.call_count, 5)

    @patch("concept_model_runner.resolve_fair_paths")
    @patch("concept_model_runner.call_fair_bridge")
    def test_paid_inference_fails_closed(self, call_bridge, resolve_paths):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request_path = root / "curiosity_gap.concept_request.json"
            request_path.write_text(
                json.dumps(self.request()),
                encoding="utf-8",
            )
            resolve_paths.return_value = {
                "repo": root,
                "env_file": root / ".env",
                "python": root / "python.exe",
            }
            call_bridge.return_value = {
                "status": "ACCEPTED",
                "paid_inference_executed": True,
            }

            old_runs = runner.MODEL_RUNS_DIR
            try:
                runner.MODEL_RUNS_DIR = root / "runs"
                result = runner.run_one(
                    request_path,
                    force=True,
                    runner_config=self.runner_config(),
                )
            finally:
                runner.MODEL_RUNS_DIR = old_runs

        self.assertEqual(result["status"], "COST_POLICY_VIOLATION")

    def test_stale_model_response_is_rejected_by_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requests = root / "requests"
            responses = root / "responses"
            requests.mkdir()
            responses.mkdir()

            request_path = requests / "curiosity_gap.concept_request.json"
            request_path.write_text(
                json.dumps(self.request()),
                encoding="utf-8",
            )
            response = {
                "mechanism_id": "curiosity_gap",
                "concepts": [self.valid_concept()],
                "response_provenance": {
                    "request_sha256": "stale",
                },
            }
            (responses / "curiosity_gap.json").write_text(
                json.dumps(response),
                encoding="utf-8",
            )

            old_requests = engine.REQUESTS_DIR
            old_responses = engine.RESPONSES_DIR
            try:
                engine.REQUESTS_DIR = requests
                engine.RESPONSES_DIR = responses
                accepted, rejected = engine.merge_candidate_files()
            finally:
                engine.REQUESTS_DIR = old_requests
                engine.RESPONSES_DIR = old_responses

        self.assertEqual(accepted, [])
        self.assertEqual(len(rejected), 1)
        self.assertIn(
            "provenance",
            rejected[0]["errors"][0],
        )


if __name__ == "__main__":
    unittest.main()
