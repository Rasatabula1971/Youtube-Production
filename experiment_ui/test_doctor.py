"""The one-click doctor (D-169): every check reports on its own."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import doctor  # noqa: E402


class DoctorTests(unittest.TestCase):
    def test_every_check_reports_even_when_one_crashes_or_times_out(self) -> None:
        def ok() -> tuple[str, str]:
            return doctor.READY, "fine"

        def boom() -> tuple[str, str]:
            raise RuntimeError("provider exploded")

        def slow() -> tuple[str, str]:
            raise subprocess.TimeoutExpired(cmd="x", timeout=20)

        with tempfile.TemporaryDirectory() as tmp:
            result_file = Path(tmp) / "ui" / "doctor.json"
            with patch.object(doctor, "RESULT_FILE", result_file):
                report = doctor.run([("a", "A", ok), ("b", "B", boom), ("c", "C", slow)])
                saved = json.loads(result_file.read_text(encoding="utf-8"))
                self.assertEqual(doctor.last_report()["ready"], 1)
        statuses = {row["id"]: row["status"] for row in report["checks"]}
        self.assertEqual(statuses, {"a": "READY", "b": "MISSING", "c": "MISSING"})
        details = {row["id"]: row["detail"] for row in report["checks"]}
        self.assertIn("provider exploded", details["b"])
        self.assertIn("Timed out", details["c"])
        self.assertEqual((report["ready"], report["warn"], report["missing"]), (1, 0, 2))
        self.assertEqual(saved["checks"][0]["id"], "a")
        self.assertTrue(all("ms" in row for row in report["checks"]))

    def test_youtube_key_check_never_calls_out_without_a_plausible_key(self) -> None:
        with patch.object(doctor, "env_value", return_value=""):
            self.assertEqual(doctor.check_youtube_key()[0], doctor.MISSING)
        with patch.object(doctor, "env_value", return_value="AIza" + "x" * 34):
            status, detail = doctor.check_youtube_key()
        self.assertEqual(status, doctor.WARN)
        self.assertIn("38 characters", detail)

    def test_youtube_key_check_reads_the_live_answer(self) -> None:
        import experiment_01_discovery.youtube_discovery as discovery

        key = "AIza" + "y" * 35
        with (
            patch.object(doctor, "env_value", return_value=key),
            patch.object(discovery, "api_get", return_value={"items": [{"id": doctor.YOUTUBE_PROBE_VIDEO}]}) as call,
        ):
            status, detail = doctor.check_youtube_key()
        self.assertEqual(status, doctor.READY)
        self.assertIn("1 quota unit", detail)
        self.assertEqual(call.call_args.args[:2], ("videos", key))

    def test_binary_check_reports_missing_binaries(self) -> None:
        with patch.object(doctor.shutil, "which", return_value=None):
            status, detail = doctor.check_binary("ffmpeg")()
        self.assertEqual(status, doctor.MISSING)
        self.assertIn("ffmpeg", detail)

    def test_kokoro_check_names_what_is_missing(self) -> None:
        with patch.object(doctor.importlib.util, "find_spec", return_value=None):
            status, detail = doctor.check_kokoro()
        self.assertEqual(status, doctor.MISSING)
        self.assertIn("kokoro", detail)

    def test_the_default_check_list_covers_every_key_and_binary(self) -> None:
        ids = [check_id for check_id, _, _ in doctor.CHECKS]
        for needed in ("youtube_key", "gemini", "ffmpeg", "ffprobe", "yt_dlp", "search", "kokoro", "narration", "images", "upload", "disk"):
            self.assertIn(needed, ids)


if __name__ == "__main__":
    unittest.main()
