from __future__ import annotations

import json
import shutil
import unittest
from urllib.parse import parse_qs, urlparse

from production_engine import thumbnail_review as review
from production_engine.test_thumbnail_render import (
    CAN_RENDER,
    TEMPLATE,
    PipelineTestCase,
    RID,
)

m = review.render


class ThumbnailReviewSnapshotTests(PipelineTestCase):
    def test_waiting_without_validated_packages(self):
        self.assertEqual(review.snapshot()["status"], "WAITING_FOR_VALIDATED_PACKAGES")

    def test_snapshot_lists_unrendered_package_before_any_spec(self):
        self.set_units()
        snapshot = review.snapshot()
        item = snapshot["items"][0]
        self.assertEqual(item["render_status"], "NOT_RENDERED")
        self.assertFalse(item["spec_ready"])
        self.assertEqual(item["accent_hex"], TEMPLATE["accent_names"]["blue"])
        self.assertEqual(item["decision"], "PENDING")
        self.assertIsNone(item["image_url"])
        self.assertEqual(snapshot["allowed_source_tiers"], TEMPLATE["subject_allowed_source_tiers"])

    def test_update_spec_creates_spec_and_validates(self):
        self.set_units()
        image = self.root / "s.png"
        image.write_bytes(b"x")
        with self.assertRaisesRegex(ValueError, "6-digit hex"):
            review.update_spec(render_id=RID, accent_hex="blue", subject_image={})
        with self.assertRaisesRegex(ValueError, "not permitted"):
            review.update_spec(
                render_id=RID,
                accent_hex="#FF0000",
                subject_image={"path": str(image), "source_tier": "EDITORIAL_EXCERPT", "license": "x"},
            )
        with self.assertRaisesRegex(ValueError, "Unknown or no longer validated"):
            review.update_spec(render_id="nope", accent_hex="FF0000", subject_image={})
        snapshot = review.update_spec(
            render_id=RID,
            accent_hex="#ff0000",
            subject_image={"path": str(image), "source_tier": "OWN_LIBRARY", "extra": "ignored"},
        )
        item = snapshot["items"][0]
        self.assertEqual(item["accent_hex"], "FF0000")
        self.assertEqual(item["subject_image"]["path"], str(image))
        self.assertNotIn("extra", item["subject_image"])

    def test_file_paths_are_restricted(self):
        self.set_units()
        with self.assertRaisesRegex(ValueError, "Unknown thumbnail file"):
            review.thumbnail_file_path(RID, "../render_spec.json")
        with self.assertRaisesRegex(ValueError, "Unknown or no longer validated"):
            review.thumbnail_file_path("other", "thumbnail.jpg")
        with self.assertRaisesRegex(ValueError, "not rendered"):
            review.thumbnail_file_path(RID, "thumbnail.jpg")
        with self.assertRaisesRegex(ValueError, "Invalid video_id"):
            review.competitor_file_path(RID, "../../etc")


@unittest.skipUnless(CAN_RENDER, "ffmpeg or a bold font is unavailable")
class ThumbnailReviewFlowTests(PipelineTestCase):
    def setUp(self):
        super().setUp()
        self.set_units()
        m.run_prepare()
        self.attach_subject()

    def test_render_review_and_rerender_invalidation(self):
        m.run_render()
        item = review.snapshot()["items"][0]
        self.assertEqual(item["render_status"], "RENDERED")
        query = parse_qs(urlparse(item["image_url"]).query)
        self.assertEqual(review.thumbnail_file_path(query["render_id"][0], query["name"][0]).name, "thumbnail.jpg")
        self.assertEqual(len(item["previews"]), len(TEMPLATE["phone_previews"]))

        criteria = {name: True for name in TEMPLATE["review_criteria"]}
        snapshot = review.apply_action(render_id=RID, decision="ACCEPT", criteria=criteria, note="")
        self.assertEqual(snapshot["items"][0]["decision"], "ACCEPT")
        self.assertTrue(snapshot["complete"])
        approved = self.root / "approved" / f"{RID}.json"
        self.assertTrue(approved.exists())
        current = m.current_approvals()
        self.assertEqual(list(current), [RID])
        self.assertEqual(
            current[RID]["image_sha256"], json.loads(approved.read_text())["image_sha256"]
        )

        spec_path = self.spec_path()
        spec = json.loads(spec_path.read_text())
        spec["accent_hex"] = "FF0000"
        spec_path.write_text(json.dumps(spec))
        stale = review.snapshot()["items"][0]
        self.assertEqual(stale["decision"], "PENDING")
        self.assertIn("render spec changed after rendering", stale["stale_reasons"])
        self.assertEqual(m.current_approvals(), {})

        m.run_render()
        self.assertFalse(approved.exists())
        self.assertEqual(review.snapshot()["items"][0]["decision"], "PENDING")

    def test_competitor_images_resolve_inside_study(self):
        self.packaging_config.write_text(json.dumps({"channel_niche": "automotive_racing"}))
        study = m.niche.study_dir("automotive_racing", "long_form")
        (study / "thumbnails").mkdir(parents=True)
        shutil.copyfile(self.root / "subject.png", study / "thumbnails" / "abcdefghijk.jpg")
        (study / "study_set.json").write_text(json.dumps({"videos": [{"video_id": "abcdefghijk", "title": "Rival", "views": 10}]}))
        (study / "acquisition.json").write_text(
            json.dumps({"items": {"abcdefghijk": {"status": "ACQUIRED", "path": "thumbnails/abcdefghijk.jpg"}}})
        )
        m.run_render()
        competitor = review.snapshot()["items"][0]["competitors"][0]
        query = parse_qs(urlparse(competitor["image_url"]).query)
        path = review.competitor_file_path(query["render_id"][0], query["video_id"][0])
        self.assertEqual(path.name, "abcdefghijk.jpg")
        (study / "acquisition.json").write_text(
            json.dumps({"items": {"abcdefghijk": {"status": "ACQUIRED", "path": "../../../outside.jpg"}}})
        )
        with self.assertRaisesRegex(ValueError, "not found"):
            review.competitor_file_path(RID, "abcdefghijk")


if __name__ == "__main__":
    unittest.main()
