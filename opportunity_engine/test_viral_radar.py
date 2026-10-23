import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

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
        self.hidden_from_playlist = set()
        self.playlist_errors = {}
        self.fail_videos = False
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
            if params["playlistId"] in self.playlist_errors:
                raise self.playlist_errors[params["playlistId"]]
            cid = "UC" + params["playlistId"][2:]
            ids = [
                v
                for v, data in self.videos.items()
                if data["snippet"]["channelId"] == cid and v not in self.hidden_from_playlist
            ]
            return {"items": [{"contentDetails": {"videoId": v}} for v in ids]}
        if resource == "videos":
            if self.fail_videos:
                raise vr.RadarError(vr.API_UNAVAILABLE, "HTTP 403 reason=quotaExceeded")
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

    def outcome_rows(self):
        path = vr.outcomes_file()
        self.assertTrue(str(path).startswith(str(self.root)))
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

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


class CalibrationDataTests(RadarTestCase):
    """D-177: what the day-15 test needs is kept, for flagged videos and for a
    fresh-upload comparison group, whatever the run cadence."""

    def test_milestones_survive_more_than_sixty_ratings(self):
        # With several tracked videos a tick runs nearly every two hours, and
        # each pass rates every tracked video. Before D-177 the 60-entry cap on
        # the rating list dropped the 3-day and 7-day ratings by day 15.
        api = FakeApi(MATURE + [item(10, 30, 60_000)], handles={"@brakelab": CH})
        self.run_radar(api)
        for step in range(1, 165):  # ages 32 h to 358 h, every 2 hours
            api.videos[vid(10)]["statistics"]["viewCount"] = str(60_000 + step * 500)
            vr.run(api=api, config=self.config, now=NOW + timedelta(hours=2 * step), mode=vr.MODE_SNAPSHOTS)
        self.assertEqual(len(vr.load_state()["tracked"][vid(10)]["classifications"]), 60)
        self.run_radar(api, now=NOW + timedelta(hours=332))  # age 362 h: past day 15
        marks = vr.load_state()["completed"][vid(10)]["outcome"]["classified_at"]
        self.assertIsNone(marks["24h"])  # first seen at 30 h
        self.assertEqual(marks["3d"]["age_hours"], 72.0)
        self.assertEqual(marks["7d"]["age_hours"], 168.0)
        self.assertEqual(marks["3d"]["baseline_median_views"], 10_350.0)

    def test_first_rating_is_kept_and_the_outcome_row_has_the_test_inputs(self):
        api = FakeApi(MATURE + [item(10, 30, 60_000)], handles={"@brakelab": CH})
        self.run_radar(api)
        first = vr.load_state()["tracked"][vid(10)]["first_rating"]
        self.assertEqual((first["strength"], first["rule_id"]), ("BREAKOUT", "VS-BREAKOUT"))
        self.assertEqual((first["age_hours"], first["views"]), (30.0, 60_000))
        self.assertEqual(first["baseline_median_views"], 10_350.0)
        api.videos[vid(10)]["statistics"]["viewCount"] = "90000"
        self.run_radar(api, now=NOW + timedelta(hours=12))
        self.assertEqual(vr.load_state()["tracked"][vid(10)]["first_rating"], first)

        self.run_radar(api, now=NOW + timedelta(hours=335))  # age 365 h
        rows = [r for r in self.outcome_rows() if r["group"] == vr.GROUP_TRACKED]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["video_id"], row["reading"], row["legacy"]), (vid(10), vr.READING_ON_TIME, False))
        self.assertEqual((row["final_views"], row["final_age_hours"]), (90_000, 365.0))
        self.assertEqual(row["first_rating"], first)
        self.assertEqual(row["format_basis"], "duration_heuristic")
        self.assertEqual(row["milestones"]["3d"]["strength"], "BREAKOUT")

    def test_a_late_reading_is_labelled_late(self):
        api = FakeApi(MATURE + [item(10, 30, 60_000)], handles={"@brakelab": CH})
        self.run_radar(api)
        self.run_radar(api, now=NOW + timedelta(hours=370))  # age 400 h: the PC was off
        row = self.outcome_rows()[0]
        self.assertEqual((row["reading"], row["final_age_hours"]), (vr.READING_LATE, 400.0))

    def test_a_record_tracked_before_d177_is_marked_legacy(self):
        api = FakeApi(MATURE + [item(10, 30, 60_000)], handles={"@brakelab": CH})
        self.run_radar(api)
        state = vr.load_state()
        record = state["tracked"][vid(10)]
        for key in ("first_rating", "milestones"):
            record.pop(key)
        record["classifications"] = [{"at": at(0), "age_hours": 30.0, "strength": "BREAKOUT", "trajectory": "FLAT"}]
        vr.save_state(state)
        self.run_radar(api, now=NOW + timedelta(hours=12))
        marks = vr.load_state()["tracked"][vid(10)]["milestones"]
        self.assertEqual(marks["3d"]["age_hours"], 42.0)  # the newest rating at or before 72 h
        self.run_radar(api, now=NOW + timedelta(hours=335))
        row = self.outcome_rows()[0]
        self.assertTrue(row["legacy"])
        self.assertIsNone(row["first_rating"])

    def test_fresh_uploads_join_the_comparison_group_on_first_sight_only(self):
        videos = MATURE + [
            item(20, 6, 500),  # 6 h, quiet: NORMAL, joins
            item(21, 30, 60_000),  # 30 h, already a breakout: joins too (every fresh upload)
            item(22, 60, 3_000),  # 60 h: too old on first sight
            item(23, 10, 400, duration="PT40S"),  # fresh Short, no Shorts baseline
        ]
        api = FakeApi(videos, handles={"@brakelab": CH})
        summary = self.run_radar(api)
        cohort = vr.load_state()["cohort"]
        self.assertEqual(sorted(cohort), [vid(20), vid(21)])
        self.assertEqual(summary["fresh_cohort"]["enrolled"], 2)
        self.assertEqual(summary["fresh_cohort"]["skipped_no_baseline"], 1)
        self.assertEqual(cohort[vid(20)]["first_rating"]["strength"], "NORMAL")
        self.assertEqual(cohort[vid(21)]["first_rating"]["strength"], "BREAKOUT")
        self.assertEqual(cohort[vid(20)]["first_rating"]["baseline_median_views"], 10_350.0)
        self.assertTrue(cohort[vid(20)]["channel_new"])  # the channel joined in this pass

        api.videos[vid(24)] = item(24, 1, 50)
        summary = self.run_radar(api, now=NOW + timedelta(hours=8))
        self.assertEqual(summary["fresh_cohort"]["enrolled"], 1)  # only the new upload
        cohort = vr.load_state()["cohort"]
        self.assertEqual(sorted(cohort), [vid(20), vid(21), vid(24)])
        self.assertFalse(cohort[vid(24)]["channel_new"])

    def test_the_day_15_reading_is_taken_even_off_the_uploads_page(self):
        api = FakeApi(MATURE + [item(20, 6, 500)], handles={"@brakelab": CH})
        self.run_radar(api)
        api.hidden_from_playlist = {vid(20)}  # 20+ newer uploads pushed it off
        api.videos[vid(20)]["statistics"]["viewCount"] = "70000"
        summary = self.run_radar(api, now=NOW + timedelta(hours=358))  # age 364 h
        self.assertNotIn(vid(20), vr.load_state()["cohort"])
        self.assertEqual(summary["fresh_cohort"]["readings"], 1)
        row = self.outcome_rows()[0]
        self.assertEqual((row["group"], row["video_id"], row["reading"]), (vr.GROUP_FRESH, vid(20), vr.READING_ON_TIME))
        self.assertEqual((row["final_views"], row["final_age_hours"]), (70_000, 364.0))
        self.assertEqual(row["first_rating"]["strength"], "NORMAL")
        self.assertEqual(row["format_basis"], "duration_heuristic")

    def test_snapshot_passes_take_due_readings_too(self):
        api = FakeApi(MATURE + [item(20, 6, 500)], handles={"@brakelab": CH})
        self.run_radar(api)
        vr.run(api=api, config=self.config, now=NOW + timedelta(hours=360), mode=vr.MODE_SNAPSHOTS)
        self.assertEqual(self.outcome_rows()[0]["reading"], vr.READING_ON_TIME)

    def test_a_vanished_video_is_recorded_missed_after_day_16(self):
        api = FakeApi(MATURE + [item(20, 6, 500)], handles={"@brakelab": CH})
        self.run_radar(api)
        del api.videos[vid(20)]
        self.run_radar(api, now=NOW + timedelta(hours=360))  # age 366 h: retried later
        self.assertIn(vid(20), vr.load_state()["cohort"])
        summary = self.run_radar(api, now=NOW + timedelta(hours=380))  # age 386 h
        self.assertNotIn(vid(20), vr.load_state()["cohort"])
        self.assertEqual(summary["fresh_cohort"]["missed"], 1)
        row = self.outcome_rows()[0]
        self.assertEqual((row["reading"], row["final_views"]), (vr.READING_MISSED, None))


