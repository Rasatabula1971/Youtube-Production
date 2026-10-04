import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opportunity_engine import radar_lane as lane  # noqa: E402


class RadarLaneTests(unittest.TestCase):
    """The radar page's lane filter (D-162): word lists, no model."""

    def test_mechanism_explainers_are_on_lane(self):
        for title, channel in (
            ("How Does Bulletproof Glass Stop a Bullet? | Material Science", "Material engineer"),
            ("Why It's Nearly Impossible to Return From Pluto", "THE ROGER LOGIC"),
            ("Your Airbag Decides in 0.02 Seconds", "Clearly Learn Science"),
        ):
            with self.subTest(title=title):
                self.assertEqual(lane.classify(title, channel)["lane"], lane.ON_LANE)

    def test_finance_fitness_history_and_games_are_off_lane_even_with_science_words(self):
        for title, channel in (
            ("BORN BEFORE 1967 Urgent 2026 Social Security Warning", "Finance Mechanic USA"),
            ("Why Leg Day Protects Your Testosterone (Science Explained)", "Titan Coach"),
            ("Atlantis in Antarctica? | History for Sleep", "Midnight History"),
            ("Spike Trap Every Time - Animal Revolt Battle Simulator", "ARBS Crown"),
        ):
            with self.subTest(title=title):
                result = lane.classify(title, channel)
                self.assertEqual(result["lane"], lane.OFF_LANE)
                self.assertTrue(result["hits"])

    def test_terms_match_whole_words_and_stems(self):
        self.assertEqual(lane.classify("Investigations into tyre grip", "")["lane"], lane.OFF_LANE)  # invest*
        self.assertEqual(lane.classify("The keyboard mystery", "")["lane"], lane.UNCLEAR)  # not "key"
        self.assertEqual(lane.classify("A thing that works", "")["lane"], lane.ON_LANE)  # work*

    def test_non_latin_titles_are_other_language(self):
        self.assertEqual(lane.classify("वेळेत प्रवास केला तर भूतकाळ बदलता येईल का?", "Physics Notes")["lane"], lane.OTHER_LANGUAGE)
        # Mostly English with a few Devanagari words stays readable.
        self.assertEqual(lane.classify("Factory में Pencil कैसे बनती है? How Pencils Are Made", "")["lane"], lane.ON_LANE)

    def test_theme_lane_is_the_best_of_its_members(self):
        self.assertEqual(lane.theme_lane([lane.OFF_LANE, lane.ON_LANE]), lane.ON_LANE)
        self.assertEqual(lane.theme_lane([lane.OFF_LANE, lane.UNCLEAR]), lane.UNCLEAR)
        self.assertEqual(lane.theme_lane([lane.OTHER_LANGUAGE]), lane.OTHER_LANGUAGE)
        self.assertEqual(lane.theme_lane([lane.OFF_LANE]), lane.OFF_LANE)
        self.assertEqual(lane.theme_lane([]), lane.UNCLEAR)


if __name__ == "__main__":
    unittest.main()
