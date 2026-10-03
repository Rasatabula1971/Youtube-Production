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

from opportunity_engine import active_source  # noqa: E402
from opportunity_engine import human_topic_search as hts  # noqa: E402
from opportunity_engine.human_video_intake import IntakeError  # noqa: E402
from opportunity_engine.packet_schema import validate_packet  # noqa: E402

NOW = datetime(2026, 10, 3, tzinfo=timezone.utc)


def vid(n):
    return f"vid{n:08d}"


def result(n, title, channel, views=None, duration=600):
    return {
        "video_id": vid(n),
        "title": title,
        "channel_id": channel,
        "channel_title": channel.upper(),
        "duration_seconds": duration,
        "views": views,
    }


SEARCH = {
    0: [
        result(1, "Why aircraft windows are round", "ch1"),
        result(2, "Round airplane windows explained", "ch2"),
        result(3, "Best pasta recipe", "ch3"),
    ],
    1: [
        result(1, "Why aircraft windows are round", "ch1"),
        result(4, "Aircraft window shapes: the Comet disaster", "ch4"),
        result(5, "Aircraft windows reaction compilation", "ch5"),
        result(6, "Why are plane windows round? #shorts", "ch1", duration=40),
    ],
}
MEASURED = {
    vid(1): {"views": 2_400_000, "published_at": "2025-10-03T00:00:00Z", "likes": 1},
    vid(2): {"views": 650_000, "published_at": "2026-09-03T00:00:00Z"},
    vid(4): {"views": 900_000, "published_at": "2024-01-01T00:00:00Z"},
    vid(5): {"views": 3_000_000},
    vid(6): {"views": 120_000},
}


def fake_searcher(log):
    def search(query, limit, timeout):
        index = len(log)
        log.append(query)
        if index >= 3:
            raise IntakeError("HTTP Error 429")
        return SEARCH.get(index, [])

    return search


class SeedTests(unittest.TestCase):
    def test_question_and_topic_seeds(self):
        question = hts.normalize_seed("  Why does an  F1 car suddenly lose grip in rain? ")
        self.assertEqual(question["kind"], "QUESTION")
        self.assertEqual(question["core"], "F1 car suddenly lose grip in rain")
        self.assertEqual(question["keywords"], ["f1", "car", "lose", "grip", "rain"])
        self.assertEqual(question["topic_key"], "f1_car_suddenly_lose_grip_in_rain")
        topic = hts.normalize_seed("Turbo lag")
        self.assertEqual((topic["kind"], topic["keywords"]), ("TOPIC", ["turbo", "lag"]))

    def test_rejected_seeds(self):
        for raw in ("", "   ", "x" * 200, "https://youtu.be/dQw4w9WgXcQ", "why is it?"):
            with self.assertRaises(IntakeError, msg=raw):
                hts.normalize_seed(raw)

    def test_variants_are_unique_and_capped(self):
        variants = hts.search_variants(hts.normalize_seed("Turbo lag"))
        self.assertEqual(
            variants,
            ["Turbo lag", "Turbo lag explained", "how Turbo lag works", "science of Turbo lag", "Turbo lag #shorts"],
        )
        self.assertEqual(len({v.lower() for v in variants}), len(variants))

    def test_relevance_needs_two_keyword_hits(self):
        keywords = ["aircraft", "windows", "round"]
        self.assertTrue(hts.relevance("Why aircraft windows are round", keywords)["relevant"])
        self.assertTrue(hts.relevance("Aircraft window shapes", keywords)["relevant"])
        self.assertFalse(hts.relevance("Round pasta recipe", keywords)["relevant"])
        self.assertTrue(hts.relevance("Hummingbirds hovering", ["hummingbird"])["relevant"])


class ExploreTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for item in (
            patch.object(hts, "PACKETS_DIR", self.root / "human_topic"),
            patch.object(active_source, "ACTIVE_FILE", self.root / "active.json"),
        ):
            item.start()
            self.addCleanup(item.stop)

    def explore(self, measurer=None, **kw):
        log = []
        packet = hts.explore(
            "Why aircraft windows are round",
            searcher=fake_searcher(log),
            measurer=measurer or (lambda ids: {i: MEASURED[i] for i in ids if i in MEASURED}),
            now=NOW,
            **kw,
        )
        return packet, log

    def test_explore_builds_a_rule_backed_packet(self):
        packet, log = self.explore(note="Comet history")
        self.assertEqual(validate_packet(packet), [])
        self.assertEqual(packet["source_type"], "HUMAN_TOPIC")
        self.assertEqual(packet["opportunity_id"], "opp_human_topic__aircraft_windows_are_round")
        self.assertEqual(packet["seed"]["question"], "Why aircraft windows are round")
        self.assertEqual(len(log), 5)
        intake = packet["intake"]
        self.assertEqual([e["status"] for e in intake["search_log"]], ["COMPLETE"] * 3 + ["FAILED"] * 2)
        self.assertEqual(intake["irrelevant_count"], 1)
        self.assertEqual([v["rule_id"] for v in intake["excluded_videos"]], ["EX-FORMAT"])
        ids = [v["video_id"] for v in packet["candidate_videos"]]
        self.assertEqual(ids, [vid(1), vid(4), vid(2), vid(6)])
        self.assertEqual(packet["candidate_videos"][0]["age_days"], 365.0)
        self.assertEqual(packet["candidate_videos"][3]["format"], "short")
        self.assertEqual(packet["formats"], ["long_form", "short"])
        demand = packet["evidence_state"]["historical_demand"]
        self.assertEqual((demand["level"], demand["rule_id"]), ("STRONG", "HT-DEMAND-STRONG"))
        replication = packet["evidence_state"]["cross_channel_replication"]
        self.assertEqual((replication["level"], replication["rule_id"]), ("MODERATE", "HT-CCR-MODERATE"))
        self.assertEqual(packet["evidence_state"]["viewer_need"]["level"], "HYPOTHESIS")
        self.assertEqual(packet["human_notes"], ["Comet history"])
        self.assertEqual(hts.load_packet("aircraft_windows_are_round")["opportunity_id"], packet["opportunity_id"])

    def test_measurement_failure_falls_back_to_search_metadata(self):
        def broken(ids):
            raise IntakeError("YOUTUBE_API_KEY is not configured")

        packet, _ = self.explore(measurer=broken)
        self.assertEqual(packet["intake"]["measurement"]["source"], "YT_DLP_FLAT_SEARCH")
        self.assertIn("YOUTUBE_API_KEY", packet["intake"]["measurement"]["error"])
        self.assertEqual(packet["evidence_state"]["historical_demand"]["level"], "WEAK")
        self.assertEqual(packet["evidence_state"]["cross_channel_replication"]["level"], "NONE")

    def test_every_search_failing_saves_nothing(self):
        def fail(query, limit, timeout):
            raise IntakeError("yt-dlp is not installed")

        with self.assertRaisesRegex(IntakeError, "every variant"):
            hts.explore("Turbo lag", searcher=fail, measurer=lambda ids: {}, now=NOW)
        self.assertEqual(hts.list_packets(), [])

    def test_no_relevant_results_is_honest(self):
        packet = hts.explore(
            "Turbo lag",
            searcher=lambda q, l, t: [result(9, "Cooking show", "chx")],
            measurer=lambda ids: {},
            now=NOW,
        )
        self.assertEqual(packet["candidate_videos"], [])
        self.assertEqual(packet["evidence_state"]["historical_demand"]["level"], "UNASSESSED")
        # An API answer with no items is not an API measurement.
        self.assertEqual(packet["intake"]["measurement"]["source"], "YT_DLP_FLAT_SEARCH")
        with self.assertRaisesRegex(ValueError, "no relevant videos"):
            active_source.set_active_topic("turbo_lag")

    def test_future_channel_topic_is_routed_there(self):
        packet = hts.explore(
            "How annuity payments work",
            searcher=lambda q, l, t: [],
            measurer=lambda ids: {},
            now=NOW,
        )
        self.assertEqual(packet["channel"]["channel_id"], "retirement_ageing")

    def test_analyze_topic_selects_one_video_per_channel(self):
        self.explore()
        record = active_source.set_active_topic("aircraft_windows_are_round")
        rows = record["study_set"]
        self.assertEqual([r["video_id"] for r in rows], [vid(1), vid(4), vid(2)])
        self.assertEqual(rows[0]["handoff_id"], f"human_topic:aircraft_windows_are_round:{vid(1)}")
        self.assertEqual([r["study_set_sequence"] for r in rows], [1, 2, 3])
        self.assertEqual(rows[0]["human_opportunity_gate"]["source_type"], "HUMAN_TOPIC")
        self.assertEqual(active_source.load_active(), record)
        self.assertEqual(active_source.summary(record)["video_count"], 3)

        # Re-exploring later keeps the frozen study set while the packet identity holds.
        self.explore()
        self.assertEqual(active_source.load_active()["study_set"], rows)
        hts.packet_path("aircraft_windows_are_round").unlink()
        self.assertIsNone(active_source.load_active())

    def test_load_packet_rejects_unsafe_keys(self):
        self.assertIsNone(hts.load_packet("../secrets"))
        self.assertIsNone(hts.load_packet("UPPER"))


class FlatSearchTests(unittest.TestCase):
    def run_with(self, completed):
        with (
            patch.object(hts.shutil, "which", return_value="/bin/yt-dlp"),
            patch.object(hts.subprocess, "run", return_value=completed) as run,
        ):
            return hts.search_flat("turbo lag", 10, 45), run

    def test_flat_search_command_and_parsing(self):
        payload = {
            "_type": "playlist",
            "entries": [
                {"id": "dQw4w9WgXcQ", "title": "T", "channel": "C", "channel_id": "UC1", "duration": 61.0, "view_count": 5},
                {"id": "not-a-video-id"},
                "junk",
            ],
        }
        results, run = self.run_with(subprocess.CompletedProcess([], 0, stdout=json.dumps(payload), stderr=""))
        self.assertEqual([r["video_id"] for r in results], ["dQw4w9WgXcQ"])
        self.assertEqual(results[0]["views"], 5)
        command = run.call_args.args[0]
        self.assertIn("--flat-playlist", command)
        self.assertEqual(command[-2:], ["--", "ytsearch10:turbo lag"])
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_flat_search_failures(self):
        with self.assertRaisesRegex(IntakeError, "429"):
            self.run_with(subprocess.CompletedProcess([], 1, stdout="", stderr="ERROR: HTTP Error 429"))
        with self.assertRaisesRegex(IntakeError, "unreadable"):
            self.run_with(subprocess.CompletedProcess([], 0, stdout="<html>", stderr=""))
        with patch.object(hts.shutil, "which", return_value=None):
            with self.assertRaisesRegex(IntakeError, "not installed"):
                hts.search_flat("x", 1, 1)


if __name__ == "__main__":
    unittest.main()
