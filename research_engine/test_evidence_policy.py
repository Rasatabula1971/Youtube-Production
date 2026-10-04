"""Conditional research review: the evidence policy and its gate wiring (D-131)."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

import research_gate
import research_review as review
from evidence_policy import (
    AUTO_CLEARED,
    BLOCKED,
    REVIEW_REQUIRED,
    evaluate_claim,
    policy_fingerprint,
    policy_settings,
)
import test_research_review as base

SETTINGS = policy_settings({})


def link(url, quote, stance="SUPPORTS", source_type="primary"):
    return {
        "source_id": url,
        "stance": stance,
        "locator": "Section 1",
        "evidence_quote": quote,
        "source": {"title": "T", "publisher": "P", "url": url, "source_type": source_type},
    }


def item(statement="Owls have serrated feather edges that break up air flow.", evidence=None, state="CORROBORATED"):
    return {
        "claim_id": "clm001",
        "statement": statement,
        "coverage": {"state": state},
        "evidence": evidence
        if evidence is not None
        else [
            link("https://www.example.org/owls", "Serrated edges break up turbulent air."),
            link("https://university.edu/flight", "The feather fringe reduces noise by 18 dB."),
        ],
    }


class PolicyTests(unittest.TestCase):
    def classify(self, claim):
        return evaluate_claim(claim, SETTINGS)

    def test_strong_plain_claim_clears_with_reasons(self):
        result = self.classify(item())
        self.assertEqual(result["classification"], AUTO_CLEARED)
        self.assertIn("2 independent websites", result["reasons"][0])

    def test_no_traceable_support_is_blocked(self):
        claim = item(evidence=[link("https://a.org", "", stance="SUPPORTS")])
        self.assertEqual(self.classify(claim)["classification"], BLOCKED)
        claim = item(evidence=[link("https://a.org", "Quote.", stance="CONTRADICTS")])
        self.assertEqual(self.classify(claim)["classification"], BLOCKED)

    def assert_review(self, claim, fragment):
        result = self.classify(claim)
        self.assertEqual(result["classification"], REVIEW_REQUIRED)
        self.assertTrue(any(fragment in reason for reason in result["reasons"]), result["reasons"])

    def test_each_review_condition_names_its_reason(self):
        two = item()["evidence"]
        self.assert_review(item(evidence=two[:1]), "Weak evidence: supported by 1")
        # Two pages of one website are not independent.
        self.assert_review(
            item(evidence=[link("https://example.org/a", "Q."), link("https://www.example.org/b", "Q.")]),
            "Weak evidence",
        )
        self.assert_review(item(state="CONFLICTED"), "contradicts")
        self.assert_review(item(evidence=two + [link("https://c.org", "Q.", stance="CONTRADICTS")]), "contradicts")
        self.assert_review(item(evidence=two + [link("https://c.org", "Q.", stance="QUALIFIES")]), "qualifies")
        self.assert_review(
            item(evidence=[two[0], link("https://blog.net", "Q.", source_type="expert_statement")]),
            "expert_statement",
        )
        self.assert_review(item("Owls are always silent in flight."), "Absolute wording needs care: always")
        self.assert_review(item("The fringe cuts noise by 25 dB."), "not in any quoted evidence: 25")
        self.assert_review(item("Owl feathers can cause injuries to handlers."), "Elevated risk (injur")

    def test_one_work_mirrored_on_two_sites_counts_once(self):
        quote = "The highest increase in vibration amplitude occurred on the steering wheel."
        mirror = link("https://exa.ai/library/publication/x", quote)
        doi = link("https://doi.org/10.14669/AM.VOL94.ART5", quote)
        self.assert_review(item(evidence=[mirror, doi]), "Weak evidence: supported by 1")
        title = "Assessment of the effect of passenger car wheel unbalance on driving comfort"
        a = link("https://exa.ai/a", "Quote one.")
        b = link("https://doi.org/b", "Quote two.")
        a["source"]["title"] = b["source"]["title"] = title
        self.assert_review(item(evidence=[a, b]), "Weak evidence: supported by 1")

    def test_risk_terms_match_whole_words(self):
        for statement in (
            "Experimental investigations show the steering wheel shakes at speed.",
            "A diesel engine idles with a steady vibration.",
        ):
            with self.subTest(statement=statement):
                self.assertEqual(self.classify(item(statement))["classification"], AUTO_CLEARED)
        self.assert_review(item("Owls do not affect pregnancy outcomes."), "Elevated risk (pregnan")
        self.assert_review(item("Investors watch tyre makers closely."), "Elevated risk (investors")

    def test_quoted_figures_are_fine(self):
        self.assertEqual(self.classify(item("The fringe reduces noise by 18 dB."))["classification"], AUTO_CLEARED)

    def test_settings_merge_and_fingerprint(self):
        settings = policy_settings({"evidence_policy": {"minimum_independent_supporting_hosts": 1}})
        self.assertEqual(settings["minimum_independent_supporting_hosts"], 1)
        self.assertIn("always", settings["absolute_terms"])
        self.assertNotEqual(policy_fingerprint(settings), policy_fingerprint(SETTINGS))
        one = item(evidence=item()["evidence"][:1])
        self.assertEqual(evaluate_claim(one, settings)["classification"], AUTO_CLEARED)


class ConditionalReviewTests(unittest.TestCase):
    """Runs the Research Review flow with a package the policy can clear."""

    # The Research Review fixtures, without inheriting (and re-running) its tests.
    config = base.ResearchReviewTests.config
    package = base.ResearchReviewTests.package
    patch_paths = base.ResearchReviewTests.patch_paths

    def strong_package(self):
        package = self.package()
        package["sources"].append(
            {
                "source_id": "web002",
                "title": "Second",
                "publisher": "Other",
                "url": "https://other.org/page",
                "source_type": "secondary",
            }
        )
        claim = package["claims"][0]
        claim["evidence_links"].append(
            {
                "source_id": "web002",
                "stance": "SUPPORTS",
                "locator": "Para 2",
                "evidence_note": "Independent confirmation.",
                "evidence_quote": "An independent page confirms the bounded claim.",
            }
        )
        claim["coverage"] = {"state": "CORROBORATED"}
        return package

    def prepared(self, stack, root, package):
        self.patch_paths(stack, root)
        path = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
        path.write_text(json.dumps(package), encoding="utf-8")
        return review.prepare_state()

    def test_cleared_claim_completes_research_without_a_human(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            snapshot = self.prepared(stack, Path(tmp), self.strong_package())
            verified = json.loads(
                (review.VERIFIED_DIR / "c1.verified_research_package.json").read_text(encoding="utf-8")
            )
        self.assertTrue(snapshot["complete"])
        self.assertEqual(snapshot["pending"], 0)
        self.assertEqual(snapshot["auto_cleared"], 1)
        claim = snapshot["claims"][0]
        self.assertEqual((claim["decision"], claim["decided_by"]), ("ACCEPT", "EVIDENCE_POLICY"))
        self.assertTrue(claim["note"].startswith("Cleared automatically:"))
        self.assertEqual(verified["status"], "READY_FOR_STORY_SCRIPT")
        gate = verified["claims"][0]["research_gate"]
        self.assertEqual(gate["decided_by"], "EVIDENCE_POLICY")
        self.assertEqual(gate["reviewer"], "EVIDENCE_POLICY")
        self.assertTrue(gate["policy_reasons"])
        self.assertEqual(verified["research_gate"]["auto_cleared_claim_ids"], ["clm001"])

    def test_weak_claim_stays_with_the_human_and_says_why(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            snapshot = self.prepared(stack, Path(tmp), self.package())
        self.assertEqual(snapshot["pending"], 1)
        self.assertEqual(snapshot["auto_cleared"], 0)
        policy = snapshot["claims"][0]["evidence_policy"]
        self.assertEqual(policy["classification"], REVIEW_REQUIRED)
        self.assertIn("Weak evidence", policy["reasons"][0])

    def test_human_decision_wins_and_survives_reprepare(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.prepared(stack, Path(tmp), self.strong_package())
            review.apply_action(
                concept_id="c1", claim_id="clm001", decision="REJECT", criteria={}, note="Off topic."
            )
            snapshot = review.prepare_state()
        claim = snapshot["claims"][0]
        self.assertEqual((claim["decision"], claim["decided_by"]), ("REJECT", "HUMAN"))
        self.assertFalse(snapshot["complete"])

    def test_disabled_policy_leaves_every_claim_to_the_human(self):
        config = self.config()
        config["evidence_policy"] = {"enabled": False}
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.patch_paths(stack, Path(tmp))
            stack.enter_context(mock.patch.object(review, "load_config", return_value=config))
            path = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
            path.write_text(json.dumps(self.strong_package()), encoding="utf-8")
            snapshot = review.prepare_state()
        self.assertEqual(snapshot["pending"], 1)
        self.assertFalse(snapshot["evidence_policy_enabled"])

    def test_stale_automatic_decision_is_dropped_when_the_claim_weakens(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            self.prepared(stack, Path(tmp), self.strong_package())
            weaker = self.strong_package()
            weaker["claims"][0]["statement"] = "A bounded factual claim that always holds."
            path = review.DEFAULT_DRAFTS_DIR / "c1.draft_research_package.json"
            path.write_text(json.dumps(weaker), encoding="utf-8")
            snapshot = review.prepare_state()
        self.assertEqual(snapshot["pending"], 1)
        self.assertIn("always", " ".join(snapshot["claims"][0]["evidence_policy"]["reasons"]))


class GateValidationTests(unittest.TestCase):
    CONFIG = {
        "required_accept_criteria": ["source_traceable"],
        "require_reviewer_name": True,
        "require_conflict_resolution_note": True,
    }

    def request(self, claim):
        return {"concept_id": "c1", "items": [claim]}

    def response(self, decided_by):
        return {
            "concept_id": "c1",
            "reviewer": "me",
            "decisions": [
                {
                    "claim_id": "clm001",
                    "decision": "ACCEPT",
                    "criteria": {"source_traceable": True},
                    "note": "",
                    "decided_by": decided_by,
                }
            ],
        }

    def test_policy_can_only_accept_a_claim_it_clears_now(self):
        mapped = research_gate.validate_decisions(
            self.request(item()), self.response("EVIDENCE_POLICY"), self.CONFIG
        )
        self.assertEqual(mapped["clm001"]["decided_by"], "EVIDENCE_POLICY")
        self.assertTrue(mapped["clm001"]["policy_reasons"])
        weak = copy.deepcopy(item())
        weak["evidence"] = weak["evidence"][:1]
        with self.assertRaisesRegex(ValueError, "no longer holds"):
            research_gate.validate_decisions(self.request(weak), self.response("EVIDENCE_POLICY"), self.CONFIG)
        with self.assertRaisesRegex(ValueError, "decided_by"):
            research_gate.validate_decisions(self.request(item()), self.response("ROBOT"), self.CONFIG)

    def test_decisions_without_decided_by_are_human(self):
        response = self.response(None)
        mapped = research_gate.validate_decisions(self.request(item()), response, self.CONFIG)
        self.assertEqual(mapped["clm001"]["decided_by"], "HUMAN")


if __name__ == "__main__":
    unittest.main()
