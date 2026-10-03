import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from opportunity_engine import channel_scope, viral_cluster  # noqa: E402
from opportunity_engine import viral_radar as vr  # noqa: E402
from opportunity_engine.test_viral_radar import FakeApi, RadarTestCase, item  # noqa: E402

SETTINGS = channel_scope.load_config()["viral_clustering"]


def record(video_id, title, channel, strength="BREAKOUT", ratio=6.0, duration=600, published="2026-10-01T00:00:00Z"):
    return video_id, {
        "strength": strength,
        "metrics": {"lifetime_ratio": ratio},
        "video": {
            "title": title,
            "channel_id": channel,
            "channel_title": channel,
            "duration_seconds": duration,
            "published_at": published,
        },
    }


class ClusterTests(unittest.TestCase):
    def test_keywords_drop_stopwords_and_plural_s(self):
        self.assertEqual(viral_cluster.keywords("Why F1 brakes glow orange"), {"f1", "brake", "glow", "orange"})

    def test_three_independent_channels_replicate_a_question(self):
        records = dict(
            [
                record("v1", "Why F1 brakes glow orange", "c1", ratio=9),
                record("v2", "Why do F1 brake discs glow?", "c2", ratio=7),
                record("v3", "F1 brakes glow: the 1000 degree secret", "c3", ratio=5),
                record("v4", "Hummingbird wings in slow motion", "c4"),
                record("v5", "Normal video about F1 brakes glow", "c5", strength="NORMAL"),
            ]
        )
        clusters = viral_cluster.cluster(records, SETTINGS)
        top = clusters[0]
        self.assertEqual(top["independent_channel_count"], 3)
        self.assertEqual((top["breadth"], top["kind"]), ("REPLICATED", "SAME_VIEWER_QUESTION"))
        self.assertEqual(top["replication_rule_id"], "CL-REPLICATED")
        self.assertIn("brake", top["shared_keywords"])
        self.assertEqual(sorted(m["video_id"] for m in top["members"]), ["v1", "v2", "v3"])
        lone = next(c for c in clusters if c["members"][0]["video_id"] == "v4")
        self.assertEqual((lone["breadth"], lone["replication_rule_id"]), ("ONE_OFF", "CL-ONE-OFF"))
        self.assertNotIn("v5", [m["video_id"] for c in clusters for m in c["members"]])

    def test_same_creator_and_reuploads_are_not_independent(self):
        records = dict(
            [
                record("v1", "How a turbo spools up", "c1", published="2026-10-01T00:00:00Z"),
                record("v2", "How a turbo spools up fast", "c1", published="2026-10-02T00:00:00Z"),
                record("v3", "How a turbo spools up", "clipper", published="2026-10-02T06:00:00Z"),
                record("v4", "Turbo spools explained with smoke", "c2"),
            ]
        )
        top = viral_cluster.cluster(records, SETTINGS)[0]
        independence = {m["video_id"]: m["independence"] for m in top["members"]}
        self.assertEqual(independence["v2"], "SAME_CHANNEL")
        self.assertEqual(independence["v3"], "REUPLOAD_OF:v1")
        self.assertEqual(top["independent_channel_count"], 2)
        self.assertEqual((top["breadth"], top["replication_rule_id"]), ("ONE_OFF", "CL-PAIR"))

    def test_event_bound_replication_is_weak_evidence(self):
        records = dict(
            [
                # Different lengths: three real videos, not re-uploads of one.
                record(f"v{i}", f"Verstappen wins Monaco Grand Prix 2026 {suffix}", f"c{i}", duration=300 * i)
                for i, suffix in enumerate(["highlights", "reaction", "analysis"], start=1)
            ]
        )
        top = viral_cluster.cluster(records, SETTINGS)[0]
        self.assertEqual((top["kind"], top["breadth"]), ("SAME_EVENT", "REPLICATED"))
        self.assertEqual(top["replication_rule_id"], "CL-EVENT-BOUND")

    def test_cluster_ids_are_deterministic(self):
        records = dict([record("v1", "Why F1 brakes glow", "c1"), record("v2", "F1 brakes glow orange", "c2")])
        self.assertEqual(
            viral_cluster.cluster(records, SETTINGS)[0]["cluster_id"],
            viral_cluster.cluster(dict(reversed(list(records.items()))), SETTINGS)[0]["cluster_id"],
        )


CHANNELS = ["UC" + letter * 22 for letter in "abc"]


class RadarClusteringTests(RadarTestCase):
    def test_replicated_theme_reaches_packets_and_clusters_file(self):
        videos = []
        for index, channel in enumerate(CHANNELS):
            videos += [item(100 * index + i, 24 * (30 + i), 10_000, channel=channel, title=f"Old upload {i}") for i in range(1, 5)]
        titles = ["Why F1 brakes glow orange", "Why do F1 brake discs glow?", "F1 brakes glow at 1000 degrees"]
        for index, (channel, title) in enumerate(zip(CHANNELS, titles, strict=True)):
            videos.append(item(900 + index, 48, 80_000, channel=channel, title=title))
        self.config["viral_radar"]["watchlist_handles"] = []
        api = FakeApi(videos, channels={c: {"subs": "1000"} for c in CHANNELS})
        state = vr.load_state()
        for channel in CHANNELS:
            state["watchlist"][channel] = {"source": "test"}
        vr.save_state(state)
        summary = self.run_radar(api)
        self.assertEqual(summary["clusters"], {"count": 1, "replicated": 1})
        packet = vr.load_packet("video000900")
        viral = packet["viral_evidence"]
        self.assertEqual(viral["breadth"], "REPLICATED")
        self.assertEqual(viral["cluster"]["independent_channel_count"], 3)
        self.assertEqual(packet["evidence_state"]["cross_channel_replication"]["rule_id"], "CL-REPLICATED")
        clusters = vr.load_clusters()
        self.assertEqual(vr.load_cluster(clusters[0]["cluster_id"])["kind"], "SAME_VIEWER_QUESTION")
        self.assertEqual(vr.status_snapshot()["replicated_themes"], 1)
        self.assertEqual(json.loads(vr.CLUSTERS_FILE.read_text())["clusters"][0]["method"], "deterministic_title_keywords")

        # O11: the whole theme becomes the study set, one video per channel, with context.
        from opportunity_engine import active_source, inbox

        with (
            patch.object(active_source, "ACTIVE_FILE", self.root / "active.json"),
            patch.object(inbox, "STATE_FILE", self.root / "inbox.json"),
        ):
            items = inbox.build_inbox({})["items"]
            self.assertTrue(all("APPROVE_THEME" in i["actions"] for i in items))
            record = active_source.set_active_cluster(clusters[0]["cluster_id"])
            rows = record["study_set"]
            self.assertEqual(len(rows), 3)
            self.assertEqual(len({r["channel_id"] for r in rows}), 3)
            self.assertTrue(rows[0]["handoff_id"].startswith("viral_cluster:" + clusters[0]["cluster_id"]))
            context = rows[0]["opportunity_context"]
            self.assertEqual(context["breakout"]["breadth"], "REPLICATED")
            self.assertEqual(context["breakout"]["theme_independent_channels"], 3)
            self.assertEqual(active_source.load_active(), record)
            items = inbox.build_inbox({})["items"]
            self.assertTrue(all(i["is_active"] for i in items))
            vr.packet_path("video000900").unlink()
            self.assertIsNone(active_source.load_active())
        with self.assertRaisesRegex(ValueError, "no longer in the latest radar run"):
            active_source.set_active_cluster("cl_missing")



if __name__ == "__main__":
    unittest.main()
