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

    class Answer:
        def __init__(self, body: bytes) -> None:
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self) -> bytes:
            return self.body

    def test_youtube_key_check_reads_the_live_answer(self) -> None:
        key = "AIza" + "y" * 35
        answer = self.Answer(json.dumps({"items": [{"id": doctor.YOUTUBE_PROBE_VIDEO}]}).encode())
        with (
            patch.object(doctor, "env_value", return_value=key),
            patch.object(doctor.urllib.request, "urlopen", return_value=answer) as call,
        ):
            status, detail = doctor.check_youtube_key()
        self.assertEqual(status, doctor.READY)
        self.assertIn("1 quota unit", detail)
        request = call.call_args.args[0]
        self.assertTrue(request.full_url.startswith("https://www.googleapis.com/youtube/v3/videos?"))
        self.assertEqual(call.call_args.kwargs["timeout"], doctor.CHECK_TIMEOUT_SECONDS)

    def test_a_refused_key_is_reported_not_fatal(self) -> None:
        """Audit 2 F1: a bad key used to end the whole request with no answer."""
        import io
        import urllib.error

        key = "AIza" + "z" * 35
        cases = {
            b'{"error":{"errors":[{"reason":"keyInvalid"}],"message":"API key not valid"}}': "not valid",
            b'{"error":{"errors":[{"reason":"quotaExceeded"}]}}': "quota exceeded",
            b'{"error":{"errors":[{"reason":"accessNotConfigured"}]}}': "not enabled",
        }
        for body, words in cases.items():
            with self.subTest(words=words):
                error = urllib.error.HTTPError("https://x", 403, "Forbidden", {}, io.BytesIO(body))
                with (
                    patch.object(doctor, "env_value", return_value=key),
                    patch.object(doctor.urllib.request, "urlopen", side_effect=error),
                ):
                    status, detail = doctor.check_youtube_key()
                self.assertEqual(status, doctor.MISSING)
                self.assertIn(words, detail)
                self.assertNotIn(key, detail)
        with (
            patch.object(doctor, "env_value", return_value=key),
            patch.object(doctor.urllib.request, "urlopen", side_effect=urllib.error.URLError("https://x?key=" + key)),
        ):
            status, detail = doctor.check_youtube_key()
        self.assertEqual(status, doctor.WARN)
        self.assertNotIn(key, detail)

    def test_a_check_that_exits_still_reports(self) -> None:
        def exits() -> tuple[str, str]:
            raise SystemExit("fatal")

        with tempfile.TemporaryDirectory() as tmp, patch.object(doctor, "RESULT_FILE", Path(tmp) / "d.json"):
            report = doctor.run([("x", "X", exits)])
        self.assertEqual(report["checks"][0]["status"], doctor.MISSING)
        self.assertIn("SystemExit", report["checks"][0]["detail"])

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
