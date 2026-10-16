"""D-178: two niches in one historical-lane cohort.

The motorsport niche's results must not change at all; the Science Inside
niche gets its own title rules; 01.5 archives, never deletes, an earlier gate
decision.
"""

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from experiment_01_discovery import experiment_01_3 as e3
from experiment_01_discovery import experiment_01_4 as e4
from experiment_01_discovery import experiment_01_5 as e5

# The 18 words and 8 exclusions the F1 lane has always used (c0adb20).
F1_CONTEXT = [
    "f1", "formula 1", "formula one", "motorsport", "race car", "racecar", "racing", "grand prix",
    "pit stop", "mclaren", "ferrari", "red bull", "mercedes", "aston martin", "alpine", "williams",
    "sauber", "haas",
]
SHARED_EXCLUDE = [
    "sim racing", "simracing", "gameplay", "assetto corsa", "gran turismo", "forza", "f1 26 game", "ea sports",
]
GOLDEN_TITLES = [
    "Why F1 brakes glow red hot", "How an F1 gearbox works", "F1 tyre degradation explained",
    "Formula 1 steering wheel secrets", "The genius of F1 suspension", "Red Bull's DRS trick explained",
    "Mercedes power unit: hybrid engine inside", "Fastest pit stop in F1 history", "How car brakes work",
    "Tyres explained: why they grip", "F1 26 game gameplay: brake settings", "Sim racing brake pedal review",
    "Ferrari engine sound", "Racing gearbox rebuild", "Grand Prix aero upgrades and downforce",
    "pitstop practice McLaren", "F1 turbo lag explained", "Haas chassis problems", "How hummingbirds fly",
    "Formula One tire blowout", "F1: Why the floor matters", "Aston Martin brakes failure",
    "Williams gear ratio choices", "Alpine F1 transmission issue #shorts", "Sauber steering column",
]
# sha256 of the 400 F1 topic/title results computed with the code on main
# (a10af38) before D-178. Any change to an F1 result changes this hash.
GOLDEN_SHA256 = "5f8f82f15b4ca80b17336d422a42e6a012ec1944e40b309ea621940307a01587"


def f1_results() -> dict:
    c3, c4 = e3.load_config(), e4.load_config()
    out = {}
    for topic in c3["topics"]:
        if topic["niche"] != "automotive_racing":
            continue
        for title in GOLDEN_TITLES:
            out[f"01.3|{topic['topic']}|{title}"] = e3.classify_topic_relevance(
                title, topic["match_terms"],
                e3.niche_context_terms(c3, topic["niche"]), e3.niche_exclude_terms(c3, topic["niche"]),
                niche=topic["niche"],
            )
    for name, definition in c4["topic_definitions"].items():
        if definition["niche"] != "automotive_racing":
            continue
        for title in GOLDEN_TITLES:
            out[f"01.4|{name}|{title}"] = e3.classify_topic_relevance(
                title, definition["match_terms"],
                e3.niche_context_terms(c4, definition["niche"]), e3.niche_exclude_terms(c4, definition["niche"]),
                niche=definition["niche"],
            )
    return out


