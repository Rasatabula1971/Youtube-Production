import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import format_engine as module

from format_engine import (
    build_format_request,
    load_config,
    resolve_branches,
    validate_format_response,
)


class FormatEngineTests(unittest.TestCase):
    def config(self):
        return load_config()

    def branch_script(self, fmt):
        sections = (
            [
                {
                    "section_id": "lf1",
                    "purpose": "Setup",
                    "narration": "Long setup explains the context.",
                    "claim_ids": [],
                },
                {
                    "section_id": "lf2",
                    "purpose": "Explain",
                    "narration": "Heat changes braking behavior.",
                    "claim_ids": ["clm001"],
                },
                {
                    "section_id": "lf3",
                    "purpose": "Payoff",
                    "narration": "The full tradeoff now makes sense.",
                    "claim_ids": ["clm001"],
                },
            ]
            if fmt == "long_form"
            else [
                {
                    "section_id": "sh1",
                    "purpose": "Hook proof",
                    "narration": "Cold race brakes can feel worse.",
                    "claim_ids": ["clm001"],
                },
                {
                    "section_id": "sh2",
                    "purpose": "Reveal",
                    "narration": "Heat is part of the target.",
                    "claim_ids": ["clm001"],
                },
                {
                    "section_id": "sh3",
                    "purpose": "Payoff",
                    "narration": "That is why the design looks backwards.",
                    "claim_ids": ["clm001"],
                },
            ]
        )
        return {
            "format": fmt,
            "title": "Why Racing Brakes Work Backwards",
            "opening_hook": f"{fmt} hook",
            "opening_hook_mechanism": "CONTRADICTION",
            "sections": sections,
            "closing": f"{fmt} close",
            "psychology_profile": {
                "reward_density": "HIGH" if fmt == "short" else "MODERATE"
            },
        }

    def script(self, format_intent="either"):
        required = resolve_branches(format_intent, self.config())
        return {
            "artifact": "approved_script_bundle",
            "status": "READY_FOR_PRODUCTION",
            "concept_id": "c1",
            "title": "Why Racing Brakes Work Backwards",
            "package": {
                "title": "Why Racing Brakes Work Backwards",
                "one_sentence_promise": "Explain the counterintuitive behavior",
                "expected_payoff": "A clear explanation",
                "format_intent": format_intent,
            },
            "accepted_claims": [
                {
                    "claim_id": "clm001",
                    "statement": "Heat changes braking behavior.",
                    "role": "core",
                }
            ],
            "required_branches": required,
            "branch_scripts": {
                fmt: self.branch_script(fmt)
                for fmt in required
            },
            "script_gate": {
                "status": "READY_FOR_PRODUCTION",
                "accepted_formats": required,
            },
            "approved_provenance": {
                fmt: {
                    "section_review_prepared": False,
                    "section_state": None,
                    "section_state_sha256": None,
                    "section_state_version": None,
                    "section_target_count": 0,
                    "section_targets": [],
                }
                for fmt in required
            },
        }

    def request(self, format_intent="either"):
        script = self.script(format_intent)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "script.json"
            path.write_text(json.dumps(script), encoding="utf-8")
            return build_format_request(script, path, self.config())

    def beat(self, beat_id, purpose, treatment, section_id, claim_ids=("clm001",)):
        key = purpose.lower()
        drama = 7 if "hook" in key or "cold" in key else 8 if "reveal" in key else 6 if "payoff" in key or "close" in key else 5
        tempo = 7 if "hook" in key or "cold" in key else 6 if "reveal" in key else 4 if "payoff" in key or "close" in key else 5
        return {
            "beat_id": beat_id,
            "purpose": purpose,
            "treatment": treatment,
            "drama_level": drama,
            "tempo_level": tempo,
            "claim_ids": list(claim_ids),
            "source_section_ids": [section_id],
        }

    def long_form_branch(self):
        return {
            "format": "long_form",
            "duration_intent_seconds": 600,
            "promise_delivery": "Full explanation of the braking system",
            "payoff": "Viewer understands the whole mechanism",
            "beats": [
                self.beat("lfb1", "hook", "Open on the failed corner", "lf1", ()),
                self.beat("lfb2", "context", "Lay out the mechanism", "lf2"),
                self.beat("lfb3", "reveal", "Show where heat changes behavior", "lf2"),
                self.beat("lfb4", "payoff", "Tie it back to the tradeoff", "lf3"),
            ],
        }

    def short_branch(self):
        return {
            "format": "short",
            "duration_intent_seconds": 45,
            "promise_delivery": "One counterintuitive fact, delivered fast",
            "payoff": "Viewer leaves with the single surprising mechanism",
            "beats": [
                self.beat("shb1", "cold open", "State the claim first", "sh1"),
                self.beat("shb2", "proof", "Show the heat effect", "sh2"),
                self.beat("shb3", "close", "Pay off the contradiction", "sh3"),
            ],
        }

    def test_either_intent_carries_two_approved_script_branches(self):
        request = self.request("either")
        self.assertEqual(request["required_branches"], ["long_form", "short"])
        self.assertEqual(
            sorted(request["branch_story_packages"]),
            ["long_form", "short"],
        )
        self.assertEqual(
            request["script_section_ids_by_branch"]["short"],
            ["sh1", "sh2", "sh3"],
        )

    def test_single_intent_requires_one_branch(self):
        self.assertEqual(self.request("short")["required_branches"], ["short"])
        self.assertEqual(self.request("long_form")["required_branches"], ["long_form"])

    def test_unknown_format_intent_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_branches("vertical_reel", self.config())

    def test_bundle_branch_set_must_match_format_intent(self):
        script = self.script("either")
        script["required_branches"] = ["short"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "script.json"
            path.write_text(json.dumps(script), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "branches do not match"):
                build_format_request(script, path, self.config())

    def test_script_not_approved_is_rejected(self):
        script = self.script()
        script["script_gate"] = {"status": "SCRIPT_REWORK_REQUIRED"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "script.json"
            path.write_text(json.dumps(script), encoding="utf-8")
            with self.assertRaises(ValueError):
                build_format_request(script, path, self.config())


    def test_prepared_section_review_provenance_is_verified_and_carried_forward(self):
        script = self.script("short")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drafts = root / "script_drafts"
            states = root / "script_section_states"
            drafts.mkdir()
            states.mkdir()

            draft_path = drafts / "c1.short.script_draft.json"
            draft_path.write_text(
                json.dumps({"concept_id": "c1", "format": "short"}),
                encoding="utf-8",
            )
            state_path = states / "c1.short.section_state.json"
            targets = [
                {
                    "target_id": "hook:opening",
                    "target_sha256": "h1",
                    "ordinal": 0,
                    "decision": "ACCEPTED",
                    "locked": True,
                },
                {
                    "target_id": "section:sh1",
                    "target_sha256": "h2",
                    "ordinal": 1,
                    "decision": "ACCEPTED",
                    "locked": True,
                },
            ]
            state = {
                "concept_id": "c1",
                "format": "short",
                "source_draft": str(draft_path.resolve()),
                "source_draft_sha256": module.sha256_file(draft_path),
                "state_version": 4,
                "targets": targets,
            }
            state_path.write_text(json.dumps(state), encoding="utf-8")
            script["approved_provenance"]["short"] = {
                "section_review_prepared": True,
                "section_state": str(state_path.resolve()),
                "section_state_sha256": module.sha256_file(state_path),
                "section_state_version": 4,
                "section_target_count": 2,
                "section_targets": [
                    {
                        "target_id": "hook:opening",
                        "target_sha256": "h1",
                    },
                    {
                        "target_id": "section:sh1",
                        "target_sha256": "h2",
                    },
                ],
            }
            script_path = root / "approved.json"
            script_path.write_text(json.dumps(script), encoding="utf-8")

            with (
                patch.object(module, "SCRIPT_DRAFTS_DIR", drafts),
                patch.object(module, "SCRIPT_SECTION_STATE_DIR", states),
            ):
                request = build_format_request(
                    script,
                    script_path,
                    self.config(),
                )

        section = request["request_provenance"]["section_review"]["short"]
        self.assertTrue(section["prepared"])
        self.assertEqual(section["state_version"], 4)
        self.assertEqual(section["target_count"], 2)

    def test_changed_prepared_section_state_blocks_format_handoff(self):
        script = self.script("short")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drafts = root / "script_drafts"
            states = root / "script_section_states"
            drafts.mkdir()
            states.mkdir()

            draft_path = drafts / "c1.short.script_draft.json"
            draft_path.write_text(
                json.dumps({"concept_id": "c1", "format": "short"}),
                encoding="utf-8",
            )
            state_path = states / "c1.short.section_state.json"
            state = {
                "concept_id": "c1",
                "format": "short",
                "source_draft": str(draft_path.resolve()),
                "source_draft_sha256": module.sha256_file(draft_path),
                "state_version": 2,
                "targets": [
                    {
                        "target_id": "hook:opening",
                        "target_sha256": "h1",
                        "ordinal": 0,
                        "decision": "ACCEPTED",
                        "locked": True,
                    }
                ],
            }
            state_path.write_text(json.dumps(state), encoding="utf-8")
            bound_hash = module.sha256_file(state_path)
            script["approved_provenance"]["short"] = {
                "section_review_prepared": True,
                "section_state": str(state_path.resolve()),
                "section_state_sha256": bound_hash,
                "section_state_version": 2,
                "section_target_count": 1,
                "section_targets": [
                    {
                        "target_id": "hook:opening",
                        "target_sha256": "h1",
                    }
                ],
            }
            state["state_version"] = 3
            state_path.write_text(json.dumps(state), encoding="utf-8")
            script_path = root / "approved.json"
            script_path.write_text(json.dumps(script), encoding="utf-8")

            with (
                patch.object(module, "SCRIPT_DRAFTS_DIR", drafts),
                patch.object(module, "SCRIPT_SECTION_STATE_DIR", states),
                self.assertRaisesRegex(
                    ValueError,
                    "section-state provenance is stale",
                ),
            ):
                build_format_request(
                    script,
                    script_path,
                    self.config(),
                )

    def test_separate_branches_pass(self):
        request = self.request("either")
        response = {
            "concept_id": "c1",
            "branches": [self.long_form_branch(), self.short_branch()],
        }
        result = validate_format_response(response, request)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["claim_usage"], ["clm001"])
        self.assertFalse(result["branch_separation"]["identical"])

    def test_branch_cannot_reference_other_formats_script_sections(self):
        request = self.request("either")
        short = self.short_branch()
        short["beats"][0]["source_section_ids"] = ["lf1"]
        result = validate_format_response(
            {
                "concept_id": "c1",
                "branches": [self.long_form_branch(), short],
            },
            request,
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("unknown script section lf1" in e for e in result["errors"]))

    def test_identical_production_branches_are_rejected(self):
        request = self.request("either")
        long_form = self.long_form_branch()
        short = self.short_branch()
        short["beats"] = [
            {
                **dict(beat),
                "source_section_ids": ["sh1"],
            }
            for beat in long_form["beats"]
        ]
        result = validate_format_response(
            {"concept_id": "c1", "branches": [long_form, short]},
            request,
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("identical edits" in e for e in result["errors"]))

    def test_missing_required_branch_is_rejected(self):
        request = self.request("either")
        result = validate_format_response(
            {"concept_id": "c1", "branches": [self.long_form_branch()]},
            request,
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("missing required branch: short" in e for e in result["errors"]))

    def test_duration_outside_branch_constraints_is_rejected(self):
        request = self.request("short")
        branch = self.short_branch()
        branch["duration_intent_seconds"] = 600
        result = validate_format_response(
            {"concept_id": "c1", "branches": [branch]},
            request,
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("above maximum" in e for e in result["errors"]))

    def test_slug_collision_is_rejected_before_format_request_writes(self):
        with self.assertRaisesRegex(ValueError, "collide"):
            module.assert_unique_slug_ids(
                ["gear/ratio", "gear ratio"],
                label="concept",
            )



    def test_changed_script_handoff_prunes_all_stale_format_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approved_scripts = root / "approved_scripts"
            requests = root / "format_requests"
            responses = root / "format_responses"
            plans = root / "format_plans"
            model_runs = root / "format_model_runs"
            raw = root / "raw_format_outputs"
            review_requests = root / "format_review_requests"
            review_responses = root / "format_review_responses"
            approved_plans = root / "approved_format_plans"
            for directory in (
                approved_scripts,
                requests,
                responses,
                plans,
                model_runs,
                raw,
                review_requests,
                review_responses,
                approved_plans,
            ):
                directory.mkdir()

            approved_path = approved_scripts / "c1.approved_script.json"
            approved_path.write_text(
                json.dumps(self.script("short")),
                encoding="utf-8",
            )
            (requests / "c1.format_request.json").write_text(
                json.dumps({"concept_id": "c1", "old": True}),
                encoding="utf-8",
            )

            stale_paths = [
                responses / "c1.json",
                plans / "c1.format_plan.json",
                model_runs / "c1.model_run.json",
                raw / "c1.txt",
                review_requests / "c1.format_review_request.json",
                review_responses / "c1.format_review_response.json",
                approved_plans / "c1.approved_format_plan.json",
            ]
            for path in stale_paths:
                path.write_text("old", encoding="utf-8")

            model_summary = root / "format_model_batch_summary.json"
            gate_summary = root / "format_gate_summary.json"
            model_summary.write_text("old", encoding="utf-8")
            gate_summary.write_text("old", encoding="utf-8")

            with (
                patch.object(module, "REQUESTS_DIR", requests),
                patch.object(module, "RESPONSES_DIR", responses),
                patch.object(module, "PLANS_DIR", plans),
                patch.object(module, "MODEL_RUNS_DIR", model_runs),
                patch.object(module, "RAW_OUTPUTS_DIR", raw),
                patch.object(module, "FORMAT_REVIEW_REQUESTS_DIR", review_requests),
                patch.object(module, "FORMAT_REVIEW_RESPONSES_DIR", review_responses),
                patch.object(module, "APPROVED_FORMAT_PLANS_DIR", approved_plans),
                patch.object(module, "MODEL_BATCH_SUMMARY_FILE", model_summary),
                patch.object(module, "FORMAT_GATE_SUMMARY_FILE", gate_summary),
                patch.object(module, "OUTPUT_DIR", root),
                patch.object(module, "SUMMARY_FILE", root / "summary.json"),
            ):
                summary = module.run_prepare(
                    approved_scripts,
                    self.config(),
                )

            new_request = requests / "c1.format_request.json"
            request_payload = json.loads(
                new_request.read_text(encoding="utf-8")
            )
            new_request_exists = new_request.exists()
            stale_exists = [path.exists() for path in stale_paths]
            model_summary_exists = model_summary.exists()
            gate_summary_exists = gate_summary.exists()

        self.assertEqual(summary["prepared"], 1)
        self.assertEqual(
            summary["stale_cleanup"]["invalidated_concept_slugs"],
            ["c1"],
        )
        self.assertEqual(request_payload["concept_id"], "c1")
        self.assertTrue(new_request_exists)
        self.assertTrue(all(not exists for exists in stale_exists))
        self.assertFalse(model_summary_exists)
        self.assertFalse(gate_summary_exists)

    def test_unchanged_current_format_provenance_preserves_valid_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approved_scripts = root / "approved_scripts"
            requests = root / "format_requests"
            responses = root / "format_responses"
            plans = root / "format_plans"
            model_runs = root / "format_model_runs"
            raw = root / "raw_format_outputs"
            review_requests = root / "format_review_requests"
            review_responses = root / "format_review_responses"
            approved_plans = root / "approved_format_plans"
            for directory in (
                approved_scripts,
                requests,
                responses,
                plans,
                model_runs,
                raw,
                review_requests,
                review_responses,
                approved_plans,
            ):
                directory.mkdir()

            approved_path = approved_scripts / "c1.approved_script.json"
            approved_path.write_text(
                json.dumps(self.script("short")),
                encoding="utf-8",
            )

            model_summary = root / "format_model_batch_summary.json"
            gate_summary = root / "format_gate_summary.json"

            patches = (
                patch.object(module, "REQUESTS_DIR", requests),
                patch.object(module, "RESPONSES_DIR", responses),
                patch.object(module, "PLANS_DIR", plans),
                patch.object(module, "MODEL_RUNS_DIR", model_runs),
                patch.object(module, "RAW_OUTPUTS_DIR", raw),
                patch.object(module, "FORMAT_REVIEW_REQUESTS_DIR", review_requests),
                patch.object(module, "FORMAT_REVIEW_RESPONSES_DIR", review_responses),
                patch.object(module, "APPROVED_FORMAT_PLANS_DIR", approved_plans),
                patch.object(module, "MODEL_BATCH_SUMMARY_FILE", model_summary),
                patch.object(module, "FORMAT_GATE_SUMMARY_FILE", gate_summary),
                patch.object(module, "OUTPUT_DIR", root),
                patch.object(module, "SUMMARY_FILE", root / "summary.json"),
            )
            for item in patches:
                item.start()
            try:
                module.run_prepare(
                    approved_scripts,
                    self.config(),
                )
                request_path = requests / "c1.format_request.json"
                request_hash = module.sha256_file(request_path)

                response_path = responses / "c1.json"
                response_path.write_text(
                    json.dumps(
                        {
                            "concept_id": "c1",
                            "response_provenance": {
                                "request_sha256": request_hash,
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                plan_path = plans / "c1.format_plan.json"
                plan_path.write_text(
                    json.dumps(
                        {
                            "concept_id": "c1",
                            "plan_provenance": {
                                "request_sha256": request_hash,
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                plan_hash = module.sha256_file(plan_path)
                (model_runs / "c1.model_run.json").write_text(
                    json.dumps(
                        {
                            "status": "VALIDATED",
                            "request_sha256": request_hash,
                        }
                    ),
                    encoding="utf-8",
                )
                (raw / "c1.txt").write_text("model output", encoding="utf-8")
                (review_requests / "c1.format_review_request.json").write_text(
                    json.dumps(
                        {
                            "concept_id": "c1",
                            "request_provenance": {
                                "format_plan": str(plan_path.resolve()),
                                "format_plan_sha256": plan_hash,
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                (review_responses / "c1.format_review_response.json").write_text(
                    json.dumps(
                        {
                            "decision": "ACCEPT",
                            "format_plan_sha256": plan_hash,
                        }
                    ),
                    encoding="utf-8",
                )
                (approved_plans / "c1.approved_format_plan.json").write_text(
                    json.dumps(
                        {
                            "concept_id": "c1",
                            "approved_provenance": {
                                "format_plan_sha256": plan_hash,
                            },
                        }
                    ),
                    encoding="utf-8",
                )

                summary = module.run_prepare(
                    approved_scripts,
                    self.config(),
                )
                preserved = [
                    response_path,
                    plan_path,
                    model_runs / "c1.model_run.json",
                    raw / "c1.txt",
                    review_requests / "c1.format_review_request.json",
                    review_responses / "c1.format_review_response.json",
                    approved_plans / "c1.approved_format_plan.json",
                ]
                existence = [path.exists() for path in preserved]
            finally:
                for item in reversed(patches):
                    item.stop()

        self.assertEqual(
            summary["stale_cleanup"]["invalidated_concept_slugs"],
            [],
        )
        self.assertEqual(
            summary["stale_cleanup"]["active_provenance_cleanup"][
                "removed_artifacts"
            ],
            [],
        )
        self.assertTrue(all(existence))

    def test_format_request_ignores_legacy_public_title_selections(self):
        script = self.script("either")
        script["package"]["selected_titles"] = {
            "long_form": {
                "candidate_id": "long-curiosity",
                "title": "Different Long Public Title",
            },
            "short": {
                "candidate_id": "short-stakes",
                "title": "Cold Brakes Can Betray You",
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "script.json"
            path.write_text(json.dumps(script), encoding="utf-8")
            request = build_format_request(script, path, self.config())

        self.assertEqual(
            request["branch_story_packages"]["long_form"]["title"],
            "Why Racing Brakes Work Backwards",
        )
        self.assertEqual(
            request["branch_story_packages"]["short"]["title"],
            "Why Racing Brakes Work Backwards",
        )
        self.assertEqual(request["package"]["selected_titles"], {})
        self.assertEqual(
            request["package"]["title_role"],
            "INTERNAL_WORKING_TITLE",
        )



if __name__ == "__main__":
    unittest.main()
