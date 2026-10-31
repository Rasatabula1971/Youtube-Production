from research_engine import research_engine as module
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from research_engine.research_engine import (
    build_research_plan,
    claim_coverage_state,
    validate_research_response,
)


class ResearchEngineTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "allowed_source_types": [
                "primary",
                "secondary",
                "dataset",
                "documentation",
                "expert_statement",
            ],
            "allowed_stances": [
                "SUPPORTS",
                "CONTRADICTS",
                "QUALIFIES",
            ],
            "allowed_claim_roles": [
                "core",
                "supporting",
                "context",
            ],
            "require_source_locator": True,
        }
        self.concept = {
            "concept_id": "c1",
            "mechanism_id": "curiosity_gap",
            "mechanism_label": "Curiosity",
            "working_title": "Why Racing Brakes Behave Backwards",
            "premise": "Investigate a brake engineering constraint.",
            "audience_promise": "Explain the hidden reason.",
            "viewer_problem": "Why do racing brakes need extreme heat?",
            "viewer_moment": "Trying to understand a counterintuitive engineering tradeoff.",
            "desired_outcome": "Understand why temperature changes the brake design.",
            "content_gap": {
                "hypothesis": "The design consequence is often under-explained.",
                "evidence_status": "HYPOTHESIS",
                "evidence_basis": [],
            },
            "channel_fit": {
                "status": "FIT",
                "rationale": "Automotive engineering audience.",
            },
            "title_clarity_test": {
                "options": [
                    "Why Racing Brakes Behave Backwards",
                    "Why F1 Brakes Hate Normal Temperatures",
                    "The Brake Problem Road Cars Never Face",
                ],
                "result": "PASS",
                "rationale": "Clear across three framings.",
            },
            "format_intent": "long_form",
            "research_questions": [
                "What thermal limits drive the design?",
                "Which rules constrain the system?",
            ],
            "concept_gate": {
                "decision": "ACCEPT",
            },
            "packaging": {
                "package_id": "c1-pkg001",
                "title": "Why F1 Brakes Work Backwards",
                "thumbnail": {
                    "message": "Visual contrast",
                    "visual_concept": "Split comparison",
                    "text_overlay": "",
                },
                "opening_frame": {
                    "purpose": "Prove the problem exists",
                    "visual_concept": "Close-up evidence",
                },
                "expected_viewer": "Curious automotive viewer",
                "awareness_level": "Basic familiarity",
                "viewer_problem": "Why do racing brakes need extreme heat?",
                "viewer_moment": "Trying to understand a counterintuitive engineering tradeoff.",
                "desired_outcome": "Understand why temperature changes the brake design.",
                "one_sentence_promise": "This video helps curious automotive viewers understand why racing brakes need extreme heat so they can make sense of the design tradeoff.",
                "gap_positioning": "Explain the design consequence rather than only showing hot brakes.",
                "channel_fit_alignment": "Automotive engineering explanation.",
                "core_promise": "Explain the hidden mechanism",
                "curiosity_gap": "Why does the obvious solution fail?",
                "expected_payoff": "Viewer understands the tradeoff",
                "format_intent": "long_form",
                "title_thumbnail_relationship": "Title asks why; thumbnail shows contrast",
                "research_dependencies": [
                    "Verify the package's central brake-temperature comparison."
                ],
                "packaging_gate": {
                    "decision": "ACCEPT",
                },
            },
        }

    def source(self, source_id="src001", publisher="FIA"):
        return {
            "source_id": source_id,
            "title": "Technical Regulations",
            "publisher": publisher,
            "url": "https://example.com/regulations",
            "source_type": "primary",
            "published_at": "",
            "accessed_at": "",
            "provenance_note": "Defines the technical rules.",
        }

    def claim(self):
        return {
            "claim_id": "clm001",
            "statement": "The design is constrained by a technical rule.",
            "role": "core",
            "question_ids": ["rq002"],
            "evidence_links": [
                {
                    "source_id": "src001",
                    "stance": "SUPPORTS",
                    "locator": "Article 11",
                    "evidence_note": "The rule limits the component geometry.",
                    "evidence_quote": "The rule limits the component geometry.",
                }
            ],
        }

    def test_plan_creates_stable_question_ids(self):
        plan = build_research_plan(self.concept)

        # rq001 tests the working title's promise (D-182); the concept's own
        # questions follow it.
        self.assertEqual(
            [item["question_id"] for item in plan["research_questions"]],
            ["rq001", "rq002", "rq003", "pkgq001"],
        )
        self.assertEqual(plan["research_questions"][0]["origin"], "title_promise")
        self.assertEqual(
            plan["research_questions"][-1]["origin"],
            "legacy_packaging",
        )
        self.assertEqual(
            plan["viewer_problem"],
            self.concept["viewer_problem"],
        )
        self.assertEqual(
            plan["packaging"]["one_sentence_promise"],
            self.concept["packaging"]["one_sentence_promise"],
        )

    def test_plan_does_not_require_pre_script_packaging(self):
        concept = dict(self.concept)
        concept.pop("packaging")
        plan = build_research_plan(concept)

        self.assertEqual(
            [item["question_id"] for item in plan["research_questions"]],
            ["rq001", "rq002", "rq003"],
        )
        self.assertEqual(plan["packaging"], {})

    def test_single_source_is_not_called_verified(self):
        coverage = claim_coverage_state(self.claim()["evidence_links"])

        self.assertEqual(coverage["state"], "SINGLE_SOURCE")
        self.assertNotIn("verified", coverage)

    def test_multiple_supporting_sources_are_multi_source(self):
        links = self.claim()["evidence_links"] + [
            {
                "source_id": "src002",
                "stance": "SUPPORTS",
                "locator": "Section 4",
                "evidence_note": "Independent source describes the same constraint.",
                "evidence_quote": "Independent source describes the same constraint.",
            }
        ]

        coverage = claim_coverage_state(links)

        self.assertEqual(coverage["state"], "MULTI_SOURCE")

    def test_any_contradiction_marks_claim_conflicted(self):
        links = self.claim()["evidence_links"] + [
            {
                "source_id": "src002",
                "stance": "CONTRADICTS",
                "locator": "Section 8",
                "evidence_note": "This source describes an exception.",
                "evidence_quote": "This source describes an exception.",
            }
        ]

        coverage = claim_coverage_state(links)

        self.assertEqual(coverage["state"], "CONFLICTED")

    def test_valid_response_preserves_conflict_structure(self):
        plan = build_research_plan(self.concept)
        response = {
            "concept_id": "c1",
            "sources": [
                self.source("src001", "FIA"),
                self.source("src002", "Engineering Journal"),
            ],
            "claims": [
                {
                    **self.claim(),
                    "evidence_links": self.claim()["evidence_links"]
                    + [
                        {
                            "source_id": "src002",
                            "stance": "CONTRADICTS",
                            "locator": "Section 8",
                            "evidence_note": "Describes an exception.",
                            "evidence_quote": "Describes an exception.",
                        }
                    ],
                }
            ],
        }

        package = validate_research_response(
            response,
            plan,
            self.config,
        )

        self.assertEqual(
            package["claims"][0]["coverage"]["state"],
            "CONFLICTED",
        )

    def test_carried_claims_are_merged_with_prefixed_ids(self):
        plan = build_research_plan(self.concept)
        plan["carried_claims"] = [
            {"claim": self.claim(), "sources": [self.source("src001", "FIA")]}
        ]
        response = {
            "concept_id": "c1",
            "sources": [self.source("src001", "Other publisher")],
            "claims": [self.claim()],
        }
        merged = module.merge_carried_claims(response, plan)
        package = validate_research_response(merged, plan, self.config)
        ids = [claim["claim_id"] for claim in package["claims"]]
        self.assertEqual(ids, ["clm001", "kept_clm001"])
        kept = package["claims"][1]
        self.assertEqual(kept["evidence_links"][0]["source_id"], "kept_src001")
        self.assertEqual(kept["carried_from_review"]["original_claim_id"], "clm001")
        self.assertIn(
            "kept_src001", [source["source_id"] for source in package["sources"]]
        )
        self.assertEqual(package.get("rejected_claims", []), [])

    def test_recarried_claim_keeps_a_single_prefix(self):
        plan = build_research_plan(self.concept)
        claim = {**self.claim(), "claim_id": "kept_clm001"}
        claim["evidence_links"] = [{**claim["evidence_links"][0], "source_id": "kept_src001"}]
        plan["carried_claims"] = [
            {"claim": claim, "sources": [self.source("kept_src001")]}
        ]
        merged = module.merge_carried_claims({"concept_id": "c1", "sources": [], "claims": []}, plan)
        self.assertEqual(merged["claims"][0]["claim_id"], "kept_clm001")
        self.assertEqual(merged["sources"][0]["source_id"], "kept_src001")

    def test_no_carried_claims_leaves_response_unchanged(self):
        response = {"concept_id": "c1", "sources": [], "claims": []}
        self.assertIs(module.merge_carried_claims(response, {}), response)

    def test_unknown_source_rejects_claim(self):
        plan = build_research_plan(self.concept)
        claim = self.claim()
        claim["evidence_links"][0]["source_id"] = "missing"
        response = {
            "concept_id": "c1",
            "sources": [self.source()],
            "claims": [claim],
        }

        package = validate_research_response(
            response,
            plan,
            self.config,
        )

        self.assertEqual(len(package["claims"]), 0)
        self.assertEqual(len(package["rejected_claims"]), 1)

    def test_unknown_question_rejects_claim(self):
        plan = build_research_plan(self.concept)
        claim = self.claim()
        claim["question_ids"] = ["rq999"]
        response = {
            "concept_id": "c1",
            "sources": [self.source()],
            "claims": [claim],
        }

        package = validate_research_response(
            response,
            plan,
            self.config,
        )

        self.assertEqual(len(package["claims"]), 0)

    def test_question_coverage_reports_unanswered_questions(self):
        plan = build_research_plan(self.concept)
        response = {
            "concept_id": "c1",
            "sources": [self.source()],
            "claims": [self.claim()],
        }

        package = validate_research_response(
            response,
            plan,
            self.config,
        )

        by_id = {item["question_id"]: item for item in package["question_coverage"]}
        self.assertFalse(by_id["rq001"]["has_claims"])
        self.assertTrue(by_id["rq002"]["has_claims"])


    def test_slug_collision_is_rejected_before_plan_writes(self):
        with self.assertRaisesRegex(ValueError, "collide"):
            module.assert_unique_slug_ids(
                ["gear/ratio", "gear ratio"],
                label="concept",
            )

    def test_the_first_question_tests_the_working_title_promise(self):
        """D-182: "Single Cup of Water" reached the script with nothing behind its title."""
        plan = build_research_plan(self.concept)
        first = plan["research_questions"][0]
        self.assertEqual(first["question_id"], "rq001")
        self.assertEqual(first["origin"], "title_promise")
        self.assertIn("Why Racing Brakes Behave Backwards", first["question"])
        self.assertEqual(plan["research_questions"][1]["origin"], "concept")

    def test_a_concept_without_a_working_title_gets_no_promise_question(self):
        concept = dict(self.concept)
        concept.pop("working_title")
        concept.pop("packaging", None)
        plan = build_research_plan(concept)
        self.assertNotIn(
            "title_promise", [item["origin"] for item in plan["research_questions"]]
        )

    def prepared_dirs(self, stack, root):
        output = root / "output"
        plans = output / "plans"
        stack.enter_context(patch.object(module, "OUTPUT_DIR", output))
        stack.enter_context(patch.object(module, "PLANS_DIR", plans))
        stack.enter_context(patch.object(module, "SUMMARY_FILE", output / "summary.json"))
        stack.enter_context(patch.object(module, "DROPPED_FILE", output / "dropped_concepts.json"))
        handoff = root / "research_handoff.json"
        second = {**self.concept, "concept_id": "c2", "working_title": "Second"}
        handoff.write_text(
            json.dumps({"artifact": "research_handoff", "concepts": [self.concept, second]}),
            encoding="utf-8",
        )
        return output, plans, handoff

    def test_a_plan_already_built_from_the_same_handoff_is_kept_as_it_is(self):
        """Research under way must not restart because this code adds a question."""
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            output, plans, handoff = self.prepared_dirs(stack, Path(tmp))
            module.run_prepare(handoff)
            plan_path = plans / "c1.research_plan.json"
            old = json.loads(plan_path.read_text(encoding="utf-8"))
            old["research_questions"] = [q for q in old["research_questions"] if q["origin"] != "title_promise"]
            plan_path.write_text(json.dumps(old), encoding="utf-8")
            before = plan_path.read_bytes()
            module.run_prepare(handoff)
            self.assertEqual(plan_path.read_bytes(), before)

            handoff.write_text(
                json.dumps({"artifact": "research_handoff", "concepts": [self.concept]}),
                encoding="utf-8",
            )
            module.run_prepare(handoff)
            rebuilt = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertEqual(rebuilt["research_questions"][0]["origin"], "title_promise")

    def test_a_dropped_concept_gets_no_research_plan(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            output, plans, handoff = self.prepared_dirs(stack, Path(tmp))
            module.run_prepare(handoff)
            self.assertTrue((plans / "c2.research_plan.json").exists())
            (output / "dropped_concepts.json").write_text(
                json.dumps({"concepts": {"c2": {"note": "Too thin."}}}), encoding="utf-8"
            )
            summary = module.run_prepare(handoff)
            self.assertFalse((plans / "c2.research_plan.json").exists())
            self.assertTrue((plans / "c1.research_plan.json").exists())
        self.assertEqual(summary["dropped_concepts_skipped"], ["c2"])


if __name__ == "__main__":
    unittest.main()
