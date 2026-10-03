import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from opportunity_engine import active_source, historical_adapter, inbox  # noqa: E402
from opportunity_engine import human_topic_search as hts  # noqa: E402
from opportunity_engine import human_video_intake as hvi  # noqa: E402
from opportunity_engine import viral_radar as vr  # noqa: E402
from opportunity_engine.test_viral_radar import MATURE, NOW, FakeApi  # noqa: E402
from opportunity_engine.test_viral_radar import item as radar_item  # noqa: E402

VID = "dQw4w9WgXcQ"


def video_metadata(video_id=VID, title="How hummingbirds hover"):
    return {
        "video_id": video_id,
        "title": title,
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


def study_item(video_id, topic, fmt="long_form_candidate"):
    return {
        "handoff_id": f"{video_id}:{topic}:{fmt}",
        "gate_status": "PASS",
        "video_id": video_id,
        "title": f"{topic} video",
        "channel_id": "UC1",
        "format_candidate": fmt,
        "niche": "automotive_racing",
        "views": 900000,
        "topic": topic,
        "topic_evidence": {"unique_channels": 4},
        "primary_metric": {"value": 2.0},
    }


class InboxTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.study_file = self.root / "study_set.json"
        for item in (
            patch.object(inbox, "STATE_FILE", self.root / "inbox_state.json"),
            patch.object(active_source, "ACTIVE_FILE", self.root / "active.json"),
            patch.object(hvi, "PACKETS_DIR", self.root / "human_video"),
            patch.object(hts, "PACKETS_DIR", self.root / "human_topic"),
            patch.object(historical_adapter, "STUDY_SET_FILE", self.study_file),
            patch.object(vr, "RADAR_DIR", self.root / "viral"),
            patch.object(vr, "STATE_FILE", self.root / "viral" / "state.json"),
            patch.object(vr, "SUMMARY_FILE", self.root / "viral" / "last_run.json"),
            patch.object(vr, "SNAPSHOT_FILE", self.root / "viral" / "snapshots.jsonl"),
            patch.object(vr, "PACKETS_DIR", self.root / "viral_packets"),
        ):
            item.start()
            self.addCleanup(item.stop)

    def save_video(self, video_id=VID, title="How hummingbirds hover", when=None):
        now = when or datetime(2026, 10, 3, tzinfo=timezone.utc)
        packet = hvi.build_video_packet(video_metadata(video_id, title), now=now)
        hvi.save_packet(packet)
        return packet

    def by_id(self, snapshot):
        return {item["opportunity_id"]: item for item in snapshot["items"]}

    def test_empty_inbox(self):
        snapshot = inbox.build_inbox({})
        self.assertEqual(snapshot["items"], [])
        self.assertEqual(set(snapshot["counts"]), set(inbox.STATUSES))
        self.assertIsNone(snapshot["historical_error"])

    def test_historical_items_follow_gate_decisions(self):
        self.study_file.write_text(
            json.dumps([study_item("a1", "brakes"), study_item("b1", "tyres_tires")]), encoding="utf-8"
        )
        os.utime(self.study_file, (1_700_000_000, 1_700_000_000))
        gate = {
            "ready_for_experiment_02": True,
            "opportunities": [
                {"opportunity_id": "automotive_racing:brakes:long_form_candidate", "decision": "APPROVE"},
                {"opportunity_id": "automotive_racing:tyres_tires:long_form_candidate", "decision": "HOLD"},
            ],
        }
        items = self.by_id(inbox.build_inbox(gate))
        brakes = items["opp_historical__automotive_racing__brakes__long_form_candidate"]
        tyres = items["opp_historical__automotive_racing__tyres_tires__long_form_candidate"]
        self.assertEqual((brakes["status"], brakes["is_active"]), ("APPROVED", True))
        self.assertEqual(tyres["status"], "SAVED")
        self.assertEqual(brakes["actions"], ["REVIEW_BELOW"])
        self.assertEqual(brakes["source_label"], "HISTORICAL")
        self.assertEqual(brakes["created_at"], "2023-11-14T22:13:20+00:00")
        with self.assertRaisesRegex(ValueError, "Historical review"):
            inbox.apply_action(brakes["opportunity_id"], "REJECT")

        # A human idea that is active takes the active slot from the historical approval.
        self.save_video()
        active_source.set_active(VID)
        snapshot = inbox.build_inbox(gate)
        self.assertEqual(snapshot["items"][0]["video_id"], VID)
        brakes = self.by_id(snapshot)[brakes["opportunity_id"]]
        self.assertFalse(brakes["is_active"])
        self.assertIn("Your own idea is the active study set", brakes["status_reason"])

    def test_unreadable_study_set_is_reported_not_fatal(self):
        self.study_file.write_text("{}", encoding="utf-8")
        self.save_video()
        snapshot = inbox.build_inbox({})
        self.assertIn("could not be read", snapshot["historical_error"])
        self.assertEqual(len(snapshot["items"]), 1)

    def test_save_reject_restore_human_ideas(self):
        packet = self.save_video()
        oid = packet["opportunity_id"]
        item = self.by_id(inbox.build_inbox({}))[oid]
        self.assertEqual((item["status"], item["actions"]), ("NEEDS_REVIEW", ["ANALYZE", "SAVE", "REJECT"]))
        inbox.apply_action(oid, "REJECT", note="Too generic")
        item = self.by_id(inbox.build_inbox({}))[oid]
        self.assertEqual((item["status"], item["status_reason"]), ("REJECTED", "Too generic"))
        self.assertEqual(item["actions"], ["RESTORE", "ANALYZE"])
        inbox.apply_action(oid, "SAVE")
        self.assertEqual(self.by_id(inbox.build_inbox({}))[oid]["status"], "SAVED")
        inbox.apply_action(oid, "RESTORE")
        self.assertEqual(self.by_id(inbox.build_inbox({}))[oid]["status"], "NEEDS_REVIEW")
        # Inbox choices never touch the evidence packet.
        self.assertEqual(hvi.load_packet(VID)["packet_sha256"], packet["packet_sha256"])

    def test_invalid_actions(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            inbox.apply_action("opp_x", "APPROVE")
        with self.assertRaisesRegex(ValueError, "Unknown opportunity"):
            inbox.apply_action("opp_human_video__missing", "SAVE")

    def test_future_channel_ideas_are_parked_on_the_shelf(self):
        packet = self.save_video("abcdefghijk", "My project car turbo kit install")
        item = self.by_id(inbox.build_inbox({}))[packet["opportunity_id"]]
        self.assertEqual(item["status"], "SAVED")
        self.assertIn("car_modifications", item["status_reason"])
        self.assertEqual(item["actions"], ["ANALYZE", "REJECT"])

    def test_topic_items_and_newest_first(self):
        self.save_video(when=datetime(2026, 9, 1, tzinfo=timezone.utc))
        hts.explore(
            "Turbo lag",
            searcher=lambda q, l, t: [
                {"video_id": "turbolag001", "title": "Turbo lag explained", "channel_id": "c1", "channel_title": "C1", "duration_seconds": 500, "views": 600000}
            ],
            measurer=lambda ids: {},
            now=datetime(2026, 10, 1, tzinfo=timezone.utc),
        )
        items = inbox.build_inbox({})["items"]
        self.assertEqual([i["source_label"] for i in items], ["YOUR TOPIC", "YOUR VIDEO"])
        topic = items[0]
        self.assertEqual(topic["topic_key"], "turbo_lag")
        self.assertEqual([c["label"] for c in topic["evidence"]], ["Demand", "Replication"])
        self.assertEqual(topic["search_count"], 5)

    def run_radar(self):
        from opportunity_engine import channel_scope

        config = json.loads(json.dumps(channel_scope.load_config()))
        config["viral_radar"]["watchlist_handles"] = ["@brakelab"]
        api = FakeApi(MATURE + [radar_item(10, 48, 80_000)], handles={"@brakelab": "UC" + "a" * 22})
        vr.run(api=api, searcher=lambda u, l, t: [], config=config, now=NOW)

    def test_radar_breakouts_can_be_watched_and_analysed(self):
        self.run_radar()
        snapshot = inbox.build_inbox({})
        breakout = snapshot["items"][0]
        self.assertEqual((breakout["source_label"], breakout["status"]), ("VIRAL", "NEEDS_REVIEW"))
        self.assertEqual(breakout["actions"], ["ANALYZE", "WATCH", "SAVE", "REJECT"])
        self.assertEqual(breakout["viral"]["strength"], "BREAKOUT")
        self.assertEqual(breakout["viral"]["ratio_basis"], ["lifetime_vs_lifetime", "vph_vs_lifetime_vph"])
        inbox.apply_action(breakout["opportunity_id"], "WATCH")
        watched = inbox.build_inbox({})["items"][0]
        self.assertEqual(watched["status"], "WATCHING")
        self.assertEqual(snapshot["counts"]["NEEDS_REVIEW"], 1)

        record = active_source.set_active("video000010", source_type="VIRAL_RADAR")
        self.assertEqual(record["study_set"][0]["handoff_id"], "viral_radar:video000010")
        self.assertEqual(active_source.load_active(), record)
        active_item = inbox.build_inbox({})["items"][0]
        self.assertEqual((active_item["status"], active_item["is_active"]), ("APPROVED", True))

        # Re-running the radar (new evidence) keeps the frozen decision.
        self.run_radar()
        self.assertEqual(active_source.load_active()["study_set"], record["study_set"])

    def test_only_radar_items_can_be_watched(self):
        packet = self.save_video()
        with self.assertRaisesRegex(ValueError, "Only viral-radar"):
            inbox.apply_action(packet["opportunity_id"], "WATCH")

    def test_corrupt_state_file_is_ignored(self):
        inbox.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        inbox.STATE_FILE.write_text("[not a dict", encoding="utf-8")
        self.save_video()
        self.assertEqual(inbox.build_inbox({})["items"][0]["status"], "NEEDS_REVIEW")


if __name__ == "__main__":
    unittest.main()
