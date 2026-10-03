import unittest

from analysis_execute import OPPORTUNITY_INSTRUCTIONS, build_analysis_request
from experiment_02 import build_profile_from_study_item, load_config

CONTEXT = {
    "source_type": "VIRAL_RADAR",
    "seed_question": None,
    "seed_topic": None,
    "breakout": {
        "strength": "BREAKOUT",
        "channel_multiple": 8.7,
        "trajectory": "ACCELERATING",
        "breadth": "REPLICATED",
        "theme": "f1 brake glow",
        "theme_kind": "SAME_VIEWER_QUESTION",
        "theme_independent_channels": 3,
    },
}


def study_item(**extra):
    item = {
        "video_id": "abc123def45",
        "title": "Why F1 brakes glow",
        "handoff_id": "x",
        "channel_id": "UC1",
        "channel_title": "C",
        "format_candidate": "long_form_candidate",
        "topic": "brakes",
    }
    item.update(extra)
    return item


class OpportunityBridgeTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()

    def test_historical_rows_are_unchanged(self):
        profile = build_profile_from_study_item(study_item(), self.config)
        self.assertNotIn("opportunity_context", profile["source"])
        self.assertEqual(profile["evidence"][1]["locator"], "Experiment 01.5 handoff packet")
        request = build_analysis_request(profile, self.config)
        for line in OPPORTUNITY_INSTRUCTIONS:
            self.assertNotIn(line, request["instructions"])

    def test_radar_rows_carry_context_and_the_opportunity_questions(self):
        profile = build_profile_from_study_item(study_item(opportunity_context=CONTEXT), self.config)
        self.assertEqual(profile["source"]["opportunity_context"], CONTEXT)
        upstream = profile["evidence"][1]
        self.assertEqual(upstream["evidence_id"], "opportunity.01_5")
        self.assertEqual(upstream["locator"], "Opportunity packet (VIRAL_RADAR)")
        self.assertIn("8.7x its channel's normal views", upstream["observation"])
        self.assertIn("Context only", upstream["observation"])
        request = build_analysis_request(profile, self.config)
        self.assertEqual(request["source"]["opportunity_context"]["breakout"]["breadth"], "REPLICATED")
        for line in OPPORTUNITY_INSTRUCTIONS:
            self.assertIn(line, request["instructions"])

    def test_human_question_is_named(self):
        context = {"source_type": "HUMAN_TOPIC", "seed_question": "Why are aircraft windows round?"}
        profile = build_profile_from_study_item(study_item(opportunity_context=context), self.config)
        self.assertIn("Human question: Why are aircraft windows round?", profile["evidence"][1]["observation"])


if __name__ == "__main__":
    unittest.main()
