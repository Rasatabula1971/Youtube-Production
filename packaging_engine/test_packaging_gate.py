import unittest

from packaging_gate import (
    apply_gate,
    build_review_request,
    validate_decisions,
)


class PackagingGateTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "required_accept_criteria": [
                "promise_clear",
                "concept_aligned",
                "title_thumbnail_complementary",
                "not_misleading",
                "viewer_awareness_fit",
                "payoff_defined",
                "research_dependencies_explicit",
            ],
            "require_reviewer_name": True,
        }
        self.candidates = {
            "artifact": "package_candidates",
            "packages": [
                self.package(
                    "pkg1",
                    "c1",
                    "Why F1 Brakes Work Backwards",
                ),
                self.package(
                    "pkg2",
                    "c1",
                    "The Brake Problem Road Cars Never Face",
                ),
                self.package(
                    "pkg3",
                    "c2",
                    "Why F1 Gearboxes Shift So Fast",
                ),
            ],
        }

    def package(
        self,
        package_id,
        concept_id,
        title,
    ):
        return {
            "package_id": package_id,
            "concept_id": concept_id,
            "title": title,
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
                "Verify the claimed engineering difference"
            ],
            "concept_context": {
                "working_title": title,
                "premise": "Independent concept",
                "audience_promise": "Explain it",
                "format_intent": "long_form",
                "research_questions": [
                    "What causes the difference?"
                ],
                "concept_gate": {
                    "decision": "ACCEPT"
                },
            },
        }

    def response(self, request):
        decisions = []
        accepted_concepts = set()
        for item in request["items"]:
            concept_id = item["concept_id"]
            value = (
                "ACCEPT"
                if concept_id not in accepted_concepts
                else "REJECT"
            )
            if value == "ACCEPT":
                accepted_concepts.add(concept_id)
            decisions.append(
                {
                    "package_id": item["package_id"],
                    "decision": value,
                    "criteria": {
                        criterion: True
                        for criterion in self.config[
                            "required_accept_criteria"
                        ]
                    },
                    "note": "",
                }
            )
        return {
            "reviewer": "reviewer-1",
            "decisions": decisions,
            "overall_note": "",
        }

    def test_request_contains_all_packages(self):
        request = build_review_request(
            self.candidates,
            self.config,
        )
        self.assertEqual(
            request["package_count"],
            3,
        )

    def test_accept_requires_all_criteria(self):
        request = build_review_request(
            self.candidates,
            self.config,
        )
        response = self.response(request)
        response["decisions"][0]["criteria"][
            "not_misleading"
        ] = False

        with self.assertRaises(ValueError):
            validate_decisions(
                request,
                response,
                self.config,
            )

    def test_only_one_accept_per_concept(self):
        request = build_review_request(
            self.candidates,
            self.config,
        )
        response = self.response(request)
        response["decisions"][1][
            "decision"
        ] = "ACCEPT"

        with self.assertRaises(ValueError):
            validate_decisions(
                request,
                response,
                self.config,
            )

    def test_accepted_package_enters_research_handoff(self):
        request = build_review_request(
            self.candidates,
            self.config,
        )
        reviewed, handoff = apply_gate(
            self.candidates,
            request,
            self.response(request),
            self.config,
        )

        self.assertEqual(
            reviewed["counts"]["accepted"],
            2,
        )
        self.assertEqual(
            handoff["concept_count"],
            2,
        )
        self.assertIn(
            "packaging",
            handoff["concepts"][0],
        )

    def test_rework_requires_note(self):
        request = build_review_request(
            self.candidates,
            self.config,
        )
        response = self.response(request)
        response["decisions"][0][
            "decision"
        ] = "REWORK"

        with self.assertRaises(ValueError):
            validate_decisions(
                request,
                response,
                self.config,
            )


if __name__ == "__main__":
    unittest.main()
