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
from experiment_01_discovery import opportunity_research as research

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
        for topic in [t for t, d in config["topic_definitions"].items() if d["niche"] == "everyday_science"]:
            cell = {"topic": topic, "niche": "everyday_science", "format_candidate": "short_candidate"}
            for task in e4.build_tasks_for_cell(cell, config):
                words = task["query"].split()
                self.assertEqual(len(words), len(set(words)), task["query"])  # no "physics physics"

    def test_a_niche_without_words_fails_loudly(self):
        config = json.loads(json.dumps(self.config))
        del config["niche_context_terms"]["everyday_science"]
        with self.assertRaisesRegex(ValueError, "everyday_science"):
            e3.check_niche_terms(config, {"automotive_racing", "everyday_science"})


class ReviewFindingTests(unittest.TestCase):
    """Stage 8 review of D-178 (87aa30b): each failed before its fix."""

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
        )["topic_relevance"]

    def test_off_niche_titles_no_longer_pass(self):
        for topic, title in (
            ("road_cars", "How I got abs in 30 days"),
            ("road_cars", "Why hybrid work is failing"),
            ("weather_storms", "How cloud computing works"),
            ("weather_storms", "Why the Thunder won the NBA Finals"),
            ("animal_abilities", "Why Spider-Man: No Way Home works"),
            ("musical_acoustics", "How the Speaker of the House is chosen"),
            ("aircraft_wings", "Inside a $70 million private jet"),
            ("earth_oceans", "Why Moon Knight failed"),
            ("road_cars", "Inside Ferrari's new hybrid engine"),
            ("road_cars", "Why are cars so expensive now"),
        ):
            with self.subTest(title=title):
                self.assertEqual(self.rate(topic, title), "OFF_TOPIC")

    def test_real_explainers_pass(self):
        for topic, title in (
            ("road_cars", "The chemical reaction inside your car battery"),
            ("weather_storms", "Why cloud cover keeps nights warm"),
            ("aircraft_wings", "Why Planes Don't Fly Over the Pacific"),
            ("earth_oceans", "Why is the sky blue?"),
            ("household_appliances", "How a fridge actually makes cold"),
            ("animal_abilities", "Why do cats always land on their feet"),
            ("musical_acoustics", "The physics of the steelpan's tuned notes"),
            ("tyre_grip", "Why airplane tires are filled with nitrogen"),
        ):
            with self.subTest(title=title):
                self.assertEqual(self.rate(topic, title), "ON_TOPIC")


