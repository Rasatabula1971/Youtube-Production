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

    def two_question_package(self, *, weak_claim=True):
        package = self.package()
        package["research_questions"].append(
            {"question_id": "rq002", "question": "How long does it last?", "origin": "concept"}
        )
        if weak_claim:
            package["claims"].append(
                {
                    **package["claims"][0],
                    "claim_id": "clm002",
                    "statement": "A weak claim about how long it lasts.",
                    "question_ids": ["rq002"],
                }
            )
        return package

    def prepared_with_unanswered_question(self, stack, root):
        """One accepted claim, and a rejected claim on the second question."""
        self.patch_paths(stack, root)
        path = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
        path.write_text(json.dumps(self.two_question_package()), encoding="utf-8")
        review.prepare_state()
        review.apply_action(
            concept_id="c1", claim_id="clm002", decision="REJECT", criteria={}, note="Too weak."
        )
        return review.apply_action(
            concept_id="c1", claim_id="clm001", decision="ACCEPT", criteria={}, note=""
        )

    def test_coverage_says_in_plain_words_why_the_concept_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            final = self.prepared_with_unanswered_question(stack, Path(tmp))
        coverage = final["question_coverage"][0]
        self.assertFalse(coverage["ready"])
        self.assertEqual(coverage["pending_claims"], 0)
        self.assertEqual(coverage["accepted_claims"], 1)
        self.assertIn("1 question unanswered", coverage["summary"])
        self.assertIn("Not needed for script", coverage["summary"])

    def test_question_no_claim_refers_to_is_waived_automatically(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            path = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
            path.write_text(json.dumps(self.two_question_package(weak_claim=False)), encoding="utf-8")
            prepared = review.prepare_state()
            self.assertIn("1 claim to decide", prepared["question_coverage"][0]["summary"])
            final = review.apply_action(
                concept_id="c1", claim_id="clm001", decision="ACCEPT", criteria={}, note=""
            )
            verified = json.loads(
                (review.VERIFIED_DIR / "c1.verified_research_package.json").read_text()
            )
            history = [
                json.loads(line)
                for line in review.history_file().read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        question = next(q for q in final["question_coverage"][0]["questions"] if q["question_id"] == "rq002")
        self.assertEqual(question["status"], "WAIVED")
        self.assertEqual(question["waiver"]["decided_by"], review.POLICY_DECIDER)
        self.assertIn("no claim", question["waiver"]["note"])
        self.assertEqual(final["ready_for_story_script"], 1)
        self.assertEqual(verified["status"], "READY_FOR_STORY_SCRIPT")
        self.assertEqual(verified["waived_question_ids"], ["rq002"])
        self.assertEqual(final["question_coverage"][0]["summary"], "Ready for the script. 1 question was waived.")
        events = [e for e in history if e.get("decision") == "WAIVE_QUESTION"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["decided_by"], review.POLICY_DECIDER)

    def test_an_unchanged_automatic_waiver_leaves_the_verified_package_unchanged(self):
        """Audit 2: a new waived_at on every prepare made every downstream script stale."""
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            path = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
            path.write_text(json.dumps(self.two_question_package(weak_claim=False)), encoding="utf-8")
            review.prepare_state()
            review.apply_action(concept_id="c1", claim_id="clm001", decision="ACCEPT", criteria={}, note="")
            verified = review.VERIFIED_DIR / "c1.verified_research_package.json"
            first = verified.read_bytes()
            review.prepare_state()
            review.prepare_state()
            self.assertEqual(verified.read_bytes(), first)

    def test_removing_an_automatic_waiver_sticks_across_prepares(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            path = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
            path.write_text(json.dumps(self.two_question_package(weak_claim=False)), encoding="utf-8")
            review.prepare_state()
            undone = review.apply_question_waiver(
                concept_id="c1", question_id="rq002", waive=False, note=None
            )
            again = review.prepare_state()
            rewaived = review.apply_question_waiver(
                concept_id="c1", question_id="rq002", waive=True, note="Fine after all."
            )
        for snapshot in (undone, again):
            statuses = {q["question_id"]: q["status"] for q in snapshot["question_coverage"][0]["questions"]}
            self.assertEqual(statuses["rq002"], "UNANSWERED")
        question = next(q for q in rewaived["question_coverage"][0]["questions"] if q["question_id"] == "rq002")
        self.assertEqual(question["waiver"]["decided_by"], "HUMAN")

    def test_unsourced_question_from_acquisition_is_waived_with_the_rounds(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            path = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
            path.write_text(json.dumps(self.two_question_package()), encoding="utf-8")
            evidence = review.evidence_file("c1")
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(
                json.dumps(
                    {
                        "concept_id": "c1",
                        "status": "COMPLETE",
                        "unsourced_question_ids": ["rq002"],
                        "search_rounds": {"rq001": 2, "rq002": 2},
                    }
                ),
                encoding="utf-8",
            )
            prepared = review.prepare_state()
        question = next(q for q in prepared["question_coverage"][0]["questions"] if q["question_id"] == "rq002")
        self.assertEqual(question["status"], "WAIVED")
        self.assertIn("after 2 search rounds", question["waiver"]["note"])

    def test_automatic_waivers_can_be_switched_off(self):
        config = {**self.config(), "auto_waive_questions": {"enabled": False}}
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            stack.enter_context(patch.object(review, "load_config", return_value=config))
            path = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
            path.write_text(json.dumps(self.two_question_package(weak_claim=False)), encoding="utf-8")
            prepared = review.prepare_state()
        statuses = {q["question_id"]: q["status"] for q in prepared["question_coverage"][0]["questions"]}
        self.assertEqual(statuses["rq002"], "UNANSWERED")

    def test_coverage_names_unanswered_question(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            final = self.prepared_with_unanswered_question(stack, Path(tmp))
        self.assertFalse(final["complete"])
        self.assertEqual(final["status"], "AWAITING_HUMAN_DECISION")
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

    def second_package(self):
        package = self.package()
        package["concept_id"] = "c2"
        package["concept"] = {"working_title": "Second concept"}
        package["claims"].append(
            {
                **package["claims"][0],
                "claim_id": "clm002",
                "statement": "A second bounded claim.",
            }
        )
        return package

    def write_drafts(self, *packages):
        for package in packages:
            path = review.DEFAULT_DRAFTS_DIR / f"{package['concept_id']}.draft_research_package.json"
            path.write_text(json.dumps(package), encoding="utf-8")

    def test_ready_concept_goes_ahead_while_another_is_pending(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            self.write_drafts(self.package(), self.second_package())
            review.prepare_state()
            snap = review.apply_action(
                concept_id="c1", claim_id="clm001", decision="ACCEPT", criteria={}, note=""
            )
            c1_path = review.VERIFIED_DIR / "c1.verified_research_package.json"
            c1_bytes = c1_path.read_bytes()
            c2_exists = (review.VERIFIED_DIR / "c2.verified_research_package.json").exists()
            review.apply_action(
                concept_id="c2", claim_id="clm001", decision="ACCEPT", criteria={}, note=""
            )
            c1_after_c2_action = c1_path.read_bytes()
            final = review.apply_action(
                concept_id="c2", claim_id="clm002", decision="ACCEPT", criteria={}, note=""
            )
        self.assertFalse(snap["complete"])
        self.assertEqual(snap["ready_for_story_script"], 1)
        self.assertEqual(
            [item["concept_id"] for item in snap["verified_packages"]], ["c1"]
        )
        self.assertFalse(c2_exists)
        self.assertEqual(c1_bytes, c1_after_c2_action)
        self.assertTrue(final["complete"])
        self.assertEqual(final["ready_for_story_script"], 2)

    def test_changing_a_decision_after_completion_reopens_the_concept(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            self.write_drafts(self.package())
            review.prepare_state()
            done = review.apply_action(
                concept_id="c1", claim_id="clm001", decision="ACCEPT", criteria={}, note=""
            )
            changed = review.apply_action(
                concept_id="c1", claim_id="clm001", decision="REJECT", criteria={}, note="No."
            )
        self.assertTrue(done["complete"])
        self.assertFalse(changed["complete"])
        self.assertEqual(changed["verified_packages"][0]["status"], "RESEARCH_INCOMPLETE")

    def test_rework_carries_accepted_claims_into_the_plan(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            package = self.second_package()
            package["concept_id"] = "c1"
            self.write_drafts(package)
            plan_path = review.OUTPUT_DIR / "plans" / "c1.research_plan.json"
            plan_path.write_text(
                json.dumps({"concept_id": "c1", "research_questions": package["research_questions"]}),
                encoding="utf-8",
            )
            review.prepare_state()
            review.apply_action(
                concept_id="c1", claim_id="clm001", decision="ACCEPT", criteria={}, note=""
            )
            review.apply_action(
                concept_id="c1", claim_id="clm002", decision="REWORK", criteria={}, note="Find a stronger source."
            )
            plan = json.loads(plan_path.read_text())
        carried = plan["carried_claims"]
        self.assertEqual([entry["claim"]["claim_id"] for entry in carried], ["clm001"])
        self.assertEqual(carried[0]["sources"][0]["source_id"], "web001")

    def test_carried_claim_is_accepted_automatically_after_regeneration(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            package = self.package()
            carried = dict(package["claims"][0])
            carried["claim_id"] = "kept_clm001"
            carried["carried_from_review"] = {"original_claim_id": "clm001", "reason": "x"}
            package["claims"] = [carried]
            self.write_drafts(package)
            snap = review.prepare_state()
        claim = snap["claims"][0]
        self.assertEqual(claim["decision"], "ACCEPT")
        self.assertIn("carried forward", claim["note"])
        self.assertTrue(snap["complete"])

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
