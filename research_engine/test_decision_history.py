"""Append-only Research Gate decision history (D-133)."""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path

import research_review as review
import test_evidence_policy as policy_tests
from pipeline_integrity import append_jsonl, read_jsonl


class JsonlLogTests(unittest.TestCase):
    def test_append_never_rewrites_and_torn_lines_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "log" / "history.jsonl"
            append_jsonl(path, {"n": 1})
            first = path.read_bytes()
            append_jsonl(path, {"n": 2})
            self.assertTrue(path.read_bytes().startswith(first))
            with path.open("a", encoding="utf-8") as handle:
                handle.write('{"n": 3')  # a write cut off by a crash
            self.assertEqual([record["n"] for record in read_jsonl(path)], [1, 2])
            self.assertEqual(read_jsonl(Path(tmp) / "missing.jsonl"), [])


class ResearchHistoryTests(unittest.TestCase):
    fixture = policy_tests.ConditionalReviewTests

    def setUp(self):
        self.case = self.fixture()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)

    def history(self):
        return read_jsonl(review.history_file())

    def test_every_human_decision_is_kept_in_order(self):
        self.case.prepared(self.stack, Path(self.tmp.name), self.case.package())
        review.apply_action(concept_id="c1", claim_id="clm001", decision="ACCEPT", criteria={}, note="")
        snapshot = review.apply_action(
            concept_id="c1", claim_id="clm001", decision="REJECT", criteria={}, note="Changed my mind."
        )
        events = self.history()
        self.assertEqual([event["decision"] for event in events], ["ACCEPT", "REJECT"])
        self.assertEqual(events[1]["previous_decision"], "ACCEPT")
        self.assertEqual(events[1]["note"], "Changed my mind.")
        self.assertEqual(events[0]["gate"], "research")
        # The live state holds only the latest; the snapshot shows the whole trail.
        self.assertEqual(snapshot["claims"][0]["decision"], "REJECT")
        self.assertEqual(len(snapshot["claims"][0]["decision_history"]), 2)

    def test_automatic_acceptance_is_logged_once_and_its_withdrawal_too(self):
        self.case.prepared(self.stack, Path(self.tmp.name), self.case.strong_package())
        review.prepare_state()  # unchanged: no second record
        self.assertEqual(
            [(event["decision"], event["decided_by"]) for event in self.history()],
            [("ACCEPT", "EVIDENCE_POLICY")],
        )
        weaker = self.case.strong_package()
        weaker["claims"][0]["evidence_links"].pop()
        path = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
        path.write_text(json.dumps(weaker), encoding="utf-8")
        review.prepare_state()
        self.assertEqual(self.history()[-1]["decision"], "WITHDRAWN")

    def test_a_changed_claim_that_still_clears_logs_withdrawal_then_acceptance(self):
        self.case.prepared(self.stack, Path(self.tmp.name), self.case.strong_package())
        changed = self.case.strong_package()
        changed["claims"][0]["statement"] = "A bounded factual claim, restated."
        path = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
        path.write_text(json.dumps(changed), encoding="utf-8")
        review.prepare_state()
        self.assertEqual(
            [event["decision"] for event in self.history()],
            ["ACCEPT", "WITHDRAWN", "ACCEPT"],
        )

    def test_waivers_are_logged(self):
        package = self.case.package()
        package["research_questions"].append({"question_id": "rq002", "question": "How long?"})
        self.case.prepared(self.stack, Path(self.tmp.name), package)
        review.apply_question_waiver(concept_id="c1", question_id="rq002", waive=True, note="Not knowable.")
        review.apply_question_waiver(concept_id="c1", question_id="rq002", waive=False, note=None)
        # No claim refers to rq002, so the policy waived it first (D-163);
        # the person's waiver and its removal follow.
        self.assertEqual(
            [(event["decision"], event["decided_by"]) for event in self.history()],
            [
                ("WAIVE_QUESTION", review.POLICY_DECIDER),
                ("WAIVE_QUESTION", "HUMAN"),
                ("UNWAIVE_QUESTION", "HUMAN"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
