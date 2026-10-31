"""The Short lane's automatic pick and its reserve (Two Lanes, D-188)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from transformation_engine import concept_review as review
from transformation_engine import test_concept_review as base

POLICY = {review.DECIDED_BY_ENV: "GATE_POLICY", review.REVIEWER_ENV: "gate-policy-auto"}


class ConceptReserveTests(unittest.TestCase):
    patch_paths = base.ConceptReviewTests.patch_paths
    candidates = base.ConceptReviewTests.candidates

    def prepared(self, stack, root):
        self.patch_paths(stack, root)
        review.DEFAULT_CANDIDATES.write_text(json.dumps(self.candidates()), encoding="utf-8")
        review.prepare_state()

    def handoff(self):
        return json.loads(review.RESEARCH_HANDOFF_FILE.read_text(encoding="utf-8"))

    def test_an_automatic_decision_says_so_and_a_human_one_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.prepared(stack, Path(tmp))
            with patch.dict(os.environ, POLICY):
                review.apply_action(concept_id="c1", decision="ACCEPT", criteria={}, note="auto")
            snapshot = review.apply_action(concept_id="c2", decision="ACCEPT", criteria={}, note="")
            handoff = self.handoff()
        by_id = {item["concept_id"]: item for item in snapshot["concepts"]}
        self.assertEqual(by_id["c1"]["decided_by"], "GATE_POLICY")
        self.assertEqual(by_id["c2"]["decided_by"], "HUMAN")
        gates = {item["concept_id"]: item["concept_gate"] for item in handoff["concepts"]}
        self.assertEqual(gates["c1"]["decided_by"], "GATE_POLICY")
        self.assertNotIn("decided_by", gates["c2"])

    def test_when_the_pick_is_dropped_the_next_reserve_concept_goes_to_research(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.prepared(stack, Path(tmp))
            with patch.dict(os.environ, POLICY):
                review.apply_action(concept_id="c1", decision="ACCEPT", criteria={}, note="pick")
                review.apply_action(concept_id="c2", decision="REJECT", criteria={}, note="reserve")
                review.record_lane_reserve(["c2"])
                self.assertEqual([item["concept_id"] for item in self.handoff()["concepts"]], ["c1"])
                promoted = review.promote_reserve(exclude={"c1"}, note="next after c1 was too thin")
                handoff = self.handoff()
                again = review.promote_reserve(exclude={"c1", "c2"}, note="x")
            snapshot = review.snapshot()
        self.assertEqual(promoted, "c2")
        self.assertEqual([item["concept_id"] for item in handoff["concepts"]], ["c1", "c2"])
        c2 = next(item for item in handoff["concepts"] if item["concept_id"] == "c2")
        self.assertEqual(c2["concept_gate"]["decided_by"], "GATE_POLICY")
        self.assertEqual(c2["concept_gate"]["note"], "next after c1 was too thin")
        self.assertIsNone(again)
        self.assertEqual(snapshot["lane_reserve"], [])
        self.assertTrue(snapshot["complete"])

    def test_the_reserve_survives_a_prepare(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.prepared(stack, Path(tmp))
            review.record_lane_reserve(["c2"])
            review.prepare_state()
            self.assertEqual(review.snapshot()["lane_reserve"], ["c2"])

    def test_nothing_is_promoted_before_the_gate_is_complete(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.prepared(stack, Path(tmp))
            with self.assertRaisesRegex(ValueError, "not complete"):
                review.promote_reserve(exclude=set(), note="x")


if __name__ == "__main__":
    unittest.main()
