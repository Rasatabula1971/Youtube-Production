from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import experiment_02_evidence as acquisition


class Experiment02EvidenceAcquisitionTests(unittest.TestCase):
    def patch_paths(self, stack: ExitStack, root: Path) -> None:
        prepared = root / "prepared"
        enriched = root / "enriched"
        acquired = root / "acquired"
        prepared.mkdir()
        enriched.mkdir()
        acquired.mkdir()

        stack.enter_context(patch.object(acquisition, "PROJECT_ROOT", root))
        stack.enter_context(patch.object(acquisition, "PREPARED_DIR", prepared))
        stack.enter_context(patch.object(acquisition, "ENRICHED_DIR", enriched))
        stack.enter_context(patch.object(acquisition, "ACQUISITION_ROOT", acquired))
        stack.enter_context(
            patch.object(acquisition, "SUMMARY_FILE", acquired / "summary.json")
        )
        stack.enter_context(
            patch.object(acquisition, "INGEST_SCRIPT", root / "evidence_ingest.py")
        )

    def write_profile(self, path: Path, video_id: str = "abc123") -> None:
        path.write_text(
            json.dumps(
                {
                    "video_id": video_id,
                    "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                    "source_inputs": {
                        "transcript": {
                            "status": "NOT_PROVIDED",
                            "source": None,
                        }
                    },
                    "evidence": [],
                }
            ),
            encoding="utf-8",
        )

    def test_ytdlp_command_never_requests_video_media(self):
        command = acquisition.yt_dlp_command(
            "yt-dlp",
            url="https://www.youtube.com/watch?v=abc123",
            directory=Path("out"),
        )

        self.assertIn("--skip-download", command)
        self.assertIn("--write-subs", command)
        self.assertIn("--write-auto-subs", command)
        self.assertIn("--write-thumbnail", command)
        self.assertIn("--write-info-json", command)
        self.assertNotIn("-f", command)
        self.assertNotIn("--format", command)

    def test_transcript_selection_prefers_exact_english_vtt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "abc123.en-US.vtt").write_text("regional", encoding="utf-8")
            (root / "abc123.en.vtt").write_text("exact", encoding="utf-8")
            (root / "abc123.other.vtt").write_text("other", encoding="utf-8")

            selected = acquisition.find_transcript(root, "abc123")

        self.assertIsNotNone(selected)
        self.assertEqual(selected.name, "abc123.en.vtt")

    def test_enriched_profile_requires_matching_profile_hash_and_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared = root / "abc123.json"
            enriched = root / "enriched.json"
            self.write_profile(prepared)

            enriched.write_text(
                json.dumps(
                    {
                        "evidence_ingestion": {
                            "profile_source_sha256": acquisition.sha256_file(prepared),
                        },
                        "source_inputs": {
                            "transcript": {"status": "PROVIDED"}
                        },
                        "evidence": [
                            {
                                "evidence_id": "transcript.p0001",
                                "type": "transcript",
                                "observation": "Caption",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(
                acquisition.enriched_profile_ready(enriched, prepared)
            )

            prepared.write_text(
                prepared.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            self.assertFalse(
                acquisition.enriched_profile_ready(enriched, prepared)
            )

    def test_missing_transcript_does_not_run_offline_ingest(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            profile = acquisition.PREPARED_DIR / "abc123.json"
            self.write_profile(profile)

            completed = subprocess.CompletedProcess(
                args=["yt-dlp"],
                returncode=0,
                stdout="",
                stderr="",
            )
            run = stack.enter_context(
                patch.object(
                    acquisition.subprocess,
                    "run",
                    return_value=completed,
                )
            )
            ingest = stack.enter_context(
                patch.object(acquisition, "run_ingest")
            )

            result = acquisition.acquire_one(
                profile,
                yt_dlp="yt-dlp-test",
                python_executable="python-test",
            )

        self.assertEqual(result["status"], "TRANSCRIPT_UNAVAILABLE")
        self.assertTrue(result["network_called"])
        ingest.assert_not_called()
        self.assertEqual(run.call_count, 1)

    def test_ytdlp_429_is_reported_as_rate_limited(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            profile = acquisition.PREPARED_DIR / "abc123.json"
            self.write_profile(profile)

            completed = subprocess.CompletedProcess(
                args=["yt-dlp"],
                returncode=1,
                stdout="",
                stderr="ERROR: Unable to download video subtitles for 'en': HTTP Error 429: Too Many Requests",
            )
            stack.enter_context(
                patch.object(
                    acquisition.subprocess,
                    "run",
                    return_value=completed,
                )
            )
            ingest = stack.enter_context(
                patch.object(acquisition, "run_ingest")
            )

            result = acquisition.acquire_one(
                profile,
                yt_dlp="yt-dlp-test",
                python_executable="python-test",
            )

        self.assertEqual(result["status"], "RATE_LIMITED_429")
        self.assertIn("rate-limited", result["message"].lower())
        ingest.assert_not_called()

    def test_existing_transcript_reuses_files_and_skips_ytdlp(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            profile = acquisition.PREPARED_DIR / "abc123.json"
            self.write_profile(profile)

            video_dir = acquisition.ACQUISITION_ROOT / "abc123"
            video_dir.mkdir()
            transcript = video_dir / "abc123.en.vtt"
            transcript.write_text(
                "WEBVTT\n\n00:00.000 --> 00:01.000\nHello.\n",
                encoding="utf-8",
            )

            def fake_ingest(bundle_path, *, python_executable):
                enriched = acquisition.ENRICHED_DIR / "abc123.json"
                enriched.write_text(
                    json.dumps(
                        {
                            "evidence_ingestion": {
                                "profile_source_sha256": acquisition.sha256_file(profile),
                            },
                            "source_inputs": {
                                "transcript": {"status": "PROVIDED"}
                            },
                            "evidence": [
                                {
                                    "evidence_id": "transcript.t1",
                                    "type": "transcript",
                                    "observation": "Hello.",
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(
                    args=["python-test"],
                    returncode=0,
                    stdout="ok",
                    stderr="",
                )

            network = stack.enter_context(
                patch.object(acquisition.subprocess, "run")
            )
            stack.enter_context(
                patch.object(
                    acquisition,
                    "run_ingest",
                    side_effect=fake_ingest,
                )
            )

            result = acquisition.acquire_one(
                profile,
                yt_dlp="yt-dlp-test",
                python_executable="python-test",
            )

        self.assertEqual(result["status"], "READY")
        self.assertFalse(result["network_called"])
        network.assert_not_called()

    def test_current_enriched_profile_skips_network_and_reingestion(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            profile = acquisition.PREPARED_DIR / "abc123.json"
            self.write_profile(profile)
            enriched = acquisition.ENRICHED_DIR / "abc123.json"
            enriched.write_text(
                json.dumps(
                    {
                        "evidence_ingestion": {
                            "profile_source_sha256": acquisition.sha256_file(profile),
                        },
                        "source_inputs": {
                            "transcript": {"status": "PROVIDED"}
                        },
                        "evidence": [
                            {
                                "evidence_id": "transcript.p0001",
                                "type": "transcript",
                                "observation": "Ready.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            network = stack.enter_context(
                patch.object(acquisition.subprocess, "run")
            )
            ingest = stack.enter_context(
                patch.object(acquisition, "run_ingest")
            )

            result = acquisition.acquire_one(
                profile,
                yt_dlp="yt-dlp-test",
                python_executable="python-test",
            )

        self.assertEqual(result["status"], "READY_EXISTING")
        self.assertFalse(result["network_called"])
        network.assert_not_called()
        ingest.assert_not_called()


if __name__ == "__main__":
    unittest.main()
