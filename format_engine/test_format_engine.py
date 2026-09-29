import json
import tempfile
import unittest
from pathlib import Path

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
        }

    def request(self, format_intent="either"):
        script = self.script(format_intent)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "script.json"
            path.write_text(json.dumps(script), encoding="utf-8")
            return build_format_request(script, path, self.config())

    def beat(self, beat_id, purpose, treatment, section_id, claim_ids=("clm001",)):
        return {
            "beat_id": beat_id,
            "purpose": purpose,
            "treatment": treatment,
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


if __name__ == "__main__":
    unittest.main()
