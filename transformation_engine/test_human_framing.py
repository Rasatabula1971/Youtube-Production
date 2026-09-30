import unittest

from human_framing import validate


def valid_framing():
    return {
        "hook_experience": {
            "archetype": "FAILURE_CONSEQUENCE",
            "description": "A car grips normally, hits standing water, then suddenly loses control.",
        },
        "viewer_question": "Why did the grip disappear so suddenly?",
        "psychological_pull": {
            "primary_pull": "EXPECTATION_VIOLATION",
            "viewer_expectation": "The car should keep following the driver's steering input.",
            "violation_or_tension": "Water suddenly changes the available grip.",
            "stakes": "Loss of control at racing speed.",
            "information_gap": "What changed underneath the tyre?",
            "desired_resolution": "Understand why water can separate the tyre from useful road contact.",
        },
        "explanation_payoff": (
            "Understand why slicks, intermediates and full wets work in different "
            "amounts of water."
        ),
        "visual_opening_plan": {
            "moments": [
                {"visual": "Car grips through a corner.", "purpose": "Establish control."},
                {"visual": "Car enters standing water.", "purpose": "Introduce the hidden variable."},
                {"visual": "Car snaps sideways.", "purpose": "Create the unanswered consequence."},
            ],
            "opening_narration_intent": "One second it had grip. Then it hit water. What changed?",
        },
        "drama": {
            "capacity": 8,
            "target": 6,
            "source": "Sudden visible loss of control at speed.",
            "constraint": "Do not imply every wet patch causes aquaplaning or a crash.",
            "hook_level": 7,
            "story_curve": [7, 5, 6, 8, 5, 7],
            "tempo_curve": [7, 4, 6, 7, 5, 6],
        },
    }


class HumanFramingTests(unittest.TestCase):
    def test_valid_framing_passes(self):
        self.assertEqual(validate(valid_framing()), [])

    def test_drama_below_floor_is_rejected(self):
        payload = valid_framing()
        payload["drama"]["story_curve"][1] = 3
        errors = validate(payload)
        self.assertTrue(any("story_curve levels" in item for item in errors))

    def test_target_cannot_exceed_capacity(self):
        payload = valid_framing()
        payload["drama"]["capacity"] = 6
        payload["drama"]["target"] = 7
        errors = validate(payload)
        self.assertTrue(any("target cannot exceed capacity" in item for item in errors))

    def test_high_drama_capacity_cannot_be_wasted(self):
        payload = valid_framing()
        payload["drama"]["capacity"] = 9
        payload["drama"]["target"] = 5
        errors = validate(payload)
        self.assertTrue(any("underuses a high-drama opportunity" in item for item in errors))

    def test_flat_drama_curve_is_rejected(self):
        payload = valid_framing()
        payload["drama"]["target"] = 5
        payload["drama"]["story_curve"] = [5, 5, 5, 5, 5, 5]
        errors = validate(payload)
        self.assertTrue(any("must pulse" in item for item in errors))

    def test_flat_tempo_curve_is_rejected(self):
        payload = valid_framing()
        payload["drama"]["tempo_curve"] = [5, 5, 5, 5, 5, 5]
        errors = validate(payload)
        self.assertTrue(any("tempo_curve must change" in item for item in errors))

    def test_curve_lengths_must_match(self):
        payload = valid_framing()
        payload["drama"]["tempo_curve"] = [7, 4, 6, 7]
        errors = validate(payload)
        self.assertTrue(any("same number of beats" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
