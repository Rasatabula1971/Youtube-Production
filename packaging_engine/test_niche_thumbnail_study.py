import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import niche_thumbnail_study as module
import packaging_engine


def video_row(index, *, niche="automotive_racing", channel=None, **overrides):
    row = {
        "video_id": f"vid{index:08d}",
        "title": f"Why Race Car Brakes Glow Red Hot Under Pressure {index}",
        "channel_id": channel or f"ch{index}",
        "channel_title": f"Channel {index}",
        "niches": [niche],
        "format_candidate": "long_form_candidate",
        "relevance": "ON_INTENT",
        "outlier_reliability": "TRUSTED",
        "outlier_ratio": float(100 - index),
        "views": 1_000_000 + index,
    }
    row.update(overrides)
    return row


def confirmed(video_id, *, text="GLOWS ON PURPOSE", elements=2, cues=0, face=False):
    return {
        "video_id": video_id,
        "status": "CONFIRMED",
        "text_overlay": text,
        "focal_subject": "glowing rotor",
        "focal_subject_type": "object_product",
        "visual_element_count": elements,
        "visual_cue_count": cues,
        "face_present": face,
    }


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.config = module.load_config()

    def test_selects_breakouts_with_channel_cap_and_filters(self):
        rows = [video_row(i) for i in range(1, 26)]
        rows += [
            video_row(30, channel="ch1"),
            video_row(31, channel="ch1"),
            video_row(40, relevance="OFF_INTENT"),
            video_row(41, format_candidate="short_candidate"),
            video_row(42, niche="fitness"),
            video_row(43, outlier_reliability="CAUTION", outlier_ratio=999.0),
        ]
        study = module.select_study_set(
            rows, niche="automotive_racing", video_format="long_form", config=self.config
        )
        ids = [video["video_id"] for video in study["videos"]]
        self.assertEqual(study["status"], "READY")
        self.assertEqual(ids[0], "vid00000001")
        self.assertNotIn("vid00000031", ids)
        self.assertNotIn("vid00000040", ids)
        self.assertNotIn("vid00000041", ids)
        self.assertNotIn("vid00000042", ids)
        self.assertEqual(ids[-1], "vid00000043")
        self.assertEqual(study["excluded_counts"]["channel_cap"], 1)

    def test_small_sample_is_flagged(self):
        study = module.select_study_set(
            [video_row(i) for i in range(1, 6)],
            niche="automotive_racing",
            video_format="long_form",
            config=self.config,
        )
        self.assertEqual(study["status"], "INSUFFICIENT_SAMPLE")


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.config = module.load_config()

    def grid(self, background, subject, width=16, height=10):
        pixels = []
        for y in range(height):
            for x in range(width):
                inside = width * 0.25 <= x < width * 0.75 and height * 0.2 <= y < height * 0.8
                pixels.append(subject if inside else background)
        return pixels

    def test_bright_orange_subject_on_dark_background(self):
        metrics = module.measure_pixels(
            self.grid((10, 10, 20), (255, 140, 0)), width=16, height=10, config=self.config
        )
        self.assertEqual(metrics["background_tone"], "dark")
        self.assertTrue(metrics["bright_subject_on_dark_background"])
        self.assertEqual(metrics["dominant_hue_family"], "orange")
        self.assertEqual(metrics["warm_share"], 1.0)

    def test_light_neutral_thumbnail(self):
        metrics = module.measure_pixels(
            self.grid((240, 240, 240), (200, 200, 200)), width=16, height=10, config=self.config
        )
        self.assertEqual(metrics["background_tone"], "light")
        self.assertEqual(metrics["dominant_hue_family"], "neutral")
        self.assertFalse(metrics["bright_subject_on_dark_background"])

    def test_hue_family_wraps_red(self):
        self.assertEqual(module.hue_family(359.0), "red")
        self.assertEqual(module.hue_family(5.0), "red")
        self.assertEqual(module.hue_family(220.0), "blue")


class AnnotationTests(unittest.TestCase):
    def test_confirmed_annotation_requires_complete_fields(self):
        config = module.load_config()
        item = confirmed("vid00000001")
        self.assertEqual(module.validate_annotation(item, config), [])
        item["visual_element_count"] = None
        item["focal_subject_type"] = "explosion"
        errors = module.validate_annotation(item, config)
        self.assertEqual(len(errors), 2)
        self.assertEqual(
            module.validate_annotation({"status": "DRAFT"}, config), []
        )