class ReviewFindingTests(RadarTestCase):
    """Stage 8 review of PR 1 (D-177): each test failed on 55c9eaf."""

    def quiet_fresh(self):
        return [item(20, 6, 500), item(21, 6, 600), item(22, 6, 700)]

    def test_snapshot_passes_never_rebuild_the_baseline_from_comparison_videos(self):
        api = FakeApi(MATURE + self.quiet_fresh(), handles={"@brakelab": CH})
        self.run_radar(api)
        api.videos[vid(30)] = item(30, -322, 40_000)  # published at +322 h
        self.run_radar(api, now=NOW + timedelta(hours=352))  # age 30 h: 3.9x -> candidate
        record = vr.load_state()["tracked"][vid(30)]
        self.assertEqual((record["strength"], record["baseline"]["median_views"]), ("BREAKOUT_CANDIDATE", 10_350.0))
        # Six hours later the three quiet uploads are past day 15 and due for
        # their reading in a snapshot pass; they must not become the baseline.
        vr.run(api=api, config=self.config, now=NOW + timedelta(hours=358), mode=vr.MODE_SNAPSHOTS)
        record = vr.load_state()["tracked"][vid(30)]
        self.assertEqual(record["baseline"]["median_views"], 10_350.0)
        self.assertEqual(record["strength"], "BREAKOUT_CANDIDATE")
        self.assertEqual(record["milestones"]["3d"]["baseline_median_views"], 10_350.0)

    def test_a_pass_that_crashes_before_saving_does_not_record_twice(self):
        api = FakeApi(MATURE + [item(10, 30, 60_000)], handles={"@brakelab": CH})
        self.run_radar(api)
        with patch.object(vr, "save_state", side_effect=OSError("file in use")):
            with self.assertRaises(OSError):
                self.run_radar(api, now=NOW + timedelta(hours=335))
        self.run_radar(api, now=NOW + timedelta(hours=337))
        rows = self.outcome_rows()
        self.assertEqual(sorted((r["group"], r["video_id"]) for r in rows), [("fresh_cohort", vid(10)), ("tracked", vid(10))])
        self.assertEqual({r["final_age_hours"] for r in rows}, {365.0})  # the first reading stands

    def test_a_vanished_candidate_is_recorded_missed_with_its_ratings(self):
        api = FakeApi(MATURE + [item(10, 48, 80_000)], handles={"@brakelab": CH})
        self.run_radar(api)
        del api.videos[vid(10)]
        self.run_radar(api, now=NOW + timedelta(hours=1))
        rows = self.outcome_rows()
        self.assertEqual([(r["group"], r["reading"], r["final_views"]) for r in rows], [("tracked", vr.READING_MISSED, None)])
        self.assertEqual(rows[0]["milestones"]["3d"]["strength"], "BREAKOUT")

    def test_hidden_views_after_day_15_end_as_missed_not_tracked_forever(self):
        api = FakeApi(MATURE + [item(10, 30, 60_000), item(20, 6, 500)], handles={"@brakelab": CH})
        self.run_radar(api)
        for video_id in (vid(10), vid(20)):
            api.videos[video_id]["statistics"] = {}
        self.run_radar(api, now=NOW + timedelta(hours=356))  # ages 386 h and 362 h
        state = vr.load_state()
        self.assertNotIn(vid(10), state["tracked"])
        self.assertIn(vid(20), state["cohort"])  # still inside day 16: try again
        self.run_radar(api, now=NOW + timedelta(hours=380))
        self.assertEqual(vr.load_state()["cohort"], {})
        readings = sorted((r["group"], r["video_id"], r["reading"], r["final_views"]) for r in self.outcome_rows())
        self.assertEqual(readings, [
            ("fresh_cohort", vid(10), "MISSED", None),
            ("fresh_cohort", vid(20), "MISSED", None),
            ("tracked", vid(10), "MISSED", None),
        ])
        self.assertIsNone(vr.next_snapshot_due(vr.load_state(), self.config["viral_radar"], NOW + timedelta(hours=381)))

    def test_comparison_videos_get_milestone_ratings_on_full_passes_only(self):
        api = FakeApi(MATURE + [item(20, 6, 500)], handles={"@brakelab": CH})
        self.run_radar(api)  # age 6 h
        self.run_radar(api, now=NOW + timedelta(hours=18))  # 24 h
        vr.run(api=api, config=self.config, now=NOW + timedelta(hours=20), mode=vr.MODE_SNAPSHOTS)
        api.hidden_from_playlist = {vid(20)}  # off the uploads page from now on
        self.run_radar(api, now=NOW + timedelta(hours=66))  # 72 h
        self.run_radar(api, now=NOW + timedelta(hours=162))  # 168 h
        self.run_radar(api, now=NOW + timedelta(hours=356))  # 362 h: the reading
        row = self.outcome_rows()[0]
        marks = row["milestones"]
        self.assertEqual([marks[k]["age_hours"] for k in ("24h", "3d", "7d")], [24.0, 72.0, 168.0])
        self.assertEqual({marks[k]["baseline_median_views"] for k in marks}, {10_350.0})
        self.assertEqual(row["first_rating"]["age_hours"], 6.0)
        observed = [json.loads(line)["age_hours"] for line in vr.cohort_observations_file().read_text().splitlines()]
        self.assertEqual(observed, [6.0, 24.0, 72.0, 168.0])

    def test_running_totals_survive_the_next_pass(self):
        api = FakeApi(MATURE + [item(23, 10, 400, duration="PT40S")], handles={"@brakelab": CH})
        self.run_radar(api)
        api.videos[vid(24)] = item(24, -6, 300, duration="PT30S")
        self.run_radar(api, now=NOW + timedelta(hours=8))
        counts = vr.load_state()["cohort_counts"]
        self.assertEqual(counts["skipped_no_baseline"], 2)
        self.assertEqual(vr.status_snapshot()["fresh_cohort_counts"], counts)

    def test_one_missing_playlist_does_not_stop_the_pass(self):
        api = FakeApi(
            MATURE + [item(20, 6, 500), item(40, 6, 500, channel=CH2)],
            channels={CH: {"subs": "5"}, CH2: {"subs": "9"}},
            handles={"@brakelab": CH, "@gone": CH2},
        )
        self.config["viral_radar"]["watchlist_handles"] = ["@brakelab", "@gone"]
        api.playlist_errors["UU" + CH2[2:]] = vr.RadarError(
            vr.API_UNAVAILABLE,
            "YouTube API request failed: YouTube rejected the request (HTTP 404 reason=playlistNotFound).",
        )
        summary = self.run_radar(api)
        self.assertEqual(summary["status"], "COMPLETE")
        self.assertTrue(any("not found; skipped" in e for e in summary["errors"]))
        self.assertIn(vid(20), vr.load_state()["cohort"])

        # Any other failure still ends the pass.
        api.playlist_errors["UU" + CH2[2:]] = vr.RadarError(vr.API_UNAVAILABLE, "HTTP 403 reason=quotaExceeded")
        self.assertEqual(self.run_radar(api, now=NOW + timedelta(hours=8))["status"], "API_VALIDATION_UNAVAILABLE")

    def test_a_channel_youtube_no_longer_returns_stops_being_crawled(self):
        api = FakeApi(MATURE, channels={CH: {"subs": "5"}, CH2: {"subs": "9"}}, handles={"@brakelab": CH})
        state = vr.empty_state()
        state["watchlist"][CH2] = {"source": "x", "uploads_playlist": "UU" + CH2[2:]}
        vr.save_state(state)
        del api.channels[CH2]
        self.run_radar(api)
        self.assertIsNone(vr.load_state()["watchlist"][CH2]["uploads_playlist"])
        self.assertNotIn(("playlistItems", "UU" + CH2[2:]), [(c[0], c[1].get("playlistId")) for c in api.calls])

    def test_an_unmeasured_length_is_never_labelled_long_form(self):
        from opportunity_engine import inbox, models

        self.assertEqual(models.format_basis(0), "duration_unknown")
        self.assertEqual(models.format_basis(None), "duration_unknown")
        self.assertEqual(models.format_basis(181), "duration_heuristic")
        self.assertEqual(models.format_label("long_form", "duration_unknown"), "Format unknown (no length measured)")
        old_packet = {"candidate_videos": [{"video_id": vid(1), "format": "long_form", "duration_seconds": 0}]}
        self.assertEqual(inbox._videos(old_packet)[0]["format_label"], "Format unknown (no length measured)")
        measured = {"candidate_videos": [{"video_id": vid(1), "format": "long_form", "duration_seconds": 600}]}
        self.assertEqual(inbox._videos(measured)[0]["format_label"], "Long-form (over 180 s)")