class NewCohortFlowTests(unittest.TestCase):
    """Finding 1: a new cohort must go through 01.4 and 01.5 again."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "output"
        self.exp13 = self.root / "experiment_01_3"
        for name in ("experiment_01_3", "experiment_01_4", "experiment_01_5"):
            (self.root / name).mkdir(parents=True)
        (self.exp13 / "cohort_manifest.json").write_text("{}", encoding="utf-8")
        (self.root / "experiment_01_4" / "summary.json").write_text('{"execution_status": "COMPLETE"}', encoding="utf-8")
        (self.root / "experiment_01_5" / "study_set.json").write_text('[{"video_id": "old"}]', encoding="utf-8")
        (self.root / "experiment_01_5" / "approved_study_set.json").write_text('[{"video_id": "old"}]', encoding="utf-8")
        target = patch.object(e3, "OUTPUT_DIR", self.exp13)
        target.start()
        self.addCleanup(target.stop)

    def test_replacing_the_cohort_archives_its_01_4_and_01_5_output(self):
        destination = e3.archive_existing_output()
        archived = sorted(p.name.rsplit("_", 1)[0] for p in (self.root / "archive").iterdir())
        self.assertEqual(archived, ["experiment_01_3", "experiment_01_4", "experiment_01_5"])
        self.assertTrue(destination.name.startswith("experiment_01_3_"))
        for name in ("experiment_01_3", "experiment_01_4", "experiment_01_5"):
            self.assertFalse((self.root / name).exists(), name)
        old_gate = next((self.root / "archive").glob("experiment_01_5_*"))
        self.assertEqual(json.loads((old_gate / "approved_study_set.json").read_text()), [{"video_id": "old"}])

    def test_downstream_output_is_archived_even_without_a_01_3_folder(self):
        # Fourth review, item 2: a study set left behind would be handed off,
        # with its paid vidIQ supplement, as if the new cohort had built it.
        import shutil
        shutil.rmtree(self.exp13)
        self.assertIsNone(e3.prepare_output_for_discovery(replace_cohort=False))
        for name in ("experiment_01_4", "experiment_01_5"):
            self.assertFalse((self.root / name).exists(), name)
        archived = sorted(p.name.rsplit("_", 1)[0] for p in (self.root / "archive").iterdir())
        self.assertEqual(archived, ["experiment_01_4", "experiment_01_5"])
        self.assertIsNone(e3.archive_existing_output())  # nothing left: nothing to do

    def test_a_failed_put_back_says_where_each_folder_is(self):
        real_rename = e3.os.rename
        calls = []

        def flaky(source, target):
            calls.append(source)
            if len(calls) >= 2:
                raise PermissionError("file in use")
            return real_rename(source, target)

        with patch.object(e3.os, "rename", side_effect=flaky):
            with self.assertRaisesRegex(SystemExit, "could not put everything back: experiment_01_4 is now"):
                e3.archive_existing_output()

    def test_a_failed_move_leaves_everything_in_place(self):
        real_rename = e3.os.rename
        calls = []

        def flaky(source, target):
            calls.append(source)
            if len(calls) == 2:
                raise PermissionError("file in use")
            return real_rename(source, target)

        with patch.object(e3.os, "rename", side_effect=flaky):
            with self.assertRaisesRegex(SystemExit, "Nothing was moved"):
                e3.archive_existing_output()
        for name in ("experiment_01_3", "experiment_01_4", "experiment_01_5"):
            self.assertTrue((self.root / name).exists(), name)
        self.assertEqual(list((self.root / "archive").iterdir()), [])


class QuotaDayTests(unittest.TestCase):
    """Finding 5: 01.4's searches wait for the quota day after discovery."""

    def test_the_next_quota_day_starts_at_08_00_utc(self):
        summary = {"cohort_created_at": "2026-10-16T14:00:00+00:00"}  # 06:00 PST, 16 Oct
        wait = research.next_quota_day_wait(summary, datetime(2026, 10, 16, 16, tzinfo=timezone.utc))
        self.assertEqual(wait, datetime(2026, 10, 17, 8, tzinfo=timezone.utc))
        self.assertEqual(research.next_quota_day_wait(summary, datetime(2026, 10, 17, 7, 59, tzinfo=timezone.utc)), wait)
        self.assertIsNone(research.next_quota_day_wait(summary, datetime(2026, 10, 17, 8, tzinfo=timezone.utc)))
        # Discovered at 03:00 UTC is still the previous Pacific day.
        late = {"cohort_created_at": "2026-10-17T03:00:00Z"}
        self.assertIsNone(research.next_quota_day_wait(late, datetime(2026, 10, 17, 9, tzinfo=timezone.utc)))
        self.assertIsNone(research.next_quota_day_wait({}, datetime(2026, 10, 17, tzinfo=timezone.utc)))

    def test_summer_and_resumed_discoveries_never_allow_same_day_spending(self):
        # PDT: the real reset is 07:00Z. Finished 07:30Z on 15 Jul = 00:30 Pacific.
        summer = {"cohort_created_at": "2026-07-15T07:30:00Z"}
        self.assertEqual(research.next_quota_day_wait(summer, datetime(2026, 7, 15, 9, 30, tzinfo=timezone.utc)),
                         datetime(2026, 7, 16, 8, tzinfo=timezone.utc))
        # A discovery that resumed and finished a day later counts from its end.
        resumed = {"cohort_created_at": "2026-10-15T20:00:00Z", "discovery_completed_at": "2026-10-16T15:00:00Z"}
        self.assertEqual(research.next_quota_day_wait(resumed, datetime(2026, 10, 16, 18, tzinfo=timezone.utc)),
                         datetime(2026, 10, 17, 8, tzinfo=timezone.utc))

    def test_a_recorded_wait_holds_until_it_is_due(self):
        state = {"status": "WAITING_FOR_NEXT_QUOTA_DAY", "next_refresh_due_at": "2026-10-17T08:00:00+00:00"}
        self.assertEqual(research.held_until(state, datetime(2026, 10, 17, 7, tzinfo=timezone.utc)),
                         datetime(2026, 10, 17, 8, tzinfo=timezone.utc))
        self.assertIsNone(research.held_until(state, datetime(2026, 10, 17, 8, tzinfo=timezone.utc)))
        self.assertIsNone(research.held_until({"status": "FAILED_01_5"}, datetime(2026, 10, 17, tzinfo=timezone.utc)))

    def test_a_quota_pause_in_01_4_waits_instead_of_failing(self):
        now = datetime(2026, 10, 18, 16, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("experiment_01_3", "experiment_01_4"):
                (root / name).mkdir()
            (root / "experiment_01_3" / "summary.json").write_text(
                json.dumps({"mode": "refresh", "cohort_created_at": "2026-10-16T14:00:00+00:00"}), encoding="utf-8")
            (root / "experiment_01_4" / "search_checkpoint.json").write_text('{"status": "QUOTA_EXHAUSTED"}', encoding="utf-8")
            with patch.multiple(research, EXP13_DIR=root / "experiment_01_3", EXP14_DIR=root / "experiment_01_4",
                                EXP15_DIR=root / "experiment_01_5", OUTPUT_ROOT=root, STATE_FILE=root / "state.json"), \
                    patch.object(research, "velocity_ready", return_value=True), \
                    patch.object(research, "exp14_plan_ready", return_value=True), \
                    patch.object(research, "utc_now", return_value=now), \
                    patch.object(research, "run_command", return_value=0):
                state = research.advance_downstream(python_executable="python", refresh_attempts=1)
        self.assertEqual(state["status"], "WAITING_FOR_NEXT_QUOTA_DAY")
        self.assertEqual(state["next_refresh_due_at"], "2026-10-19T08:00:00+00:00")

    def test_only_a_quota_answer_pauses_01_4(self):
        plan = {"search_tasks": [{"task_id": "t1", "query": "q", "search_order": "viewCount", "video_duration_filter": "short",
                                  "sequence": 1, "topic": "x", "format_candidate": "short_candidate", "family": "f"}],
                "published_after": "2021-01-01T00:00:00Z", "created_at": "now"}
        with tempfile.TemporaryDirectory() as tmp, patch.object(e4, "OUTPUT_DIR", Path(tmp)), \
                patch.object(e4, "CHECKPOINT_FILE", Path(tmp) / "search_checkpoint.json"):
            for message, expected in (
                ("YouTube rejected the request (HTTP 403 reason=quotaExceeded).", "QUOTA_EXHAUSTED"),
                ("YouTube rejected the request (HTTP 400 reason=keyInvalid).", "API_ERROR"),
            ):
                (Path(tmp) / "search_checkpoint.json").unlink(missing_ok=True)
                with patch.object(e4, "api_get", side_effect=SystemExit(message)):
                    _, status, calls = e4.execute_plan(plan, "key", max_searches=10, region_code=None, language=None)
                self.assertEqual((status, calls), (expected, 0), message)

    def test_01_4_execute_defaults_to_the_whole_plan(self):
        import inspect
        source = inspect.getsource(e4.run_execute)
        self.assertIn('len(plan.get("search_tasks", []))', source)

    def test_01_4_execution_waits_and_says_why(self):
        commands = []
        now = datetime(2026, 10, 16, 16, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "experiment_01_3").mkdir()
            (root / "experiment_01_3" / "summary.json").write_text(
                json.dumps({"mode": "refresh", "cohort_created_at": "2026-10-16T14:00:00+00:00"}), encoding="utf-8")
            with patch.multiple(research, EXP13_DIR=root / "experiment_01_3", EXP14_DIR=root / "experiment_01_4",
                                EXP15_DIR=root / "experiment_01_5", OUTPUT_ROOT=root, STATE_FILE=root / "state.json"), \
                    patch.object(research, "velocity_ready", return_value=True), \
                    patch.object(research, "exp14_plan_ready", return_value=True), \
                    patch.object(research, "utc_now", return_value=now), \
                    patch.object(research, "run_command", side_effect=lambda c, l: commands.append(c) or 0):
                state = research.advance_downstream(python_executable="python", refresh_attempts=1)
        self.assertEqual(state["status"], "WAITING_FOR_NEXT_QUOTA_DAY")
        self.assertEqual(state["next_refresh_due_at"], "2026-10-17T08:00:00+00:00")
        self.assertEqual(commands, [])

    def test_the_01_4_budget_suits_two_niches_on_their_own_day(self):
        self.assertEqual(e4.load_config()["maximum_plan_searches"], 60)  # 6,000 units, a day of its own


class StudySetShareTests(unittest.TestCase):
    """Finding 6: one niche cannot take the whole study set."""

    def packet(self, n, niche, index):
        return {"gate_status": "PASS", "video_id": f"{niche}{n}", "channel_id": f"ch_{niche}_{n}", "niche": niche,
                "topic": f"{niche}_t{n % 4}", "format_candidate": "long_form_candidate",
                "primary_metric": {"value": index}, "views": 1000}

    def config(self, floor=2):
        return {"max_study_candidates": 8, "max_per_topic_format": 2, "max_per_channel": 1, "min_per_niche": floor}

    def test_each_niche_gets_its_floor(self):
        packets = [self.packet(n, "automotive_racing", 9 - n * 0.01) for n in range(24)]
        packets += [self.packet(n, "everyday_science", 1 - n * 0.01) for n in range(24)]
        chosen = e5.build_study_set(packets, self.config())
        niches = [p["niche"] for p in chosen]
        self.assertEqual((len(chosen), niches.count("everyday_science")), (8, 2))
        self.assertEqual([p["study_set_sequence"] for p in chosen], list(range(1, 9)))
        self.assertIn("at least 2 per niche where available", chosen[0]["selection_basis"])

    def test_one_niche_is_unchanged(self):
        packets = [self.packet(n, "automotive_racing", 9 - n * 0.01) for n in range(24)]
        with_floor = e5.build_study_set(packets, self.config(2))
        without = e5.build_study_set(packets, self.config(0))
        self.assertEqual(with_floor, without)


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

    def test_a_failed_move_puts_everything_back(self):
        for name in ("human_opportunity_decision.json", "approved_study_set.json", "study_set.json"):
            (self.out / name).write_text("{}", encoding="utf-8")
        real_rename = e5.os.rename
        calls = []

        def flaky(source, target):
            calls.append(source)
            if len(calls) == 2:
                raise PermissionError("sharing violation")
            return real_rename(source, target)

        with patch.object(e5.os, "rename", side_effect=flaky):
            with self.assertRaises(PermissionError):
                e5.archive_gate_files()
        for name in ("human_opportunity_decision.json", "approved_study_set.json", "study_set.json"):
            self.assertTrue((self.out / name).exists(), name)
        self.assertEqual(list((self.out / "archive").iterdir()), [])

    def test_nothing_is_archived_without_a_decision(self):
        (self.out / "study_set.json").write_text("[]", encoding="utf-8")
        self.assertIsNone(e5.archive_gate_files())
        self.assertTrue((self.out / "study_set.json").exists())
        self.assertFalse((self.out / "archive").exists())


if __name__ == "__main__":
    unittest.main()
