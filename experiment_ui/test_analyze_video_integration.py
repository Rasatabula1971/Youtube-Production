import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from opportunity_engine import active_source
from opportunity_engine import human_video_intake as hvi

VID = "dQw4w9WgXcQ"


def save_packet():
    packet = hvi.build_video_packet(
        {
            "video_id": VID,
            "title": "How hummingbirds hover",
            "tags": [],
            "channel_id": "UC9",
            "channel_title": "Nature Lab",
            "published_at": "2026-09-01T00:00:00Z",
            "duration_seconds": 600,
            "views": 400000,
            "likes": 1,
            "made_for_kids": False,
            "measurement_source": "YOUTUBE_DATA_API",
        }
    )
    hvi.save_packet(packet)
    return packet


class AnalyzeVideoIntegrationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.prepared = self.root / "profiles_to_complete"
        self.exp15 = self.root / "experiment_01_5"
        self.prepared.mkdir()
        self.exp15.mkdir()
        for item in (
            patch.object(active_source, "ACTIVE_FILE", self.root / "active.json"),
            patch.object(hvi, "PACKETS_DIR", self.root / "human_video"),
            patch.object(server, "EXP2_PREPARED_DIR", self.prepared),
            patch.object(server, "EXP15_DIR", self.exp15),
            patch.object(server, "opportunity_gate_snapshot", return_value={}),
        ):
            item.start()
            self.addCleanup(item.stop)

    def test_analyze_and_stop_are_locked_while_jobs_run_but_submit_is_not(self):
        self.assertIn("/api/opportunity/video/analyze", server.HUMAN_GATE_MUTATION_ROUTES)
        self.assertIn("/api/opportunity/video/stop", server.HUMAN_GATE_MUTATION_ROUTES)
        self.assertNotIn("/api/opportunity/video", server.HUMAN_GATE_MUTATION_ROUTES)

    def test_static_ui_has_the_analyze_video_card(self):
        static = Path(server.__file__).resolve().parent / "static"
        html = (static / "index.html").read_text(encoding="utf-8")
        script = (static / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="analyzeVideoForm"', html)
        self.assertIn('id="submittedVideos"', html)
        for needle in (
            "/api/opportunity/video/analyze",
            "/api/opportunity/video/stop",
            "CONFIRM_REPLACE: ",
            "renderSubmittedVideos(data.submitted_videos",
        ):
            self.assertIn(needle, script)

    def test_snapshot_lists_submitted_videos_and_the_active_one(self):
        save_packet()
        snapshot = server.submitted_videos_snapshot()
        self.assertEqual([v["video_id"] for v in snapshot["videos"]], [VID])
        self.assertEqual(snapshot["videos"][0]["route"], "ACTIVE_CHANNEL")
        self.assertIsNone(snapshot["active"])

    def test_replacing_existing_work_needs_confirmation(self):
        save_packet()
        (self.prepared / "oldvideo001.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "^CONFIRM_REPLACE: "):
            server.analyze_submitted_video(video_id=VID, confirm_replace=False, allow_excluded=False)
        self.assertIsNone(active_source.load_active())
        payload = server.analyze_submitted_video(video_id=VID, confirm_replace=True, allow_excluded=False)
        self.assertEqual(payload["active"]["video_id"], VID)
        # Re-selecting the active video is a no-op, not another confirmation.
        server.analyze_submitted_video(video_id=VID, confirm_replace=False, allow_excluded=False)

    def test_no_existing_work_needs_no_confirmation(self):
        save_packet()
        payload = server.analyze_submitted_video(video_id=VID, confirm_replace=False, allow_excluded=False)
        self.assertEqual(payload["active"]["video_id"], VID)

    def test_prepared_profiles_for_another_study_set_are_stale(self):
        (self.exp15 / "approved_study_set.json").write_text(
            json.dumps([{"video_id": VID}]), encoding="utf-8"
        )
        (self.prepared / "oldvideo001.json").write_text("{}", encoding="utf-8")
        self.assertEqual(server.exp2_artifact_state()["prepared_count"], 0)
        (self.prepared / "oldvideo001.json").unlink()
        (self.prepared / f"{VID}.json").write_text("{}", encoding="utf-8")
        self.assertEqual(server.exp2_artifact_state()["prepared_ids"], [VID])


if __name__ == "__main__":
    unittest.main()
