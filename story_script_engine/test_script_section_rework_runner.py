import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import script_section_rework_runner as rework_runner
import script_section_state as section_state


class ScriptSectionReworkRunnerTests(unittest.TestCase):
    def script_request(self):
        return {
            "concept_id": "c1",
            "format": "long_form",
            "package": {
                "title": "Why Flexible Parts Can Be Stronger",
                "one_sentence_promise": "Explain the counterintuitive load path.",
                "expected_payoff": "The strange motion becomes mechanically clear.",
            },
            "story_plan": {
                "story_question": "Why can controlled movement make a structure stronger?",
                "opening_hook_intent": "Show movement that looks like failure.",
                "viewer_state": {
                    "awareness": "The viewer sees movement that looks wrong.",
                    "expectation": "Strong parts should stay rigid.",
                    "desired_resolution": "Understand why controlled flex can help.",
                },
                "beats": [
                    {
                        "beat_id": "b1",
                        "role": "SETUP",
                        "purpose": "Establish the puzzle.",
                    },
                    {
                        "beat_id": "b2",
                        "role": "EXPLANATION",
                        "purpose": "Explain the load path.",
                    },
                    {
                        "beat_id": "b3",
                        "role": "PAYOFF",
                        "purpose": "Resolve the apparent contradiction.",
                    },
                ],
                "payoff_intent": "Resolve why controlled movement is useful.",
                "closing_intent": "Leave one clear mental model.",
            },
            "accepted_claims": [
                {
                    "claim_id": "clm001",
                    "statement": "The flexible joint changes how load is distributed.",
                },
                {
                    "claim_id": "clm999",
                    "statement": "An unrelated accepted fact that this target does not use.",
                },
            ],
            "psychology_contract": {
                "opening_line": {"required": True}
            },
            "psychology_profile": {
                "reward_density": "MODERATE",
            },
            "channel_voice": {
                "profile": {
                    "profile_id": "UNCONFIGURED",
                    "version": 0,
                    "status": "UNCONFIGURED",
                },
                "apply_to_generation": False,
            },
        }

    def draft(self, request_path, request_hash):
        return {
            "concept_id": "c1",
            "format": "long_form",
            "opening_hook": "That movement looks like failure, but it is deliberate.",
            "opening_hook_mechanism": "CONTRADICTION",
            "opening_hook_claim_ids": [],
            "sections": [
                {
                    "section_id": "setup_01",
                    "source_story_beat_ids": ["b1"],
                    "purpose": "Establish the puzzle.",
                    "psychology_mechanism": "CURIOSITY",
                    "reward_type": "NONE",
                    "narration": "Watch the joint move before the load settles.",
                    "claim_ids": [],
                },
                {
                    "section_id": "explanation_02",
                    "source_story_beat_ids": ["b2"],
                    "purpose": "Explain the mechanism.",
                    "psychology_mechanism": "CLARITY",
                    "reward_type": "PROGRESS",
                    "narration": "The joint changes how the force travels through the structure.",
                    "claim_ids": ["clm001"],
                },
                {
                    "section_id": "payoff_03",
                    "source_story_beat_ids": ["b3"],
                    "purpose": "Resolve the contradiction.",
                    "psychology_mechanism": "PAYOFF",
                    "reward_type": "PROGRESS",
                    "narration": "So the movement is part of the load path, not evidence that the part is weak.",
                    "claim_ids": ["clm001"],
                },
            ],
            "closing": "The part looks less rigid because the structure is managing force differently.",
            "draft_provenance": {
                "request_source": str(request_path.resolve()),
                "request_sha256": request_hash,
            },
        }

    def setup_rework(self, root):
        script_request_path = root / "c1.long_form.script_request.json"
        script_request_path.write_text(
            json.dumps(self.script_request()),
            encoding="utf-8",
        )
        request_hash = rework_runner.sha256_file(script_request_path)

        draft_path = root / "c1.long_form.script_draft.json"
        draft = self.draft(script_request_path, request_hash)
        draft_path.write_text(json.dumps(draft), encoding="utf-8")

        state_dir = root / "states"
        section_state.prepare_state(draft_path, state_dir=state_dir)
        state_path = section_state.state_path_for(
            "c1",
            "long_form",
            state_dir,
        )
        section_state.apply_target_action(
            state_path,
            draft_path,
            target_id="section:setup_01",
            action="ACCEPT",
            reviewer="r",
        )
        section_state.apply_target_action(
            state_path,
            draft_path,
            target_id="section:explanation_02",
            action="REWORK",
            reviewer="r",
            reason="TOO_TECHNICAL",
            custom_instruction="Make the mechanism visual and easy to picture.",
        )
        review_request_path = root / "c1.long_form.script_review_request.json"
        review_request_path.write_text(
            json.dumps(
                {
                    "concept_id": "c1",
                    "format": "long_form",
                    "request_provenance": {
                        "script_draft": str(draft_path.resolve()),
                        "script_draft_sha256": rework_runner.sha256_file(draft_path),
                    },
                }
            ),
            encoding="utf-8",
        )
        return draft_path, state_path, review_request_path

    def build_request(self, root):
        draft_path, state_path, review_request_path = self.setup_rework(root)
        request = rework_runner.build_rework_request(
            section_state.load_json(state_path),
            state_path,
            rework_runner.load_json(draft_path),
            draft_path,
            target_id="section:explanation_02",
            review_request_path=review_request_path,
        )
        return draft_path, state_path, review_request_path, request

    def response(self):
        return {
            "concept_id": "c1",
            "format": "long_form",
            "target_id": "section:explanation_02",
            "alternatives": [
                {
                    "alternative_id": "A",
                    "replacement_text": "Instead of taking the force in one rigid hit, the joint redirects part of that load as it moves.",
                    "change_summary": "Uses a concrete force-path image with minimal structural change.",
                },
                {
                    "alternative_id": "B",
                    "replacement_text": "Picture the force entering the joint and being guided through a different path as the joint flexes.",
                    "change_summary": "Makes the mechanism more visual and conversational.",
                },
                {
                    "alternative_id": "C",
                    "replacement_text": "The motion is doing work: it changes the route the force takes through the structure.",
                    "change_summary": "Uses a shorter reveal-first explanation.",
                },
            ],
        }

    def test_request_contains_only_selected_target_and_adjacent_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, request = self.build_request(Path(tmp))

        self.assertEqual(
            request["selected_target"]["original_text"],
            "The joint changes how the force travels through the structure.",
        )
        self.assertEqual(
            request["selected_target"]["immutable_metadata"]["section_id"],
            "explanation_02",
        )
        self.assertEqual(
            request["adjacent_context"]["before"]["target_id"],
            "section:setup_01",
        )
        self.assertEqual(
            request["adjacent_context"]["after"]["target_id"],
            "section:payoff_03",
        )
        self.assertIn("section:setup_01", request["locked_target_ids"])
        self.assertNotIn("section:explanation_02", request["locked_target_ids"])


    def test_request_scopes_claims_and_story_context_to_selected_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, request = self.build_request(Path(tmp))

        self.assertEqual(
            [item["claim_id"] for item in request["accepted_claims"]],
            ["clm001"],
        )
        self.assertEqual(
            [item["beat_id"] for item in request["story_constraints"]["relevant_beats"]],
            ["b2"],
        )
        self.assertEqual(
            request["story_constraints"]["story_question"],
            "Why can controlled movement make a structure stronger?",
        )
        self.assertEqual(
            request["psychology_contract"]["opening_line"]["required"],
            True,
        )
        self.assertIn(
            "script_review_request_sha256",
            request["request_provenance"],
        )

    def test_prepared_request_tampering_fails_current_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, _, _, request = self.build_request(root)
            request["selected_target"]["original_text"] = "Tampered prompt text."
            with self.assertRaisesRegex(
                ValueError,
                "prepared request content changed",
            ):
                rework_runner.assert_request_current(request)

    def test_review_request_change_makes_rework_request_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, _, review_request_path, request = self.build_request(root)
            review = json.loads(review_request_path.read_text(encoding="utf-8"))
            review["tampered"] = True
            review_request_path.write_text(json.dumps(review), encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                "Human Script Gate request changed",
            ):
                rework_runner.assert_request_current(request)

    def test_non_rework_target_cannot_generate_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path, state_path, review_request_path = self.setup_rework(root)
            with self.assertRaisesRegex(
                ValueError,
                "not marked REWORK_REQUESTED",
            ):
                rework_runner.build_rework_request(
                    section_state.load_json(state_path),
                    state_path,
                    rework_runner.load_json(draft_path),
                    draft_path,
                    target_id="section:payoff_03",
                    review_request_path=review_request_path,
                )

    def test_prompt_explicitly_forbids_adjacent_rewrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, request = self.build_request(Path(tmp))
            prompt = rework_runner.build_prompt(request, 95000)

        self.assertIn("Rewrite ONLY selected_target.original_text", prompt)
        self.assertIn("adjacent_context is READ-ONLY", prompt)
        self.assertIn("exactly A, B and C", prompt)

    def test_valid_response_requires_distinct_abc_alternatives(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, request = self.build_request(Path(tmp))
            validation = rework_runner.validate_response(
                self.response(),
                request,
            )

        self.assertTrue(validation["valid"], validation["errors"])

    def test_duplicate_or_unchanged_alternatives_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, request = self.build_request(Path(tmp))
            response = self.response()
            response["alternatives"][1]["replacement_text"] = (
                response["alternatives"][0]["replacement_text"]
            )
            response["alternatives"][2]["replacement_text"] = (
                request["selected_target"]["original_text"]
            )
            validation = rework_runner.validate_response(response, request)

        self.assertFalse(validation["valid"])
        self.assertTrue(
            any("duplicates another alternative" in item for item in validation["errors"])
        )
        self.assertTrue(
            any("unchanged from original" in item for item in validation["errors"])
        )

    def test_wrong_alternative_ids_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, request = self.build_request(Path(tmp))
            response = self.response()
            response["alternatives"][2]["alternative_id"] = "D"
            validation = rework_runner.validate_response(response, request)

        self.assertFalse(validation["valid"])
        self.assertIn(
            "alternatives must be exactly A, B, C in order",
            validation["errors"],
        )

    def test_request_becomes_stale_when_review_state_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path, state_path, _, request = self.build_request(root)
            request_path = root / "rework.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")

            section_state.apply_target_action(
                state_path,
                draft_path,
                target_id="section:payoff_03",
                action="LOCK",
                reviewer="r",
            )

            stale = rework_runner.load_json(request_path)
            with self.assertRaisesRegex(
                ValueError,
                "STALE_REWORK_REQUEST: section state changed",
            ):
                rework_runner.assert_request_current(stale)


    def test_state_change_during_fair_discards_returned_alternatives(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path, state_path, _, request = self.build_request(root)
            requests_dir = root / "rework_requests"
            requests_dir.mkdir()
            request_path = requests_dir / "c1.rework.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")

            fake_result = {
                "status": "ACCEPTED",
                "reason_code": "OK",
                "request_id": "req-1",
                "provider_id": "test-provider",
                "model_id": "test-model",
                "paid_inference_executed": False,
                "direct_backup_used": False,
                "direct_backup_may_bill": False,
                "billing_authorization": None,
                "attempts": [],
                "output": json.dumps(self.response()),
            }
            config = {
                "runner": {
                    "max_prompt_chars": 95000,
                    "subprocess_timeout_seconds": 1,
                }
            }

            def mutate_state_then_return(*args, **kwargs):
                section_state.apply_target_action(
                    state_path,
                    draft_path,
                    target_id="section:payoff_03",
                    action="LOCK",
                    reviewer="other-reviewer",
                )
                return fake_result

            alternatives_dir = root / "alternatives"
            with (
                patch.object(
                    rework_runner,
                    "MODEL_RUNS_DIR",
                    root / "model_runs",
                ),
                patch.object(
                    rework_runner,
                    "RAW_OUTPUTS_DIR",
                    root / "raw",
                ),
                patch.object(
                    rework_runner,
                    "REWORK_RESPONSES_DIR",
                    root / "responses",
                ),
                patch.object(
                    rework_runner,
                    "ALTERNATIVES_DIR",
                    alternatives_dir,
                ),
                patch.object(
                    rework_runner,
                    "bridge_payload",
                    return_value={"settings": {}},
                ),
                patch.object(
                    rework_runner,
                    "resolve_fair_paths",
                    return_value={"python": Path(sys.executable)},
                ),
                patch.object(
                    rework_runner,
                    "call_fair_bridge",
                    side_effect=mutate_state_then_return,
                ),
            ):
                result = rework_runner.run_one(
                    request_path,
                    False,
                    config,
                )

        self.assertEqual(result["status"], "STALE_REWORK_REQUEST")
        self.assertFalse(
            list(alternatives_dir.glob("*.alternatives.json"))
        )

    def test_artifact_starts_unselected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, _, _, request = self.build_request(root)
            request_path = root / "rework_request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            validation = rework_runner.validate_response(
                self.response(),
                request,
            )
            artifact = rework_runner.build_alternatives_artifact(
                self.response(),
                request,
                validation,
                request_path=request_path,
                provider_id="test-provider",
                model_id="test-model",
            )

        self.assertEqual(artifact["status"], "ALTERNATIVES_READY")
        self.assertIsNone(artifact["selection"])
        self.assertEqual(
            [item["alternative_id"] for item in artifact["alternatives"]],
            ["A", "B", "C"],
        )

    def test_run_one_writes_alternatives_without_mutating_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path, state_path, _, request = self.build_request(root)
            requests_dir = root / "rework_requests"
            requests_dir.mkdir()
            request_path = requests_dir / "c1.rework.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            before = draft_path.read_bytes()

            fake_result = {
                "status": "ACCEPTED",
                "reason_code": "OK",
                "request_id": "req-1",
                "provider_id": "test-provider",
                "model_id": "test-model",
                "paid_inference_executed": False,
                "direct_backup_used": False,
                "direct_backup_may_bill": False,
                "billing_authorization": None,
                "attempts": [],
                "output": json.dumps(self.response()),
            }
            config = {
                "runner": {
                    "max_prompt_chars": 95000,
                    "subprocess_timeout_seconds": 1,
                }
            }

            with (
                patch.object(
                    rework_runner,
                    "MODEL_RUNS_DIR",
                    root / "model_runs",
                ),
                patch.object(
                    rework_runner,
                    "RAW_OUTPUTS_DIR",
                    root / "raw",
                ),
                patch.object(
                    rework_runner,
                    "REWORK_RESPONSES_DIR",
                    root / "responses",
                ),
                patch.object(
                    rework_runner,
                    "ALTERNATIVES_DIR",
                    root / "alternatives",
                ),
                patch.object(
                    rework_runner,
                    "bridge_payload",
                    return_value={"settings": {}},
                ),
                patch.object(
                    rework_runner,
                    "resolve_fair_paths",
                    return_value={"python": Path(sys.executable)},
                ),
                patch.object(
                    rework_runner,
                    "call_fair_bridge",
                    return_value=fake_result,
                ),
            ):
                result = rework_runner.run_one(
                    request_path,
                    False,
                    config,
                )

            after = draft_path.read_bytes()
            artifact = json.loads(
                Path(result["alternatives"]).read_text(encoding="utf-8")
            )

        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(before, after)
        self.assertIsNone(artifact["selection"])
        self.assertEqual(artifact["target_id"], "section:explanation_02")


if __name__ == "__main__":
    unittest.main()