class TabulationTests(unittest.TestCase):
    def setUp(self):
        self.config = module.load_config()
        self.rules = packaging_engine.load_config()["design_advisories"]
        self.study = {
            "niche": "automotive_racing",
            "format": "long_form",
            "videos": [video_row(i) for i in range(1, 21)],
        }
        dark = {
            "dominant_hue_family": "red",
            "background_tone": "dark",
            "warm_share": 0.9,
            "luminance_spread": 0.7,
            "mean_saturation": 0.5,
            "bright_subject_on_dark_background": True,
            "meets_minimum_resolution": True,
        }
        self.measurements = {video["video_id"]: dict(dark) for video in self.study["videos"]}

    def test_complete_tabulation_compares_hypotheses(self):
        annotations = [
            confirmed(video["video_id"], text="TOO MANY WORDS ON THIS ONE HERE", elements=5)
            for video in self.study["videos"]
        ]
        result = module.tabulate(
            self.study, self.measurements, annotations, config=self.config, advisory_rules=self.rules
        )
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["color"]["crowded_hue_families"], ["red"])
        self.assertNotIn("red", result["color"]["accent_differentiation_candidates"])
        self.assertIn("yellow", result["color"]["accent_differentiation_candidates"])
        verdicts = {item["hypothesis"]: item["verdict"] for item in result["hypothesis_comparison"]}
        self.assertEqual(verdicts["THUMBNAIL_TEXT_WORDS (when text is used)"], "NICHE_DIVERGES")
        self.assertEqual(verdicts["THUMBNAIL_ELEMENT_COUNT"], "NICHE_DIVERGES")
        self.assertEqual(verdicts["DARK_BACKGROUND_BRIGHT_SUBJECT"], "NICHE_FOLLOWS")
        self.assertEqual(verdicts["TITLE_LENGTH"], "NICHE_FOLLOWS")
        self.assertEqual(result["text"]["word_count_buckets"]["6+"], 1.0)

    def test_drafts_are_not_tabulated(self):
        annotations = [
            {**confirmed(video["video_id"]), "status": "DRAFT"} for video in self.study["videos"]
        ]
        result = module.tabulate(
            self.study, self.measurements, annotations, config=self.config, advisory_rules=self.rules
        )
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["sample"]["annotations_confirmed"], 0)
        self.assertEqual(result["focal"]["focal_subject_type"], {})

    def test_text_repeating_title_is_counted(self):
        annotations = [
            confirmed(video["video_id"], text="RACE CAR BRAKES") for video in self.study["videos"]
        ]
        result = module.tabulate(
            self.study, self.measurements, annotations, config=self.config, advisory_rules=self.rules
        )
        self.assertEqual(result["text"]["text_repeats_title_share"], 1.0)


class PackagingIntegrationTests(unittest.TestCase):
    def test_request_includes_conventions_only_when_niche_configured(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(module, "STUDY_ROOT", Path(tmp)):
            path = module.tabulation_path("automotive_racing", "long_form")
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"status": "COMPLETE", "color": {"crowded_hue_families": ["red"]}}))
            concept = {"concept_id": "c1", "format_intent": "either"}
            config = {"packages_per_concept": 5, "allowed_format_intents": ["long_form", "short", "either"]}

            without = packaging_engine.build_package_request(concept, config)
            self.assertEqual(without["niche_thumbnail_conventions"], {})

            config["channel_niche"] = "automotive_racing"
            request = packaging_engine.build_package_request(concept, config)
            conventions = request["niche_thumbnail_conventions"]
            self.assertEqual(list(conventions), ["long_form"])
            self.assertEqual(conventions["long_form"]["color"]["crowded_hue_families"], ["red"])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg not installed")
class EndToEndTests(unittest.TestCase):
    def make_jpeg(self, path, color):
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y",
                "-f", "lavfi", "-i", "color=c=0x101018:s=1280x720",
                "-vf", f"drawbox=x=320:y=144:w=640:h=432:color={color}:t=fill",
                "-frames:v", "1", str(path),
            ],
            check=True,
        )

    def test_select_acquire_measure_annotate_tabulate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "raw_results.json"
            source.write_text(json.dumps([video_row(i) for i in range(1, 21)]))
            image = root / "sample.jpg"
            self.make_jpeg(image, "0xFF8C00")
            body = image.read_bytes()
            requested = []

            def fake_fetch(url):
                requested.append(url)
                return None if url.endswith("maxresdefault.jpg") else body

            with patch.object(module, "STUDY_ROOT", root / "study"):
                self.assertEqual(
                    module.run_select("automotive_racing", "long_form", [source])["status"], "READY"
                )
                acquired = module.run_acquire("automotive_racing", "long_form", fetch=fake_fetch)
                self.assertEqual(acquired["acquired"], 20)
                self.assertTrue(requested[1].endswith("hqdefault.jpg"))
                self.assertEqual(
                    module.run_acquire("automotive_racing", "long_form", fetch=fake_fetch)["reused"], 20
                )
                self.assertEqual(module.run_measure("automotive_racing", "long_form")["measured"], 20)
                module.run_annotate("automotive_racing", "long_form")

                directory = module.study_dir("automotive_racing", "long_form")
                sheet_path = directory / "annotations.json"
                sheet = json.loads(sheet_path.read_text())
                for item in sheet["items"]:
                    item.update(confirmed(item["video_id"]))
                sheet_path.write_text(json.dumps(sheet))
                module.run_annotate("automotive_racing", "long_form")
                summary = module.run_tabulate("automotive_racing", "long_form")

                result = json.loads((directory / "tabulation.json").read_text())
                self.assertEqual(summary["status"], "COMPLETE")
                self.assertEqual(result["color"]["dominant_hue_family"], {"orange": 1.0})
                self.assertEqual(result["color"]["bright_subject_on_dark_share"], 1.0)
                self.assertEqual(result["color"]["meets_minimum_resolution_share"], 1.0)
                self.assertTrue((directory / "tabulation.csv").exists())
                self.assertIn("NICHE_FOLLOWS", (directory / "REPORT.md").read_text())


if __name__ == "__main__":
    unittest.main()
