from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import research_review as review


class ResearchReviewTests(unittest.TestCase):
    def config(self):
        return {
            "required_accept_criteria": [
                "source_traceable",
                "wording_supported",
                "conflicts_addressed",
                "safe_for_script",
            ],
            "require_reviewer_name": True,
            "require_conflict_resolution_note": True,
        }

    def package(self):
        return {
            "artifact": "draft_research_package",
            "concept_id": "c1",
            "concept": {"working_title": "Test concept"},
            "research_questions": [
                {"question_id": "rq001", "question": "What causes it?"}
            ],
            "sources": [
                {
                    "source_id": "web001",
                    "title": "Source",
                    "publisher": "Publisher",
                    "url": "https://example.com/source",
                    "source_type": "primary",
                }
            ],
            "claims": [
                {
                    "claim_id": "clm001",
                    "statement": "A bounded factual claim.",
                    "role": "core",
                    "question_ids": ["rq001"],
                    "evidence_links": [
                        {
                            "source_id": "web001",
                            "stance": "SUPPORTS",
                            "locator": "Section 1",
                            "evidence_note": "The source supports the bounded claim.",
                            "evidence_quote": "The source supports the bounded claim.",
                        }
                    ],
                    "coverage": {"state": "SINGLE_SOURCE"},
                }
            ],
        }

    def patch_paths(self, stack: ExitStack, root: Path) -> None:
        output = root / "output"
        drafts = output / "draft_packages"
        requests = output / "review_requests"
        reviewed = output / "reviewed_packages"
        verified = output / "verified_packages"
        for path in (drafts, requests, reviewed, verified):
            path.mkdir(parents=True, exist_ok=True)

        stack.enter_context(patch.object(review, "OUTPUT_DIR", output))
        stack.enter_context(patch.object(review, "DEFAULT_DRAFTS_DIR", drafts))
        stack.enter_context(patch.object(review, "REVIEW_REQUESTS_DIR", requests))
        stack.enter_context(patch.object(review, "REVIEWED_DIR", reviewed))
        stack.enter_context(patch.object(review, "VERIFIED_DIR", verified))
        stack.enter_context(
            patch.object(review, "STATE_FILE", output / "research_gate_ui_state.json")
        )
        stack.enter_context(
            patch.object(review, "SUMMARY_FILE", output / "research_gate_summary.json")
        )
        stack.enter_context(patch.object(review, "load_config", return_value=self.config()))

    def criteria(self):
        return {name: True for name in self.config()["required_accept_criteria"]}

    def test_prepare_exposes_pending_claim(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            path = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
            path.write_text(json.dumps(self.package()), encoding="utf-8")

            snapshot = review.prepare_state()

        self.assertEqual(snapshot["status"], "AWAITING_HUMAN_DECISION")
        self.assertEqual(snapshot["pending"], 1)
        self.assertEqual(snapshot["claims"][0]["claim_id"], "clm001")

    def test_accept_completes_ready_for_story_script(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            path = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
            path.write_text(json.dumps(self.package()), encoding="utf-8")
            review.prepare_state()

            final = review.apply_action(
                concept_id="c1",
                claim_id="clm001",
                decision="ACCEPT",
                criteria=self.criteria(),
                note="",
            )

        self.assertTrue(final["complete"])
        self.assertEqual(final["ready_for_story_script"], 1)
        self.assertEqual(
            final["verified_packages"][0]["status"],
            "READY_FOR_STORY_SCRIPT",
        )

    def test_rework_requires_note(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            path = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
            path.write_text(json.dumps(self.package()), encoding="utf-8")
            review.prepare_state()

            with self.assertRaises(ValueError):
                review.apply_action(
                    concept_id="c1",
                    claim_id="clm001",
                    decision="REWORK",
                    criteria=self.criteria(),
                    note="",
                )


if __name__ == "__main__":
    unittest.main()
