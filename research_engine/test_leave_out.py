"""Claims the evidence cannot confirm are left out, not decided one by one (D-188)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from research_engine import research_gate
from research_engine import research_review as review
from research_engine import test_research_review as base

POLICY = {review.DECIDED_BY_ENV: "GATE_POLICY", review.REVIEWER_ENV: "gate-policy-auto"}


class LeaveOutTests(unittest.TestCase):
    config = base.ResearchReviewTests.config
    package = base.ResearchReviewTests.package
    patch_paths = base.ResearchReviewTests.patch_paths
    two_question_package = base.ResearchReviewTests.two_question_package
    write_draft = base.ResearchReviewTests.write_draft
    verified = base.ResearchReviewTests.verified

    def prepared(self, stack, root):
        """clm001 answers rq001; the weak clm002 is the only claim on rq002."""
        self.patch_paths(stack, root)
        self.write_draft(self.two_question_package())
        review.prepare_state()
        review.apply_action(concept_id="c1", claim_id="clm001", decision="ACCEPT", criteria={}, note="")

    def test_the_unconfirmed_claim_is_left_out_and_its_question_waived(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.prepared(stack, Path(tmp))
            with patch.dict(os.environ, POLICY):
                outcome = review.leave_out_unconfirmed()
            snapshot = review.snapshot()
            verified = self.verified()
            listed = review.left_out_claims("c1")
        self.assertEqual([item["claim_id"] for item in outcome["left_out"]], ["clm002"])
        self.assertEqual([item["question_id"] for item in outcome["waived"]], ["rq002"])
        self.assertEqual(outcome["packages"][0]["status"], "READY_FOR_STORY_SCRIPT")
        claim = next(item for item in snapshot["claims"] if item["claim_id"] == "clm002")
        self.assertEqual((claim["decision"], claim["decided_by"]), ("REJECT", "GATE_POLICY"))
        self.assertTrue(snapshot["complete"])
        self.assertEqual(verified["status"], "READY_FOR_STORY_SCRIPT")
        self.assertEqual([c["claim_id"] for c in verified["claims"]], ["clm001"])
        self.assertEqual(listed[0]["statement"], "A weak claim about how long it lasts.")
        self.assertIn("It is not used in the script.", listed[0]["reason"])

    def test_left_out_stays_left_out_across_prepares_and_the_package_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.prepared(stack, Path(tmp))
            with patch.dict(os.environ, POLICY):
                review.leave_out_unconfirmed()
            path = review.VERIFIED_DIR / "c1.verified_research_package.json"
            before = path.read_bytes()
            review.prepare_state()
            after = path.read_bytes()
            snapshot = review.snapshot()
        self.assertEqual(before, after)
        self.assertTrue(snapshot["complete"])

    def test_the_owner_can_still_accept_a_left_out_claim(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.prepared(stack, Path(tmp))
            with patch.dict(os.environ, POLICY):
                review.leave_out_unconfirmed()
            review.apply_action(concept_id="c1", claim_id="clm002", decision="ACCEPT", criteria={}, note="")
            listed = review.left_out_claims("c1")
            verified = self.verified()
        self.assertEqual(listed, [])
        self.assertEqual(sorted(c["claim_id"] for c in verified["claims"]), ["clm001", "clm002"])

    def test_the_evidence_policy_still_clears_a_left_out_claim_later(self):
        cleared = {"classification": review.AUTO_CLEARED, "reasons": ["Two independent sources."]}
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.prepared(stack, Path(tmp))
            with patch.dict(os.environ, POLICY):
                review.leave_out_unconfirmed()
            stack.enter_context(patch.object(review, "evaluate_claim", return_value=cleared))
            stack.enter_context(patch.object(research_gate, "evaluate_claim", return_value=cleared))
            snapshot = review.prepare_state()
        decided_by = {item["claim_id"]: item["decided_by"] for item in snapshot["claims"]}
        self.assertEqual(decided_by["clm002"], research_gate.POLICY_DECIDER)

    def test_the_title_promise_is_not_waived_so_a_thin_concept_shows_as_thin(self):
        package = self.two_question_package()
        package["research_questions"][1]["origin"] = "title_promise"
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            self.write_draft(package)
            review.prepare_state()
            review.apply_action(concept_id="c1", claim_id="clm001", decision="ACCEPT", criteria={}, note="")
            with patch.dict(os.environ, POLICY):
                outcome = review.leave_out_unconfirmed()
        self.assertEqual(outcome["waived"], [])
        self.assertEqual(outcome["packages"][0]["status"], research_gate.TOO_THIN)
        self.assertTrue(outcome["packages"][0]["evidence_shortfalls"])

    def test_an_automatic_drop_is_recorded_as_the_gate_policy(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.prepared(stack, Path(tmp))
            with patch.dict(os.environ, POLICY):
                review.drop_concept(concept_id="c1", note="Dropped automatically: too thin.")
            registry = json.loads(review.research_plans.DROPPED_FILE.read_text(encoding="utf-8"))
        self.assertEqual(registry["concepts"]["c1"]["decided_by"], "GATE_POLICY")

    def test_the_gate_policy_may_never_accept_a_claim(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            self.write_draft(self.two_question_package())
            review.prepare_state()
            request = review.build_requests()[0]["request"]
            decisions = [
                {"claim_id": item["claim_id"], "decision": "ACCEPT", "note": "",
                 "criteria": {name: True for name in self.config()["required_accept_criteria"]},
                 "decided_by": research_gate.LEFT_OUT_DECIDER}
                for item in request["items"]
            ]
            with self.assertRaisesRegex(ValueError, "only leave"):
                research_gate.validate_decisions(
                    request, {"concept_id": "c1", "reviewer": "x", "decisions": decisions}, self.config()
                )


if __name__ == "__main__":
    unittest.main()
