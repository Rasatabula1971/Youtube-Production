import unittest

from concept_gate import (
    apply_gate,
    build_review_request,
    validate_decisions,
)


class ConceptGateTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "required_accept_criteria": [
                "originality_clear",
                "audience_promise_clear",
                "viewer_problem_specific",
                "viewer_moment_clear",
                "desired_outcome_specific",
                "content_gap_honest",
                "channel_fit_confirmed",
                "title_clarity_passes",
                "source_independent",
                "feasible",
                "researchable",
            ],
            "require_reviewer_name": True,
        }
        self.candidates = {
            "artifact": "concept_candidates",
            "concepts": [
                {
                    "concept_id": "c1",
                    "mechanism_id": "curiosity_gap",
                    "mechanism_label": "Curiosity",
                    "working_title": "Why Racing Brakes Behave Backwards",
                    "premise": "Investigate a counterintuitive brake constraint.",
                    "audience_promise": "Explain the hidden reason.",
                    "viewer_problem": "Why do racing brakes need conditions that seem wrong for road cars?",
                    "viewer_moment": "Trying to understand a surprising race-car engineering tradeoff.",
                    "desired_outcome": "Understand why temperature changes the brake design.",
                    "content_gap": {
                        "hypothesis": "Many explanations show hot brakes without explaining the design consequence.",
                        "evidence_status": "HYPOTHESIS",
                        "evidence_basis": [],
                    },
                    "channel_fit": {
                        "status": "FIT",
                        "rationale": "Automotive engineering explainer.",
                    },
                    "title_clarity_test": {
                        "options": [
                            "Why Racing Brakes Behave Backwards",
                            "Why F1 Brakes Hate Normal Temperatures",
                            "The Brake Problem Road Cars Never Face",
                        ],
                        "result": "PASS",
                        "rationale": "Clear problem across three title framings.",
                    },
                    "format_intent": "long_form",
                    "mechanism_application": "One unanswered question.",
                    "transformation_method": "Different system and research path.",
                    "research_questions": [
                        "What thermal constraints matter?",
                        "What rules apply?",
                    ],
                    "source_dependency_test": {
                        "passes": True,
                        "source_assets_required": False,
                        "rationale": "Independent concept.",
                    },
                },
                {
                    "concept_id": "c2",
                    "mechanism_id": "hidden_mechanism",
                    "working_title": "Inside an F1 Brake Duct",
                    "premise": "Explain an unseen mechanism.",
                    "audience_promise": "Show how airflow is managed.",
                    "viewer_problem": "What does an F1 brake duct actually do?",
                    "viewer_moment": "Watching or learning about F1 and noticing the hidden duct complexity.",
                    "desired_outcome": "Understand the duct's functional role.",
                    "content_gap": {
                        "hypothesis": "The component is often shown without its function being explained.",
                        "evidence_status": "HYPOTHESIS",
                        "evidence_basis": [],
                    },
                    "channel_fit": {
                        "status": "FIT",
                        "rationale": "Fits hidden-mechanism automotive content.",
                    },
                    "title_clarity_test": {
                        "options": [
                            "Inside an F1 Brake Duct",
                            "What F1 Brake Ducts Actually Do",
                            "The Hidden Job of an F1 Brake Duct",
                        ],
                        "result": "PASS",
                        "rationale": "Three clear ways to express the same mechanism.",
                    },
                    "format_intent": "short",
                    "mechanism_application": "Reveal hidden function.",
                    "transformation_method": "New subsystem.",
                    "research_questions": [
                        "What does the duct control?",
                        "What sources document it?",
                    ],
                    "source_dependency_test": {
                        "passes": True,
                        "source_assets_required": False,
                        "rationale": "Independent concept.",
                    },
                },
            ],
        }

    def response(self, request):
        return {
            "reviewer": "reviewer-1",
            "decisions": [
                {
                    "concept_id": item["concept_id"],
                    "decision": "ACCEPT",
                    "criteria": {
                        criterion: True
                        for criterion in self.config[
                            "required_accept_criteria"
                        ]
                    },
                    "note": "",
                }
                for item in request["items"]
            ],
            "overall_note": "",
        }

    def test_prepare_contains_all_concepts(self):
        request = build_review_request(
            self.candidates,
            self.config,
        )

        self.assertEqual(request["concept_count"], 2)
        self.assertEqual(len(request["items"]), 2)


    def test_duplicate_concept_ids_are_rejected(self):
        candidates = {
            "concepts": [
                dict(self.candidates["concepts"][0]),
                dict(self.candidates["concepts"][0]),
            ]
        }

        with self.assertRaises(ValueError):
            build_review_request(
                candidates,
                self.config,
            )

    def test_review_request_exposes_viewer_need_and_gap(self):
        request = build_review_request(
            self.candidates,
            self.config,
        )

        first = request["items"][0]
        self.assertIn("viewer_problem", first)
        self.assertIn("viewer_moment", first)
        self.assertIn("content_gap", first)
        self.assertIn("channel_fit", first)
        self.assertIn("title_clarity_test", first)

    def test_accept_requires_all_criteria_true(self):
        request = build_review_request(
            self.candidates,
            self.config,
        )
        response = self.response(request)
        response["decisions"][0]["criteria"][
            "researchable"
        ] = False

        with self.assertRaises(ValueError):
            validate_decisions(
                request,
                response,
                self.config,
            )

    def test_rework_requires_note(self):
        request = build_review_request(
            self.candidates,
            self.config,
        )
        response = self.response(request)
        response["decisions"][0]["decision"] = "REWORK"

        with self.assertRaises(ValueError):
            validate_decisions(
                request,
                response,
                self.config,
            )

    def test_missing_decision_is_rejected(self):
        request = build_review_request(
            self.candidates,
            self.config,
        )
        response = self.response(request)
        response["decisions"] = response["decisions"][:1]

        with self.assertRaises(ValueError):
            validate_decisions(
                request,
                response,
                self.config,
            )

    def test_only_accepted_concepts_enter_research_handoff(self):
        request = build_review_request(
            self.candidates,
            self.config,
        )
        response = self.response(request)
        response["decisions"][1]["decision"] = "REJECT"

        reviewed, handoff = apply_gate(
            self.candidates,
            request,
            response,
            self.config,
        )

        self.assertEqual(reviewed["counts"]["accepted"], 1)
        self.assertEqual(reviewed["counts"]["rejected"], 1)
        self.assertEqual(handoff["concept_count"], 1)
        self.assertEqual(
            handoff["concepts"][0]["concept_id"],
            "c1",
        )

    def test_rework_is_preserved_but_not_handed_to_research(self):
        request = build_review_request(
            self.candidates,
            self.config,
        )
        response = self.response(request)
        response["decisions"][0]["decision"] = "REWORK"
        response["decisions"][0]["criteria"][
            "audience_promise_clear"
        ] = False
        response["decisions"][0]["note"] = (
            "Clarify the viewer payoff."
        )

        reviewed, handoff = apply_gate(
            self.candidates,
            request,
            response,
            self.config,
        )

        self.assertEqual(reviewed["counts"]["rework"], 1)
        self.assertEqual(handoff["concept_count"], 1)
        self.assertEqual(
            handoff["concepts"][0]["concept_id"],
            "c2",
        )


if __name__ == "__main__":
    unittest.main()
