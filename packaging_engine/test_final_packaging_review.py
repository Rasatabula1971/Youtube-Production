import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import final_packaging_review as fpr
import script_review
import thumbnail_concepts
import title_direction_review

CRITERIA = {
    "title_and_thumbnail_read_as_one_unit": True,
    "single_clear_promise": True,
    "opening_hook_confirms_the_click": True,
    "script_delivers_the_promise": True,
    "claims_within_approved_evidence": True,
    "approved_image_is_the_thumbnail": True,
}


def package(video_id, title_id, thumbnail_id, status="PASS", **extra):
    concept_id, fmt = video_id.split(":")
    value = {
        "package_id": f"package-{title_id}--{thumbnail_id}",
        "video_id": video_id,
        "concept_id": concept_id,
        "format": fmt,
        "title_id": title_id,
        "title_text": f"Title {title_id}",
        "thumbnail_id": thumbnail_id,
        "thumbnail_text": f"TEXT {thumbnail_id}",
        "thumbnail_hero_subject": "glowing rotor",
        "angle_primary_driver": "curiosity",
        "selected_title_direction_match": title_id.endswith("1"),
        "validation_status": status,
        "viewer_promise": "Discover why brakes glow.",
        "opening_hook": "The rotor is 800 degrees.",
        "diagnostics": {"clarity": 4},
        "hard_validation_findings": [],
        "rework_findings": [],
        "request_sha256": "req",
        "response_sha256": "resp",
    }
    value.update(extra)
    return value


def approval(video_id, thumbnail_id, sha="img-1"):
    return {
        "render_id": f"{video_id}--{thumbnail_id}",
        "image": f"/tmp/{thumbnail_id}.jpg",
        "image_sha256": sha,
        "width": 1280,
        "height": 720,
        "template_id": "channel-v1",
        "subject_image": {"source_tier": "OWN_LIBRARY"},
    }


class FinalPackagingGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.config = copy.deepcopy(fpr.load_config())
        self.validations = [
            package("c1:long_form", "lt1", "lth1"),
            package("c1:long_form", "lt2", "lth1"),
            package("c1:long_form", "lt1", "lth2", status="REWORK"),
            package("c1:short", "st1", "sth1"),
            package("c1:short", "st2", "sth2", status="REJECT"),
        ]
        self.approvals = {
            a["render_id"]: a
            for a in (approval("c1:long_form", "lth1"), approval("c1:short", "sth1"))
        }
        for item in (
            patch.object(fpr, "STATE_FILE", root / "state.json"),
            patch.object(fpr, "FINAL_PACKAGES_DIR", root / "final_packages"),
            patch.object(fpr, "HISTORY_DIR", root / "history"),
            patch.object(fpr, "load_config", side_effect=lambda: self.config),
            patch.object(fpr, "current_validations", side_effect=lambda: self.validations),
            patch.object(fpr, "thumbnail_approvals", side_effect=lambda: self.approvals),
        ):
            item.start()
            self.addCleanup(item.stop)

    def item(self, payload, video_id):
        return next(x for x in payload["items"] if x["video_id"] == video_id)

    def accept_both(self):
        fpr.apply_action(
            video_id="c1:long_form",
            decision="ACCEPT",
            package_id="package-lt1--lth1",
            criteria=CRITERIA,
        )
        return fpr.apply_action(
            video_id="c1:short",
            decision="ACCEPT",
            package_id="package-st1--sth1",
            criteria=CRITERIA,
        )

    def test_waits_for_complete_validation(self):
        self.validations = None
        payload = fpr.public_snapshot()
        self.assertEqual(payload["status"], "WAITING_FOR_PACKAGE_VALIDATION")
        with self.assertRaises(ValueError):
            fpr.apply_action(video_id="c1:short", decision="REJECT")

    def test_snapshot_orders_pass_first_and_marks_acceptable(self):
        payload = fpr.public_snapshot()
        self.assertEqual(payload["status"], "AWAITING_HUMAN_FINAL_PACKAGING")
        self.assertNotIn("_validations", payload)
        long_item = self.item(payload, "c1:long_form")
        statuses = [p["validation_status"] for p in long_item["packages"]]
        self.assertEqual(statuses, ["PASS", "PASS", "REWORK"])
        self.assertEqual(long_item["packages"][0]["package_id"], "package-lt1--lth1")
        self.assertEqual(long_item["acceptable"], 2)
        rework = long_item["packages"][2]
        self.assertFalse(rework["acceptable"])
        self.assertIn("thumbnail image is not approved at the Thumbnail Gate", rework["blocked_reasons"])
        self.assertIn("approved_image_is_the_thumbnail", payload["required_criteria"])

    def test_accept_requires_pass_image_and_every_criterion(self):
        with self.assertRaisesRegex(ValueError, "not PASS"):
            fpr.apply_action(
                video_id="c1:long_form",
                decision="ACCEPT",
                package_id="package-lt1--lth2",
                criteria=CRITERIA,
            )
        missing = dict(CRITERIA, single_clear_promise=False)
        with self.assertRaisesRegex(ValueError, "single_clear_promise"):
            fpr.apply_action(
                video_id="c1:long_form",
                decision="ACCEPT",
                package_id="package-lt1--lth1",
                criteria=missing,
            )
        del self.approvals["c1:long_form--lth1"]
        with self.assertRaisesRegex(ValueError, "Thumbnail Gate"):
            fpr.apply_action(
                video_id="c1:long_form",
                decision="ACCEPT",
                package_id="package-lt1--lth1",
                criteria=CRITERIA,
            )

    def test_image_requirement_can_be_switched_off(self):
        self.config["require_approved_thumbnail_image"] = False
        self.approvals = {}
        payload = fpr.public_snapshot()
        self.assertNotIn("approved_image_is_the_thumbnail", payload["required_criteria"])
        fpr.apply_action(
            video_id="c1:long_form",
            decision="ACCEPT",
            package_id="package-lt2--lth1",
            criteria=CRITERIA,
        )
        self.assertEqual(self.item(fpr.public_snapshot(), "c1:long_form")["decision"], "ACCEPT")

    def test_bundle_written_only_when_every_format_accepted(self):
        fpr.apply_action(
            video_id="c1:long_form",
            decision="ACCEPT",
            package_id="package-lt1--lth1",
            criteria=CRITERIA,
        )
        self.assertIsNone(fpr.approved_bundle("c1"))
        self.assertFalse(fpr.bundle_path("c1").exists())

        payload = self.accept_both()
        self.assertEqual(payload["status"], "FINAL_PACKAGING_APPROVED")
        self.assertTrue(payload["ready"])
        path, bundle, digest = fpr.approved_bundle("c1")
        self.assertEqual(json.loads(path.read_text()), bundle)
        self.assertEqual(bundle["formats"], ["long_form", "short"])
        long_package = bundle["packages"]["long_form"]
        self.assertEqual(long_package["title_text"], "Title lt1")
        self.assertEqual(long_package["thumbnail_image"]["image_sha256"], "img-1")
        self.assertEqual(long_package["viewer_promise"], "Discover why brakes glow.")
        self.assertEqual(fpr.current_bundle_hashes(), {"c1": digest})
        self.assertEqual(len(list(fpr.HISTORY_DIR.glob("*.json"))), 3)

    def test_changed_image_or_package_makes_decision_stale(self):
        self.accept_both()
        self.approvals["c1:long_form--lth1"] = approval("c1:long_form", "lth1", sha="img-2")
        payload = fpr.public_snapshot()
        long_item = self.item(payload, "c1:long_form")
        self.assertEqual(long_item["decision"], "PENDING")
        self.assertTrue(long_item["stale_decision"])
        self.assertFalse(payload["ready"])
        self.assertIsNone(fpr.approved_bundle("c1"))
        self.assertFalse(fpr.bundle_path("c1").exists())

        self.approvals["c1:long_form--lth1"] = approval("c1:long_form", "lth1")
        self.validations[0] = dict(self.validations[0], title_text="Changed")
        self.assertEqual(self.item(fpr.public_snapshot(), "c1:long_form")["decision"], "PENDING")

    def test_reject_blocks_until_matrix_changes(self):
        fpr.apply_action(
            video_id="c1:long_form",
            decision="ACCEPT",
            package_id="package-lt1--lth1",
            criteria=CRITERIA,
        )
        payload = fpr.apply_action(video_id="c1:short", decision="REJECT", note="None fit.")
        self.assertEqual(payload["status"], "FINAL_PACKAGING_REJECTED")
        self.assertFalse(payload["ready"])
        self.validations.append(package("c1:short", "st3", "sth3"))
        payload = fpr.public_snapshot()
        self.assertEqual(self.item(payload, "c1:short")["decision"], "PENDING")
        self.assertEqual(payload["status"], "AWAITING_HUMAN_FINAL_PACKAGING")

    def test_rework_requires_target_and_note(self):
        with self.assertRaisesRegex(ValueError, "target"):
            fpr.apply_action(video_id="c1:short", decision="REWORK", note="x")
        with self.assertRaisesRegex(ValueError, "note"):
            fpr.apply_action(
                video_id="c1:short", decision="REWORK", rework_target="SCRIPT"
            )

    def test_rework_routes_to_the_chosen_layer(self):
        with patch.object(title_direction_review, "reopen_for_rework") as titles:
            fpr.apply_action(
                video_id="c1:short",
                decision="REWORK",
                rework_target="TITLE_DIRECTIONS",
                note="Lead with the temperature.",
            )
        titles.assert_called_once()
        self.assertEqual(titles.call_args.kwargs["concept_id"], "c1")
        self.assertIn("Lead with the temperature.", titles.call_args.kwargs["note"])
        self.assertIn("(short)", titles.call_args.kwargs["note"])

        concepts = {"c1:short": {"thumbnail_concepts": [{"thumbnail_id": "sth1"}]}}
        with (
            patch.object(fpr.package_pairing, "_current_thumbnail_items", return_value=concepts),
            patch.object(thumbnail_concepts, "request_rework") as thumbs,
        ):
            fpr.apply_action(
                video_id="c1:short",
                decision="REWORK",
                rework_target="THUMBNAIL_CONCEPTS",
                note="Simpler subject.",
            )
        self.assertEqual(thumbs.call_args.kwargs["video_id"], "c1:short")
        self.assertEqual(
            thumbs.call_args.kwargs["previous_concepts"], [{"thumbnail_id": "sth1"}]
        )

        with patch.object(script_review, "apply_action") as script:
            fpr.apply_action(
                video_id="c1:long_form",
                decision="REWORK",
                rework_target="SCRIPT",
                note="Hook must confirm the glow in the first line.",
            )
        self.assertEqual(script.call_args.kwargs["format"], "long_form")
        self.assertEqual(script.call_args.kwargs["decision"], "REWORK")

        state = json.loads(fpr.STATE_FILE.read_text())
        self.assertEqual(
            [r["rework_target"] for r in state["reworks"]],
            ["TITLE_DIRECTIONS", "THUMBNAIL_CONCEPTS", "SCRIPT"],
        )
        last = self.item(fpr.public_snapshot(), "c1:long_form")["last_rework"]
        self.assertEqual(last["rework_target"], "SCRIPT")

    def test_rework_withdraws_an_accepted_package(self):
        self.accept_both()
        with patch.object(script_review, "apply_action"):
            payload = fpr.apply_action(
                video_id="c1:short",
                decision="REWORK",
                rework_target="SCRIPT",
                note="Different payoff.",
            )
        self.assertEqual(self.item(payload, "c1:short")["decision"], "PENDING")
        self.assertFalse(fpr.bundle_path("c1").exists())


if __name__ == "__main__":
    unittest.main()