class ReReviewFindingTests(RadarTestCase):
    """Stage 8 re-review of PR 1 (D-177), at d6fc1ef."""

    def test_comparison_ratings_use_the_frozen_baseline_tracked_or_not(self):
        # B1: three mature uploads; one drops off the page, so the page
        # baseline becomes insufficient. An untracked member must still be
        # rated against the baseline frozen when it joined.
        mature3 = [item(i, 24 * (30 + i), 10_000 + i * 100) for i in range(1, 4)]
        api = FakeApi(mature3 + [item(20, 6, 500)], handles={"@brakelab": CH})
        self.run_radar(api)
        frozen = vr.load_state()["cohort"][vid(20)]["baseline"]
        self.assertEqual((frozen["median_views"], frozen["sample_size"]), (10_200.0, 3))
        api.hidden_from_playlist = {vid(1)}
        api.videos[vid(20)]["statistics"]["viewCount"] = "35700"  # 3.5x
        self.run_radar(api, now=NOW + timedelta(hours=66))  # age 72 h
        state = vr.load_state()
        mark = state["cohort"][vid(20)]["milestones"]["3d"]
        self.assertEqual((mark["strength"], mark["baseline_median_views"]), ("BREAKOUT_CANDIDATE", 10_200.0))
        self.assertNotIn(vid(20), state["tracked"])  # the radar's own page rating had no baseline

    def test_a_channel_stays_new_until_a_pass_that_saw_it_completes(self):
        # B2: a bucket search adds a channel, then the API fails mid-pass.
        mature2 = [item(50 + i, 24 * (30 + i), 10_000 + i * 100, channel=CH2) for i in range(1, 7)]
        api = FakeApi(
            MATURE + mature2 + [item(40, 6, 500, channel=CH2)],
            channels={CH: {"subs": "5"}, CH2: {"subs": "9"}},
            handles={"@brakelab": CH},
        )
        api.fail_videos = True

        def searcher(url, limit, timeout):
            return [{"video_id": vid(40), "channel_id": CH2, "title": "x"}]

        failed = self.run_radar(api, searcher=searcher)
        self.assertEqual(failed["status"], "API_VALIDATION_UNAVAILABLE")
        api.fail_videos = False
        self.run_radar(api, now=NOW + timedelta(hours=8), searcher=searcher)
        state = vr.load_state()
        self.assertTrue(state["cohort"][vid(40)]["channel_new"])
        self.assertNotIn("pending_first_crawl", state["watchlist"][CH2])
        api.videos[vid(41)] = item(41, -14, 300, channel=CH2)
        self.run_radar(api, now=NOW + timedelta(hours=16), searcher=searcher)
        self.assertFalse(vr.load_state()["cohort"][vid(41)]["channel_new"])

    def test_a_comparison_video_off_the_page_never_starts_tracking(self):
        # B3: it is measured only for the comparison group.
        api = FakeApi(MATURE + [item(20, 6, 500)], handles={"@brakelab": CH})
        self.run_radar(api)
        api.hidden_from_playlist = {vid(20)}
        api.videos[vid(20)]["statistics"]["viewCount"] = "90000"
        summary = self.run_radar(api, now=NOW + timedelta(hours=42))  # age 48 h, 8.7x
        state = vr.load_state()
        self.assertNotIn(vid(20), state["tracked"])
        self.assertIsNone(vr.load_packet(vid(20)))
        self.assertEqual(state["cohort"][vid(20)]["milestones"]["3d"]["strength"], "BREAKOUT")
        self.assertEqual(summary["recent_videos"], 0)

    def test_duplicate_guard_reads_only_the_end_of_the_log(self):
        # B5: keys come from the last few MB, not the whole history.
        rows = [{"group": "tracked", "video_id": vid(n), "pad": "x" * 200} for n in range(3)]
        vr._append_rows(vr.outcomes_file(), rows)
        last = len(json.dumps(rows[-1], sort_keys=True)) + 1
        self.assertEqual(vr.written_outcome_keys(tail_bytes=last + 50), {("tracked", vid(2))})
        self.assertEqual(len(vr.written_outcome_keys()), 3)

    def test_a_torn_last_line_does_not_swallow_the_next_row(self):
        # B6: a crash mid-write leaves half a line; the next row starts fresh.
        vr.outcomes_file().parent.mkdir(parents=True, exist_ok=True)
        vr.outcomes_file().write_text('{"group": "tracked", "video_id": "vide', encoding="utf-8")
        self.assertTrue(vr._append_outcome({"group": "fresh_cohort", "video_id": vid(1)}, set()))
        self.assertEqual([r["video_id"] for r in self.outcome_rows_tolerant()], [vid(1)])

    def outcome_rows_tolerant(self):
        rows = []
        for line in vr.outcomes_file().read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
        return rows

    def test_a_manual_pass_waits_for_a_running_one(self):
        # Pre-existing: "Run Viral Radar" bypassed the scheduler's lock.
        lock = self.root / "viral" / "radar_tick.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("{}", encoding="utf-8")
        with patch.object(vr, "TICK_LOCK_FILE", lock), patch.object(vr, "run") as run:
            self.assertIsNone(vr.locked_run(vr.MODE_FULL))
            run.assert_not_called()
        lock.unlink()
        with patch.object(vr, "TICK_LOCK_FILE", lock), patch.object(vr, "run", return_value={"status": "COMPLETE"}) as run:
            self.assertEqual(vr.locked_run(vr.MODE_FULL), {"status": "COMPLETE"})
            run.assert_called_once()
        self.assertFalse(lock.exists())


