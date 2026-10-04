"""Tesseract project exchange and its Final Export Gate binding (D-144)."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import final_export_review as export_review
import tesseract_exchange as te
from visual_acquisition import sha256_file

PROFILE = {"width": 320, "height": 180, "fps": 30}


def fake_probe(**overrides):
    info = {"has_video": True, "has_audio": True, "width": 320, "height": 180,
            "video_codec": "h264", "audio_codec": "aac", "duration_seconds": 9.5}
    info.update(overrides)
    return lambda path: dict(info)


class ExchangeTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = self.root = Path(tmp.name)
        media = root / "media"
        media.mkdir()
        files = {}
        for name in ("v1.png", "v2.mp4", "n1.wav", "n2.wav", "music.mp3", "sfx.wav", "sfx2.wav"):
            (media / name).write_bytes(name.encode() * 8)
            files[name] = media / name
        self.files = files

        def asset(name):
            return {"asset_file": str(files[name]), "asset_sha256": sha256_file(files[name])}

        self.manifest = {
            "artifact": "final_render_manifest", "concept_id": "c1", "format": "long_form",
            "video_profile": dict(PROFILE), "duration_seconds": 10.0,
            "visual_track": [
                {"shot_id": "shot-001", "scene_index": 1, "beat_id": "b1", "start_seconds": 0, "end_seconds": 4, **asset("v1.png")},
                {"shot_id": "shot-002", "scene_index": 2, "beat_id": "b2", "start_seconds": 4, "end_seconds": 9, **asset("v2.mp4")},
            ],
            "narration_track": [
                {"segment_id": "seg-1", "audio_file": str(files["n1.wav"]), "audio_sha256": sha256_file(files["n1.wav"]),
                 "audio_start_seconds": 0.5, "audio_end_seconds": 4.0},
                {"segment_id": "seg-2", "audio_file": str(files["n2.wav"]), "audio_sha256": sha256_file(files["n2.wav"]),
                 "audio_start_seconds": 4.5, "audio_end_seconds": 9.0},
            ],
            "sound_track": [
                {"requirement_id": "music-1", "kind": "MUSIC", "segment_id": "seg-1", "start_seconds": 0, "end_seconds": 9,
                 "volume": 0.18, "loop_to_fill": True, **asset("music.mp3")},
                {"requirement_id": "sfx-1", "kind": "SFX", "segment_id": "seg-2", "start_seconds": 4.5, "end_seconds": 9,
                 "volume": 0.45, **asset("sfx.wav")},
                {"requirement_id": "sfx-2", "kind": "SFX", "segment_id": "seg-2", "start_seconds": 5.0, "end_seconds": 9,
                 "volume": 0.45, **asset("sfx2.wav")},
            ],
        }
        self.render = root / "renders" / "c1.long_form.final_candidate.mp4"
        self.render.parent.mkdir()
        self.render.write_bytes(b"automated render")
        self.results = root / "results"
        self.results.mkdir()
        self.result_path = self.results / "c1.long_form.final_render_result.json"
        self.write_result()

        thumbs = root / "thumbs" / "c1-pkg"
        thumbs.mkdir(parents=True)
        (thumbs / "thumbnail.jpg").write_bytes(b"\xff\xd8thumb")
        (thumbs / "subject.png").write_bytes(b"subject")
        (thumbs / "render_spec.json").write_text(json.dumps({"subject_image": {"path": "subject.png"}}))
        bundles = root / "bundles"
        bundles.mkdir()
        (bundles / "c1.final_package.json").write_text(json.dumps(
            {"packages": {"long_form": {"thumbnail_image": {"image": str(thumbs / "thumbnail.jpg")}}}}))

        for item in (
            patch.object(te, "RESULT_DIR", self.results),
            patch.object(te, "EXPORT_DIR", root / "projects"),
            patch.object(te, "RETURN_DIR", root / "returns"),
            patch.object(te, "HISTORY_FILE", root / "history.jsonl"),
            patch.object(te, "FINAL_PACKAGES_DIR", bundles),
            patch.object(te, "result_is_current", side_effect=self.current_result),
            patch.object(te, "manifest_is_current", side_effect=lambda path: copy.deepcopy(self.manifest)),
        ):
            item.start()
            self.addCleanup(item.stop)

    def write_result(self, **changes):
        self.result = {
            "artifact": "final_render_result", "concept_id": "c1", "format": "long_form",
            "status": "READY_FOR_HUMAN_FINAL_EXPORT_GATE",
            "render_file": str(self.render), "render_sha256": sha256_file(self.render),
            "render_bytes": self.render.stat().st_size, "duration_seconds": 10.0,
            "sound_assets_mixed": 3, "sound_omissions": 0,
            "provenance": {"final_render_manifest": str(self.root / "manifest.json")}, **changes,
        }
        self.result_path.write_text(json.dumps(self.result))

    def current_result(self, path):
        return copy.deepcopy(self.result) if Path(path) == self.result_path and self.result_path.is_file() else None

    def export(self):
        return te.export(concept_id="c1", format="long_form")

    def edited_video(self, name="final_edit.mp4", payload=b"edited video"):
        path = self.root / name
        path.write_bytes(payload)
        return path


class ExportTests(ExchangeTestCase):
    def test_export_writes_an_editable_project_with_stable_clip_ids(self):
        record = self.export()
        folder = Path(record["folder"])
        exchange = json.loads((folder / "exchange.json").read_text())
        ids = [c["clip_id"] for c in exchange["clips"]]
        self.assertEqual(ids, ["V-shot-001", "V-shot-002", "N-seg-1", "N-seg-2", "S-music-1", "S-sfx-1", "S-sfx-2"])
        tracks = {t["name"]: t["clip_ids"] for t in exchange["tracks"]}
        self.assertEqual(tracks["V1 Visuals"], ["V-shot-001", "V-shot-002"])
        self.assertEqual(tracks["A1 Narration"], ["N-seg-1", "N-seg-2"])
        self.assertEqual(tracks["A2 Music"], ["S-music-1"])
        # Overlapping sound effects go on separate tracks.
        self.assertEqual(tracks["A3 Sound effects"], ["S-sfx-1"])
        self.assertEqual(tracks["A4 Sound effects 2"], ["S-sfx-2"])
        # The last visual is held to the end, as in the automated render.
        last = next(c for c in exchange["clips"] if c["clip_id"] == "V-shot-002")
        self.assertEqual((last["start_frame"], last["duration_frames"]), (120, 180))
        for clip in exchange["clips"]:
            copied = folder / clip["media"]
            self.assertEqual(sha256_file(copied), clip["source_sha256"])
        self.assertTrue((folder / "reference" / "automated_render.mp4").is_file())
        self.assertEqual(sorted(record["thumbnail_files"]),
                         ["thumbnail/render_spec.json", "thumbnail/subject.png", "thumbnail/thumbnail.jpg"])

        otio = json.loads(Path(record["otio_file"]).read_text())
        self.assertEqual(otio["OTIO_SCHEMA"], "Timeline.1")
        narration = next(t for t in otio["tracks"]["children"] if t["name"] == "A1 Narration")
        self.assertEqual([c["OTIO_SCHEMA"] for c in narration["children"]], ["Gap.1", "Clip.1", "Gap.1", "Clip.1"])
        url = narration["children"][1]["media_reference"]["target_url"]
        self.assertTrue(url.startswith("file://") and url.endswith("media/narration/N-seg-1.wav"))

        xml = ET.parse(record["xml_file"]).getroot()
        self.assertEqual(xml.tag, "xmeml")
        names = [n.text for n in xml.iter("clipitem") for n in [n.find("name")]]
        self.assertEqual(sorted(names), sorted(ids))
        self.assertIn("V-<shot>", (folder / "README.txt").read_text())

    def test_short_moving_media_loops_and_short_effects_play_once(self):
        lengths = {"v2.mp4": 2.0, "music.mp3": 4.0, "sfx.wav": 1.0, "sfx2.wav": 1.0, "n1.wav": 3.5, "n2.wav": 4.5}
        clips = {c["clip_id"]: c for c in te.build_clips(self.manifest, media_seconds=lambda p: lengths.get(p.name))}
        self.assertEqual(te.pieces(clips["V-shot-002"]), [(120, 60), (180, 60), (240, 60)])
        self.assertEqual(te.pieces(clips["S-music-1"]), [(0, 120), (120, 120), (240, 30)])
        self.assertEqual(te.pieces(clips["S-sfx-1"]), [(135, 30)])
        self.assertEqual(te.pieces(clips["V-shot-001"]), [(0, 120)])
        self.assertIsNone(clips["V-shot-001"]["media_duration_frames"])

    def test_export_is_idempotent_and_goes_stale_when_the_render_changes(self):
        first = self.export()
        self.assertEqual(self.export(), first)
        self.render.write_bytes(b"re-rendered")
        self.write_result()
        self.assertIsNone(te.export_is_current("c1", "long_form"))
        second = self.export()
        self.assertNotEqual(second["export_id"], first["export_id"])
        events = [json.loads(line)["event"] for line in (self.root / "history.jsonl").read_text().splitlines()]
        self.assertEqual(events, ["EXPORTED", "EXPORTED"])

    def test_export_needs_a_current_render_and_unchanged_media(self):
        self.result_path.unlink()
        with self.assertRaisesRegex(ValueError, "no current final render"):
            self.export()
        self.write_result()
        self.files["n2.wav"].write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "narration file changed"):
            self.export()
        self.assertFalse((self.root / "projects" / "c1.long_form.editor_export.json").exists())


class ImportTests(ExchangeTestCase):
    def import_edit(self, video, timeline=None, probe=None):
        return te.import_edit(concept_id="c1", format="long_form", video_path=str(video),
                              timeline_path=str(timeline) if timeline else None, note="tightened the intro",
                              probe=probe or fake_probe())

    def test_import_needs_an_export_and_a_valid_video(self):
        video = self.edited_video()
        with self.assertRaisesRegex(ValueError, "Export the editable project"):
            self.import_edit(video)
        self.export()
        with self.assertRaisesRegex(ValueError, "not found"):
            self.import_edit(self.root / "missing.mp4")
        with self.assertRaisesRegex(ValueError, "must be one of"):
            self.import_edit(self.edited_video("edit.avi"))
        with self.assertRaisesRegex(ValueError, "FRAME_SIZE"):
            self.import_edit(video, probe=fake_probe(width=1280, height=720))
        with self.assertRaisesRegex(ValueError, "AUDIO_STREAM"):
            self.import_edit(video, probe=fake_probe(has_audio=False))
        self.assertIsNone(te.current_return("c1", "long_form"))

    def test_imported_edit_is_bound_to_its_bytes_and_the_automated_render(self):
        self.export()
        edit = self.import_edit(self.edited_video())
        self.assertEqual(edit["duration_seconds"], 9.5)
        self.assertTrue(all(c["status"] == "PASS" for c in edit["quality_checks"]))
        self.assertIn("-0.50 s against", edit["quality_checks"][-1]["detail"])
        path, current = te.current_return("c1", "long_form")
        self.assertEqual(current["render_sha256"], sha256_file(Path(edit["render_file"])))
        Path(edit["render_file"]).write_bytes(b"tampered")
        self.assertIsNone(te.current_return("c1", "long_form"))
        edit = self.import_edit(self.edited_video())
        self.assertIsNotNone(te.current_return("c1", "long_form"))
        self.render.write_bytes(b"upstream change")
        self.write_result()
        self.assertIsNone(te.current_return("c1", "long_form"))

    def test_returned_timeline_maps_scenes_back(self):
        record = self.export()
        otio = json.loads(Path(record["otio_file"]).read_text())
        tracks = {t["name"]: t for t in otio["tracks"]["children"]}
        visuals = tracks["V1 Visuals"]["children"]
        visuals[0]["source_range"]["duration"]["value"] = 90.0       # shot-001 trimmed to 3 s
        visuals.append({"OTIO_SCHEMA": "Clip.1", "name": "end card",  # an added clip
                        "source_range": {"duration": {"rate": 30.0, "value": 30.0}}, "metadata": {}})
        tracks["A4 Sound effects 2"]["children"] = []                # sfx-2 removed
        timeline = self.root / "returned.otio"
        timeline.write_text(json.dumps(otio))
        edit = self.import_edit(self.edited_video(), timeline)
        changes = {row["clip_id"]: row["change"] for row in edit["scene_changes"]["clips"]}
        self.assertEqual(changes["V-shot-001"], "RETIMED")
        self.assertEqual(changes["V-shot-002"], "MOVED")
        self.assertEqual(changes["N-seg-1"], "KEPT")
        self.assertEqual(changes["S-sfx-2"], "REMOVED")
        self.assertEqual([a["clip_id"] for a in edit["scene_changes"]["added"]], ["end card"])
        self.assertEqual(edit["scene_changes"]["counts"]["ADDED"], 1)
        bad = self.root / "bad.otio"
        bad.write_text("{not json")
        with self.assertRaisesRegex(ValueError, "not readable"):
            self.import_edit(self.edited_video(), bad)

    def test_discard_needs_a_note_and_restores_the_automated_render(self):
        self.export()
        self.import_edit(self.edited_video())
        with self.assertRaisesRegex(ValueError, "Say why"):
            te.discard_edit(concept_id="c1", format="long_form", note=" ")
        te.discard_edit(concept_id="c1", format="long_form", note="the automated cut is better")
        self.assertIsNone(te.current_return("c1", "long_form"))
        self.assertFalse((self.root / "returns" / "c1.long_form").exists())
        events = [json.loads(line)["event"] for line in (self.root / "history.jsonl").read_text().splitlines()]
        self.assertEqual(events, ["EXPORTED", "EDIT_IMPORTED", "EDIT_DISCARDED"])
        snapshot = te.snapshot()
        self.assertEqual(snapshot["items"][0]["status"], "EXPORTED")
        self.assertFalse(snapshot["round_trip_verified"])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg is not installed")
    def test_real_probe_reads_frame_size_and_audio(self):
        video = self.root / "real.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=30:duration=1",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-shortest", "-c:v", "libx264",
             "-pix_fmt", "yuv420p", "-c:a", "aac", str(video)],
            check=True,
        )
        info = te.probe_video(video)
        self.assertEqual((info["width"], info["height"], info["has_audio"]), (320, 180, True))
        self.export()
        edit = te.import_edit(concept_id="c1", format="long_form", video_path=str(video))
        self.assertAlmostEqual(edit["duration_seconds"], 1.0, delta=0.2)
        silent = self.root / "silent.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-an", "-c", "copy", str(silent)], check=True)
        with self.assertRaisesRegex(ValueError, "AUDIO_STREAM"):
            te.import_edit(concept_id="c1", format="long_form", video_path=str(silent))


class FinalExportGateTests(ExchangeTestCase):
    def setUp(self):
        super().setUp()
        for item in (
            patch.object(export_review, "RESULT_DIR", self.results),
            patch.object(export_review, "REVIEW_DIR", self.root / "reviews"),
            patch.object(export_review, "APPROVED_DIR", self.root / "approved"),
            patch.object(export_review, "REWORK_DIR", self.root / "rework"),
            patch.object(export_review, "result_is_current", side_effect=self.current_result),
        ):
            item.start()
            self.addCleanup(item.stop)

    def test_the_returned_edit_is_the_candidate_that_gets_approved(self):
        approved_path = self.root / "approved" / "c1.long_form.approved_final_export.json"
        export_review.apply_action(result_file=str(self.result_path), decision="APPROVE_EXPORT", note="")
        self.assertIsNotNone(export_review.approval_is_current(approved_path))

        self.export()
        edit = te.import_edit(concept_id="c1", format="long_form", video_path=str(self.edited_video()),
                              probe=fake_probe())
        # The automated approval no longer counts, and cannot be renewed.
        self.assertIsNone(export_review.approval_is_current(approved_path))
        with self.assertRaisesRegex(ValueError, "STALE"):
            export_review.apply_action(result_file=str(self.result_path), decision="APPROVE_EXPORT", note="")

        item = export_review.snapshot()["items"][0]
        self.assertEqual(item["source"], "EDITOR")
        self.assertEqual(item["decision"], "PENDING")
        self.assertEqual(item["render_sha256"], edit["render_sha256"])
        export_review.apply_action(result_file=item["result_file"], decision="APPROVE_EXPORT", note="")
        approval = export_review.approval_is_current(approved_path)
        self.assertEqual(approval["render_file"], edit["render_file"])
        self.assertTrue(export_review.snapshot()["items"][0]["export_approved"])

        te.discard_edit(concept_id="c1", format="long_form", note="go back")
        self.assertIsNone(export_review.approval_is_current(approved_path))
        self.assertEqual(export_review.snapshot()["items"][0]["source"], "AUTOMATED")

    def test_an_edit_can_be_sent_back_to_the_editor(self):
        self.export()
        te.import_edit(concept_id="c1", format="long_form", video_path=str(self.edited_video()), probe=fake_probe())
        item = export_review.snapshot()["items"][0]
        snapshot = export_review.apply_action(result_file=item["result_file"], decision="RETURN_TO_EDITOR",
                                              note="the end card is too long")
        self.assertEqual(snapshot["rework"], 1)
        request = json.loads((self.root / "rework" / "c1.long_form.final_export_rework.json").read_text())
        self.assertEqual(request["target"], "FINAL_EDIT")


if __name__ == "__main__":
    unittest.main()
