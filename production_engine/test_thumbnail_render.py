from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from production_engine import thumbnail_render as m

TEMPLATE = m.load_template()
CAN_RENDER = bool(
    shutil.which("ffmpeg") and shutil.which("ffprobe") and m.find_font(TEMPLATE)
)


VIDEO_ID = "c1-long_form"
THUMBNAIL_ID = "thumbnail-angle-1"
RID = f"{VIDEO_ID}--{THUMBNAIL_ID}"


def pairing_fixture(
    text="GLOWS ON PURPOSE",
    statuses=("PASS", "REWORK", "PASS"),
    background="near-black with a cold blue rim light",
):
    """Slice 26 pair validations plus the Slice 25 concept set they refer to."""
    validations = [
        {
            "package_id": f"package-title-{index}--{THUMBNAIL_ID}",
            "video_id": VIDEO_ID,
            "concept_id": "c1",
            "format": "long_form",
            "title_id": f"title-{index}",
            "title_text": f"Why F1 Brakes Work Backwards {index}",
            "thumbnail_id": THUMBNAIL_ID,
            "validation_status": status,
            "selected_title_direction_match": index == 2,
        }
        for index, status in enumerate(statuses)
    ]
    concepts = {
        VIDEO_ID: {
            "video_id": VIDEO_ID,
            "thumbnail_concepts": [
                {
                    "thumbnail_id": THUMBNAIL_ID,
                    "angle_id": "angle-1",
                    "text": text,
                    "hero_subject": "glowing race brake rotor",
                    "secondary_element": None,
                    "visual_anomaly": "rotor glowing on purpose",
                    "visual_action": "rotor glows under braking",
                    "emotion": "surprise",
                    "composition": "subject right, text left",
                    "background": background,
                    "subject_separation_method": "rim light",
                    "viewer_visual_question": "Why is it glowing?",
                    "mobile_legibility_intent": "large rotor, three bold words",
                    "face_present": False,
                }
            ],
        }
    }
    return validations, concepts


class TemplateTests(unittest.TestCase):
    def test_shipped_template_is_valid(self):
        self.assertEqual(m.validate_template(TEMPLATE), [])

    def test_text_in_timestamp_zone_is_rejected(self):
        template = copy.deepcopy(TEMPLATE)
        template["text"]["box"] = {"x": 900, "y": 500, "w": 300, "h": 200}
        errors = m.validate_template(template)
        self.assertIn("text.box overlaps the YouTube timestamp safe zone", errors)

    def test_accent_from_palette(self):
        names = TEMPLATE["accent_names"]
        self.assertEqual(m.accent_from_palette("cold blue for the road rotor", TEMPLATE), names["blue"])
        self.assertEqual(m.accent_from_palette("red then yellow", TEMPLATE), names["red"])
        self.assertEqual(m.accent_from_palette("use #ff00aa", TEMPLATE), "FF00AA")
        self.assertEqual(
            m.accent_from_palette("facade grey", TEMPLATE), TEMPLATE["default_accent_hex"]
        )
        self.assertEqual(m.hex_hue_family("2F80FF"), "blue")

    def test_candidate_splits(self):
        splits = m.candidate_splits(["A", "B", "C"], 3)
        self.assertIn(["A B C"], splits)
        self.assertIn(["A", "B C"], splits)
        self.assertIn(["A", "B", "C"], splits)
        self.assertEqual(len(splits), 4)


class SubjectTests(unittest.TestCase):
    def test_subject_provenance_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "s.png"
            image.write_bytes(b"x")
            check = lambda **subject: m.validate_subject(  # noqa: E731
                subject, spec_dir=Path(tmp), template=TEMPLATE
            )[1]
            self.assertEqual(check(path="s.png", source_tier="OWN_LIBRARY"), [])
            self.assertTrue(check(path="s.png", source_tier="EDITORIAL_EXCERPT", license="x"))
            self.assertIn(
                "subject source_url is required for CREATIVE_COMMONS_ALLOWED",
                check(path="s.png", source_tier="CREATIVE_COMMONS_ALLOWED", license="CC BY"),
            )
            self.assertIn(
                "subject licence is required unless source_tier is OWN_LIBRARY",
                check(path="s.png", source_tier="CHEAP_AI"),
            )
            self.assertEqual(m.validate_subject({}, spec_dir=Path(tmp), template=TEMPLATE), (None, []))


class PipelineTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.sources = ([], {})
        self.packaging_config = self.root / "packaging_config.json"
        self.packaging_config.write_text(json.dumps({"channel_niche": None}))
        patches = [
            patch.object(m, "THUMBNAILS_DIR", self.root / "thumbnails"),
            patch.object(m, "APPROVED_THUMBNAILS_DIR", self.root / "approved"),
            patch.object(m, "pairing_sources", lambda: self.sources),
            patch.object(m, "PACKAGING_CONFIG_FILE", self.packaging_config),
            patch.object(m.niche, "STUDY_ROOT", self.root / "niche"),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.addCleanup(self.tmp.cleanup)

    def set_units(self, **kwargs):
        self.sources = pairing_fixture(**kwargs)

    def spec_path(self, render_id=RID):
        return m.unit_dir(render_id) / "render_spec.json"

    def attach_subject(self, render_id=RID, **overrides):
        image = self.root / "subject.png"
        if not image.exists():
            subprocess.run(
                [
                    "ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", "color=c=0x101010:s=900x900:d=1",
                    "-vf", "drawbox=x=200:y=200:w=500:h=500:color=0xFFB040:t=fill",
                    "-frames:v", "1", str(image),
                ],
                check=True,
            )
        spec = json.loads(self.spec_path(render_id).read_text())
        spec["subject_image"] = {
            "path": str(image),
            "source_tier": "OWN_LIBRARY",
            "license": "",
            "source_url": "",
            "attribution": "",
            **overrides,
        }
        self.spec_path(render_id).write_text(json.dumps(spec))

    def accept(self, render_id=RID, **criteria_overrides):
        criteria = {name: True for name in TEMPLATE["review_criteria"]}
        criteria.update(criteria_overrides)
        return m.apply_review(
            {
                "reviewer": "r1",
                "decisions": [
                    {"render_id": render_id, "decision": "ACCEPT", "criteria": criteria}
                ],
            },
            TEMPLATE,
        )


class PrepareTests(PipelineTestCase):
    def test_prepare_binds_concept_and_keeps_human_fields(self):
        self.assertEqual(m.run_prepare()["status"], "WAITING_FOR_VALIDATED_PACKAGES")
        self.set_units()
        m.run_prepare()
        spec = json.loads(self.spec_path().read_text())
        self.assertEqual(spec["unit"]["text_overlay"], "GLOWS ON PURPOSE")
        self.assertEqual(spec["accent_hex"], TEMPLATE["accent_names"]["blue"])
        spec["accent_hex"] = "FF0000"
        spec["subject_image"]["path"] = "keep.png"
        self.spec_path().write_text(json.dumps(spec))

        self.set_units(text="HEAT IS THE POINT")
        m.run_prepare()
        spec = json.loads(self.spec_path().read_text())
        self.assertEqual(spec["unit"]["text_overlay"], "HEAT IS THE POINT")
        self.assertEqual(spec["accent_hex"], "FF0000")
        self.assertEqual(spec["subject_image"]["path"], "keep.png")


class RenderUnitTests(PipelineTestCase):
    def test_units_use_only_renderable_pairs_with_selected_title_first(self):
        self.set_units(statuses=("PASS", "REWORK", "PASS", "REJECT"))
        units = m.load_render_units(TEMPLATE)
        self.assertEqual([unit["render_id"] for unit in units], [RID])
        unit = units[0]
        self.assertEqual(
            [title["title_id"] for title in unit["titles"]], ["title-2", "title-0"]
        )
        self.assertEqual(unit["title"], "Why F1 Brakes Work Backwards 2")
        self.assertEqual(unit["text_overlay"], "GLOWS ON PURPOSE")
        self.assertEqual(unit["format"], "long_form")

    def test_concept_without_passing_pair_is_not_rendered(self):
        self.set_units(statuses=("REWORK", "REJECT"))
        self.assertEqual(m.load_render_units(TEMPLATE), [])
        self.assertEqual(m.run_prepare()["status"], "WAITING_FOR_VALIDATED_PACKAGES")

    def test_pair_without_current_concept_is_skipped(self):
        validations, _ = pairing_fixture()
        self.sources = (validations, {})
        self.assertEqual(m.load_render_units(TEMPLATE), [])

    def test_source_hash_tracks_titles_and_concept(self):
        self.set_units()
        first = m.load_render_units(TEMPLATE)[0]["source_sha256"]
        self.set_units(statuses=("PASS", "PASS", "PASS"))
        self.assertNotEqual(m.load_render_units(TEMPLATE)[0]["source_sha256"], first)
        self.set_units(background="white studio")
        self.assertNotEqual(m.load_render_units(TEMPLATE)[0]["source_sha256"], first)


@unittest.skipUnless(CAN_RENDER, "ffmpeg or a bold font is unavailable")
class RenderTests(PipelineTestCase):
    def setUp(self):
        super().setUp()
        self.set_units()
        m.run_prepare()

    def report(self, render_id=RID):
        return json.loads((m.unit_dir(render_id) / "render_report.json").read_text())

    def test_waits_for_subject_and_placeholder_cannot_be_accepted(self):
        self.assertEqual(m.run_render()["results"][RID], "WAITING_FOR_SUBJECT_IMAGE")
        self.assertEqual(
            m.run_render(placeholder=True)["results"][RID], "PREVIEW_ONLY"
        )
        rules = {item["rule"] for item in self.report()["render_advisories"]}
        self.assertIn("PLACEHOLDER_SUBJECT", rules)
        with self.assertRaisesRegex(ValueError, "only a RENDERED"):
            self.accept()

    def test_render_outputs_and_gate(self):
        self.attach_subject()
        self.assertEqual(m.run_render()["results"][RID], "RENDERED")
        report = self.report()
        directory = m.unit_dir(RID)
        self.assertEqual((report["width"], report["height"]), (1280, 720))
        self.assertLessEqual(report["image_bytes"], TEMPLATE["max_jpeg_bytes"])
        self.assertEqual(" ".join(report["text_layout"]["lines"]), "GLOWS ON PURPOSE")
        self.assertTrue(report["text_layout"]["fits"])
        for name in report["previews"].values():
            self.assertTrue((directory / name).exists())
        self.assertIn("thumbnail.jpg", (directory / "feed.html").read_text())
        self.assertLess(report["zone_luminance"]["background"], 0.35)

        with self.assertRaisesRegex(ValueError, "readable_at_phone_size"):
            self.accept(readable_at_phone_size=False)
        self.accept()
        approved = json.loads((self.root / "approved" / f"{RID}.json").read_text())
        self.assertEqual(approved["image_sha256"], report["image_sha256"])

        m.apply_review(
            {
                "reviewer": "r1",
                "decisions": [{"render_id": RID, "decision": "REJECT", "criteria": {}}],
            },
            TEMPLATE,
        )
        self.assertFalse((self.root / "approved" / f"{RID}.json").exists())
        with self.assertRaisesRegex(ValueError, "REWORK requires a note"):
            m.apply_review(
                {
                    "reviewer": "r1",
                    "decisions": [{"render_id": RID, "decision": "REWORK", "criteria": {}}],
                },
                TEMPLATE,
            )

    def test_stale_render_cannot_be_accepted(self):
        self.attach_subject()
        m.run_render()
        self.set_units(text="DIFFERENT TEXT NOW")
        with self.assertRaisesRegex(ValueError, "thumbnail concept or its validated titles changed"):
            self.accept()

    def test_disallowed_subject_and_overlong_text_are_blocked(self):
        self.attach_subject(source_tier="EDITORIAL_EXCERPT", license="fair use")
        self.assertEqual(m.run_render()["results"][RID], "BLOCKED")
        self.set_units(text="THIS OVERLAY IS FAR TOO LONG FOR ANY SENSIBLE THUMBNAIL LAYOUT AT ALL")
        m.run_prepare()
        self.attach_subject()
        self.assertEqual(m.run_render()["results"][RID], "BLOCKED")
        self.assertIn("Rework the thumbnail concept text", self.report()["errors"][0])

    def test_missing_font_blocks(self):
        self.attach_subject()
        with patch.object(m, "find_font", return_value=None):
            self.assertEqual(m.run_render()["results"][RID], "BLOCKED")

    def test_feed_includes_niche_breakouts_and_crowded_accent_advisory(self):
        self.packaging_config.write_text(json.dumps({"channel_niche": "automotive_racing"}))
        study = m.niche.study_dir("automotive_racing", "long_form")
        (study / "thumbnails").mkdir(parents=True)
        self.attach_subject()
        shutil.copyfile(self.root / "subject.png", study / "thumbnails" / "abcdefghijk.jpg")
        (study / "study_set.json").write_text(
            json.dumps(
                {"videos": [{"video_id": "abcdefghijk", "title": "Rival <b>video</b>", "channel_title": "Rival", "views": 2_500_000}]}
            )
        )
        (study / "acquisition.json").write_text(
            json.dumps({"items": {"abcdefghijk": {"status": "ACQUIRED", "path": "thumbnails/abcdefghijk.jpg"}}})
        )
        (study / "tabulation.json").write_text(
            json.dumps({"color": {"crowded_hue_families": ["blue"], "accent_differentiation_candidates": ["yellow"]}})
        )
        m.run_render()
        feed = (m.unit_dir(RID) / "feed.html").read_text()
        self.assertIn("abcdefghijk.jpg", feed)
        self.assertIn("Rival &lt;b&gt;video&lt;/b&gt;", feed)
        self.assertIn("2.5M views", feed)
        rules = {item["rule"] for item in self.report()["render_advisories"]}
        self.assertIn("ACCENT_IN_CROWDED_HUE", rules)


if __name__ == "__main__":
    unittest.main()
