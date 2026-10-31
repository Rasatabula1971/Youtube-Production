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
    def test_a_short_prompt_carries_every_detail_for_an_image_tool(self):
        prompt = thumbs.build_prompt(SHORT, BRIEF)
        for expected in (
            "Shorts thumbnail", "vertical 9:16, 1080 x 1920", SHORT["title_text"],
            BRIEF["strongest_visual_event"], BRIEF["opening_hook"], BRIEF["central_question"],
            "Mood: tense, high stakes.", "2 to 4 large, bold words",
            "- Aircraft tires use longitudinal grooves instead of block patterns.",
            "Show no other number, statistic or claim.", "where YouTube puts the caption and buttons",
            "real or famous people, logos",
        ):
            self.assertIn(expected, prompt)

    def test_a_long_form_prompt_uses_the_accepted_thumbnail_concept_and_its_exact_text(self):
        prompt = thumbs.build_prompt(LONG, {**BRIEF, "format": "long_form"})
        self.assertIn("16:9, 1280 x 720", prompt)
        self.assertIn("Main subject: A worn aircraft tire close up", prompt)
        self.assertIn("What is surprising about it: No tread blocks at all", prompt)
        self.assertIn('Text on the image, exactly: "BALD ON PURPOSE"', prompt)
        self.assertIn("bottom-right corner", prompt)

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
