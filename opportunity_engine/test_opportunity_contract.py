import copy
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from opportunity_engine import channel_scope, models  # noqa: E402
from opportunity_engine.packet_schema import build_packet, evidence, validate_packet  # noqa: E402
from opportunity_engine.provenance import opportunity_id, packet_sha256  # noqa: E402

ACTIVE = {"route": "ACTIVE_CHANNEL", "channel_id": "science_inside", "rule_id": "NICHE-x"}


def topic_packet(**extra):
    values = dict(
        opportunity_id=opportunity_id(models.SOURCE_HUMAN_TOPIC, "hummingbird flight"),
        source_type=models.SOURCE_HUMAN_TOPIC,
        title="How hummingbirds hover",
        summary="Human seed.",
        channel=ACTIVE,
        seed={"question": "How does a hummingbird hover?"},
        generator="test",
        created_at="2026-10-03T00:00:00+00:00",
    )
    values.update(extra)
    return build_packet(**values)


class PacketContractTests(unittest.TestCase):
    def test_minimal_human_packet_is_valid_and_unassessed(self):
        packet = topic_packet()
        self.assertEqual(validate_packet(packet), [])
        self.assertEqual(packet["evidence_state"]["historical_demand"]["level"], "UNASSESSED")
        self.assertEqual(packet["evidence_state"]["viewer_need"]["level"], "HYPOTHESIS")
        self.assertIsNone(packet["viral_evidence"])

    def test_identity_is_stable_and_ignores_timestamps(self):
        self.assertEqual(
            opportunity_id("HISTORICAL", "automotive_racing", "Tyres/Tires", "long_form"),
            "opp_historical__automotive_racing__tyres_tires__long_form",
        )
        a = topic_packet(created_at="2026-10-01T00:00:00+00:00")
        b = topic_packet(created_at="2026-10-02T00:00:00+00:00")
        self.assertEqual(a["packet_sha256"], b["packet_sha256"])
        with self.assertRaises(ValueError):
            opportunity_id("HISTORICAL", " ", "")

    def test_level_above_hypothesis_needs_a_written_rule(self):
        with self.assertRaisesRegex(ValueError, "needs a rule_id"):
            topic_packet(evidence_state={"viewer_need": evidence("STRONG")})
        packet = topic_packet(
            evidence_state={"viewer_need": evidence("STRONG", "VN-COMMENTS", ["12 repeated questions"])}
        )
        self.assertEqual(packet["evidence_state"]["viewer_need"]["rule_id"], "VN-COMMENTS")

    def test_unknown_levels_dimensions_and_sources_rejected(self):
        with self.assertRaisesRegex(ValueError, "level must be one of"):
            topic_packet(evidence_state={"content_gap": evidence("STRONG", "r")})
        with self.assertRaisesRegex(ValueError, "unknown evidence dimensions"):
            topic_packet(evidence_state={"virality_score": evidence("STRONG", "r")})
        with self.assertRaisesRegex(ValueError, "source_type"):
            topic_packet(source_type="TRENDING")

    def test_lane_specific_requirements(self):
        with self.assertRaisesRegex(ValueError, "seed"):
            topic_packet(seed={})
        with self.assertRaisesRegex(ValueError, "historical_evidence"):
            topic_packet(source_type=models.SOURCE_HISTORICAL)
        with self.assertRaisesRegex(ValueError, "viral_evidence"):
            topic_packet(source_type=models.SOURCE_VIRAL_RADAR)

    def test_viral_evidence_uses_four_separate_axes(self):
        viral = {
            "strength": "BREAKOUT",
            "trajectory": "ACCELERATING",
            "breadth": "REPLICATED",
            "historical_alignment": "UNASSESSED",
            "trajectory_history_available": True,
        }
        packet = topic_packet(source_type=models.SOURCE_VIRAL_RADAR, viral_evidence=viral)
        self.assertEqual(validate_packet(packet), [])
        with self.assertRaisesRegex(ValueError, "strength"):
            topic_packet(
                source_type=models.SOURCE_VIRAL_RADAR,
                viral_evidence=dict(viral, strength="ACCELERATING_BREAKOUT"),
            )
        with self.assertRaisesRegex(ValueError, "trajectory_history_available"):
            topic_packet(
                source_type=models.SOURCE_VIRAL_RADAR,
                viral_evidence={k: v for k, v in viral.items() if k != "trajectory_history_available"},
            )

    def test_channel_routing_contract(self):
        with self.assertRaisesRegex(ValueError, "channel_id is required"):
            topic_packet(channel={"route": "FUTURE_CHANNEL", "channel_id": None})
        with self.assertRaisesRegex(ValueError, "rule_id"):
            topic_packet(channel={"route": "EXCLUDED", "channel_id": None})

    def test_tampered_packet_fails_hash_check(self):
        packet = copy.deepcopy(topic_packet())
        packet["title"] = "Edited"
        self.assertIn("packet_sha256 does not match packet content", validate_packet(packet))
        packet["packet_sha256"] = packet_sha256(packet)
        self.assertEqual(validate_packet(packet), [])


