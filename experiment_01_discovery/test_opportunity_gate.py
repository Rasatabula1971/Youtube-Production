import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import opportunity_gate as gate
from opportunity_engine import active_source
from opportunity_engine import human_topic_search as hts
from opportunity_engine import human_video_intake as hvi

VID = "dQw4w9WgXcQ"


class OpportunityGateTests(unittest.TestCase):
    def setUp(self):
        isolation = tempfile.TemporaryDirectory()
        self.addCleanup(isolation.cleanup)
        self.isolated = Path(isolation.name)
        for item in (
            patch.object(active_source, "ACTIVE_FILE", self.isolated / "active.json"),
            patch.object(hvi, "PACKETS_DIR", self.isolated / "human_video"),
            patch.object(hts, "PACKETS_DIR", self.isolated / "human_topic"),
        ):
            item.start()
            self.addCleanup(item.stop)
        self.study_set = [
            {
                "gate_status": "PASS",
                "handoff_id": "v1:tyres_tires:short_candidate",
                "video_id": "v1",
                "youtube_url": "https://www.youtube.com/watch?v=v1",
                "title": "First tyre example",
                "channel_id": "c1",
                "channel_title": "Channel 1",
                "topic": "tyres_tires",
                "niche": "automotive_racing",
                "format_candidate": "short_candidate",
                "views": 2_000_000,
                "age_days": 120,
                "primary_metric": {"value": 3.0},
                "topic_evidence": {
                    "unique_channels": 4,
                    "velocity_sample_count": 3,
                    "age_matched_velocity_index": 3.0,
                },
            },
            {
                "gate_status": "PASS",
                "handoff_id": "v2:tyres_tires:short_candidate",
                "video_id": "v2",
                "youtube_url": "https://www.youtube.com/watch?v=v2",
                "title": "Second tyre example",
                "channel_id": "c2",
                "channel_title": "Channel 2",
                "topic": "tyres_tires",
                "niche": "automotive_racing",
                "format_candidate": "short_candidate",
                "views": 1_500_000,
                "age_days": 130,
                "primary_metric": {"value": 3.0},
                "topic_evidence": {
                    "unique_channels": 4,
                    "velocity_sample_count": 3,
                    "age_matched_velocity_index": 3.0,
                },
            },
        ]
        self.packets = [
            *self.study_set,
            {
                "gate_status": "PASS",
                "handoff_id": "v3:tyres_tires:short_candidate",
                "video_id": "v3",
                "youtube_url": "https://www.youtube.com/watch?v=v3",
                "title": "Replacement tyre example",
                "channel_id": "c3",
                "channel_title": "Channel 3",
                "topic": "tyres_tires",
                "niche": "automotive_racing",
                "format_candidate": "short_candidate",
                "views": 1_000_000,
                "age_days": 110,
                "primary_metric": {"value": 3.0},
                "topic_evidence": {
                    "unique_channels": 4,
                    "velocity_sample_count": 3,
                    "age_matched_velocity_index": 3.0,
                },
            },
        ]

    def patched_paths(self, root: Path):
        output = root / "experiment_01_5"
        output.mkdir()
        study = output / "study_set.json"
        packets = output / "handoff_packets.json"
        decision = output / "human_opportunity_decision.json"
        approved = output / "approved_study_set.json"
        study.write_text(json.dumps(self.study_set), encoding="utf-8")
        packets.write_text(json.dumps(self.packets), encoding="utf-8")

        return (
            patch.object(gate, "OUTPUT_DIR", output),
            patch.object(gate, "STUDY_SET_FILE", study),
            patch.object(gate, "HANDOFF_PACKETS_FILE", packets),
            patch.object(gate, "DECISION_FILE", decision),
            patch.object(gate, "APPROVED_STUDY_SET_FILE", approved),
            approved,
        )

    def activate_human_video(self):
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
        return active_source.set_active(VID)

    def test_human_video_is_the_study_set_without_any_historical_run(self):
        approved = self.isolated / "approved_study_set.json"
        with (
            patch.object(gate, "STUDY_SET_FILE", self.isolated / "missing_study_set.json"),
            patch.object(gate, "APPROVED_STUDY_SET_FILE", approved),
        ):
            self.assertEqual(gate.gate_snapshot()["status"], "WAITING_FOR_01_5")
            self.activate_human_video()
            snapshot = gate.gate_snapshot()
            self.assertEqual(snapshot["status"], "APPROVED_HUMAN_VIDEO")
            self.assertTrue(snapshot["ready_for_experiment_02"])
            self.assertEqual(snapshot["active_human_video"]["video_id"], VID)
            rows = json.loads(approved.read_text(encoding="utf-8"))
            self.assertEqual([row["video_id"] for row in rows], [VID])

            active_source.clear_active()
            snapshot = gate.gate_snapshot()
            self.assertFalse(snapshot["ready_for_experiment_02"])
            self.assertFalse(approved.exists())

    def test_human_topic_videos_become_the_study_set_and_are_cleaned_up(self):
        hts.explore(
            "Turbo lag",
            searcher=lambda q, l, t: [
                {"video_id": "turbolag001", "title": "Turbo lag explained", "channel_id": "c1", "channel_title": "C1", "duration_seconds": 500, "views": 1},
                {"video_id": "turbolag002", "title": "Why turbo lag happens", "channel_id": "c2", "channel_title": "C2", "duration_seconds": 500, "views": 2},
            ],
            measurer=lambda ids: {},
        )
        approved = self.isolated / "approved_study_set.json"
        with (
            patch.object(gate, "STUDY_SET_FILE", self.isolated / "missing_study_set.json"),
            patch.object(gate, "APPROVED_STUDY_SET_FILE", approved),
        ):
            active_source.set_active_topic("turbo_lag")
            snapshot = gate.gate_snapshot()
            self.assertEqual(snapshot["status"], "APPROVED_HUMAN_TOPIC")
            self.assertEqual(snapshot["active_human_video"]["source_type"], "HUMAN_TOPIC")
            rows = json.loads(approved.read_text(encoding="utf-8"))
            self.assertEqual([row["video_id"] for row in rows], ["turbolag002", "turbolag001"])
            active_source.clear_active()
            gate.gate_snapshot()
            self.assertFalse(approved.exists())

    def test_historical_approval_replaces_an_active_human_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            patches = self.patched_paths(Path(tmp))
            approved = patches[-1]
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                self.activate_human_video()
                snapshot = gate.gate_snapshot()
                self.assertEqual(snapshot["status"], "APPROVED_HUMAN_VIDEO")
                self.assertEqual(len(snapshot["opportunities"]), 1)
                key = snapshot["opportunities"][0]["opportunity_id"]

                # Reviewing historical examples leaves the human video active.
                for video_id in ("v1", "v2"):
                    gate.apply_gate_action(
                        action="KEEP_EXAMPLE", opportunity_key=key, video_id=video_id
                    )
                rows = json.loads(approved.read_text(encoding="utf-8"))
                self.assertEqual([row["video_id"] for row in rows], [VID])

                result = gate.apply_gate_action(action="APPROVE_TOPIC", opportunity_key=key)
                self.assertEqual(result["status"], "APPROVED")
                self.assertIsNone(result["active_human_video"])
                self.assertIsNone(active_source.load_active())
                rows = json.loads(approved.read_text(encoding="utf-8"))
                self.assertEqual([row["video_id"] for row in rows], ["v1", "v2"])

    def test_approval_requires_every_selected_example_to_be_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = self.patched_paths(root)
            approved = patches[-1]
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                snapshot = gate.gate_snapshot()
                opportunity = snapshot["opportunities"][0]
                key = opportunity["opportunity_id"]

                self.assertEqual(
                    opportunity["niche"],
                    "automotive_racing",
                )
                self.assertFalse(opportunity["can_approve"])
                with self.assertRaisesRegex(
                    ValueError, "Review every selected example"
                ):
                    gate.apply_gate_action(
                        action="APPROVE_TOPIC",
                        opportunity_key=key,
                    )

                for video_id in ("v1", "v2"):
                    gate.apply_gate_action(
                        action="KEEP_EXAMPLE",
                        opportunity_key=key,
                        video_id=video_id,
                    )

                result = gate.apply_gate_action(
                    action="APPROVE_TOPIC",
                    opportunity_key=key,
                )

                self.assertTrue(result["ready_for_experiment_02"])
                self.assertTrue(approved.exists())
                approved_rows = json.loads(approved.read_text(encoding="utf-8"))
                self.assertEqual(
                    [item["video_id"] for item in approved_rows],
                    ["v1", "v2"],
                )

    def test_replacing_example_invalidates_existing_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = self.patched_paths(root)
            approved = patches[-1]
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                key = gate.gate_snapshot()["opportunities"][0]["opportunity_id"]

                for video_id in ("v1", "v2"):
                    gate.apply_gate_action(
                        action="KEEP_EXAMPLE",
                        opportunity_key=key,
                        video_id=video_id,
                    )
                gate.apply_gate_action(
                    action="APPROVE_TOPIC",
                    opportunity_key=key,
                )
                self.assertTrue(approved.exists())

                result = gate.apply_gate_action(
                    action="REPLACE_EXAMPLE",
                    opportunity_key=key,
                    video_id="v1",
                )

                self.assertFalse(result["ready_for_experiment_02"])
                self.assertFalse(approved.exists())
                opportunity = result["opportunities"][0]
                self.assertEqual(opportunity["decision"], "PENDING")
                selected = {
                    item["video_id"]: item["decision"]
                    for item in opportunity["selected_examples"]
                }
                self.assertEqual(selected["v3"], "PENDING")
                self.assertEqual(selected["v2"], "KEEP")

    def test_reject_completes_gate_without_unlocking_experiment_02(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = self.patched_paths(root)
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                key = gate.gate_snapshot()["opportunities"][0]["opportunity_id"]
                result = gate.apply_gate_action(
                    action="REJECT_TOPIC",
                    opportunity_key=key,
                )

                self.assertTrue(result["gate_complete"])
                self.assertFalse(result["ready_for_experiment_02"])
                self.assertEqual(result["status"], "COMPLETE_NO_APPROVED_TOPIC")


if __name__ == "__main__":
    unittest.main()