class FormatBasisTests(RadarTestCase):
    """M1 criterion 5 (D-177): a length-based format is never shown as a confirmed Short."""

    def test_every_lane_uses_the_one_length_rule(self):
        from opportunity_engine import models

        self.assertEqual(self.config["viral_radar"]["short_max_seconds"], models.SHORT_MAX_SECONDS)
        self.assertEqual(hvi.SHORT_MAX_SECONDS, models.SHORT_MAX_SECONDS)
        self.assertEqual(hts.SHORT_MAX_SECONDS, models.SHORT_MAX_SECONDS)
        self.assertEqual(models.format_label("short_candidate"), "Short (≤ 180 s, by length)")
        self.assertEqual(models.format_label("long_form"), "Long-form (over 180 s)")
        self.assertEqual(models.format_label("long"), "Format unknown")

    def test_radar_records_packets_and_rows_name_the_basis(self):
        api = FakeApi(MATURE + [item(10, 30, 60_000)], handles={"@brakelab": CH})
        self.run_radar(api)
        self.assertEqual(vr.load_state()["tracked"][vid(10)]["format_basis"], "duration_heuristic")
        candidate = vr.load_packet(vid(10))["candidate_videos"][0]
        self.assertEqual((candidate["format"], candidate["format_basis"]), ("long_form", "duration_heuristic"))
        row = vr.radar_overview(now=NOW)["tracked"][0]
        self.assertEqual(row["format_label"], "Long-form (over 180 s)")


