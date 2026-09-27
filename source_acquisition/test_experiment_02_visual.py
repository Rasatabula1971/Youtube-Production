from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import experiment_02_visual as visual


class Experiment02VisualEvidenceTests(unittest.TestCase):
    def patch_paths(self, stack: ExitStack, root: Path) -> None:
        prepared = root / "prepared"
        enriched = root / "enriched"
        acquired = root / "acquired"
        prepared.mkdir()
        enriched.mkdir()
        acquired.mkdir()

        stack.enter_context(patch.object(visual, "PROJECT_ROOT", root))
        stack.enter_context(patch.object(visual, "PREPARED_DIR", prepared))
        stack.enter_context(patch.object(visual, "ENRICHED_DIR", enriched))
        stack.enter_context(patch.object(visual, "ACQUISITION_ROOT", acquired))
        stack.enter_context(
            patch.object(
                visual,
                "VISUAL_SUMMARY_FILE",
                acquired / "visual_summary.json",
            )
        )
        stack.enter_context(patch.object(visual.base, "PROJECT_ROOT", root))
        stack.enter_context(patch.object(visual.base, "PREPARED_DIR", prepared))
        stack.enter_context(patch.object(visual.base, "ENRICHED_DIR", enriched))
        stack.enter_context(
            patch.object(visual.base, "ACQUISITION_ROOT", acquired)
        )

    def write_profile(self, path: Path, video_id: str = "abc123") -> None:
        path.write_text(
            json.dumps(
                {
                    "video_id": video_id,
                    "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                    "source_inputs": {},
                    "evidence": [],
                }
            ),
            encoding="utf-8",
        )

    def test_stream_url_command_requests_low_resolution_url_only(self):
        command = visual.stream_url_command(
            "yt-dlp",
            "https://www.youtube.com/watch?v=abc123",
        )

        self.assertIn("--get-url", command)
        self.assertIn("--format", command)
        self.assertIn("best[height<=360]/best", command)
        self.assertNotIn("--output", command)
        self.assertNotIn("--write-video", command)

    def test_scene_detection_command_has_no_saved_video_output(self):
        command = visual.scene_detection_command(
            "ffmpeg",
            stream_url="https://stream.invalid/video",
            destination_pattern=Path("scene_%04d.jpg"),
            threshold=0.28,
        )

        self.assertIn("select=gt(scene\,0.2800)", " ".join(command))
        self.assertIn("scene_%04d.jpg", command[-1])
        self.assertNotIn(".mp4", " ".join(command))

    def test_parse_scene_times_deduplicates_adjacent_showinfo_events(self):
        stderr = (
            "[showinfo] n:0 pts:1 pts_time:1.250\n"
            "[showinfo] n:1 pts:2 pts_time:1.250\n"
            "[showinfo] n:2 pts:3 pts_time:3.500\n"
        )

        self.assertEqual(
            visual.parse_scene_times(stderr),
            [1.25, 3.5],
        )

    def test_timing_notes_are_detector_claims_not_semantic_descriptions(self):
        payload = visual.timing_notes_payload(
            [1.0, 3.0, 7.0],
            duration=10.0,
        )

        self.assertFalse(
            payload["detector"]["semantic_interpretation"]
        )
        self.assertEqual(
            payload["summary"]["scene_transition_candidate_count"],
            3,
        )
        self.assertEqual(
            payload["summary"]["median_candidate_interval_seconds"],
            3.0,
        )
        self.assertIn(
            "transition candidate",
            payload["notes"][0]["observation"],
        )
        self.assertEqual(
            payload["notes"][1]["type"],
            "timing_note",
        )

    def test_pruned_scene_frames_keep_timestamp_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index in range(1, 6):
                (root / f"scene_{index:04d}.jpg").write_bytes(b"x")

            retained = visual.prune_scene_frames(
                root,
                scene_times=[1, 2, 3, 4, 5],
                maximum=3,
            )

            self.assertEqual(len(retained), 3)
            self.assertEqual(
                [item["timestamp_seconds"] for item in retained],
                [1, 3, 5],
            )
            self.assertEqual(
                len(list(root.glob("scene_*.jpg"))),
                3,
            )

    def test_visual_stage_waits_for_transcript_before_network(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            profile = visual.PREPARED_DIR / "abc123.json"
            self.write_profile(profile)

            stream = stack.enter_context(
                patch.object(visual, "resolve_stream_url")
            )

            result = visual.acquire_visual_one(
                profile,
                yt_dlp="yt-dlp-test",
                ffmpeg="ffmpeg-test",
                python_executable="python-test",
            )

        self.assertEqual(result["status"], "WAITING_FOR_TRANSCRIPT")
        stream.assert_not_called()

    def test_successful_visual_stage_rebuilds_combined_bundle(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            profile = visual.PREPARED_DIR / "abc123.json"
            self.write_profile(profile)

            video_dir = visual.ACQUISITION_ROOT / "abc123"
            video_dir.mkdir()
            transcript = video_dir / "abc123.en.vtt"
            transcript.write_text(
                "WEBVTT\n\n00:00.000 --> 00:01.000\nHello.\n",
                encoding="utf-8",
            )
            info = video_dir / "abc123.info.json"
            info.write_text(
                json.dumps({"duration": 10.0}),
                encoding="utf-8",
            )

            stack.enter_context(
                patch.object(
                    visual,
                    "resolve_stream_url",
                    return_value=(
                        "https://stream.invalid/video",
                        subprocess.CompletedProcess(
                            args=["yt-dlp"],
                            returncode=0,
                            stdout="https://stream.invalid/video\n",
                            stderr="",
                        ),
                    ),
                )
            )

            def fake_ffmpeg(command, **kwargs):
                command_text = " ".join(str(part) for part in command)
                if "opening_frame.jpg" in command_text:
                    (video_dir / "opening_frame.jpg").write_bytes(b"frame")
                    return subprocess.CompletedProcess(
                        args=command,
                        returncode=0,
                        stdout="",
                        stderr="",
                    )
                for index in range(1, 4):
                    (video_dir / f"scene_{index:04d}.jpg").write_bytes(b"scene")
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout="",
                    stderr=(
                        "[showinfo] pts_time:1.000\n"
                        "[showinfo] pts_time:3.000\n"
                        "[showinfo] pts_time:7.000\n"
                    ),
                )

            stack.enter_context(
                patch.object(
                    visual.subprocess,
                    "run",
                    side_effect=fake_ffmpeg,
                )
            )

            def fake_ingest(bundle_path, *, python_executable):
                bundle = json.loads(
                    Path(bundle_path).read_text(encoding="utf-8")
                )
                self.assertIn("notes", bundle)
                self.assertIn("opening_frame", bundle)
                self.assertEqual(bundle["video_id"], "abc123")
                (visual.ENRICHED_DIR / "abc123.json").write_text(
                    json.dumps({"video_id": "abc123"}),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(
                    args=["python-test"],
                    returncode=0,
                    stdout="ok",
                    stderr="",
                )

            stack.enter_context(
                patch.object(
                    visual.base,
                    "run_ingest",
                    side_effect=fake_ingest,
                )
            )

            result = visual.acquire_visual_one(
                profile,
                yt_dlp="yt-dlp-test",
                ffmpeg="ffmpeg-test",
                python_executable="python-test",
            )

        self.assertEqual(result["status"], "READY")
        self.assertFalse(result["full_video_saved"])
        self.assertEqual(
            result["scene_transition_candidate_count"],
            3,
        )
        self.assertEqual(
            result["retained_scene_frames"][0]["timestamp_seconds"],
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
