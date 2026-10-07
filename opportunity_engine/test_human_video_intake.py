import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from opportunity_engine import active_source, human_topic_search as hts, human_video_intake as hvi  # noqa: E402
from opportunity_engine.packet_schema import validate_packet  # noqa: E402

VID = "dQw4w9WgXcQ"
NOW = datetime(2026, 10, 3, tzinfo=timezone.utc)


def metadata(**extra):
    value = {
        "video_id": VID,
        "title": "How hummingbirds hover",
        "description": "",
        "tags": ["birds", "physics"],
        "channel_id": "UC1",
        "channel_title": "Nature Lab",
        "published_at": "2026-09-23T00:00:00Z",
        "duration_seconds": 640,
        "views": 420000,
        "likes": 21000,
        "comments": 900,
        "made_for_kids": False,
        "live_broadcast": "none",
        "measurement_source": "YOUTUBE_DATA_API",
    }
    value.update(extra)
    return value


class ParseVideoIdTests(unittest.TestCase):
    def test_accepted_link_shapes(self):
        for raw in (
            VID,
            f"https://www.youtube.com/watch?v={VID}",
            f"https://www.youtube.com/watch?feature=share&v={VID}&t=42s",
            f"youtube.com/watch?v={VID}",
            f"https://m.youtube.com/watch?v={VID}",
            f"https://music.youtube.com/watch?v={VID}",
            f"https://youtu.be/{VID}?si=abc",
            f"https://www.youtube.com/shorts/{VID}",
            f"https://www.youtube.com/embed/{VID}",
            f"https://www.youtube.com/live/{VID}?feature=share",
            f"  https://www.youtube-nocookie.com/embed/{VID}  ",
        ):
            self.assertEqual(hvi.parse_video_id(raw), VID, raw)

    def test_rejected_inputs(self):
        for raw in (
            "",
            "   ",
            f"https://vimeo.com/{VID}",
            f"https://youtube.com.evil.example/watch?v={VID}",
            "https://www.youtube.com/playlist?list=PL123",
            "https://www.youtube.com/@veritasium",
            "https://www.youtube.com/results?search_query=tyres",
            "https://www.youtube.com/watch?v=short",
            f"https://www.youtube.com/watch?v={VID}x",
            f"javascript:alert('{VID}')",
            f"ftp://youtube.com/watch?v={VID}",
            "https://youtu.be/",
        ):
            with self.assertRaises(hvi.IntakeError, msg=raw):
                hvi.parse_video_id(raw)


class FetchMetadataTests(unittest.TestCase):
    def fetchers(self, api, ytdlp):
        return patch.dict(hvi.FETCHERS, {"youtube_api": api, "yt_dlp": ytdlp}, clear=True)

    def test_api_failure_falls_back_to_yt_dlp(self):
        def api(video_id):
            raise hvi.IntakeError("quota exceeded")

        with self.fetchers(api, lambda video_id: metadata(measurement_source="YT_DLP")):
            result = hvi.fetch_metadata(VID)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["metadata"]["measurement_source"], "YT_DLP")
        self.assertEqual(
            [(a["backend"], a["status"]) for a in result["attempts"]],
            [("youtube_api", "FAILED"), ("yt_dlp", "COMPLETE")],
        )

    def test_definitive_not_found_stops_without_fallback(self):
        def never(video_id):
            raise AssertionError("must not fall back after a definitive answer")

        with self.fetchers(lambda video_id: None, never):
            result = hvi.fetch_metadata(VID)
        self.assertEqual(result["status"], "VIDEO_UNAVAILABLE")

    def test_all_failures_are_failed_not_unavailable(self):
        def fail(video_id):
            raise hvi.IntakeError("down")

        with self.fetchers(fail, fail):
            result = hvi.fetch_metadata(VID)
        self.assertEqual(result["status"], "METADATA_FAILED")
        self.assertEqual(len(result["attempts"]), 2)

    def test_api_item_mapping(self):
        item = {
            "id": VID,
            "snippet": {"title": "T", "channelId": "UC1", "channelTitle": "C", "publishedAt": "2026-01-01T00:00:00Z", "tags": ["a"]},
            "statistics": {"viewCount": "1200", "likeCount": "30"},
            "contentDetails": {"duration": "PT1H2M3S"},
            "status": {"madeForKids": True},
        }
        mapped = hvi.metadata_from_api_item(item)
        self.assertEqual((mapped["views"], mapped["likes"], mapped["comments"]), (1200, 30, None))
        self.assertEqual(mapped["duration_seconds"], 3723)
        self.assertTrue(mapped["made_for_kids"])

    def test_yt_dlp_mapping_handles_dates(self):
        mapped = hvi.metadata_from_yt_dlp(
            {"id": VID, "title": "T", "channel": "C", "upload_date": "20260921", "duration": 45, "view_count": 9}
        )
        self.assertEqual(mapped["published_at"], "2026-09-21T00:00:00+00:00")
        self.assertEqual(mapped["duration_seconds"], 45)
        self.assertIsNone(mapped["made_for_kids"])