class OverviewTests(RadarTestCase):
    """UI-04: the radar page reads themes, tracked videos and sparklines from files."""

    def write_fixture(self):
        def record(n, ratio, trajectory, hours_old, channel=CH):
            return {
                "first_seen_at": at(hours_old - 2),
                "video": {
                    "video_id": vid(n),
                    "title": f"Brake cooling {n}",
                    "channel_id": channel,
                    "channel_title": "Lab",
                    "published_at": at(hours_old),
                },
                "format": "long",
                "metrics": {"lifetime_ratio": ratio, "views": 1000 * n},
                "strength": "BREAKOUT",
                "trajectory": trajectory,
                "breadth": "REPLICATED",
                "historical_alignment": "ALIGNED",
                "cluster": {"cluster_id": "cl_x"},
            }

        state = vr.empty_state()
        state["tracked"] = {
            vid(1): record(1, 8.0, "STABLE_HIGH", 30),
            vid(2): record(2, 14.0, "ACCELERATING", 60, channel=CH2),
            vid(3): record(3, 3.0, "DECELERATING", 400),
        }
        vr.save_state(state)
        vr.CLUSTERS_FILE.write_text(json.dumps({"clusters": [
            {"cluster_id": "cl_solo", "label": "solo", "breadth": "ONE_OFF", "members": [
                {"video_id": vid(3), "lifetime_ratio": 3.0}]},
            {"cluster_id": "cl_x", "label": "brake cooling", "breadth": "REPLICATED",
             "independent_channel_count": 2, "member_count": 2, "replication_rule_id": "CL-REPLICATED",
             "members": [{"video_id": vid(1), "lifetime_ratio": 8.0}, {"video_id": vid(2), "lifetime_ratio": 14.0}]},
        ]}))
        rows = [{"video_id": vid(2), "views": v, "video_age_hours": h} for h, v in ((24, 5000), (6, 1000), (12, 2500))]
        rows += [{"video_id": vid(1), "views": 10, "video_age_hours": 3}, {"video_id": "other", "views": 1, "video_age_hours": 1}]
        vr.SNAPSHOT_FILE.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")

    def test_overview_ranks_replicated_themes_and_sorts_series(self):
        self.write_fixture()
        overview = vr.radar_overview(now=NOW)
        self.assertEqual(overview["window_days"], 15)
        self.assertEqual([t["cluster_id"] for t in overview["themes"]], ["cl_x", "cl_solo"])
        theme = overview["themes"][0]
        self.assertEqual(theme["strongest_ratio"], 14.0)
        self.assertEqual(theme["median_ratio"], 11.0)
        self.assertEqual(theme["direction"], "ACCELERATING")
        self.assertEqual(theme["top_video_id"], vid(2))
        self.assertEqual(theme["momentum"], [[6.0, 1000.0], [12.0, 2500.0], [24.0, 5000.0]])
        self.assertEqual(theme["first_detected_at"], at(58))
        self.assertEqual([v["video_id"] for v in theme["videos"]], [vid(2), vid(1)])

    def test_overview_rows_and_themes_carry_a_lane(self):
        overview = vr.radar_overview(now=NOW)
        for row in overview["tracked"]:
            self.assertIn(row["lane"], ("ON_LANE", "UNCLEAR", "OFF_LANE", "OTHER_LANGUAGE"))
        for theme in overview["themes"]:
            self.assertIn(theme["lane"], ("ON_LANE", "UNCLEAR", "OFF_LANE", "OTHER_LANGUAGE"))
            for video in theme["videos"]:
                self.assertIn("lane", video)
                self.assertIn("day", video)

    def test_overview_tracked_rows_carry_day_in_window_and_inbox_id(self):
        self.write_fixture()
        tracked = vr.radar_overview(now=NOW)["tracked"]
        self.assertEqual([row["video_id"] for row in tracked], [vid(2), vid(1), vid(3)])
        by_id = {row["video_id"]: row for row in tracked}
        self.assertEqual(by_id[vid(1)]["day"], 2)
        self.assertEqual(by_id[vid(2)]["day"], 3)
        self.assertEqual(by_id[vid(3)]["day"], 15)  # capped at the window
        self.assertEqual(by_id[vid(1)]["opportunity_id"], "opp_viral_radar__" + vid(1))
        self.assertEqual(by_id[vid(3)]["series"], [])

    def test_theme_headline_is_the_strongest_members_title_trimmed(self):
        self.write_fixture()
        overview = vr.radar_overview(now=NOW)
        theme = next(t for t in overview["themes"] if t["cluster_id"] == "cl_x")
        self.assertEqual(theme["headline"], "Brake cooling 2")
        self.assertEqual(theme["label"], "brake cooling")
        self.assertEqual(vr.theme_headline("Why F1 brakes GLOW (4K) [Part 2] #shorts #f1"), "Why F1 brakes GLOW")
        self.assertEqual(vr.theme_headline("How a jet engine works | Explained"), "How a jet engine works")
        long = vr.theme_headline("word " * 40)
        self.assertLessEqual(len(long), 92)
        self.assertTrue(long.endswith("…"))
        self.assertEqual(vr.theme_headline(""), "")
        # Audit 2: a "#" inside the title belongs to it; hostile input stays fast.
        self.assertEqual(vr.theme_headline("Price #1 in the world"), "Price #1 in the world")
        self.assertEqual(vr.theme_headline("C# tutorial for beginners #code #learn"), "C# tutorial for beginners")
        import time as _time
        started = _time.monotonic()
        vr.theme_headline(" " * 50_000 + "x")
        vr.theme_headline("(" * 50_000)
        vr.theme_headline("#a " * 20_000)
        self.assertLess(_time.monotonic() - started, 0.5)

    def test_overview_without_files_is_empty(self):
        overview = vr.radar_overview(now=NOW)
        self.assertEqual((overview["themes"], overview["tracked"]), ([], []))
        self.assertFalse(overview["learning"]["active"])
        self.assertEqual(overview["learning"]["decisions"], 0)

    def test_overview_learns_taste_from_inbox_decisions(self):
        """D-165: enough Save/Reject decisions on radar packets rank the tracked rows."""
        from opportunity_engine import inbox

        self.write_fixture()
        picks = ["How brakes stop a car", "Why tyres do not burst", "How a jet engine works",
                 "How glass stops a bullet", "Why bridges sway", "How a fridge makes cold",
                 "How airbags fire", "Why magnets stick", "How turbines spin", "How popcorn pops"]
        rejects = ["Social security for seniors", "Chest workout for muscle", "Crypto crash",
                   "Atlantis history for sleep", "Tax brackets 2026", "Leg day for lifters",
                   "Bitcoin news", "Hypertrophy tips", "Medicare guide", "Templar bloodline"]
        items = {}
        vr.PACKETS_DIR.mkdir(parents=True, exist_ok=True)
        for n, title in enumerate(picks + rejects):
            video_id = f"L{n:010d}"
            packet = {"opportunity_id": "opp_viral_radar__" + video_id, "source_type": "VIRAL_RADAR",
                      "title": title, "candidate_videos": [{"video_id": video_id, "title": title, "channel_id": CH2 if n >= len(picks) else CH}]}
            (vr.PACKETS_DIR / f"{video_id}.json").write_text(json.dumps(packet), encoding="utf-8")
            items[packet["opportunity_id"]] = {"status": "SAVED" if n < len(picks) else "REJECTED"}
        state_file = self.root / "inbox_state.json"
        state_file.write_text(json.dumps({"schema_version": 1, "items": items}), encoding="utf-8")
        with patch.object(inbox, "STATE_FILE", state_file):
            overview = vr.radar_overview(now=NOW)
        self.assertTrue(overview["learning"]["active"])
        self.assertEqual(overview["learning"]["decisions"], 20)
        by_id = {row["video_id"]: row for row in overview["tracked"]}
        self.assertIn(by_id[vid(1)]["taste_label"], ("LIKELY", "UNSURE", "UNLIKELY"))
        self.assertIsNotNone(by_id[vid(1)]["taste"])
        # The brake-cooling fixture is on the picked channel and uses no rejected words.
        self.assertGreater(by_id[vid(1)]["taste"], 0)
        theme = next(t for t in overview["themes"] if t["cluster_id"] == "cl_x")
        self.assertIsNotNone(theme["taste"])
        self.assertIn("taste_label", theme["videos"][0])

    def test_sparkline_series_is_downsampled(self):
        vr.RADAR_DIR.mkdir(parents=True, exist_ok=True)
        rows = [{"video_id": vid(1), "views": i, "video_age_hours": i} for i in range(100)]
        vr.SNAPSHOT_FILE.write_text("\n".join(json.dumps(r) for r in rows))
        points = vr._snapshot_series({vid(1)})[vid(1)]
        self.assertEqual(len(points), vr.SPARKLINE_MAX_POINTS)
        self.assertEqual((points[0], points[-1]), ([0.0, 0.0], [99.0, 99.0]))


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
        self.assertEqual(vr.classify_strength({"age_hours": 50, "lifetime_ratio": 3.5, "vph_ratio": 12}, self.settings), ("BREAKOUT_CANDIDATE", "VS-OUTLIER"))
        self.assertEqual(vr.classify_strength({"age_hours": 100, "lifetime_ratio": 3.5, "vph_ratio": 12}, self.settings), ("BREAKOUT_CANDIDATE", "VS-OUTLIER"))
        self.assertEqual(vr.classify_strength({"age_hours": 50, "lifetime_ratio": 5.0, "vph_ratio": 40}, self.settings), ("BREAKOUT", "VS-BREAKOUT"))

    def test_a_viral_outlier_is_3x_the_channel_normal_or_more(self):
        """Owner, D-177: under 3x is never flagged once a video is a day old,
        whatever its views per hour (the old 1x/2x rules are gone)."""
        for ratio, vph in ((1.0, 50), (2.0, 50), (2.99, 500)):
            for hours in (25, 50, 100, 300):  # past the first day (VS-EARLY covers up to 24 h)
                self.assertEqual(
                    vr.classify_strength({"age_hours": hours, "lifetime_ratio": ratio, "vph_ratio": vph}, self.settings),
                    ("NORMAL", None),
                )
        self.assertEqual(vr.classify_strength({"age_hours": 24, "lifetime_ratio": 3.0, "vph_ratio": 1}, self.settings)[0], "BREAKOUT_CANDIDATE")
        self.assertEqual(vr.classify_strength({"age_hours": 72, "lifetime_ratio": 4.99, "vph_ratio": 100}, self.settings)[0], "BREAKOUT_CANDIDATE")
        for rule in self.settings["strength_rules"]:
            if rule["strength"] != "EARLY_SIGNAL":
                self.assertGreaterEqual(rule["min_lifetime_ratio"], 3.0, rule["rule_id"])
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
        topics = [{"topic": "brakes", "niche": "automotive_racing", "match_terms": ["brake", "brakes"],
                   "context_terms": ["f1", "formula 1"], "exclude_terms": ["sim racing"]}]
        self.assertEqual(vr.classify_history("Why F1 brakes glow", topics), ("ESTABLISHED_DEMAND", "brakes"))
        self.assertEqual(vr.classify_history("Why F1 brake discs glow", topics)[0], "ESTABLISHED_DEMAND")
        self.assertEqual(vr.classify_history("Hummingbirds", topics)[0], "NO_HISTORY")
        self.assertEqual(vr.classify_history("How car brakes work", topics)[0], "NO_HISTORY")  # no F1 context
        self.assertEqual(vr.classify_history("Sim racing F1 brakes", topics)[0], "NO_HISTORY")
        self.assertEqual(vr.classify_history("anything", [])[0], "UNASSESSED")

    def test_historical_topics_carry_the_01_3_rule_not_id_words(self):
        """D-178 review: 'road_cars' must not align every title with 'road' or 'car'."""
        packets = [{"topic": "road_cars", "niche": "everyday_science"}, {"topic": "road_cars", "niche": "everyday_science"},
                   {"topic": "no_longer_configured", "niche": "everyday_science"}]
        with patch.object(historical_adapter, "build", return_value={"packets": packets}):
            topics = vr.historical_topics()
        self.assertEqual([t["topic"] for t in topics], ["road_cars"])
        for title in ("I bought the cheapest car in America", "Road trip across Iceland", "Funny animal moments",
                      "Chicken wings eating contest", "Grip strength workout"):
            self.assertEqual(vr.classify_history(title, topics)[0], "NO_HISTORY", title)
        self.assertEqual(vr.classify_history("Why car brakes glow when overheated", topics), ("ESTABLISHED_DEMAND", "road_cars"))

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


class RadarJobImportTests(unittest.TestCase):
    """The radar job runs as a plain script, without the test runner's path setup."""

    def test_default_api_imports_youtube_discovery_outside_pytest(self):
        import os
        import subprocess

        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env["YOUTUBE_API_KEY"] = "test"
        completed = subprocess.run(
            [sys.executable, "-c", "import opportunity_engine.viral_radar as v; v.default_api()"],
            cwd=str(Path(__file__).resolve().parent.parent), env=env,
            capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr[-800:])
