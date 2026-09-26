import unittest

from research_engine import (
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
                }
            ],
        }

    def test_plan_creates_stable_question_ids(self):
        plan = build_research_plan(self.concept)

        self.assertEqual(
            [item["question_id"] for item in plan["research_questions"]],
            ["rq001", "rq002", "pkgq001"],
        )
        self.assertEqual(
            plan["research_questions"][-1]["origin"],
            "packaging",
        )


    def test_plan_requires_approved_packaging_context(self):
        concept = dict(self.concept)
        concept.pop("packaging")

        with self.assertRaises(ValueError):
            build_research_plan(concept)

    def test_single_source_is_not_called_verified(self):
        coverage = claim_coverage_state(
            self.claim()["evidence_links"]
        )

        self.assertEqual(coverage["state"], "SINGLE_SOURCE")
        self.assertNotIn("verified", coverage)

    def test_multiple_supporting_sources_are_multi_source(self):
        links = self.claim()["evidence_links"] + [
            {
                "source_id": "src002",
                "stance": "SUPPORTS",
                "locator": "Section 4",
                "evidence_note": "Independent source describes the same constraint.",
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

        by_id = {
            item["question_id"]: item
            for item in package["question_coverage"]
        }
        self.assertFalse(by_id["rq001"]["has_claims"])
        self.assertTrue(by_id["rq002"]["has_claims"])


if __name__ == "__main__":
    unittest.main()
