import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from testing_isolation import ModuleIsolation  # noqa: E402

_ISOLATION = ModuleIsolation(server)


def setUpModule() -> None:
    # Never read the real pipeline outputs of the machine running the tests.
    _ISOLATION.start()


def tearDownModule() -> None:
    _ISOLATION.stop()
from opportunity_engine import active_source
from opportunity_engine import human_topic_search as hts
from opportunity_engine import historical_adapter
from opportunity_engine import human_video_intake as hvi
from opportunity_engine import inbox
from opportunity_engine import viral_radar as vr

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
            # D-174 searches the video's title for context; never the web in tests.
            patch.object(active_source, "DEFAULT_SEARCHER", lambda q, l, t: []),
            patch.object(hvi, "PACKETS_DIR", self.root / "human_video"),
            patch.object(hts, "PACKETS_DIR", self.root / "human_topic"),
            patch.object(inbox, "STATE_FILE", self.root / "inbox_state.json"),
            patch.object(vr, "STATE_FILE", self.root / "viral" / "state.json"),
            patch.object(vr, "SUMMARY_FILE", self.root / "viral" / "last_run.json"),
            patch.object(vr, "SNAPSHOT_FILE", self.root / "viral" / "snapshots.jsonl"),
            patch.object(vr, "CLUSTERS_FILE", self.root / "viral" / "clusters.json"),
            patch.object(vr, "PACKETS_DIR", self.root / "viral_packets"),
            patch.object(historical_adapter, "STUDY_SET_FILE", self.root / "no_study_set.json"),
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
        self.assertIn("/api/opportunity/topic/analyze", server.HUMAN_GATE_MUTATION_ROUTES)
        self.assertIn("/api/opportunity/viral/analyze", server.HUMAN_GATE_MUTATION_ROUTES)
        # Inbox decisions can change the historical gate, so they wait for running jobs.
        self.assertIn("/api/opportunity/inbox", server.HUMAN_GATE_MUTATION_ROUTES)
        self.assertNotIn("/api/opportunity/topic", server.HUMAN_GATE_MUTATION_ROUTES)

    def test_static_ui_is_a_workspace_with_an_inbox(self):
        static = Path(server.__file__).resolve().parent / "static"
        html = (static / "index.html").read_text(encoding="utf-8")
        script = (static / "app.js").read_text(encoding="utf-8")
        for element_id in (
            "historicalEntryPanel",
            "exploreTopicForm",
            "analyzeVideoForm",
            "viralEntryPanel",
            "runViralRadar",
            "opportunityInboxTabs",
            "opportunityInbox",
            "historicalReviewPanel",
            "evidenceDrawer",
            "closeEvidenceDrawer",
            "opportunityGate",
        ):
            self.assertIn(f'id="{element_id}"', html)
        for needle in (
            "/api/opportunity/video/analyze",
            "/api/opportunity/topic/analyze",
            "/api/opportunity/video/stop",
            "/api/opportunity/inbox",
            "CONFIRM_REPLACE: ",
            "renderInbox(data.opportunity_inbox",
            'runAction("opportunity_research")',
            'runAction("viral_radar")',
            "/api/opportunity/viral/analyze",
            "renderViralEntry(data)",
            "data-inbox-theme",
            "evidenceMatrix(item)",
            "Evidence has moved since your decision",
            "What evidence is missing?",
            "openEvidenceDrawer(",
            "/api/opportunity/viral/snapshots?video_id=",
            "renderTrajectory(chart",
        ):
            self.assertIn(needle, script)

    def test_inbox_lists_submitted_videos_and_the_active_one(self):
        save_packet()
        snapshot = server.opportunity_inbox_snapshot()
        self.assertEqual([i["video_id"] for i in snapshot["items"]], [VID])
        self.assertEqual(snapshot["items"][0]["route"], "ACTIVE_CHANNEL")
        self.assertEqual(snapshot["items"][0]["status"], "NEEDS_REVIEW")
        self.assertIsNone(snapshot["active"])
        server.analyze_submitted_video(video_id=VID, confirm_replace=False, allow_excluded=False)
        item = server.opportunity_inbox_snapshot()["items"][0]
        self.assertEqual((item["status"], item["is_active"], item["actions"]), ("APPROVED", True, ["STOP"]))
        with self.assertRaisesRegex(ValueError, "Stop analysing it first"):
            inbox.apply_action(item["opportunity_id"], "REJECT")

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

    def test_analyze_brings_replication_context_from_other_channels(self):
        """D-174: the submitted video arrives with other channels' videos on its topic."""
        save_packet()

        def found(query, limit, timeout):
            return [
                {"video_id": VID, "title": "How hummingbirds hover", "channel_id": "UC9", "channel_title": "Nature Lab", "duration_seconds": 400, "views": 9_000_000},
                {"video_id": "samechan001", "title": "Hummingbirds hover again", "channel_id": "UC9", "channel_title": "Nature Lab", "duration_seconds": 400, "views": 8_000_000},
                {"video_id": "otherchan01", "title": "How hummingbirds hover in place", "channel_id": "UC2", "channel_title": "Bird Lab", "duration_seconds": 300, "views": 700_000},
                {"video_id": "otherchan02", "title": "Hummingbirds hover: the physics", "channel_id": "UC3", "channel_title": "Physics Now", "duration_seconds": 60, "views": 500_000},
                {"video_id": "otherchan03", "title": "Why hummingbirds can hover", "channel_id": "UC3", "channel_title": "Physics Now", "duration_seconds": 90, "views": 400_000},
                {"video_id": "otherchan04", "title": "Hover like a hummingbird", "channel_id": "UC4", "channel_title": "Wings", "duration_seconds": 120, "views": 300_000},
                {"video_id": "otherchan05", "title": "Hummingbird hover slow motion", "channel_id": "UC5", "channel_title": "Slow", "duration_seconds": 120, "views": 200_000},
                {"video_id": "unrelated01", "title": "Best pizza in town", "channel_id": "UC6", "channel_title": "Food", "duration_seconds": 120, "views": 9_900_000},
            ]

        with patch.object(active_source, "DEFAULT_SEARCHER", found):
            payload = server.analyze_submitted_video(video_id=VID, confirm_replace=False, allow_excluded=False)
        self.assertEqual(payload["active"]["video_count"], 4)
        self.assertEqual(payload["active"]["context_search"]["status"], "FOUND")
        rows = active_source.load_active()["study_set"]
        self.assertEqual([r["video_id"] for r in rows], [VID, "otherchan01", "otherchan02", "otherchan04"])
        self.assertEqual([r["study_role"] for r in rows], ["SEED", "REPLICATION_CONTEXT", "REPLICATION_CONTEXT", "REPLICATION_CONTEXT"])
        self.assertEqual(len({r["channel_id"] for r in rows}), 4)
        self.assertEqual(rows[1]["handoff_id"], f"human_video:{VID}:context:otherchan01")
        self.assertEqual(rows[1]["human_opportunity_gate"]["opportunity_id"], rows[0]["human_opportunity_gate"]["opportunity_id"])
        self.assertEqual(rows[1]["opportunity_context"]["seed_video_id"], VID)
        self.assertEqual([r["study_set_sequence"] for r in rows], [1, 2, 3, 4])
        # Nothing was saved to the topic inbox: the search was context, not an idea.
        self.assertEqual([i["video_id"] for i in payload["items"]], [VID])
        self.assertIn("3 videos from other channels", payload["items"][0]["status_reason"])
        # The gate materialises all four as the approved study set.
        from experiment_01_discovery import opportunity_gate as gate

        with patch.object(gate, "APPROVED_STUDY_SET_FILE", self.root / "approved_study_set.json"):
            self.assertEqual(gate._human_video_override()["video_id"], VID)
            approved = json.loads((self.root / "approved_study_set.json").read_text(encoding="utf-8"))
        self.assertEqual([r["video_id"] for r in approved], [VID, "otherchan01", "otherchan02", "otherchan04"])

    def test_analyze_without_context_still_works_and_says_so(self):
        save_packet()
        payload = server.analyze_submitted_video(video_id=VID, confirm_replace=False, allow_excluded=False)
        self.assertEqual(payload["active"]["video_count"], 1)
        self.assertEqual(payload["active"]["context_search"]["status"], "NONE")
        self.assertIn("No video from another channel", payload["items"][0]["status_reason"])

    def test_no_existing_work_needs_no_confirmation(self):
        save_packet()
        payload = server.analyze_submitted_video(video_id=VID, confirm_replace=False, allow_excluded=False)
        self.assertEqual(payload["active"]["video_id"], VID)

    def explore_topic(self):
        return hts.explore(
            "Why aircraft windows are round",
            searcher=lambda q, l, t: [
                {"video_id": "aircraftw01", "title": "Why aircraft windows are round", "channel_id": "c1", "channel_title": "C1", "duration_seconds": 500, "views": 900000},
                {"video_id": "aircraftw02", "title": "Round aircraft windows explained", "channel_id": "c2", "channel_title": "C2", "duration_seconds": 500, "views": 300000},
            ],
            measurer=lambda ids: {},
        )

    def test_topic_snapshot_and_analyze(self):
        self.explore_topic()
        snapshot = server.opportunity_inbox_snapshot()
        topic = snapshot["items"][0]
        self.assertEqual(topic["topic_key"], "aircraft_windows_are_round")
        self.assertEqual(
            {chip["label"]: chip["rule_id"] for chip in topic["evidence"]},
            {"Demand": "HT-DEMAND-MODERATE", "Replication": "HT-CCR-LOW"},
        )
        self.assertEqual(len(topic["videos"]), 2)
        (self.prepared / "oldvideo001.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "^CONFIRM_REPLACE: Analyzing this topic"):
            server.analyze_explored_topic(
                topic_key="aircraft_windows_are_round", confirm_replace=False, allow_excluded=False
            )
        payload = server.analyze_explored_topic(
            topic_key="aircraft_windows_are_round", confirm_replace=True, allow_excluded=False
        )
        self.assertEqual(payload["active"]["source_type"], "HUMAN_TOPIC")
        self.assertEqual(payload["active"]["video_count"], 2)
        # Switching to a submitted video also asks first, because work exists.
        save_packet()
        with self.assertRaisesRegex(ValueError, "^CONFIRM_REPLACE: "):
            server.analyze_submitted_video(video_id=VID, confirm_replace=False, allow_excluded=False)

    def test_viral_radar_action_and_analyze(self):
        self.assertIn("viral_radar", server.ACTION_DEFS)
        self.assertEqual(server.ACTION_DEFS["viral_radar"]["command"][1:], ["opportunity_engine/viral_radar.py", "run"])
        self.assertNotIn("viral_radar", server.AUTO_MACHINE_ACTION_ORDER)
        self.assertTrue(server.action_readiness()["viral_radar"]["enabled"])
        from opportunity_engine import channel_scope
        from opportunity_engine.test_viral_radar import MATURE, NOW, FakeApi, item

        config = json.loads(json.dumps(channel_scope.load_config()))
        config["viral_radar"]["watchlist_handles"] = ["@brakelab"]
        vr.run(
            api=FakeApi(MATURE + [item(10, 48, 80_000)], handles={"@brakelab": "UC" + "a" * 22}),
            searcher=lambda u, l, t: [],
            config=config,
            now=NOW,
        )
        self.assertEqual(vr.status_snapshot()["tracked_count"], 1)
        (self.prepared / "oldvideo001.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "^CONFIRM_REPLACE: Analyzing this breakout"):
            server.analyze_viral_candidate(video_id="video000010", confirm_replace=False, allow_excluded=False)
        payload = server.analyze_viral_candidate(video_id="video000010", confirm_replace=True, allow_excluded=False)
        self.assertEqual(payload["active"]["source_type"], "VIRAL_RADAR")

    def test_unified_gate_routes_historical_saves_and_rejects_to_the_gate(self):
        historical = {
            "opportunity_id": "opp_historical__automotive_racing__brakes__long_form_candidate",
            "gate_opportunity_id": "automotive_racing:brakes:long_form_candidate",
        }
        with (
            patch.object(server, "opportunity_inbox_snapshot", return_value={"items": [historical]}),
            patch.object(server, "apply_gate_action") as gate_action,
        ):
            server.apply_inbox_decision(opportunity_id=historical["opportunity_id"], action="SAVE", note="")
            gate_action.assert_called_once_with(
                action="HOLD_TOPIC", opportunity_key="automotive_racing:brakes:long_form_candidate"
            )
            server.apply_inbox_decision(opportunity_id=historical["opportunity_id"], action="REJECT", note="")
            self.assertEqual(gate_action.call_args.kwargs["action"], "REJECT_TOPIC")
            with self.assertRaisesRegex(ValueError, "Historical review"):
                server.apply_inbox_decision(opportunity_id=historical["opportunity_id"], action="APPROVE", note="")

    def test_approval_through_analyze_is_in_the_decision_history(self):
        save_packet()
        server.analyze_submitted_video(video_id=VID, confirm_replace=False, allow_excluded=False)
        item = server.opportunity_inbox_snapshot()["items"][0]
        self.assertEqual([h["action"] for h in item["decision_history"]], ["APPROVE"])

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
