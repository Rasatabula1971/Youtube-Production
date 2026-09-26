import unittest

from research_gate import (
    apply_gate,
    build_review_request,
    validate_decisions,
)


class ResearchGateTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "required_accept_criteria": [
                "source_traceable",
                "wording_supported",
                "conflicts_addressed",
                "safe_for_script",
            ],
            "require_reviewer_name": True,
            "require_conflict_resolution_note": True,
        }
        self.package = {
            "artifact": "draft_research_package",
            "concept_id": "c1",
            "concept": {
                "working_title": "Why Racing Brakes Behave Backwards",
            },
            "research_questions": [
                {
                    "question_id": "rq001",
                    "question": "What thermal limits matter?",
                },
                {
                    "question_id": "rq002",
                    "question": "Which rules constrain the system?",
                },
            ],
            "sources": [
                {
                    "source_id": "src001",
                    "title": "Technical Regulations",
                    "publisher": "FIA",
                    "url": "https://example.com/rules",
                    "source_type": "primary",
                },
                {
                    "source_id": "src002",
                    "title": "Engineering Paper",
                    "publisher": "Journal",
                    "url": "https://example.com/paper",
                    "source_type": "secondary",
                },
            ],
            "claims": [
                {
                    "claim_id": "clm001",
                    "statement": "Thermal limits shape the design.",
                    "role": "core",
                    "question_ids": ["rq001"],
                    "evidence_links": [
                        {
                            "source_id": "src002",
                            "stance": "SUPPORTS",
                            "locator": "Section 2",
                            "evidence_note": "Discusses thermal constraints.",
                        }
                    ],
                    "coverage": {
                        "state": "SINGLE_SOURCE",
                    },
                },
                {
                    "claim_id": "clm002",
                    "statement": "A technical rule limits geometry.",
                    "role": "core",
                    "question_ids": ["rq002"],
                    "evidence_links": [
                        {
                            "source_id": "src001",
                            "stance": "SUPPORTS",
                            "locator": "Article 11",
                            "evidence_note": "Limits geometry.",
                        },
                        {
                            "source_id": "src002",
                            "stance": "CONTRADICTS",
                            "locator": "Section 5",
                            "evidence_note": "Describes an exception.",
                        },
                    ],
                    "coverage": {
                        "state": "CONFLICTED",
                    },
                },
            ],
        }

    def response(self, request):
        return {
            "concept_id": "c1",
            "reviewer": "reviewer-1",
            "decisions": [
                {
                    "claim_id": item["claim_id"],
                    "decision": "ACCEPT",
                    "criteria": {
                        criterion: True
                        for criterion in self.config[
                            "required_accept_criteria"
                        ]
                    },
                    "note": (
                        "Conflict resolved by limiting wording to the regulation."
                        if item["coverage"].get("state") == "CONFLICTED"
                        else ""
                    ),
                }
                for item in request["items"]
            ],
            "overall_note": "",
        }

    def test_review_request_includes_source_context(self):
        request = build_review_request(
            self.package,
            self.config,
        )

        self.assertEqual(request["claim_count"], 2)
        self.assertEqual(
            request["items"][0]["evidence"][0]["source"][
                "publisher"
            ],
            "Journal",
        )

    def test_accept_requires_all_criteria(self):
        request = build_review_request(
            self.package,
            self.config,
        )
        response = self.response(request)
        response["decisions"][0]["criteria"][
            "safe_for_script"
        ] = False

        with self.assertRaises(ValueError):
            validate_decisions(
                request,
                response,
                self.config,
            )

    def test_conflicted_accept_requires_resolution_note(self):
        request = build_review_request(
            self.package,
            self.config,
        )
        response = self.response(request)
        for decision in response["decisions"]:
            if decision["claim_id"] == "clm002":
                decision["note"] = ""

        with self.assertRaises(ValueError):
            validate_decisions(
                request,
                response,
                self.config,
            )

    def test_all_questions_resolved_is_ready_for_story_script(self):
        request = build_review_request(
            self.package,
            self.config,
        )

        reviewed, verified = apply_gate(
            self.package,
            request,
            self.response(request),
            self.config,
        )

        self.assertEqual(
            verified["status"],
            "READY_FOR_STORY_SCRIPT",
        )
        self.assertEqual(reviewed["counts"]["accepted"], 2)
        self.assertEqual(
            verified["unresolved_question_ids"],
            [],
        )

    def test_rejected_claim_can_leave_research_incomplete(self):
        request = build_review_request(
            self.package,
            self.config,
        )
        response = self.response(request)
        for decision in response["decisions"]:
            if decision["claim_id"] == "clm001":
                decision["decision"] = "REJECT"
                decision["note"] = "Insufficient support."

        _, verified = apply_gate(
            self.package,
            request,
            response,
            self.config,
        )

        self.assertEqual(
            verified["status"],
            "RESEARCH_INCOMPLETE",
        )
        self.assertIn(
            "rq001",
            verified["unresolved_question_ids"],
        )

    def test_verified_package_keeps_only_used_sources(self):
        package = dict(self.package)
        package["sources"] = list(self.package["sources"]) + [
            {
                "source_id": "src003",
                "title": "Unused source",
                "publisher": "Unused",
                "url": "https://example.com/unused",
                "source_type": "secondary",
            }
        ]
        request = build_review_request(
            package,
            self.config,
        )

        _, verified = apply_gate(
            package,
            request,
            self.response(request),
            self.config,
        )

        self.assertEqual(
            {source["source_id"] for source in verified["sources"]},
            {"src001", "src002"},
        )


if __name__ == "__main__":
    unittest.main()
