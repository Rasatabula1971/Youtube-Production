import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from opportunity_engine import historical_adapter  # noqa: E402
from opportunity_engine.packet_schema import validate_packet  # noqa: E402


def study_item(video_id, topic="tyres_tires", fmt="long_form", channel="UC1", channels=4, status="PASS"):
    return {
        "handoff_id": f"{video_id}:{topic}:{fmt}",
        "gate_status": status,
        "video_id": video_id,
        "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
        "title": f"Why F1 tyres {video_id}",
        "channel_id": channel,
        "channel_title": "Chan",
        "published_at": "2026-06-01T00:00:00Z",
        "format_candidate": fmt,
        "niche": "automotive_racing",
        "views": 900000,
        "topic": topic,
        "replicated_families": ["explained"],
        "topic_evidence": {"unique_channels": channels, "age_matched_velocity_index": 2.4},
        "primary_metric": {"name": "age_matched_velocity_index", "value": 2.4},
    }


class HistoricalAdapterTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.study_file = self.root / "study_set.json"

    def build(self, items):
        self.study_file.write_text(json.dumps(items), encoding="utf-8")
        return historical_adapter.build(self.study_file)

    def test_pipeline_candidate_format_labels_are_normalised(self):
        result = self.build(
            [
                study_item("a1", fmt="long_form_candidate"),
                study_item("s1", fmt="short_candidate"),
                study_item("u1", fmt="unknown"),
            ]
        )
        self.assertEqual(
            [p["opportunity_id"] for p in result["packets"]],
            [
                "opp_historical__automotive_racing__tyres_tires__long_form_candidate",
                "opp_historical__automotive_racing__tyres_tires__short_candidate",
            ],
        )
        self.assertEqual([p["formats"] for p in result["packets"]], [["long_form"], ["short"]])
        self.assertEqual(result["packets"][1]["candidate_videos"][0]["format"], "short")
        for packet in result["packets"]:
            self.assertEqual(validate_packet(packet), [])

    def test_missing_study_set_waits(self):
        result = historical_adapter.build(self.root / "missing.json")
        self.assertEqual(result["status"], "WAITING_FOR_01_5")
        self.assertEqual(result["packets"], [])

    def test_groups_like_the_existing_gate_and_validates(self):
        result = self.build(
            [
                study_item("a1"),
                study_item("a2", channel="UC2"),
                study_item("b1", fmt="short", channels=7),
                study_item("c1", topic="brakes", channels=2),
                {"video_id": "junk"},
            ]
        )
        self.assertEqual(result["status"], "READY")
        ids = [p["opportunity_id"] for p in result["packets"]]
        self.assertEqual(
            ids,
            [
                "opp_historical__automotive_racing__tyres_tires__long_form",
                "opp_historical__automotive_racing__tyres_tires__short",
                "opp_historical__automotive_racing__brakes__long_form",
            ],
        )
        first, short, brakes = result["packets"]
        for packet in result["packets"]:
            self.assertEqual(validate_packet(packet), [])
            self.assertEqual(packet["channel"]["route"], "ACTIVE_CHANNEL")
        self.assertEqual([v["video_id"] for v in first["candidate_videos"]], ["a1", "a2"])
        self.assertEqual(first["evidence_state"]["historical_demand"]["rule_id"], "HD-01.5-PASS")
        self.assertEqual(first["evidence_state"]["cross_channel_replication"]["level"], "MODERATE")
        self.assertEqual(short["evidence_state"]["cross_channel_replication"]["level"], "STRONG")
        self.assertEqual(brakes["evidence_state"]["cross_channel_replication"]["level"], "LOW")
        self.assertEqual(first["evidence_state"]["viewer_need"]["level"], "HYPOTHESIS")
        self.assertEqual(first["historical_evidence"]["experiment_01_5_handoff_ids"], ["a1:tyres_tires:long_form", "a2:tyres_tires:long_form"])
        self.assertEqual(first["provenance"]["source_artifacts"][0]["role"], "experiment_01_5_study_set")

    def test_changed_study_set_changes_provenance_but_not_identity(self):
        before = self.build([study_item("a1")])
        after = self.build([study_item("a1", channels=9)])
        self.assertEqual(before["packets"][0]["opportunity_id"], after["packets"][0]["opportunity_id"])
        self.assertNotEqual(before["source_study_set_sha256"], after["source_study_set_sha256"])
        self.assertNotEqual(before["packets"][0]["packet_sha256"], after["packets"][0]["packet_sha256"])

    def test_empty_study_set_is_written_so_old_packets_cannot_linger(self):
        out = self.root / "out" / "historical.json"
        historical_adapter.write(self.build([study_item("a1")]), out)
        historical_adapter.write(self.build([]), out)
        saved = json.loads(out.read_text())
        self.assertEqual(saved["status"], "NO_HISTORICAL_OPPORTUNITIES")
        self.assertEqual(saved["packets"], [])

    def test_non_list_study_set_rejected(self):
        self.study_file.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            historical_adapter.build(self.study_file)


if __name__ == "__main__":
    unittest.main()
