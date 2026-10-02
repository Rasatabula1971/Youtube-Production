import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import script_section_apply as section_apply
import script_section_rework_runner as rework_runner
import script_section_state as section_state


class ScriptSectionApplyTests(unittest.TestCase):
    def script_request(self):
        return {
            "artifact": "script_request",
            "concept_id": "c1",
            "format": "long_form",
            "required_branches": ["long_form"],
            "package": {
                "title": "Why Flexible Parts Can Be Stronger",
                "format_intent": "long_form",
                "one_sentence_promise": "Explain the counterintuitive load path.",
                "expected_payoff": "The strange motion becomes mechanically clear.",
            },
            "psychology_contract": {
                "opening_line": {
                    "allowed_mechanisms": ["CONTRADICTION"],
                },
                "beat_mechanisms": [
                    "CURIOSITY",
                    "CLARITY",
                    "PAYOFF",
                ],
            },
            "psychology_profile": {
                "min_sections": 3,
                "max_sections": 8,
                "require_all_story_beats": True,
            },
            "reward_types": [
                "NONE",
                "PROGRESS",
                "PROOF",
                "NOVELTY",
                "REVEAL",
                "EXPECTATION_SHIFT",
                "MICRO_PAYOFF",
            ],
            "story_plan": {
                "viewer_state": {
                    "awareness": "The viewer sees movement that looks wrong.",
                    "expectation": "Strong parts should stay rigid.",
                    "desired_resolution": "Understand why controlled flex can help.",
                },
                "beats": [
                    {
                        "beat_id": "b1",
                        "role": "SETUP",
                        "claim_ids": [],
                    },
                    {
                        "beat_id": "b2",
                        "role": "EXPLANATION",
                        "claim_ids": ["clm001"],
                    },
                    {
                        "beat_id": "b3",
                        "role": "PAYOFF",
                        "claim_ids": ["clm001"],
                    },
                ],
                "payoff_intent": "Resolve why controlled movement is useful.",
                "closing_intent": "Leave one clear mental model.",
            },
            "accepted_claim_ids": ["clm001"],
            "accepted_claims": [
                {
                    "claim_id": "clm001",
                    "statement": "The flexible joint changes how load is distributed.",
                }
            ],
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
            "required_branches": ["long_form"],
            "title": "Why Flexible Parts Can Be Stronger",
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
            "package": self.script_request()["package"],
            "story_plan": self.script_request()["story_plan"],
            "psychology_contract": self.script_request()["psychology_contract"],
            "psychology_profile": self.script_request()["psychology_profile"],
            "channel_voice": self.script_request()["channel_voice"],
            "accepted_claims": self.script_request()["accepted_claims"],
            "validation": {
                "valid": True,
                "source_overlap": {"blocking": False},
            },
            "draft_provenance": {
                "request_source": str(request_path.resolve()),
                "request_sha256": request_hash,
                "validation_contract_sha256": "test-contract",
            },
        }

    def alternatives_response(self):
        return {
            "concept_id": "c1",
            "format": "long_form",
            "target_id": "section:explanation_02",
            "alternatives": [
                {
                    "alternative_id": "A",
                    "replacement_text": "Instead of taking the force in one rigid hit, the joint redirects part of that load as it moves.",
                    "change_summary": "A concrete, surgical force-path explanation.",
                    "claim_ids_used": ["clm001"],
                },
                {
                    "alternative_id": "B",
                    "replacement_text": "Picture the force entering the joint and being guided through a different path as the joint flexes.",
                    "change_summary": "A more visual and conversational explanation.",
                    "claim_ids_used": ["clm001"],
                },
                {
                    "alternative_id": "C",
                    "replacement_text": "The motion is doing work: it changes the route the force takes through the structure.",
                    "change_summary": "A shorter reveal-first explanation.",
                    "claim_ids_used": ["clm001"],
                },
            ],
        }

    def setup_artifacts(self, root):
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
            target_id="section:payoff_03",
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
            custom_instruction="Make the mechanism visual.",
        )

        review_requests_dir = root / "review_requests"
        review_requests_dir.mkdir()
        review_request_path = (
            review_requests_dir
            / "c1.long_form.script_review_request.json"
        )
        review_request_path.write_text(
            json.dumps(
                {
                    "concept_id": "c1",
                    "format": "long_form",
                    "request_provenance": {
                        "script_draft": str(draft_path.resolve()),
                        "script_draft_sha256": rework_runner.sha256_file(
                            draft_path
                        ),
                    },
                }
            ),
            encoding="utf-8",
        )

        requests_dir = root / "section_rework_requests"
        rework_request_path = rework_runner.prepare_rework_request(
            state_path,
            draft_path,
            target_id="section:explanation_02",
            requests_dir=requests_dir,
            review_requests_dir=review_requests_dir,
        )
        rework_request = rework_runner.load_json(rework_request_path)
        response = self.alternatives_response()
        validation = rework_runner.validate_response(
            response,
            rework_request,
        )
        self.assertTrue(validation["valid"], validation["errors"])

        response_path = root / "c1.long_form.section_rework_response.json"
        response_path.write_text(
            json.dumps(response),
            encoding="utf-8",
        )

        alternatives_dir = root / "alternatives"
        alternatives_dir.mkdir()
        alternatives_path = alternatives_dir / "c1.long_form.explanation.alternatives.json"
        artifact = rework_runner.build_alternatives_artifact(
            response,
            rework_request,
            validation,
            request_path=rework_request_path,
            provider_id="test-provider",
            model_id="test-model",
            response_path=response_path,
        )
        alternatives_path.write_text(
            json.dumps(artifact),
            encoding="utf-8",
        )

        return {
            "draft": draft_path,
            "state": state_path,
            "alternatives": alternatives_path,
            "rework_request": rework_request_path,
        }

    def target(self, state, target_id):
        return next(
            item
            for item in state["targets"]
            if item["target_id"] == target_id
        )

    def apply_dirs(self, root):
        review_requests = root / "review_requests"
        review_responses = root / "review_responses"
        approved = root / "approved"
        versions = root / "versions"
        transactions = root / "transactions"
        for path in (
            review_requests,
            review_responses,
            approved,
            versions,
            transactions,
        ):
            path.mkdir(exist_ok=True)
        return {
            "review_requests_dir": review_requests,
            "review_responses_dir": review_responses,
            "approved_dir": approved,
            "versions_dir": versions,
            "transactions_dir": transactions,
        }

    def test_select_a_changes_only_selected_target_and_versions_previous_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.setup_artifacts(root)
            dirs = self.apply_dirs(root)

            old_draft = rework_runner.load_json(paths["draft"])
            old_state = section_state.load_json(paths["state"])
            old_setup = copy.deepcopy(old_draft["sections"][0])
            old_payoff = copy.deepcopy(old_draft["sections"][2])
            old_hook = old_draft["opening_hook"]
            old_closing = old_draft["closing"]

            response_file = (
                dirs["review_responses_dir"]
                / "c1.long_form.script_review_response.json"
            )
            response_file.write_text("{}", encoding="utf-8")
            approved_file = dirs["approved_dir"] / "c1.approved_script.json"
            approved_file.write_text("{}", encoding="utf-8")

            result = section_apply.apply_selection(
                paths["alternatives"],
                selection_id="A",
                reviewer="ricky",
                **dirs,
            )

            revised = rework_runner.load_json(paths["draft"])
            state = section_state.load_json(paths["state"])
            artifact = rework_runner.load_json(paths["alternatives"])

            self.assertEqual(result["status"], "ALTERNATIVE_SELECTED")
            self.assertEqual(result["revision"], 1)
            self.assertEqual(revised["opening_hook"], old_hook)
            self.assertEqual(revised["closing"], old_closing)
            self.assertEqual(revised["sections"][0], old_setup)
            self.assertEqual(revised["sections"][2], old_payoff)
            self.assertEqual(
                revised["sections"][1]["narration"],
                self.alternatives_response()["alternatives"][0][
                    "replacement_text"
                ],
            )
            self.assertEqual(
                {
                    key: value
                    for key, value in revised["sections"][1].items()
                    if key != "narration"
                },
                {
                    key: value
                    for key, value in old_draft["sections"][1].items()
                    if key != "narration"
                },
            )

            selected_state = self.target(
                state,
                "section:explanation_02",
            )
            self.assertEqual(selected_state["decision"], "ACCEPTED")
            self.assertTrue(selected_state["locked"])
            self.assertTrue(
                self.target(state, "section:setup_01")["locked"]
            )
            self.assertTrue(
                self.target(state, "section:payoff_03")["locked"]
            )

            version_path = (
                dirs["versions_dir"]
                / "c1.long_form"
                / "revision_0000.script_draft.json"
            )
            self.assertTrue(version_path.exists())
            self.assertEqual(
                rework_runner.load_json(version_path),
                old_draft,
            )

            self.assertEqual(
                artifact["selection"]["selection_id"],
                "A",
            )
            self.assertEqual(
                artifact["status"],
                "ALTERNATIVE_SELECTED",
            )
            self.assertFalse(response_file.exists())
            self.assertFalse(approved_file.exists())

            refreshed_request = (
                dirs["review_requests_dir"]
                / "c1.long_form.script_review_request.json"
            )
            self.assertTrue(refreshed_request.exists())
            refreshed = rework_runner.load_json(refreshed_request)
            self.assertEqual(
                refreshed["request_provenance"]["script_draft_sha256"],
                rework_runner.sha256_file(paths["draft"]),
            )

            self.assertNotEqual(
                self.target(old_state, "section:explanation_02")[
                    "target_sha256"
                ],
                selected_state["target_sha256"],
            )

    def test_select_original_keeps_draft_exact_and_accepts_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.setup_artifacts(root)
            dirs = self.apply_dirs(root)
            before = paths["draft"].read_bytes()

            result = section_apply.apply_selection(
                paths["alternatives"],
                selection_id="ORIGINAL",
                reviewer="ricky",
                **dirs,
            )

            after = paths["draft"].read_bytes()
            state = section_state.load_json(paths["state"])
            artifact = rework_runner.load_json(paths["alternatives"])

        self.assertEqual(before, after)
        self.assertEqual(result["status"], "ORIGINAL_SELECTED")
        self.assertEqual(result["revision"], 0)
        selected = self.target(state, "section:explanation_02")
        self.assertEqual(selected["decision"], "ACCEPTED")
        self.assertTrue(selected["locked"])
        self.assertEqual(
            artifact["selection"]["selection_id"],
            "ORIGINAL",
        )

    def test_alternative_cannot_be_selected_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.setup_artifacts(root)
            dirs = self.apply_dirs(root)
            section_apply.apply_selection(
                paths["alternatives"],
                selection_id="A",
                reviewer="r",
                **dirs,
            )

            with self.assertRaisesRegex(
                ValueError,
                "already been selected",
            ):
                section_apply.apply_selection(
                    paths["alternatives"],
                    selection_id="B",
                    reviewer="r",
                    **dirs,
                )

    def test_tampered_alternatives_fail_before_draft_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.setup_artifacts(root)
            dirs = self.apply_dirs(root)
            before = paths["draft"].read_bytes()

            artifact = rework_runner.load_json(paths["alternatives"])
            artifact["alternatives"][1]["replacement_text"] = (
                artifact["alternatives"][0]["replacement_text"]
            )
            paths["alternatives"].write_text(
                json.dumps(artifact),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "integrity check failed",
            ):
                section_apply.apply_selection(
                    paths["alternatives"],
                    selection_id="A",
                    reviewer="r",
                    **dirs,
                )

            self.assertEqual(before, paths["draft"].read_bytes())

    def test_stale_section_state_blocks_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.setup_artifacts(root)
            dirs = self.apply_dirs(root)
            section_state.apply_target_action(
                paths["state"],
                paths["draft"],
                target_id="closing:closing",
                action="LOCK",
                reviewer="r",
            )

            with self.assertRaisesRegex(
                ValueError,
                "STALE_REWORK_REQUEST: section state changed",
            ):
                section_apply.apply_selection(
                    paths["alternatives"],
                    selection_id="A",
                    reviewer="r",
                    **dirs,
                )

    def test_failure_rolls_back_draft_state_and_alternatives(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.setup_artifacts(root)
            dirs = self.apply_dirs(root)
            old_draft = rework_runner.load_json(paths["draft"])
            old_state = section_state.load_json(paths["state"])
            old_artifact = rework_runner.load_json(paths["alternatives"])

            with (
                patch.object(
                    section_apply,
                    "_invalidate_and_refresh_script_gate",
                    side_effect=RuntimeError("simulated interruption"),
                ),
                self.assertRaisesRegex(
                    RuntimeError,
                    "simulated interruption",
                ),
            ):
                section_apply.apply_selection(
                    paths["alternatives"],
                    selection_id="A",
                    reviewer="r",
                    **dirs,
                )

            self.assertEqual(
                rework_runner.load_json(paths["draft"]),
                old_draft,
            )
            self.assertEqual(
                section_state.load_json(paths["state"]),
                old_state,
            )
            self.assertEqual(
                rework_runner.load_json(paths["alternatives"]),
                old_artifact,
            )
            transactions = list(
                dirs["transactions_dir"].glob(
                    "*.selection_transaction.json"
                )
            )
            self.assertEqual(len(transactions), 1)
            transaction = rework_runner.load_json(transactions[0])
            self.assertEqual(transaction["status"], "ROLLED_BACK")


    def test_manual_edit_changes_only_selected_target_and_saves_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.setup_artifacts(root)
            dirs = self.apply_dirs(root)
            old_draft = rework_runner.load_json(paths["draft"])
            old_state = section_state.load_json(paths["state"])
            response_file = (
                dirs["review_responses_dir"]
                / "c1.long_form.script_review_response.json"
            )
            approved_file = dirs["approved_dir"] / "c1.approved_script.json"
            response_file.write_text("{}", encoding="utf-8")
            approved_file.write_text("{}", encoding="utf-8")

            replacement = (
                "Picture the force entering the joint, then changing route "
                "as the joint moves."
            )
            result = section_apply.apply_manual_edit(
                paths["draft"],
                paths["state"],
                target_id="section:explanation_02",
                replacement_text=replacement,
                reviewer="ricky",
                **dirs,
            )

            revised = rework_runner.load_json(paths["draft"])
            state = section_state.load_json(paths["state"])
            version_path = (
                dirs["versions_dir"]
                / "c1.long_form"
                / "revision_0000.script_draft.json"
            )
            refreshed_request = (
                dirs["review_requests_dir"]
                / "c1.long_form.script_review_request.json"
            )

            self.assertEqual(result["status"], "MANUAL_EDIT_APPLIED")
            self.assertEqual(result["revision"], 1)
            self.assertEqual(revised["sections"][1]["narration"], replacement)
            self.assertEqual(revised["sections"][0], old_draft["sections"][0])
            self.assertEqual(revised["sections"][2], old_draft["sections"][2])
            self.assertEqual(revised["opening_hook"], old_draft["opening_hook"])
            self.assertEqual(revised["closing"], old_draft["closing"])
            self.assertEqual(
                {
                    key: value
                    for key, value in revised["sections"][1].items()
                    if key != "narration"
                },
                {
                    key: value
                    for key, value in old_draft["sections"][1].items()
                    if key != "narration"
                },
            )
            self.assertEqual(
                revised["human_revision"]["edit_type"],
                "MANUAL_TARGET_EDIT",
            )
            self.assertEqual(
                revised["human_revision"]["edited_target_id"],
                "section:explanation_02",
            )

            selected = self.target(state, "section:explanation_02")
            self.assertEqual(selected["decision"], "ACCEPTED")
            self.assertTrue(selected["locked"])
            self.assertEqual(state["history"][-1]["action"], "MANUAL_EDIT")
            self.assertTrue(self.target(state, "section:setup_01")["locked"])
            self.assertTrue(self.target(state, "section:payoff_03")["locked"])
            self.assertNotEqual(
                self.target(old_state, "section:explanation_02")["target_sha256"],
                selected["target_sha256"],
            )

            self.assertTrue(version_path.exists())
            self.assertEqual(rework_runner.load_json(version_path), old_draft)
            self.assertFalse(response_file.exists())
            self.assertFalse(approved_file.exists())
            self.assertTrue(refreshed_request.exists())
            refreshed = rework_runner.load_json(refreshed_request)
            self.assertEqual(
                refreshed["request_provenance"]["script_draft_sha256"],
                rework_runner.sha256_file(paths["draft"]),
            )

    def test_manual_edit_rejects_locked_target_until_unlocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.setup_artifacts(root)
            dirs = self.apply_dirs(root)
            before = paths["draft"].read_bytes()

            with self.assertRaisesRegex(
                ValueError,
                "Locked target cannot be manually edited until unlocked",
            ):
                section_apply.apply_manual_edit(
                    paths["draft"],
                    paths["state"],
                    target_id="section:setup_01",
                    replacement_text="A different setup line.",
                    reviewer="r",
                    **dirs,
                )

            self.assertEqual(before, paths["draft"].read_bytes())

    def test_manual_edit_rejects_empty_or_unchanged_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.setup_artifacts(root)
            dirs = self.apply_dirs(root)
            original = rework_runner.load_json(paths["draft"])[
                "sections"
            ][1]["narration"]

            with self.assertRaisesRegex(
                ValueError,
                "non-empty replacement_text",
            ):
                section_apply.apply_manual_edit(
                    paths["draft"],
                    paths["state"],
                    target_id="section:explanation_02",
                    replacement_text="   ",
                    reviewer="r",
                    **dirs,
                )

            with self.assertRaisesRegex(
                ValueError,
                "must change the selected target text",
            ):
                section_apply.apply_manual_edit(
                    paths["draft"],
                    paths["state"],
                    target_id="section:explanation_02",
                    replacement_text="  " + original + "  ",
                    reviewer="r",
                    **dirs,
                )

    def test_manual_edit_runs_full_script_validator_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.setup_artifacts(root)
            dirs = self.apply_dirs(root)
            before = paths["draft"].read_bytes()

            with (
                patch.object(
                    section_apply,
                    "validate_script_response",
                    return_value={
                        "valid": False,
                        "errors": ["forced validation failure"],
                    },
                ) as validator,
                self.assertRaisesRegex(
                    ValueError,
                    "Manual edit fails full script validation",
                ),
            ):
                section_apply.apply_manual_edit(
                    paths["draft"],
                    paths["state"],
                    target_id="section:explanation_02",
                    replacement_text="A valid-looking but forced-fail edit.",
                    reviewer="r",
                    **dirs,
                )

            self.assertTrue(validator.called)
            self.assertEqual(before, paths["draft"].read_bytes())

    def test_manual_edit_failure_rolls_back_draft_and_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.setup_artifacts(root)
            dirs = self.apply_dirs(root)
            old_draft = rework_runner.load_json(paths["draft"])
            old_state = section_state.load_json(paths["state"])

            with (
                patch.object(
                    section_apply,
                    "_invalidate_and_refresh_script_gate",
                    side_effect=RuntimeError("simulated manual interruption"),
                ),
                self.assertRaisesRegex(
                    RuntimeError,
                    "simulated manual interruption",
                ),
            ):
                section_apply.apply_manual_edit(
                    paths["draft"],
                    paths["state"],
                    target_id="section:explanation_02",
                    replacement_text=(
                        "The joint visibly redirects the force as it moves."
                    ),
                    reviewer="r",
                    **dirs,
                )

            self.assertEqual(
                rework_runner.load_json(paths["draft"]),
                old_draft,
            )
            self.assertEqual(
                section_state.load_json(paths["state"]),
                old_state,
            )
            transactions = list(
                dirs["transactions_dir"].glob(
                    "*.manual_edit_transaction.json"
                )
            )
            self.assertEqual(len(transactions), 1)
            transaction = rework_runner.load_json(transactions[0])
            self.assertEqual(transaction["status"], "ROLLED_BACK")



if __name__ == "__main__":
    unittest.main()
