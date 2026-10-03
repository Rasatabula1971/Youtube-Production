import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from opportunity_engine import channel_scope, historical_adapter  # noqa: E402
from opportunity_engine import human_topic_search as hts  # noqa: E402
from opportunity_engine import human_video_intake as hvi  # noqa: E402
from opportunity_engine import viral_radar as vr  # noqa: E402
from opportunity_engine.packet_schema import validate_packet  # noqa: E402

NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
CH = "UC" + "a" * 22
CH2 = "UC" + "b" * 22


def vid(n):
    return f"video{n:06d}"


def at(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")


def item(n, hours_ago, views, duration="PT10M", channel=CH, title=None, live="none"):
    return {
        "id": vid(n),
        "snippet": {
            "title": title or f"How brakes glow {n}",
            "channelId": channel,
            "channelTitle": "Brake Lab",
            "publishedAt": at(hours_ago),
            "liveBroadcastContent": live,
        },
        "statistics": {"viewCount": str(views), "likeCount": str(views // 20), "commentCount": "10"},
        "contentDetails": {"duration": duration},
        "status": {"madeForKids": False},
    }


class FakeApi:
    def __init__(self, videos, channels=None, handles=None):
        self.videos = {v["id"]: v for v in videos}
        self.channels = channels or {CH: {"subs": "50000"}}
        self.handles = handles or {}
        self.calls = []

    def __call__(self, resource, **params):
        self.calls.append((resource, params))
        if resource == "channels" and "forHandle" in params:
            channel = self.handles.get(params["forHandle"])
            return {"items": [{"id": channel}] if channel else []}
        if resource == "channels":
            return {
                "items": [
                    {
                        "id": cid,
                        "snippet": {"title": "Brake Lab"},
                        "contentDetails": {"relatedPlaylists": {"uploads": "UU" + cid[2:]}},
                        "statistics": {"subscriberCount": self.channels[cid]["subs"]},
                    }
                    for cid in params["id"].split(",")
                    if cid in self.channels
                ]
            }
        if resource == "playlistItems":
            cid = "UC" + params["playlistId"][2:]
            ids = [v for v, data in self.videos.items() if data["snippet"]["channelId"] == cid]
            return {"items": [{"contentDetails": {"videoId": v}} for v in ids]}
        if resource == "videos":
            return {"items": [self.videos[v] for v in params["id"].split(",") if v in self.videos]}
        raise AssertionError(resource)


MATURE = [item(i, 24 * (30 + i), 10_000 + i * 100) for i in range(1, 7)]


class RadarTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.root = root
        for target in (
            patch.object(vr, "RADAR_DIR", root / "viral"),
            patch.object(vr, "STATE_FILE", root / "viral" / "state.json"),
            patch.object(vr, "SUMMARY_FILE", root / "viral" / "last_run.json"),
            patch.object(vr, "SNAPSHOT_FILE", root / "viral" / "snapshots.jsonl"),
            patch.object(vr, "CLUSTERS_FILE", root / "viral" / "clusters.json"),
            patch.object(vr, "PACKETS_DIR", root / "packets"),
            patch.object(hvi, "PACKETS_DIR", root / "hv"),
            patch.object(hts, "PACKETS_DIR", root / "ht"),
            patch.object(historical_adapter, "STUDY_SET_FILE", root / "no_study.json"),
        ):
            target.start()
            self.addCleanup(target.stop)
        self.config = json.loads(json.dumps(channel_scope.load_config()))
        self.config["viral_radar"]["watchlist_handles"] = ["@brakelab"]

    def run_radar(self, api, now=NOW, searcher=None):
        return vr.run(
            api=api,
            searcher=searcher or (lambda url, limit, timeout: []),
            config=self.config,
            now=now,
        )


class RunTests(RadarTestCase):
    def test_classifies_on_first_sight_and_writes_packets(self):
        videos = MATURE + [
            item(10, 48, 80_000),  # 2 days, 8x median -> BREAKOUT
            item(11, 12, 9_000),  # 12 hours, high views/hour -> EARLY_SIGNAL
            item(12, 72, 8_000),  # 3 days, below median -> NORMAL
            item(13, 30, 5_000, duration="PT40S"),  # Short with no Shorts baseline
            item(14, 2, 100, live="live"),  # live: ignored
        ]
        api = FakeApi(videos, handles={"@brakelab": CH})
        summary = self.run_radar(api)
        self.assertEqual(summary["status"], "COMPLETE")
        self.assertEqual(summary["classified"], {"BREAKOUT": 1, "EARLY_SIGNAL": 1, "NORMAL": 1, "INSUFFICIENT_EVIDENCE": 1})
        self.assertEqual(summary["tracked"], 2)
        self.assertEqual(summary["packets_written"], 2)
        # channels(handle) + channels(batch) + playlistItems + videos: 4 cheap calls, no search.list.
        self.assertEqual([c[0] for c in api.calls], ["channels", "channels", "playlistItems", "videos"])

        breakout = vr.load_packet(vid(10))
        self.assertEqual(validate_packet(breakout), [])
        viral = breakout["viral_evidence"]
        self.assertEqual((viral["strength"], viral["strength_rule_id"]), ("BREAKOUT", "VS-BREAKOUT"))
        self.assertEqual(viral["trajectory"], "INSUFFICIENT_SNAPSHOTS")
        self.assertEqual(viral["breadth"], "ONE_OFF")
        self.assertEqual(breakout["evidence_state"]["cross_channel_replication"]["rule_id"], "CL-ONE-OFF")
        self.assertFalse(viral["trajectory_history_available"])
        self.assertEqual(viral["metrics"]["ratio_basis"], ["lifetime_vs_lifetime", "vph_vs_lifetime_vph"])
        self.assertEqual(viral["baseline"]["sample_size"], 6)
        self.assertEqual(viral["metrics"]["subscriber_outlier"], "AVAILABLE")
        self.assertEqual(breakout["evidence_state"]["current_breakout"]["level"], "STRONG")
        self.assertIn("CTR", viral["not_publicly_observable"])

        early = vr.load_packet(vid(11))["viral_evidence"]
        self.assertEqual((early["strength"], early["strength_rule_id"]), ("EARLY_SIGNAL", "VS-EARLY"))
        self.assertIsNone(vr.load_packet(vid(12)))
        snapshots = (vr.SNAPSHOT_FILE).read_text().splitlines()
        self.assertEqual(len(snapshots), 2)

    def test_snapshots_build_a_trajectory_and_the_window_ends_tracking(self):
        api = FakeApi(MATURE + [item(10, 30, 60_000)], handles={"@brakelab": CH})
        self.run_radar(api)
        # Ages 30h -> 36h -> 42h: under 48h the cadence is every 6 hours.
        for hours_later, views in ((6, 70_000), (12, 90_000)):
            api.videos[vid(10)]["statistics"]["viewCount"] = str(views)
            self.run_radar(api, now=NOW + timedelta(hours=hours_later))
        packet = vr.load_packet(vid(10))["viral_evidence"]
        self.assertEqual(len(packet["intervals"]), 2)
        self.assertEqual(packet["trajectory"], "ACCELERATING")
        self.assertTrue(packet["trajectory_history_available"])
        self.assertEqual(len(vr.SNAPSHOT_FILE.read_text().splitlines()), 3)
        series = vr.snapshots_for(vid(10))
        self.assertEqual([row["views"] for row in series], [60_000, 70_000, 90_000])
        self.assertEqual([row["video_age_hours"] for row in series], [30.0, 36.0, 42.0])
        self.assertEqual(vr.snapshots_for("../../etc"), [])
        self.assertEqual(vr.snapshots_for(vid(99)), [])

        # Re-running inside the cadence does not add a snapshot.
        self.run_radar(api, now=NOW + timedelta(hours=13))
        self.assertEqual(len(vr.SNAPSHOT_FILE.read_text().splitlines()), 3)

        # Past 15 days the video leaves the radar and keeps its outcome (R7).
        self.run_radar(api, now=NOW + timedelta(days=15))
        state = vr.load_state()
        self.assertNotIn(vid(10), state["tracked"])
        outcome = state["completed"][vid(10)]["outcome"]
        self.assertEqual(outcome["final_views"], 90_000)
        self.assertEqual(outcome["classified_at"]["24h"], None)
        self.assertEqual(outcome["classified_at"]["3d"]["strength"], "BREAKOUT")
        self.assertEqual(vr.load_packet(vid(10))["viral_evidence"]["tracking_status"], "TRACKING_COMPLETE")

    def test_deleted_tracked_video_stops_tracking(self):
        api = FakeApi(MATURE + [item(10, 48, 80_000)], handles={"@brakelab": CH})
        self.run_radar(api)
        del api.videos[vid(10)]
        self.run_radar(api, now=NOW + timedelta(hours=1))
        state = vr.load_state()
        self.assertNotIn(vid(10), state["tracked"])
        self.assertEqual(state["completed"][vid(10)]["reason"], "video unavailable")

    def test_missing_api_key_is_named_not_empty(self):
        with patch.object(vr, "_load_api_key", return_value=None):
            summary = vr.run(api=None, searcher=lambda u, l, t: [], config=self.config, now=NOW)
        self.assertEqual(summary["status"], "API_VALIDATION_UNAVAILABLE")
        self.assertIn("YOUTUBE_API_KEY", summary["errors"][0])

    def test_api_failure_mid_run_is_reported(self):
        def broken(resource, **params):
            raise vr.RadarError(vr.API_UNAVAILABLE, "quotaExceeded")

        summary = self.run_radar(broken)
        self.assertEqual(summary["status"], "API_VALIDATION_UNAVAILABLE")
        self.assertIn("quotaExceeded", summary["errors"][0])

    def test_empty_watchlist_is_named(self):
        summary = self.run_radar(FakeApi([], handles={}))
        self.assertEqual(summary["status"], "PARTIAL")
        self.assertIn("@brakelab: no channel found", summary["errors"])
        self.assertTrue(any("watchlist is empty" in e for e in summary["errors"]))

    def test_throttling_backs_off(self):
        calls = []

        def throttled(url, limit, timeout):
            calls.append(url)
            raise vr.RadarError(vr.THROTTLED, "HTTP Error 429")

        api = FakeApi(MATURE)
        summary = self.run_radar(api, searcher=throttled)
        self.assertEqual(summary["status"], "PARTIAL")
        self.assertEqual(len(calls), 1)  # stops at the first throttle
        self.assertIsNotNone(vr.load_state()["throttled_until"])
        summary = self.run_radar(api, now=NOW + timedelta(hours=1), searcher=throttled)
        self.assertEqual(summary["bucket_discovery"]["status"], "DISCOVERY_THROTTLED")
        self.assertEqual(len(calls), 1)

    def test_bucket_search_widens_watchlist_and_rotates(self):
        seen_urls = []

        def searcher(url, limit, timeout):
            seen_urls.append(url)
            return [{"video_id": vid(90), "channel_id": CH2, "title": "x"}]

        api = FakeApi(MATURE, channels={CH: {"subs": "5"}, CH2: {"subs": "9"}}, handles={"@brakelab": CH})
        summary = self.run_radar(api, searcher=searcher)
        self.assertIn(CH2, vr.load_state()["watchlist"])
        self.assertEqual(summary["new_channels"], 2)
        self.assertEqual(len(seen_urls), 4)
        self.assertTrue(all("sp=EgIIAw" in u for u in seen_urls))
        self.run_radar(api, now=NOW + timedelta(hours=1), searcher=searcher)
        self.assertNotEqual(seen_urls[0], seen_urls[4])
        self.assertEqual(vr.load_state()["bucket_cursor"], 8 % len(self.config["viral_radar"]["bucket_queries"]))

    def test_excluded_videos_are_tracked_but_get_no_inbox_packet(self):
        api = FakeApi(MATURE + [item(10, 48, 80_000, title="Best brake fails compilation epic fails")], handles={"@brakelab": CH})
        summary = self.run_radar(api)
        self.assertEqual(summary["excluded_candidates"], 1)
        self.assertIsNone(vr.load_packet(vid(10)))


class UnitTests(unittest.TestCase):
    settings = channel_scope.load_config()["viral_radar"]

    def test_baseline_keeps_formats_apart_and_shorts_after_cutoff(self):
        shorts = [
            {"video_id": "a", "published_at": "2025-01-01T00:00:00Z", "duration_seconds": 30, "views": 999},
            {"video_id": "b", "published_at": "2026-08-01T00:00:00Z", "duration_seconds": 30, "views": 100},
            {"video_id": "c", "published_at": "2026-08-02T00:00:00Z", "duration_seconds": 600, "views": 5000},
        ]
        base = vr.channel_baseline(shorts, "short", self.settings, NOW)
        self.assertEqual((base["sample_size"], base["median_views"], base["sufficient"]), (1, 100.0, False))
        self.assertEqual(vr.channel_baseline(shorts, "long_form", self.settings, NOW)["sample_size"], 1)

    def test_strength_needs_both_bases(self):
        self.assertEqual(vr.classify_strength({"age_hours": 50, "lifetime_ratio": None, "vph_ratio": 3}, self.settings)[0], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(vr.classify_strength({"age_hours": 50, "lifetime_ratio": 3.5, "vph_ratio": 12}, self.settings), ("BREAKOUT", "VS-BREAKOUT-FAST"))
        self.assertEqual(vr.classify_strength({"age_hours": 100, "lifetime_ratio": 3.5, "vph_ratio": 12}, self.settings), ("BREAKOUT_CANDIDATE", "VS-CANDIDATE"))
        self.assertEqual(vr.classify_strength({"age_hours": 10, "lifetime_ratio": 0.2, "vph_ratio": 50}, self.settings)[0], "NORMAL")

    def test_trajectory_labels(self):
        base = {"median_lifetime_vph": 10}

        def iv(*vph):
            return [{"vph": v} for v in vph]

        self.assertEqual(vr.classify_trajectory(iv(100), base, self.settings), "INSUFFICIENT_SNAPSHOTS")
        self.assertEqual(vr.classify_trajectory(iv(100, 130), base, self.settings), "ACCELERATING")
        self.assertEqual(vr.classify_trajectory(iv(100, 50), base, self.settings), "DECELERATING")
        self.assertEqual(vr.classify_trajectory(iv(100, 100), base, self.settings), "STABLE_HIGH")
        self.assertEqual(vr.classify_trajectory(iv(20, 20), base, self.settings), "FLAT")

    def test_snapshot_cadence_by_age(self):
        record = {"last_snapshot_at": (NOW - timedelta(hours=7)).isoformat()}
        self.assertTrue(vr.snapshot_due(record, 30, self.settings, NOW))  # <48h: every 6h
        self.assertFalse(vr.snapshot_due(record, 100, self.settings, NOW))  # 2-7 days: every 12h
        self.assertTrue(vr.snapshot_due(None, 300, self.settings, NOW))

    def test_historical_alignment(self):
        topics = [{"topic": "brakes", "words": ["brakes"]}]
        self.assertEqual(vr.classify_history("Why F1 brakes glow", topics), ("ESTABLISHED_DEMAND", "brakes"))
        self.assertEqual(vr.classify_history("Why F1 brake discs glow", topics)[0], "ESTABLISHED_DEMAND")
        self.assertEqual(vr.classify_history("Hummingbirds", topics)[0], "NO_HISTORY")
        self.assertEqual(vr.classify_history("anything", [])[0], "UNASSESSED")

    def test_watchlist_rejects_bad_ids_and_respects_cap(self):
        state = vr.empty_state()
        settings = dict(self.settings, max_watchlist_channels=1)
        self.assertFalse(vr._add_channel(state, "not-a-channel", "x", settings, NOW))
        self.assertTrue(vr._add_channel(state, CH, "x", settings, NOW))
        self.assertFalse(vr._add_channel(state, CH2, "x", settings, NOW))

    def test_corrupt_state_starts_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("{oops", encoding="utf-8")
            with patch.object(vr, "STATE_FILE", path):
                self.assertEqual(vr.load_state(), vr.empty_state())


if __name__ == "__main__":
    unittest.main()
