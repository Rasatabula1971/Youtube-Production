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

    def script(self, format_intent="either"):
        return {
            "concept_id": "c1",
            "title": "Why Racing Brakes Work Backwards",
            "opening_hook": "Hook",
            "sections": [
                {
                    "section_id": "s1",
                    "purpose": "Explain",
                    "narration": "Heat changes braking behavior.",
                    "claim_ids": ["clm001"],
                },
                {
                    "section_id": "s2",
                    "purpose": "Payoff",
                    "narration": "So the pedal feels wrong.",
                    "claim_ids": ["clm001"],
                },
            ],
            "closing": "Close",
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
            "script_gate": {"status": "READY_FOR_PRODUCTION"},
        }

    def request(self, format_intent="either"):
        script = self.script(format_intent)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "script.json"
            path.write_text(json.dumps(script), encoding="utf-8")
            return build_format_request(script, path, self.config())

    def beat(self, beat_id, purpose, treatment, claim_ids=("clm001",)):
        return {
            "beat_id": beat_id,
            "purpose": purpose,
            "treatment": treatment,
            "claim_ids": list(claim_ids),
            "source_section_ids": ["s1"],
        }

    def long_form_branch(self):
        return {
            "format": "long_form",
            "duration_intent_seconds": 600,
            "promise_delivery": "Full explanation of the braking system",
            "payoff": "Viewer understands the whole mechanism",
            "beats": [
                self.beat("lf1", "hook", "Open on the failed corner", claim_ids=()),
                self.beat("lf2", "context", "Lay out how the system normally works"),
                self.beat("lf3", "reveal", "Show where heat changes the behavior"),
                self.beat("lf4", "payoff", "Tie the mechanism back to the corner"),
            ],
        }

    def short_branch(self):
        return {
            "format": "short",
            "duration_intent_seconds": 45,
            "promise_delivery": "One counterintuitive fact, delivered fast",
            "payoff": "Viewer leaves with the single surprising mechanism",
            "beats": [
                self.beat("sh1", "cold open", "State the surprising claim first"),
                self.beat("sh2", "proof", "Single visual showing the heat effect"),
                self.beat("sh3", "close", "Restate the mechanism in one line"),
            ],
        }

    def test_either_intent_requires_both_branches(self):
        request = self.request("either")
        self.assertEqual(request["required_branches"], ["long_form", "short"])
        self.assertIn("long_form", request["branch_constraints"])
        self.assertIn("short", request["branch_constraints"])

    def test_single_intent_requires_one_branch(self):
        self.assertEqual(self.request("short")["required_branches"], ["short"])
        self.assertEqual(self.request("long_form")["required_branches"], ["long_form"])

    def test_unknown_format_intent_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_branches("vertical_reel", self.config())

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

    def test_identical_branches_are_rejected(self):
        request = self.request("either")
        shared = self.long_form_branch()
        short = {
            **self.short_branch(),
            "beats": [dict(beat) for beat in shared["beats"]],
        }
        response = {"concept_id": "c1", "branches": [shared, short]}
        result = validate_format_response(response, request)
        self.assertFalse(result["valid"])
        self.assertTrue(any("identical edits" in e for e in result["errors"]))

    def test_truncated_branch_is_rejected(self):
        request = self.request("either")
        long_form = self.long_form_branch()
        short = {
            **self.short_branch(),
            "beats": [dict(beat) for beat in long_form["beats"][:3]],
        }
        response = {"concept_id": "c1", "branches": [long_form, short]}
        result = validate_format_response(response, request)
        self.assertFalse(result["valid"])
        self.assertTrue(any("truncation" in e for e in result["errors"]))

    def test_missing_required_branch_is_rejected(self):
        request = self.request("either")
        response = {"concept_id": "c1", "branches": [self.long_form_branch()]}
        result = validate_format_response(response, request)
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("missing required branch: short" in e for e in result["errors"])
        )

    def test_unrequested_branch_is_rejected(self):
        request = self.request("long_form")
        response = {
            "concept_id": "c1",
            "branches": [self.long_form_branch(), self.short_branch()],
        }
        result = validate_format_response(response, request)
        self.assertFalse(result["valid"])
        self.assertTrue(any("unrequested branch: short" in e for e in result["errors"]))

    def test_unapproved_claim_id_is_rejected(self):
        request = self.request("short")
        branch = self.short_branch()
        branch["beats"][0]["claim_ids"] = ["bad"]
        result = validate_format_response(
            {"concept_id": "c1", "branches": [branch]}, request
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("unapproved claim_id bad" in e for e in result["errors"]))

    def test_unknown_source_section_is_rejected(self):
        request = self.request("short")
        branch = self.short_branch()
        branch["beats"][0]["source_section_ids"] = ["s99"]
        result = validate_format_response(
            {"concept_id": "c1", "branches": [branch]}, request
        )
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("unknown script section s99" in e for e in result["errors"])
        )

    def test_duration_outside_branch_constraints_is_rejected(self):
        request = self.request("short")
        branch = self.short_branch()
        branch["duration_intent_seconds"] = 600
        result = validate_format_response(
            {"concept_id": "c1", "branches": [branch]}, request
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("above maximum" in e for e in result["errors"]))

    def test_branch_without_any_claim_is_rejected(self):
        request = self.request("short")
        branch = self.short_branch()
        for beat in branch["beats"]:
            beat["claim_ids"] = []
        result = validate_format_response(
            {"concept_id": "c1", "branches": [branch]}, request
        )
        self.assertFalse(result["valid"])
        self.assertTrue(
            any(
                "at least one beat carrying an accepted claim" in e
                for e in result["errors"]
            )
        )

    def test_duplicate_beat_id_is_rejected(self):
        request = self.request("short")
        branch = self.short_branch()
        branch["beats"][1]["beat_id"] = branch["beats"][0]["beat_id"]
        result = validate_format_response(
            {"concept_id": "c1", "branches": [branch]}, request
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("duplicate beat_id" in e for e in result["errors"]))

    def test_below_minimum_beats_is_rejected(self):
        request = self.request("short")
        branch = self.short_branch()
        branch["beats"] = branch["beats"][:1]
        result = validate_format_response(
            {"concept_id": "c1", "branches": [branch]}, request
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("at least 3 beats" in e for e in result["errors"]))

    def test_concept_id_mismatch_is_rejected(self):
        request = self.request("short")
        result = validate_format_response(
            {"concept_id": "other", "branches": [self.short_branch()]}, request
        )
        self.assertFalse(result["valid"])
        self.assertIn("concept_id mismatch", result["errors"])


    def test_slug_collision_is_rejected_before_format_request_writes(self):
        with self.assertRaisesRegex(ValueError, "collide"):
            module.assert_unique_slug_ids(
                ["gear/ratio", "gear ratio"],
                label="concept",
            )


if __name__ == "__main__":
    unittest.main()