class YtDlpCommandTests(unittest.TestCase):
    def run_with(self, completed):
        with (
            patch.object(hvi.shutil, "which", return_value="/bin/yt-dlp"),
            patch.object(hvi.subprocess, "run", return_value=completed) as run,
        ):
            return hvi.fetch_via_yt_dlp(VID), run

    def test_metadata_only_no_shell(self):
        info = {"id": VID, "title": "T", "duration": 30}
        result, run = self.run_with(subprocess.CompletedProcess([], 0, stdout=json.dumps(info), stderr=""))
        self.assertEqual(result["title"], "T")
        command = run.call_args.args[0]
        self.assertIn("--skip-download", command)
        self.assertIn("--no-playlist", command)
        self.assertEqual(command[-2:], ["--", f"https://www.youtube.com/watch?v={VID}"])
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_private_video_is_unavailable(self):
        result, _ = self.run_with(
            subprocess.CompletedProcess([], 1, stdout="", stderr="ERROR: [youtube] x: Private video. Sign in")
        )
        self.assertIsNone(result)

    def test_other_errors_and_mismatched_ids_raise(self):
        with self.assertRaisesRegex(hvi.IntakeError, "429"):
            self.run_with(subprocess.CompletedProcess([], 1, stdout="", stderr="HTTP Error 429"))
        with self.assertRaisesRegex(hvi.IntakeError, "different item"):
            self.run_with(subprocess.CompletedProcess([], 0, stdout=json.dumps({"id": "other"}), stderr=""))
        with self.assertRaisesRegex(hvi.IntakeError, "unreadable"):
            self.run_with(subprocess.CompletedProcess([], 0, stdout="not json", stderr=""))

    def test_timeout_is_reported(self):
        with (
            patch.object(hvi.shutil, "which", return_value="/bin/yt-dlp"),
            patch.object(hvi.subprocess, "run", side_effect=subprocess.TimeoutExpired("yt-dlp", 60)),
        ):
            with self.assertRaisesRegex(hvi.IntakeError, "timed out"):
                hvi.fetch_via_yt_dlp(VID)


class PacketAndStorageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for item in (
            patch.object(hvi, "PACKETS_DIR", root / "human_video"),
            patch.object(active_source, "ACTIVE_FILE", root / "active.json"),
        ):
            item.start()
            self.addCleanup(item.stop)

    def test_packet_is_valid_and_routed_to_science_inside(self):
        packet = hvi.build_video_packet(metadata(), note="Wings hum!", now=NOW)
        self.assertEqual(validate_packet(packet), [])
        self.assertEqual(packet["source_type"], "HUMAN_VIDEO")
        self.assertEqual(packet["opportunity_id"], f"opp_human_video__{VID.lower()}")
        self.assertEqual(packet["channel"]["route"], "ACTIVE_CHANNEL")
        self.assertEqual(packet["formats"], ["long_form"])
        self.assertEqual(packet["candidate_videos"][0]["age_days"], 10.0)
        self.assertEqual(packet["human_notes"], ["Wings hum!"])
        self.assertEqual(packet["evidence_state"]["historical_demand"]["level"], "UNASSESSED")

    def test_notes_do_not_change_the_evidence_hash(self):
        a = hvi.build_video_packet(metadata(), note="one", now=NOW)
        b = hvi.build_video_packet(metadata(), note="two", now=NOW)
        self.assertEqual(a["packet_sha256"], b["packet_sha256"])

    def test_routes_shorts_kids_and_future_channels(self):
        self.assertEqual(hvi.build_video_packet(metadata(duration_seconds=50), now=NOW)["formats"], ["short"])
        kids = hvi.build_video_packet(metadata(made_for_kids=True), now=NOW)
        self.assertEqual(kids["channel"]["rule_id"], "EX-MADE-FOR-KIDS")
        mods = hvi.build_video_packet(metadata(title="My project car turbo kit"), now=NOW)
        self.assertEqual(mods["channel"]["channel_id"], "car_modifications")

    def test_intake_saves_once_per_video_and_reports_failures(self):
        with patch.object(hvi, "fetch_metadata", return_value={"status": "COMPLETE", "metadata": metadata(), "attempts": []}):
            hvi.intake(f"https://youtu.be/{VID}", note="first")
            hvi.intake(f"https://www.youtube.com/watch?v={VID}", note="second")
        saved = hvi.list_packets()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["human_notes"], ["second"])
        with patch.object(hvi, "fetch_metadata", return_value={"status": "VIDEO_UNAVAILABLE", "attempts": []}):
            with self.assertRaisesRegex(hvi.IntakeError, "private, removed"):
                hvi.intake("abcdefghijk")
        with patch.object(
            hvi,
            "fetch_metadata",
            return_value={"status": "METADATA_FAILED", "attempts": [{"backend": "yt_dlp", "status": "FAILED", "error": "boom"}]},
        ):
            with self.assertRaisesRegex(hvi.IntakeError, "yt_dlp: boom"):
                hvi.intake("abcdefghijk")
        self.assertIsNone(hvi.load_packet("abcdefghijk"))
        self.assertIsNone(hvi.load_packet("../../etc/x"))

    def save(self, **extra):
        packet = hvi.build_video_packet(metadata(**extra), now=NOW)
        hvi.save_packet(packet)
        return packet

    def test_active_source_freezes_a_study_row(self):
        with self.assertRaisesRegex(ValueError, "Submit this video first"):
            active_source.set_active(VID)
        packet = self.save()
        record = active_source.set_active(VID)
        row = record["study_set"][0]
        self.assertEqual(row["handoff_id"], f"human_video:{VID}")
        self.assertEqual(row["format_candidate"], "long_form_candidate")
        self.assertEqual(row["human_opportunity_gate"]["opportunity_id"], packet["opportunity_id"])
        self.assertEqual(active_source.load_active(), record)

        # Re-measuring the video later does not change the frozen decision.
        self.save(views=999999)
        self.assertEqual(active_source.load_active()["study_set"][0]["views"], 420000)

        # Losing the packet orphans the decision.
        hvi.packet_path(VID).unlink()
        self.assertIsNone(active_source.load_active())
        self.assertTrue(active_source.clear_active())
        self.assertFalse(active_source.clear_active())

    def test_replication_context_rules(self):
        """D-174: title search, never the seed or its channel, one per channel, seed stays first."""
        self.save()
        settings = hts.topic_config()

        def searcher(query, limit, timeout):
            self.assertIn("hummingbirds hover", query.lower())
            return [
                {"video_id": "samechan001", "title": "Hummingbirds hover again", "channel_id": "UC1", "channel_title": "Nature Lab", "duration_seconds": 400, "views": 8_000_000},
                {"video_id": "otherchan01", "title": "How hummingbirds hover", "channel_id": "UC2", "channel_title": "Bird Lab", "duration_seconds": 300, "views": 700_000},
            ]

        record = active_source.set_active(VID, with_context=True, searcher=searcher, measurer=lambda ids: {})
        self.assertEqual([r["video_id"] for r in record["study_set"]], [VID, "otherchan01"])
        self.assertEqual(record["context_search"]["status"], "FOUND")
        self.assertEqual(record["context_search"]["companion_count"], 1)
        self.assertEqual(active_source.load_active(), record)
        self.assertEqual(active_source.summary(record)["video_count"], 2)
        self.assertEqual(int(settings["max_study_videos"]) - 1, 3)

        # A failed search leaves the seed alone and says why; the record stays valid.
        def broken(query, limit, timeout):
            raise hts.IntakeError("yt-dlp is not installed")

        record = active_source.set_active(VID, with_context=True, searcher=broken)
        self.assertEqual(len(record["study_set"]), 1)
        self.assertEqual(record["context_search"]["status"], "SEARCH_FAILED")
        self.assertIn("yt-dlp", record["context_search"]["reason"])
        self.assertEqual(active_source.load_active(), record)

        # Without the flag nothing is searched (the default for library callers).
        record = active_source.set_active(VID, searcher=broken)
        self.assertEqual(record["context_search"]["status"], "SKIPPED")

        # A context row that lost its role marks the record as not ours.
        tampered = dict(record, study_set=record["study_set"] + [dict(record["study_set"][0], video_id="x" * 11)])
        active_source.ACTIVE_FILE.write_text(json.dumps(tampered), encoding="utf-8")
        self.assertIsNone(active_source.load_active())

    def test_context_seed_text_strips_hashtags_and_links(self):
        settings = {"max_seed_chars": 40}
        self.assertEqual(
            active_source.context_seed_text("Why tyres squeal #shorts #physics https://x.y/z", settings),
            "Why tyres squeal",
        )
        long = "a very long title that keeps going on and on past the limit"
        text = active_source.context_seed_text(long, settings)
        self.assertLessEqual(len(text), 40)
        self.assertEqual(text, "a very long title that keeps going on")
        self.assertEqual(active_source.context_seed_text(None, settings), "")

    def test_excluded_video_needs_explicit_override(self):
        self.save(made_for_kids=True)
        with self.assertRaisesRegex(ValueError, "EX-MADE-FOR-KIDS"):
            active_source.set_active(VID)
        self.assertEqual(active_source.set_active(VID, allow_excluded=True)["channel_route"], "EXCLUDED")

    def test_corrupt_active_file_is_ignored(self):
        active_source.ACTIVE_FILE.write_text("{not json", encoding="utf-8")
        self.assertIsNone(active_source.load_active())


if __name__ == "__main__":
    unittest.main()
