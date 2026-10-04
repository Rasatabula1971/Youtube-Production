import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402
from testing_isolation import ModuleIsolation  # noqa: E402

_ISOLATION = ModuleIsolation(server)


def setUpModule() -> None:
    # Never read the real pipeline outputs of the machine running the tests.
    _ISOLATION.start()


def tearDownModule() -> None:
    _ISOLATION.stop()


class ToolsBackendTests(unittest.TestCase):
    """UI-15 (D-123): job history, job logs and system health."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.logs = root / "jobs"
        self.logs.mkdir()
        for target in (
            mock.patch.object(server, "UI_OUTPUT_DIR", root),
            mock.patch.object(server, "JOB_LOG_DIR", self.logs),
            mock.patch.object(server, "JOB_HISTORY_FILE", root / "job_history.jsonl"),
        ):
            target.start()
            self.addCleanup(target.stop)

    def job(self, stamp: str, action: str, status: str) -> dict:
        return {
            "id": f"{stamp}_{action}",
            "action_id": action,
            "label": action,
            "status": status,
            "started_at": "s",
            "finished_at": "f",
            "return_code": 0,
            "log_path": "ignored",
        }

    def test_history_is_newest_first_and_merges_old_logs(self) -> None:
        server.record_job_history(self.job("20261001_100000", "fair_doctor", "SUCCEEDED"))
        server.record_job_history(self.job("20261002_100000", "viral_radar", "FAILED"))
        (self.logs / "20260930_090000_viral_radar.log").write_text("old run")
        (self.logs / "20261002_100000_viral_radar.log").write_text("new run")
        (self.logs / "notes.log").write_text("not a job log")
        rows = server.job_history()
        self.assertEqual(
            [(r["id"], r["status"]) for r in rows],
            [
                ("20261002_100000_viral_radar", "FAILED"),
                ("20261001_100000_fair_doctor", "SUCCEEDED"),
                ("20260930_090000_viral_radar", "UNKNOWN"),
            ],
        )
        self.assertEqual([r["has_log"] for r in rows], [True, False, True])
        self.assertNotIn("log_path", rows[0])

    def test_history_is_trimmed(self) -> None:
        with mock.patch.object(server, "JOB_HISTORY_KEEP", 3):
            for n in range(5):
                server.record_job_history(self.job(f"2026100{n}_100000", "fair_doctor", "SUCCEEDED"))
        lines = server.JOB_HISTORY_FILE.read_text().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(json.loads(lines[-1])["id"], "20261004_100000_fair_doctor")

    def test_job_log_only_reads_job_logs(self) -> None:
        (self.logs / "20261002_100000_viral_radar.log").write_text("hello")
        self.assertEqual(server.job_log_text("20261002_100000_viral_radar"), "hello")
        for bad in ["../job_history", "20261002_100000_VIRAL", "20261002_100000_missing", "", "x/../../etc/passwd"]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    server.job_log_text(bad)

    def test_health_reports_status_without_secrets(self) -> None:
        now = datetime.now(timezone.utc)
        with mock.patch.object(server.shutil, "which", return_value="/usr/bin/x"), \
                mock.patch.object(server, "structural_ffmpeg_available", return_value=True), \
                mock.patch.object(server.human_video_intake, "_load_api_key", return_value="SECRET-KEY-123"), \
                mock.patch.object(server.radar_scheduler, "load_status",
                                  return_value={"checked_at": (now - timedelta(hours=1)).isoformat(), "action": "SNAPSHOTS"}):
            server.record_job_history(self.job("20261001_100000", "fair_doctor", "SUCCEEDED"))
            health = {c["id"]: c for c in server.system_health()}
        self.assertEqual(health["yt_dlp"]["status"], "READY")
        self.assertEqual(health["youtube_api"]["status"], "READY")
        self.assertEqual(health["scheduler"]["status"], "READY")
        self.assertIsNone(health["scheduler"]["action_id"])
        self.assertEqual(health["fair_doctor"]["status"], "READY")
        self.assertEqual(health["vidiq_doctor"]["status"], "UNKNOWN")
        self.assertNotIn("SECRET-KEY-123", json.dumps(health))

    def test_stale_or_missing_scheduler_offers_install(self) -> None:
        old = (datetime.now(timezone.utc) - timedelta(hours=9)).isoformat()
        for status, expected in ((None, "MISSING"), ({"checked_at": old, "action": "NOT_DUE"}, "WARN")):
            with self.subTest(expected=expected), \
                    mock.patch.object(server.radar_scheduler, "load_status", return_value=status):
                row = next(c for c in server.system_health() if c["id"] == "scheduler")
                self.assertEqual(row["status"], expected)
                self.assertEqual(row["action_id"], "exp13_auto_refresh_install")
                self.assertIn(row["action_id"], server.ACTION_DEFS)

    def test_doctor_actions_exist(self) -> None:
        for row in server.system_health():
            if row["action_id"]:
                self.assertIn(row["action_id"], server.ACTION_DEFS)

    def test_http_endpoints(self) -> None:
        (self.logs / "20261002_100000_viral_radar.log").write_text("radar output")
        httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        try:
            with urllib.request.urlopen(base + "/api/tools", timeout=10) as response:
                payload = json.loads(response.read())
            self.assertIn("health", payload)
            self.assertEqual(payload["jobs"][0]["id"], "20261002_100000_viral_radar")
            with urllib.request.urlopen(base + "/api/job-log?id=20261002_100000_viral_radar", timeout=10) as response:
                self.assertEqual(json.loads(response.read())["text"], "radar output")
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(base + "/api/job-log?id=..%2Fjob_history", timeout=10)
            self.assertEqual(caught.exception.code, 404)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
