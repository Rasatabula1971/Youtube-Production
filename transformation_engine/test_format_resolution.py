"""One resolved format per accepted concept (D-132)."""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path

import concept_review as review
import test_concept_gate as gate_tests
import test_concept_review as review_tests
from concept_gate import apply_gate, build_review_request, validate_decisions
from format_resolution import normalize_choice, resolve_format


class ResolveFormatTests(unittest.TestCase):
    def test_single_format_concepts_keep_their_format(self):
        for value in ("long_form", "short"):
            result = resolve_format(value)
            self.assertEqual((result["format_intent"], result["decided_by"]), (value, "CONCEPT"))

    def test_either_takes_the_configured_default(self):
        self.assertEqual(resolve_format("either")["format_intent"], "long_form")
        result = resolve_format("either", default="short")
        self.assertEqual((result["format_intent"], result["decided_by"]), ("short", "DEFAULT"))
        self.assertEqual(result["requested_format_intent"], "either")
        self.assertIn("fits either format", result["reason"])

    def test_human_choice_wins(self):
        result = resolve_format("either", chosen="short", default="long_form")
        self.assertEqual((result["format_intent"], result["decided_by"]), ("short", "HUMAN"))
        result = resolve_format("long_form", chosen="short")
        self.assertEqual(result["format_intent"], "short")
        self.assertIn("generated as long_form", result["reason"])

    def test_invalid_values_are_refused(self):
        with self.assertRaisesRegex(ValueError, "long_form or short"):
            normalize_choice("either")
        with self.assertRaisesRegex(ValueError, "Unsupported format_intent"):
            resolve_format("vertical")
        self.assertIsNone(normalize_choice(""))
        self.assertEqual(normalize_choice("Long-Form"), "long_form")


class ConceptGateResolutionTests(unittest.TestCase):
    def setUp(self):
        fixture = gate_tests.ConceptGateTests()
        fixture.setUp()
        self.config = {**fixture.config, "either_default_format": "long_form"}
        self.candidates = fixture.candidates
        for concept in self.candidates["concepts"]:
            concept["format_intent"] = "either"
        self.request = build_review_request(self.candidates, self.config)
        self.response = fixture.response(self.request)

    def test_every_accepted_concept_leaves_with_one_format(self):
        self.response["decisions"][0]["format"] = "short"
        _, handoff = apply_gate(self.candidates, self.request, self.response, self.config)
        formats = {
            concept["concept_id"]: (concept["format_intent"], concept["format_resolution"]["decided_by"])
            for concept in handoff["concepts"]
        }
        first, second = (item["concept_id"] for item in self.request["items"])
        self.assertEqual(formats[first], ("short", "HUMAN"))
        self.assertEqual(formats[second], ("long_form", "DEFAULT"))

    def test_a_format_only_goes_with_accept(self):
        self.response["decisions"][0].update({"decision": "REJECT", "format": "short"})
        with self.assertRaisesRegex(ValueError, "only be chosen when accepting"):
            validate_decisions(self.request, self.response, self.config)
        self.response["decisions"][0].update({"decision": "ACCEPT", "format": "both"})
        with self.assertRaisesRegex(ValueError, "long_form or short"):
            validate_decisions(self.request, self.response, self.config)


class ConceptReviewFormatTests(unittest.TestCase):
    fixture = review_tests.ConceptReviewTests

    def test_chosen_format_reaches_the_research_handoff(self):
        fixture = self.fixture()
        candidates = fixture.candidates()
        for concept in candidates["concepts"]:
            concept["format_intent"] = "either"
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            fixture.patch_paths(stack, Path(tmp))
            review.DEFAULT_CANDIDATES.write_text(json.dumps(candidates), encoding="utf-8")
            review.prepare_state()
            with self.assertRaisesRegex(ValueError, "only be chosen when accepting"):
                review.apply_action(
                    concept_id="c1", decision="SAVE_IDEA", criteria={}, note="", format_choice="short"
                )
            first = review.apply_action(
                concept_id="c1", decision="ACCEPT", criteria={}, note="", format_choice="short"
            )
            review.apply_action(
                concept_id="c2", decision="REJECT", criteria={}, note=""
            )
            handoff = json.loads(review.RESEARCH_HANDOFF_FILE.read_text(encoding="utf-8"))
        chosen = next(item for item in first["concepts"] if item["concept_id"] == "c1")
        self.assertEqual(chosen["chosen_format"], "short")
        self.assertEqual(handoff["concepts"][0]["format_intent"], "short")
        self.assertEqual(handoff["concepts"][0]["format_resolution"]["decided_by"], "HUMAN")


if __name__ == "__main__":
    unittest.main()