class ChannelScopeTests(unittest.TestCase):
    def setUp(self):
        self.config = channel_scope.load_config()

    def route(self, text, niche="", **kw):
        return channel_scope.route(text, niche=niche, config=self.config, **kw)

    def test_repository_config_has_one_active_channel(self):
        self.assertEqual(self.config["active_channel_id"], "science_inside")
        self.assertEqual(channel_scope.validate_config(self.config), [])
        broken = copy.deepcopy(self.config)
        broken["channels"]["storytime"]["status"] = "ACTIVE"
        self.assertIn("exactly one channel may be ACTIVE", channel_scope.validate_config(broken))

    def test_science_inside_topics_route_to_active_channel(self):
        for text, niche in (
            ("Why aircraft tyres are filled with nitrogen", "science_engineering"),
            ("Wet vs dry tyres explained", "automotive_racing"),
            ("How hummingbirds hover", "everyday_science"),
        ):
            result = self.route(text, niche)
            self.assertEqual(result["route"], "ACTIVE_CHANNEL", text)
            self.assertEqual(result["channel_id"], "science_inside")

    def test_future_channel_ideas_are_parked_not_dropped(self):
        self.assertEqual(self.route("My project car turbo kit install", "automotive_racing")["channel_id"], "car_modifications")
        self.assertEqual(self.route("How annuity payments really work")["channel_id"], "retirement_ageing")
        self.assertEqual(self.route("Storytime: the night my engine died")["route"], "FUTURE_CHANNEL")

    def test_exclusions_name_their_rule_and_respect_exceptions(self):
        highlights = self.route("Arsenal vs Chelsea highlights")
        self.assertEqual((highlights["route"], highlights["rule_id"]), ("EXCLUDED", "EX-SPORT-NONMOTOR"))
        self.assertEqual(self.route("The physics of a free kick highlights why balls dip", "everyday_science")["route"], "ACTIVE_CHANNEL")
        self.assertEqual(self.route("Minecraft gameplay part 4")["rule_id"], "EX-GAMING")
        self.assertEqual(self.route("Best crypto to buy now")["rule_id"], "EX-GET-RICH")
        self.assertEqual(self.route("DPF delete on my diesel")["rule_id"], "EX-CAR-ILLEGAL")
        self.assertEqual(self.route("How hummingbirds hover", made_for_kids=True)["rule_id"], "EX-MADE-FOR-KIDS")

    def test_whole_word_matching_avoids_false_exclusions(self):
        for text in ("Software that flies the A380", "The award-winning bridge design", "Chemical reaction inside a battery"):
            self.assertNotEqual(self.route(text, "everyday_science")["route"], "EXCLUDED", text)

    def test_unknown_niche_is_unscoped(self):
        self.assertEqual(self.route("Why steelpans ring")["route"], "UNSCOPED")


if __name__ == "__main__":
    unittest.main()
