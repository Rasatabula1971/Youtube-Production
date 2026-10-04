from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import concept_model_runner as runner

import transformation_engine as engine


class ConceptModelRunnerTests(unittest.TestCase):
    def setUp(self):
        # Tests choose their route; the real route file must not leak in.
        route = patch.object(runner, "ROUTE_FILE", Path(tempfile.gettempdir()) / "no-such-concept-route.json")
        route.start()
        self.addCleanup(route.stop)

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

    def test_provider_schema_keeps_field_bounds_but_not_the_concept_count(self):
        authoritative = runner.response_schema(self.request())
        shaped = runner.provider_schema(authoritative)
        self.assertNotIn("maxItems", shaped["properties"]["concepts"])
        self.assertIn("maxItems", authoritative["properties"]["concepts"])
        drama = shaped["properties"]["concepts"]["items"]["properties"]["human_framing"]["properties"]["drama"]["properties"]
        self.assertEqual((drama["hook_level"]["minimum"], drama["hook_level"]["maximum"]), (4, 10))
        moments = shaped["properties"]["concepts"]["items"]["properties"]["human_framing"]["properties"]["visual_opening_plan"]["properties"]["moments"]
        self.assertEqual((moments["minItems"], moments["maxItems"]), (3, 5))
        self.assertEqual(shaped["properties"]["mechanism_id"]["const"], "curiosity_gap")

    def test_prompt_states_the_drama_number_rules(self):
        prompt = runner.build_prompt(self.request(), maximum_chars=95000)
        self.assertIn("target may not exceed capacity", prompt)
        self.assertIn("3 to 5 moments", prompt)

    @patch("concept_model_runner.resolve_fair_paths")
    @patch("concept_model_runner.call_fair_bridge")
    def test_one_bad_concept_no_longer_sinks_the_batch(self, call_bridge, resolve_paths):
        bad = dict(self.valid_concept(), concept_id="bad-1", source_specific_elements_used=["the source's pit-stop clip"])
        extra = [dict(self.valid_concept(), concept_id=f"extra-{n}") for n in range(6)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request = dict(self.request(), concept_count_requested=5)
            request_path = root / "curiosity_gap.concept_request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            resolve_paths.return_value = {"repo": root, "env_file": root / ".env", "python": root / "python.exe"}
            call_bridge.return_value = {
                "status": "ACCEPTED",
                "output": json.dumps({"mechanism_id": "curiosity_gap", "concepts": [bad] + extra}),
                "paid_inference_executed": False, "provider_id": "groq", "model_id": "m", "request_id": "r", "attempts": [],
            }
            with (
                patch.object(runner, "MODEL_RUNS_DIR", root / "runs"),
                patch.object(runner, "RAW_OUTPUTS_DIR", root / "raw"),
                patch.object(runner, "RESPONSES_DIR", root / "responses"),
            ):
                result = runner.run_one(request_path, force=False, runner_config=self.runner_config())
            sent = call_bridge.call_args.args[0]["expected_schema"]
        self.assertNotIn("maxItems", sent["properties"]["concepts"])
        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(result["concepts_beyond_request_dropped"], 2)
        self.assertEqual(result["structurally_rejected"], 1)
        self.assertEqual(result["structurally_accepted"], 4)

    def run_on_route(self, route, *, gemini_available=True, gemini_result=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            route_file = root / "route.json"
            route_file.write_text(json.dumps({"route": route}), encoding="utf-8")
            request_path = root / "curiosity_gap.concept_request.json"
            request_path.write_text(json.dumps(self.request()), encoding="utf-8")
            with (
                patch.object(runner, "ROUTE_FILE", route_file),
                patch.object(runner, "MODEL_RUNS_DIR", root / "runs"),
                patch.object(runner, "RAW_OUTPUTS_DIR", root / "raw"),
                patch.object(runner, "RESPONSES_DIR", root / "responses"),
                patch.object(runner, "resolve_fair_paths", return_value={"repo": root, "env_file": root / ".env", "python": root / "py"}),
                patch.object(runner, "call_fair_bridge") as fair,
                patch.object(runner, "direct_gemini_available", return_value=gemini_available),
                patch.object(runner, "call_direct_gemini_backup", return_value=gemini_result) as gemini,
            ):
                result = runner.run_one(request_path, force=False, runner_config=self.runner_config())
        return result, fair, gemini

    def test_gemini_route_never_calls_fair(self):
        output = json.dumps({"mechanism_id": "curiosity_gap", "concepts": [self.valid_concept()]})
        accepted = {
            "status": "ACCEPTED", "output": output, "provider_id": "direct_gemini_backup", "model_id": "gemini-3.5-flash-lite",
            "paid_inference_executed": None, "direct_backup_used": True, "direct_backup_free_tier_only": True,
            "billing_authorization": "USER_APPROVED_DIRECT_GEMINI_BACKUP", "attempts": [],
        }
        result, fair, gemini = self.run_on_route("direct_gemini", gemini_result=accepted)
        fair.assert_not_called()
        self.assertEqual(gemini.call_args.kwargs["fair_result"]["reason_code"], "GEMINI_ONLY_ROUTE")
        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(result["provider_id"], "direct_gemini_backup")

    def test_gemini_route_without_a_key_stops_instead_of_falling_back(self):
        result, fair, gemini = self.run_on_route("direct_gemini", gemini_available=False)
        fair.assert_not_called()
        gemini.assert_not_called()
        self.assertEqual(result["status"], "MODEL_ESCALATION_REQUIRED")
        self.assertEqual(result["fair_reason_code"], "DIRECT_GEMINI_NOT_CONFIGURED")

    def test_route_defaults_to_fair_and_rejects_unknown_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "none.json"
            with patch.object(runner, "ROUTE_FILE", missing):
                self.assertEqual(runner.concept_route(), "fair")
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps({"route": "openai"}), encoding="utf-8")
            with patch.object(runner, "ROUTE_FILE", bad), self.assertRaisesRegex(ValueError, "route must be one of"):
                runner.concept_route()

    def run_in_calls(self, outputs, *, total=5, per_call=2, pause=0):
        """Run one mechanism with concepts_per_call set; outputs feed each FAIR call in turn."""
        results = []
        for item in outputs:
            if isinstance(item, dict) and "status" in item:
                results.append(item)
            else:
                results.append({
                    "status": "ACCEPTED", "output": json.dumps({"mechanism_id": "curiosity_gap", "concepts": item}),
                    "paid_inference_executed": False, "provider_id": "groq", "model_id": "m", "request_id": "r", "attempts": [],
                })
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            route_file = root / "route.json"
            route_file.write_text(json.dumps({"route": "fair", "concepts_per_call": per_call,
                                              "pause_between_calls_seconds": pause}), encoding="utf-8")
            request_path = root / "curiosity_gap.concept_request.json"
            request_path.write_text(json.dumps(dict(self.request(), concept_count_requested=total)), encoding="utf-8")
            with (
                patch.object(runner, "ROUTE_FILE", route_file),
                patch.object(runner, "MODEL_RUNS_DIR", root / "runs"),
                patch.object(runner, "RAW_OUTPUTS_DIR", root / "raw"),
                patch.object(runner, "RESPONSES_DIR", root / "responses"),
                patch.object(runner, "resolve_fair_paths", return_value={"repo": root, "env_file": root / ".env", "python": root / "py"}),
                patch.object(runner, "call_fair_bridge", side_effect=results) as fair,
                patch.object(runner.time, "sleep") as sleep,
                patch.object(runner, "CALL_CLOCK_FILE", root / "clock.json"),
            ):
                report = runner.run_one(request_path, force=False, runner_config=self.runner_config())
                self.sleeps = [c.args[0] for c in sleep.call_args_list]
                response_file = root / "responses" / "curiosity_gap.json"
                response = json.loads(response_file.read_text()) if response_file.exists() else None
        prompts = [c.args[0]["prompt"] for c in fair.call_args_list]
        schemas = [c.args[0]["expected_schema"] for c in fair.call_args_list]
        return report, response, prompts, schemas

    def concept(self, concept_id, title=None):
        return dict(self.valid_concept(), concept_id=concept_id, working_title=title or f"Title {concept_id}")

    def test_concepts_are_generated_in_small_calls_that_know_earlier_ones(self):
        report, response, prompts, _schemas = self.run_in_calls([
            [self.concept("c1"), self.concept("c2")],
            [self.concept("c1", "A different one"), self.concept("c3")],
            [self.concept("c4")],
        ])
        self.assertEqual(report["status"], "VALIDATED")
        self.assertEqual([c["concepts_requested"] for c in report["calls"]], [2, 2, 1])
        self.assertEqual(report["structurally_accepted"], 5)
        ids = [c["concept_id"] for c in response["concepts"]]
        self.assertEqual(ids, ["c1", "c2", "c1-2", "c3", "c4"])
        self.assertNotIn('"already_generated_concepts"', prompts[0])
        self.assertIn('"already_generated_concepts"', prompts[1])
        self.assertIn("Title c2", prompts[1])
        self.assertEqual(response["response_provenance"]["calls"], 3)

    def test_calls_after_the_first_wait_for_the_rate_limit(self):
        self.run_in_calls([[self.concept("c1"), self.concept("c2")], [self.concept("c3")]], total=3, pause=65)
        self.assertEqual(len(self.sleeps), 1)
        self.assertTrue(60 < self.sleeps[0] <= 65)

    def test_direct_gemini_429_counts_as_rate_limited(self):
        # The direct route reports HTTP_429 rather than FAIR's RATE_LIMITED (audit 2026-10-04).
        result = {"status": "MODEL_ESCALATION_REQUIRED", "attempts": [
            {"error_type": "HTTP_ERROR", "error_detail": "HTTP_429: RESOURCE_EXHAUSTED: quota"}]}
        self.assertTrue(runner._rate_limited(result))
        self.assertFalse(runner._rate_limited({"status": "MODEL_ESCALATION_REQUIRED", "attempts": [
            {"error_type": "HTTP_ERROR", "error_detail": "HTTP_404: not found"}]}))

    def test_a_rate_limited_call_waits_and_retries_once(self):
        limited = {"status": "ESCALATION_REQUIRED", "reason_code": "ALL_FREE_MODELS_FAILED_QUALITY",
                   "paid_inference_executed": False,
                   "attempts": [{"provider_id": "groq", "error_type": "RATE_LIMITED", "disposition": "QUOTA_FAILURE"}]}
        report, response, _prompts, _schemas = self.run_in_calls(
            [limited, [self.concept("c1"), self.concept("c2")], [self.concept("c3")]], total=3, pause=65
        )
        self.assertEqual(report["status"], "VALIDATED")
        self.assertTrue(report["calls"][0]["rate_limited_retry"])
        self.assertEqual(self.sleeps[0], 65)
        self.assertEqual(len(report["calls"]), 2)
        self.assertEqual(len(response["concepts"]), 3)

    def test_a_recent_call_from_another_run_is_waited_for(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock = Path(tmp) / "clock.json"
            clock.write_text(json.dumps({"last_call_at": runner.time.time() - 20}), encoding="utf-8")
            with patch.object(runner, "CALL_CLOCK_FILE", clock), patch.object(runner.time, "sleep") as sleep:
                runner._wait_for_pacing(65)
                runner._wait_for_pacing(0)
        self.assertEqual(sleep.call_count, 1)
        self.assertTrue(40 < sleep.call_args.args[0] <= 45)

    def test_a_failed_later_call_keeps_the_concepts_already_made(self):
        escalated = {"status": "ESCALATION_REQUIRED", "reason_code": "ALL_FREE_MODELS_FAILED_QUALITY",
                     "paid_inference_executed": False, "attempts": []}
        report, response, _prompts, _schemas = self.run_in_calls([[self.concept("c1"), self.concept("c2")], escalated])
        self.assertEqual(report["status"], "VALIDATED")
        self.assertEqual(report["structurally_accepted"], 2)
        self.assertEqual(report["stopped_early"], {"status": "MODEL_ESCALATION_REQUIRED"})
        self.assertEqual(len(response["concepts"]), 2)

    def test_an_incomplete_call_uses_the_spare_call(self):
        broken = dict(self.concept("bad"), source_specific_elements_used=["the source's pit-stop clip"])
        report, _response, _prompts, schemas = self.run_in_calls(
            [[broken, dict(broken, concept_id="extra")], [self.concept("c1")], [self.concept("c2")]], total=2, per_call=1
        )
        self.assertEqual(len(report["calls"]), 3)
        self.assertEqual(report["calls"][0]["status"], "MODEL_OUTPUT_VALIDATION_ERROR")
        self.assertEqual(report["structurally_accepted"], 2)
        self.assertEqual(report["structurally_rejected"], 1)
        self.assertEqual(report["concepts_beyond_request_dropped"], 1)
        self.assertNotIn("maxItems", schemas[0]["properties"]["concepts"])

    def bare(self, concept_id):
        concept = self.concept(concept_id)
        sections = {name: concept.pop(name) for name in ("human_framing", "viewer_need_evidence")}
        return concept, sections

    def completion(self, *pairs):
        return {
            "status": "ACCEPTED",
            "output": json.dumps({"concepts": [{"concept_id": cid, **sections} for cid, sections in pairs]}),
            "paid_inference_executed": False, "provider_id": "groq", "model_id": "m", "request_id": "r", "attempts": [],
        }

    def test_missing_framing_sections_are_completed_by_a_follow_up_call(self):
        first, first_sections = self.bare("s1")
        second, second_sections = self.bare("s2")
        report, response, prompts, schemas = self.run_in_calls(
            [[first, second], self.completion(("s1", first_sections), ("s2", second_sections))], total=2, per_call=1
        )
        call = report["calls"][0]
        self.assertEqual(call["section_completion"]["status"], "COMPLETED")
        self.assertEqual(call["section_completion"]["concepts"], ["s1"])
        self.assertEqual(report["structurally_accepted"], 1)
        self.assertIn("TASK FOR THIS CALL", prompts[1])
        self.assertNotIn('"premise":"', prompts[1].split("CONCEPTS:")[0][-50:])
        items = schemas[1]["properties"]["concepts"]["items"]
        self.assertEqual(items["properties"]["concept_id"]["enum"], ["s1"])
        self.assertEqual(sorted(items["required"]), ["concept_id", "human_framing", "viewer_need_evidence"])
        self.assertIsInstance(response["concepts"][0]["human_framing"], dict)

    def test_a_failed_completion_leaves_the_concept_rejected(self):
        first, _sections = self.bare("s1")
        escalated = {"status": "ESCALATION_REQUIRED", "reason_code": "ALL_FREE_MODELS_FAILED_QUALITY",
                     "paid_inference_executed": False, "attempts": []}
        report, _response, _prompts, _schemas = self.run_in_calls(
            [[first], escalated, [self.concept("c2")], [self.concept("c3")]], total=2, per_call=1
        )
        self.assertEqual(report["calls"][0]["section_completion"]["status"], "NOT_COMPLETED")
        self.assertEqual(report["calls"][0]["status"], "MODEL_OUTPUT_VALIDATION_ERROR")
        self.assertEqual(report["structurally_accepted"], 2)

    def test_a_first_call_failure_writes_no_response(self):
        escalated = {"status": "ESCALATION_REQUIRED", "reason_code": "ALL_FREE_MODELS_FAILED_QUALITY",
                     "paid_inference_executed": False, "attempts": []}
        report, response, _prompts, _schemas = self.run_in_calls([escalated])
        self.assertEqual(report["status"], "MODEL_ESCALATION_REQUIRED")
        self.assertIsNone(response)

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
