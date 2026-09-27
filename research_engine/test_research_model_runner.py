from __future__ import annotations

import unittest

import research_model_runner as runner


class ResearchModelRunnerTests(unittest.TestCase):
    def plan(self):
        return {
            "concept_id": "c1",
            "research_questions": [
                {
                    "question_id": "rq001",
                    "question": "What causes the effect?",
                }
            ],
        }

    def evidence(self):
        return {
            "concept_id": "c1",
            "pages": [
                {
                    "source_id": "web001",
                    "url": "https://example.com/source",
                    "question_ids": ["rq001"],
                    "content": "The documented mechanism is caused by heat.",
                }
            ],
        }

    def test_schema_limits_sources_to_acquired_pages(self):
        schema = runner.response_schema(self.plan(), self.evidence())
        source_schema = (
            schema["properties"]["sources"]["items"]["properties"]
        )

        self.assertEqual(
            source_schema["source_id"]["enum"],
            ["web001"],
        )
        self.assertEqual(
            source_schema["url"]["enum"],
            ["https://example.com/source"],
        )

    def test_source_boundary_accepts_exact_acquired_source(self):
        response = {
            "sources": [
                {
                    "source_id": "web001",
                    "url": "https://example.com/source",
                }
            ]
        }

        runner.validate_acquired_source_boundary(
            response,
            self.evidence(),
        )

    def test_source_boundary_rejects_invented_url(self):
        response = {
            "sources": [
                {
                    "source_id": "web001",
                    "url": "https://invented.example/source",
                }
            ]
        }

        with self.assertRaises(ValueError):
            runner.validate_acquired_source_boundary(
                response,
                self.evidence(),
            )

    def test_prompt_contains_only_acquired_page_payload(self):
        prompt = runner.build_prompt(
            self.plan(),
            self.evidence(),
            maximum_chars=10000,
        )

        self.assertIn(
            "https://example.com/source",
            prompt,
        )
        self.assertIn(
            "The documented mechanism is caused by heat.",
            prompt,
        )
        self.assertIn(
            "Use ONLY the acquired_pages",
            prompt,
        )


if __name__ == "__main__":
    unittest.main()
