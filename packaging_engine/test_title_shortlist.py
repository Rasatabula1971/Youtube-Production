"""The 2–3 title shortlist and its use at the Final Packaging Gate (D-134)."""

from __future__ import annotations

import unittest

import final_packaging_review as fpr
import test_final_packaging_review as gate_tests
from test_final_packaging_review import CRITERIA, approval, package
from title_shortlist import build_shortlist, title_similarity

DIAG = {"title_strength": 4, "clarity": 4, "credibility": 4, "promise_alignment": 4}


def pkg(title_id, thumbnail_id, status="PASS", text=None, quality=4, selected=False):
    return package(
        "c1:long_form",
        title_id,
        thumbnail_id,
        status=status,
        title_text=text or f"Title {title_id}",
        selected_title_direction_match=selected,
        diagnostics={key: quality for key in DIAG},
    )


class ShortlistTests(unittest.TestCase):
    def test_chosen_direction_leads_then_pass_count_then_quality(self):
        packages = [
            pkg("t1", "a", selected=True, text="Why brakes glow red"),
            pkg("t1", "b", status="REWORK", selected=True, text="Why brakes glow red"),
            pkg("t2", "a", text="The rotor that survives fire", quality=3),
            pkg("t2", "b", text="The rotor that survives fire", quality=3),
            pkg("t3", "a", text="Carbon discs hate the cold", quality=5),
            pkg("t4", "a", status="REWORK", text="Ceramic pads under stress"),
            pkg("t5", "a", text="Pit crews and heat soak", quality=2),
        ]
        shortlist = build_shortlist(packages)
        self.assertEqual(shortlist["title_ids"], ["t1", "t2", "t3"])
        self.assertIn("your chosen title direction", shortlist["entries"][0]["reason"])
        self.assertIn("passes with 2 of 2 thumbnails", shortlist["entries"][1]["reason"])
        self.assertEqual(shortlist["excluded"]["t4"]["reason"], "NO_PASSING_PAIR")
        self.assertEqual(shortlist["excluded"]["t5"]["reason"], "BELOW_SHORTLIST_CUTOFF")
        self.assertEqual(shortlist["shortfall"], 0)

    def test_restated_titles_never_share_the_shortlist(self):
        self.assertGreaterEqual(title_similarity("Why F1 brakes glow red", "Why do F1 brakes glow red?"), 0.5)
        packages = [
            pkg("t1", "a", text="Why F1 brakes glow red", selected=True),
            pkg("t2", "a", text="Why do F1 brakes glow red?"),
            pkg("t3", "a", text="The rotor that survives fire"),
        ]
        shortlist = build_shortlist(packages)
        self.assertEqual(shortlist["title_ids"], ["t1", "t3"])
        self.assertEqual(shortlist["excluded"]["t2"]["duplicate_of"], "t1")

    def test_shortfall_is_stated_not_filled(self):
        packages = [pkg("t1", "a"), pkg("t2", "a", status="REJECT")]
        shortlist = build_shortlist(packages)
        self.assertEqual(shortlist["title_ids"], ["t1"])
        self.assertEqual(shortlist["shortfall"], 1)
        self.assertIn("needs 2", shortlist["note"])


class GateShortlistTests(unittest.TestCase):
    def setUp(self):
        self.case = gate_tests.FinalPackagingGateTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.case.config["title_shortlist"] = {"target": 1, "minimum": 1, "near_duplicate_threshold": 0.5}
        self.case.approvals[approval("c1:long_form", "lth2")["render_id"]] = approval("c1:long_form", "lth2")

    def test_packages_are_marked_and_outside_titles_need_a_note(self):
        payload = fpr.public_snapshot()
        item = next(x for x in payload["items"] if x["video_id"] == "c1:long_form")
        self.assertEqual(item["title_shortlist"]["title_ids"], ["lt1"])
        marks = {p["package_id"]: p["in_title_shortlist"] for p in item["packages"]}
        self.assertTrue(marks["package-lt1--lth1"])
        self.assertFalse(marks["package-lt2--lth1"])
        self.assertTrue(item["packages"][0]["in_title_shortlist"])
        with self.assertRaisesRegex(ValueError, "outside the shortlist"):
            fpr.apply_action(
                video_id="c1:long_form", decision="ACCEPT", package_id="package-lt2--lth1", criteria=CRITERIA
            )
        result = fpr.apply_action(
            video_id="c1:long_form",
            decision="ACCEPT",
            package_id="package-lt2--lth1",
            criteria=CRITERIA,
            note="The shorter title reads better on mobile.",
        )
        decided = next(x for x in result["items"] if x["video_id"] == "c1:long_form")
        self.assertEqual(decided["decision"], "ACCEPT")
        state = fpr._load_state()
        self.assertFalse(state["decisions"]["c1:long_form"]["title_in_shortlist"])


if __name__ == "__main__":
    unittest.main()
