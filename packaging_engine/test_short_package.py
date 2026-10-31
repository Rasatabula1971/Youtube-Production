"""A Short is packaged from its brief: chosen title, hook and promise (D-190, D-191)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import request_memo
from packaging_engine import (
    final_packaging_review,
    packaging_brief,
    short_lane,
    short_package,
)


def brief(fmt="short", concept_id="c_tyre", title=True):
    payload = {
        "artifact": "packaging_brief",
        "status": "PACKAGING_BRIEF_READY",
        "video_id": f"{concept_id}:{fmt}",
        "concept_id": concept_id,
        "format": fmt,
        "opening_hook": "You'd think a plane needs deep treads, but its tires are almost bald.",
        "search_vs_browse_intent": "BROWSE",
        "viewer_promise_contract": {"viewer_expectation": "Discover how bald-looking tires stop a plane."},
    }
    if title:
        payload["selected_title"] = {
            "title_id": "short-stakes",
            "title_text": "How Smooth Plane Tires Keep You Safe on Wet Runways",
            "psychological_angle": "stakes",
            "evidence_refs": ["cl_002"],
        }
    return payload


class ShortPackageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "c_tyre.short.packaging_brief.json"
        self.path.write_text(json.dumps(brief()), encoding="utf-8")

    def test_the_bundle_is_the_chosen_title_hook_and_promise_with_an_uploaded_thumbnail(self):
        bundle = short_package.build_bundle(self.path, brief())
        package = bundle["packages"]["short"]
        self.assertEqual(bundle["status"], "FINAL_PACKAGE_APPROVED")
        self.assertEqual(bundle["contract"], short_lane.CONTRACT)
        self.assertEqual(package["title_text"], "How Smooth Plane Tires Keep You Safe on Wet Runways")
        self.assertEqual(package["opening_hook"], brief()["opening_hook"])
        self.assertEqual(package["viewer_promise"], "Discover how bald-looking tires stop a plane.")
        self.assertEqual(package["thumbnail_source"], short_lane.UPLOADED)
        self.assertIsNone(package["thumbnail_image"])
        self.assertEqual(package["title_evidence_refs"], ["cl_002"])
        self.assertEqual(package["decision"]["decided_by"], "GATE_POLICY")

    def test_the_bundle_has_no_timestamp_so_its_hash_holds_while_the_brief_does(self):
        self.assertEqual(short_package.build_bundle(self.path, brief()), short_package.build_bundle(self.path, brief()))
        self.assertNotIn("reviewed_at", json.dumps(short_package.build_bundle(self.path, brief())))

    def test_no_chosen_title_means_no_package(self):
        with self.assertRaisesRegex(ValueError, "MISSING_SELECTED_TITLE"):
            short_package.build_bundle(self.path, brief(title=False))

    def test_a_long_form_brief_never_takes_the_short_lane(self):
        with self.assertRaisesRegex(ValueError, "Only a Short"):
            short_package.build_bundle(self.path, brief(fmt="long_form"))

    def test_the_lane_can_be_switched_off(self):
        with patch.object(short_lane, "settings", return_value={"enabled": False}):
            self.assertFalse(short_lane.is_short_lane(brief()))
        self.assertTrue(short_lane.is_short_lane(brief()))


class ChainTests(unittest.TestCase):
    def test_the_long_form_steps_never_see_a_short_brief(self):
        briefs = {"short.json": brief(), "long.json": brief(fmt="long_form", concept_id="c_long")}
        with patch.object(packaging_brief, "brief_is_current", side_effect=lambda path: briefs[Path(path).name]):
            self.assertIsNone(packaging_brief.chain_brief_is_current(Path("short.json")))
            self.assertEqual(packaging_brief.chain_brief_is_current(Path("long.json"))["format"], "long_form")

    def test_the_brief_snapshot_counts_long_form_and_short_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payloads = {
                "c_tyre.short.packaging_brief.json": brief(),
                "c_long.long_form.packaging_brief.json": brief(fmt="long_form", concept_id="c_long"),
            }
            for name, payload in payloads.items():
                (root / name).write_text(json.dumps(payload), encoding="utf-8")
            with (
                patch.object(packaging_brief, "BRIEF_DIR", root),
                patch.object(packaging_brief, "brief_is_current", side_effect=lambda path: payloads[Path(path).name]),
                patch.object(packaging_brief, "title_direction_snapshot", return_value={}),
            ):
                state = packaging_brief.snapshot()
        self.assertEqual((state["current"], state["chain_current"], state["short_lane_current"]), (2, 1, 1))

    def test_final_packaging_bundles_include_the_short_even_with_no_matrix(self):
        """The Aviation Tires Short stopped here: no thumbnail image, so no package."""
        short = {"concept_id": "c_tyre", "packages": {"short": {}}}
        with (
            patch.object(short_package, "current_bundles", return_value={"c_tyre": short}),
            patch.object(final_packaging_review, "snapshot", return_value={"status": "WAITING_FOR_PACKAGE_VALIDATION"}),
            request_memo.scope(),
        ):
            bundles = final_packaging_review.current_bundles()
        self.assertEqual(bundles, {"c_tyre": short})


if __name__ == "__main__":
    unittest.main()
