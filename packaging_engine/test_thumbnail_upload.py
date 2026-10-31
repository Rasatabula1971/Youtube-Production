"""Thumbnails are made by the owner from a generated prompt and uploaded (D-191)."""

from __future__ import annotations

import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from packaging_engine import thumbnail_upload as thumbs

BRIEF = {
    "video_id": "c_tyre:short",
    "format": "short",
    "opening_hook": "You'd think a plane needs deep treads, but its tires are almost bald.",
    "central_question": "How do bald-looking tires stop a massive plane on a flooded runway?",
    "strongest_visual_event": "A commercial jet touching down on a wet runway with massive water splash plumes.",
    "approved_claims": [
        {"statement": "Aircraft tires use longitudinal grooves instead of block patterns."},
        {"statement": "Grooves lower hydroplaning risk."},
    ],
}
SHORT = {
    "video_id": "c_tyre:short", "format": "short", "psychological_angle": "stakes",
    "title_text": "How Smooth Plane Tires Keep You Safe on Wet Runways",
}
LONG = {
    "video_id": "c_tyre:long_form", "format": "long_form", "psychological_angle": "mystery",
    "title_text": "The Secret Behind Aircraft Tires", "thumbnail_text": "BALD ON PURPOSE",
    "thumbnail_concept": {"hero_subject": "A worn aircraft tire close up", "visual_anomaly": "No tread blocks at all"},
}


def png(width: int, height: int) -> bytes:
    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
    return header + chunk + b"\x00" * 16


class PromptTests(unittest.TestCase):
    """Specs from the owner's "Thumbnail Science" research doc (31 Oct 2026)."""

    def test_a_short_prompt_follows_the_faceless_shorts_cover_spec(self):
        prompt = thumbs.build_prompt(SHORT, {**BRIEF, "video_payoff": "Explain that ribs slice water away."})
        for expected in (
            "Shorts cover image for a faceless science channel",
            "vertical 9:16, 2160 x 3840", SHORT["title_text"], "do not write it on the image",
            BRIEF["strongest_visual_event"], BRIEF["central_question"],
            "Show the reveal moment the Short builds to: Ribs slice water away.",
            "one subject, centred, filling about 40-60% of the frame height", "4:5 or 3:2 crop",
            "sky-blue or cyan field", "3D-render look", "2-4 word label or question",
            "heavy white capital letters with a dark outline", "Montserrat ExtraBold",
            "- Aircraft tires use longitudinal grooves instead of block patterns.",
            "Show no other number, statistic or claim.", "the bottom quarter and the right edge",
            "human faces or people, logos",
        ):
            self.assertIn(expected, prompt)

    def test_a_long_form_prompt_follows_the_long_form_spec(self):
        prompt = thumbs.build_prompt(LONG, {**BRIEF, "format": "long_form"})
        for expected in (
            "16:9, 3840 x 2160", "Layout: Hero object", "Main subject: A worn aircraft tire close up",
            "What is surprising about it: No tread blocks at all", "1-3 focal objects",
            "168 x 94 pixels", 'Text on the image, exactly: "BALD ON PURPOSE"', "ALL CAPS",
            "one accent word in red or yellow", "10-20% of the image height", "No screenshots",
            "bottom-right corner", "first 30 seconds",
        ):
            self.assertIn(expected, prompt)

    def test_a_comparison_angle_gets_the_versus_layout(self):
        prompt = thumbs.build_prompt({**LONG, "psychological_angle": "comparison"}, BRIEF)
        self.assertIn("Layout: Versus / before-after", prompt)

    def test_the_prompt_is_the_same_every_time(self):
        self.assertEqual(thumbs.build_prompt(SHORT, BRIEF), thumbs.build_prompt(SHORT, BRIEF))

    def test_without_approved_claims_no_facts_may_appear(self):
        self.assertIn("Show no numbers, statistics or factual claims.", thumbs.build_prompt(SHORT, {}))


class UploadTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        for item in (
            patch.object(thumbs, "UPLOAD_DIR", self.dir),
            patch.object(thumbs, "_packages", side_effect=lambda: [dict(SHORT)]),
            patch.object(thumbs, "_briefs_by_video", return_value={"c_tyre:short": BRIEF}),
        ):
            item.start()
            self.addCleanup(item.stop)

    def test_the_upload_is_stored_and_counts_for_its_package(self):
        record = thumbs.upload(video_id="c_tyre:short", data=png(1080, 1920), made_with="Gemini", reviewer="me")
        self.assertEqual((record["width"], record["height"], record["made_with"]), (1080, 1920, "Gemini"))
        row = thumbs.items()[0]
        self.assertTrue(row["uploaded"])
        self.assertIn("Nothing important in the bottom quarter or along the right edge", row["checklist"])
        self.assertEqual(thumbs.image_file("c_tyre:short"), Path(record["image"]))

    def test_a_changed_title_asks_for_a_new_thumbnail(self):
        thumbs.upload(video_id="c_tyre:short", data=png(1080, 1920), made_with="", reviewer="me")
        self.assertIsNone(thumbs.current_upload({**SHORT, "title_text": "A New Title"}))
        with patch.object(thumbs, "_packages", return_value=[{**SHORT, "title_text": "A New Title"}]):
            row = thumbs.items()[0]
        self.assertFalse(row["uploaded"])
        self.assertTrue(row["replace_needed"])

    def test_only_png_or_jpeg_within_two_megabytes(self):
        with self.assertRaisesRegex(ValueError, "PNG or JPEG"):
            thumbs.upload(video_id="c_tyre:short", data=b"GIF89a....", made_with="", reviewer="me")
        with self.assertRaisesRegex(ValueError, "2 MB"):
            thumbs.upload(video_id="c_tyre:short", data=png(10, 10) + b"\x00" * 2_000_001, made_with="", reviewer="me")
        with self.assertRaisesRegex(ValueError, "No packaged video"):
            thumbs.upload(video_id="other:short", data=png(10, 10), made_with="", reviewer="me")

    def test_jpeg_size_is_read_from_its_header(self):
        sof = b"\xff\xc0" + struct.pack(">HBHH", 17, 8, 720, 1280) + b"\x03" + b"\x00" * 9
        self.assertEqual(thumbs.image_size(b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 4) + b"\x00\x00" + sof), (1280, 720))


if __name__ == "__main__":
    unittest.main()