class MotorsportUnchangedTests(unittest.TestCase):
    def test_the_400_f1_results_are_byte_identical(self):
        results = f1_results()
        self.assertEqual(len(results), 400)
        digest = hashlib.sha256(json.dumps(results, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(digest, GOLDEN_SHA256, "an F1 relevance result changed (D-178 forbids it)")

    def test_the_f1_words_and_exclusions_are_unchanged(self):
        for config in (e3.load_config(), e4.load_config()):
            self.assertEqual(e3.niche_context_terms(config, "automotive_racing"), F1_CONTEXT)
            self.assertEqual(e3.niche_exclude_terms(config, "automotive_racing"), SHARED_EXCLUDE)
        self.assertEqual(len([t for t in e3.load_config()["topics"] if t["niche"] == "automotive_racing"]), 8)

    def test_an_older_config_with_only_motorsport_terms_still_works(self):
        legacy = {"motorsport_context_terms": ["f1"]}
        self.assertEqual(e3.niche_context_terms(legacy, "automotive_racing"), ["f1"])
        with self.assertRaisesRegex(ValueError, "everyday_science"):
            e3.niche_context_terms(legacy, "everyday_science")

    def test_f1_keeps_its_query_families(self):
        config = e4.load_config()
        self.assertEqual(e4.query_families(config, "automotive_racing"), config["query_families"])


class ScienceInsideTests(unittest.TestCase):
    def setUp(self):
        self.config = e3.load_config()
        self.topics = {t["topic"]: t for t in self.config["topics"]}

    def rate(self, topic, title):
        definition = self.topics[topic]
        niche = definition["niche"]
        return e3.classify_topic_relevance(
            title, definition["match_terms"],
            e3.niche_context_terms(self.config, niche), e3.niche_exclude_terms(self.config, niche),
            niche=niche,
        )

    def test_eight_topics_with_unique_ids_and_specific_words(self):
        science = [t for t in self.config["topics"] if t["niche"] == "everyday_science"]
        self.assertEqual(len(science), 8)
        # The radar's historical alignment matches any 4+ letter word of a
        # topic id, so ids avoid words like "physics" or "science".
        for topic in science:
            self.assertNotRegex(topic["topic"], r"physics|science|explained|everyday")

    def test_a_science_title_is_on_topic_with_neutral_names(self):
        result = self.rate("animal_abilities", "How hummingbirds fly")
        self.assertEqual(result["topic_relevance"], "ON_TOPIC")
        self.assertEqual(result["topic_relevance_reason"], "title_topic_and_niche_context")
        self.assertEqual(result["niche_context_matches"], ["how"])
        self.assertNotIn("motorsport_context_matches", result)

    def test_motorsport_how_to_reviews_and_music_videos_are_kept_out(self):
        for topic, title in (
            ("tyre_grip", "F1 tyre degradation explained"),
            ("road_cars", "Mercedes power unit: hybrid engine inside"),
            ("tyre_grip", "How to change a tire"),
            ("household_appliances", "Best fridge review 2026: why I chose it"),
            ("musical_acoustics", "Why this guitar cover sounds amazing"),
        ):
            with self.subTest(title=title):
                self.assertEqual(self.rate(topic, title)["topic_relevance_reason"], "excluded_title_term")

    def test_a_title_without_explainer_words_misses_the_niche(self):
        result = self.rate("tyre_grip", "These tyres are enormous")
        self.assertEqual(result["topic_relevance_reason"], "missing_niche_context_in_title")

    def test_each_topic_in_a_cohort_is_checked_against_its_own_niche(self):
        now = datetime.now(timezone.utc)
        published = (now - timedelta(days=120)).isoformat().replace("+00:00", "Z")

        def detail(title):
            return {
                "snippet": {"title": title, "publishedAt": published, "channelId": "UC" + "a" * 22, "channelTitle": "Lab"},
                "statistics": {"viewCount": "900000"},
                "contentDetails": {"duration": "PT10M"},
            }

        match = lambda topic: [{"target_topic": topic, "search_format_target": "long_form_candidate", "search_phase": "strict"}]  # noqa: E731
        discovered = {"vid_f1": {"brakes"}, "vid_sci": {"road_cars"}}
        rows, rejected = e3.build_rows(
            discovered,
            {"vid_f1": match("brakes"), "vid_sci": match("road_cars")},
            {"vid_f1": detail("Why F1 brakes glow"), "vid_sci": detail("How car brakes work")},
            {},
            self.config,
            e3.calculate_age_window(now, 120, 15),
            "unused",
            include_baselines=False,
        )
        self.assertEqual(rejected, [])
        by_id = {row["video_id"]: row for row in rows}
        self.assertEqual(by_id["vid_f1"]["validated_niches"], ["automotive_racing"])
        self.assertEqual(by_id["vid_f1"]["topic_validation"]["brakes"]["motorsport_context_matches"], ["f1"])
        self.assertEqual(by_id["vid_sci"]["validated_niches"], ["everyday_science"])
        self.assertEqual(by_id["vid_sci"]["topic_validation"]["road_cars"]["niche_context_matches"], ["how"])

    def test_01_3_and_01_4_share_the_same_niche_rules(self):
        c3, c4 = e3.load_config(), e4.load_config()
        self.assertEqual(c3["niche_context_terms"], c4["niche_context_terms"])
        self.assertEqual(c3["niche_exclude_title_terms"], c4["niche_exclude_title_terms"])
        science = {t["topic"]: t for t in c3["topics"] if t["niche"] == "everyday_science"}
        for name, topic in science.items():
            self.assertEqual(c4["topic_definitions"][name]["match_terms"], topic["match_terms"], name)
            self.assertEqual(c4["topic_definitions"][name]["niche"], "everyday_science")

    def test_science_cells_plan_with_their_own_query_families(self):
        config = e4.load_config()
        cell = {"topic": "aircraft_wings", "niche": "everyday_science", "format_candidate": "short_candidate"}
        queries = [task["query"] for task in e4.build_tasks_for_cell(cell, config)]
        self.assertIn("how airplane wing works", queries)
        self.assertIn("airplane wing science explained", queries)
        self.assertFalse(any("rules banned" in q for q in queries))

    def test_a_niche_without_words_fails_loudly(self):
        config = json.loads(json.dumps(self.config))
        del config["niche_context_terms"]["everyday_science"]
        with self.assertRaisesRegex(ValueError, "everyday_science"):
            e3.check_niche_terms(config, {"automotive_racing", "everyday_science"})


class GateArchiveTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "experiment_01_5"
        out.mkdir()
        self.out = out
        for name, value in (
            ("HUMAN_DECISION_FILE", out / "human_opportunity_decision.json"),
            ("APPROVED_STUDY_SET_FILE", out / "approved_study_set.json"),
            ("STUDY_SET_FILE", out / "study_set.json"),
            ("PACKETS_FILE", out / "handoff_packets.json"),
            ("GATE_ARCHIVE_DIR", out / "archive"),
        ):
            target = patch.object(e5, name, value)
            target.start()
            self.addCleanup(target.stop)

    def test_a_rebuild_archives_the_decision_and_its_evidence(self):
        files = {
            "human_opportunity_decision.json": '{"opportunities": {"a": {"decision": "APPROVE"}}}',
            "approved_study_set.json": '[{"video_id": "x"}]',
            "study_set.json": '[{"video_id": "x"}]',
            "handoff_packets.json": "[]",
        }
        for name, text in files.items():
            (self.out / name).write_text(text, encoding="utf-8")
        destination = e5.archive_gate_files(now=datetime(2026, 10, 16, 12, tzinfo=timezone.utc))
        self.assertEqual(destination, self.out / "archive" / "gate_20261016T120000Z")
        for name, text in files.items():
            self.assertFalse((self.out / name).exists(), name)
            self.assertEqual((destination / name).read_text(encoding="utf-8"), text)
        # A second rebuild in the same second never overwrites the first.
        (self.out / "approved_study_set.json").write_text("[]", encoding="utf-8")
        again = e5.archive_gate_files(now=datetime(2026, 10, 16, 12, tzinfo=timezone.utc))
        self.assertEqual(again.name, "gate_20261016T120000Z_1")

    def test_nothing_is_archived_without_a_decision(self):
        (self.out / "study_set.json").write_text("[]", encoding="utf-8")
        self.assertIsNone(e5.archive_gate_files())
        self.assertTrue((self.out / "study_set.json").exists())
        self.assertFalse((self.out / "archive").exists())


if __name__ == "__main__":
    unittest.main()
