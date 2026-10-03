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
        plans = output / "plans"
        for path in (drafts, requests, reviewed, verified, plans):
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
        stack.enter_context(
            patch.object(review, "load_config", return_value=self.config())
        )

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

    def two_question_package(self):
        package = self.package()
        package["research_questions"].append(
            {"question_id": "rq002", "question": "How long does it last?", "origin": "concept"}
        )
        return package

    def prepared_with_unanswered_question(self, stack, root):
        self.patch_paths(stack, root)
        path = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
        path.write_text(json.dumps(self.two_question_package()), encoding="utf-8")
        review.prepare_state()
        return review.apply_action(
            concept_id="c1", claim_id="clm001", decision="ACCEPT", criteria={}, note=""
        )

    def test_coverage_names_unanswered_question(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            final = self.prepared_with_unanswered_question(stack, Path(tmp))
        self.assertTrue(final["complete"])
        self.assertEqual(final["verified_packages"][0]["status"], "RESEARCH_INCOMPLETE")
        coverage = final["question_coverage"][0]
        self.assertEqual(coverage["unanswered"], 1)
        statuses = {q["question_id"]: q["status"] for q in coverage["questions"]}
        self.assertEqual(statuses, {"rq001": "ANSWERED", "rq002": "UNANSWERED"})

    def test_waiving_unanswered_question_makes_package_ready(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.prepared_with_unanswered_question(stack, Path(tmp))
            with self.assertRaisesRegex(ValueError, "note"):
                review.apply_question_waiver(
                    concept_id="c1", question_id="rq002", waive=True, note=" "
                )
            final = review.apply_question_waiver(
                concept_id="c1",
                question_id="rq002",
                waive=True,
                note="No reliable source; the script will not mention lifespan.",
            )
            verified = json.loads(
                (review.VERIFIED_DIR / "c1.verified_research_package.json").read_text()
            )
            undone = review.apply_question_waiver(
                concept_id="c1", question_id="rq002", waive=False, note=None
            )
        self.assertEqual(final["ready_for_story_script"], 1)
        self.assertEqual(verified["status"], "READY_FOR_STORY_SCRIPT")
        self.assertEqual(verified["waived_question_ids"], ["rq002"])
        waived = next(q for q in verified["question_status"] if q["question_id"] == "rq002")
        self.assertEqual(waived["status"], "WAIVED_NOT_FOR_SCRIPT")
        self.assertIn("lifespan", waived["waiver"]["note"])
        self.assertEqual(undone["ready_for_story_script"], 0)

    def test_only_original_questions_can_be_waived(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.prepared_with_unanswered_question(stack, Path(tmp))
            with self.assertRaisesRegex(ValueError, "original research question"):
                review.apply_question_waiver(
                    concept_id="c1", question_id="hrw_clm001", waive=True, note="x"
                )

    def test_waiver_survives_reprepare_but_not_a_changed_question(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.prepared_with_unanswered_question(stack, Path(tmp))
            review.apply_question_waiver(
                concept_id="c1", question_id="rq002", waive=True, note="Not needed."
            )
            again = review.prepare_state()
            self.assertEqual(
                {q["question_id"]: q["status"] for q in again["question_coverage"][0]["questions"]}["rq002"],
                "WAIVED",
            )
            package = self.two_question_package()
            package["research_questions"][1]["question"] = "A different question?"
            path = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
            path.write_text(json.dumps(package), encoding="utf-8")
            changed = review.prepare_state()
        self.assertEqual(
            {q["question_id"]: q["status"] for q in changed["question_coverage"][0]["questions"]}["rq002"],
            "UNANSWERED",
        )

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
                criteria={},
                note="",
            )

        self.assertTrue(final["complete"])
        self.assertEqual(final["ready_for_story_script"], 1)
        self.assertEqual(
            final["verified_packages"][0]["status"],
            "READY_FOR_STORY_SCRIPT",
        )

    def test_accept_is_one_click_and_records_audit_criteria(self):
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
                criteria={},
                note="",
            )

        claim = final["claims"][0]
        self.assertEqual(claim["decision"], "ACCEPT")
        self.assertTrue(all(claim["criteria_decisions"].values()))

    def test_rework_writes_authoritative_instruction_into_research_plan(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            draft = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
            draft.write_text(json.dumps(self.package()), encoding="utf-8")
            plan_path = review.OUTPUT_DIR / "plans" / "c1.research_plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "concept_id": "c1",
                        "research_questions": [
                            {
                                "question_id": "rq001",
                                "question": "What causes it?",
                                "origin": "concept",
                            }
                        ],
                        "instructions": [],
                    }
                ),
                encoding="utf-8",
            )
            before_hash = review.sha256_file(plan_path)
            review.prepare_state()

            review.apply_action(
                concept_id="c1",
                claim_id="clm001",
                decision="REWORK",
                criteria={},
                note="Find a stronger source and verify the exact operating limit.",
            )
            updated = json.loads(plan_path.read_text(encoding="utf-8"))
            after_hash = review.sha256_file(plan_path)

        self.assertNotEqual(before_hash, after_hash)
        self.assertEqual(updated["human_rework_mode"], "HUMAN_INSTRUCTION_ONLY")
        self.assertEqual(updated["human_rework_requests"][0]["claim_id"], "clm001")
        self.assertEqual(
            updated["human_rework_requests"][0]["note"],
            "Find a stronger source and verify the exact operating limit.",
        )
        rework_questions = [
            item
            for item in updated["research_questions"]
            if item.get("origin") == "human_rework"
        ]
        self.assertEqual(len(rework_questions), 1)
        self.assertEqual(rework_questions[0]["rework_claim_id"], "clm001")

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
                    criteria={},
                    note="",
                )


if __name__ == "__main__":
    unittest.main()
