import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import opportunity_gate as gate


class OpportunityGateTests(unittest.TestCase):
    def setUp(self):
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

    def test_approval_requires_every_selected_example_to_be_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = self.patched_paths(root)
            approved = patches[-1]
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                snapshot = gate.gate_snapshot()
                opportunity = snapshot["opportunities"][0]
                key = opportunity["opportunity_id"]

                self.assertFalse(opportunity["can_approve"])
                with self.assertRaisesRegex(ValueError, "Review every selected example"):
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
