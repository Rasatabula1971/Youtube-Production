"""Pool sizing, near-duplicate detection and diverse finalists (D-130)."""

from __future__ import annotations

import unittest

from concept_diversity import (
    DEFAULT_NEAR_DUPLICATE_THRESHOLD,
    allocate_concept_counts,
    concept_similarity,
    near_duplicate_groups,
    pool_assessment,
    select_diverse,
)
from concept_triage import apply_diverse_shortlist


def concept(concept_id, mechanism, archetype, title, premise, problem, promise, question, hook, payoff):
    return {
        "concept_id": concept_id,
        "mechanism_id": mechanism,
        "working_title": title,
        "premise": premise,
        "viewer_problem": problem,
        "audience_promise": promise,
        "human_framing": {
            "viewer_question": question,
            "hook_experience": {"archetype": archetype, "description": hook},
            "explanation_payoff": payoff,
        },
    }


LANDING = concept(
    "landing", "m1", "FAILURE_CONSEQUENCE",
    "Why plane tyres don't burst on landing",
    "Explains how aircraft tyres survive the shock and heat of touchdown",
    "Viewers wonder why tyres don't explode when a jet lands",
    "Understand the engineering that keeps landing tyres intact",
    "How do aircraft tyres survive landing?",
    "A jet slams onto the runway with smoke pouring off its tyres",
    "Nitrogen inflation, reinforced plies and spin-up make landing survivable",
)
LANDING_RESTATED = concept(
    "landing-2", "m1", "FAILURE_CONSEQUENCE",
    "How aircraft tyres survive a hard landing",
    "How plane tyres withstand the heat and shock of touchdown without bursting",
    "People wonder how landing tyres don't explode",
    "See the engineering that keeps aircraft tyres from bursting",
    "Why don't plane tyres pop when the jet touches down?",
    "Smoke pours from the tyres as an airliner hits the runway",
    "Reinforced plies, nitrogen and spin-up let tyres survive landing",
)
NITROGEN = concept(
    "nitrogen", "m1", "HIDDEN_CAUSE",
    "Why aircraft tyres are filled with nitrogen",
    "Explains why airlines inflate tyres with nitrogen instead of air",
    "Passengers wonder what's special about plane tyre gas",
    "Learn why nitrogen keeps tyres safe at altitude",
    "Why not just use air in plane tyres?",
    "A technician fills a jet tyre from a green nitrogen bottle",
    "Nitrogen resists fire, moisture and pressure swings",
)
AQUAPLANE = concept(
    "aquaplane", "m2", "EXPECTATION_VIOLATION",
    "Why wet tyres stop working above a certain speed",
    "How aquaplaning happens when tread can't clear water fast enough",
    "Drivers don't know when wet tyres lose grip",
    "Know the speed where grip disappears in rain",
    "At what speed do wet tyres stop gripping?",
    "A car hits standing water and suddenly floats",
    "Tread channels clear limited water per second; beyond it the tyre rides on water",
)
SPARKS = concept(
    "sparks", "m3", "MYSTERY",
    "Why F1 cars spark at night",
    "Explains the titanium skid blocks that make Formula 1 cars throw sparks",
    "Fans wonder why F1 cars spark",
    "Learn what the sparks reveal about ride height",
    "Why do F1 cars throw sparks?",
    "An F1 car bottoms out at 300 km/h and a shower of sparks erupts",
    "Titanium skid plates protect the floor and reveal how low the car rides",
)
ALL = {item["concept_id"]: item for item in (LANDING, LANDING_RESTATED, NITROGEN, AQUAPLANE, SPARKS)}


TOPICS = {
    "alpha": ("Why glaciers glow blue", "Ice crystals absorb red light deep inside old glaciers",
              "Hikers ask why glacier caves look neon blue", "Learn how ice filters sunlight",
              "Why is glacier ice blue?", "A cave of ice glows electric blue", "Dense ice absorbs red wavelengths"),
    "bravo": ("How bees pick a new home", "Scout bees debate nest sites with waggle dances",
              "Beekeepers wonder how swarms decide", "See a democracy of insects",
              "How does a swarm choose?", "A swarm hangs from a branch for hours", "Quorum sensing settles the vote"),
    "charlie": ("Why bread rises overnight", "Yeast fermentation fills dough with carbon dioxide",
                "Bakers wonder why cold proving works", "Understand slow fermentation",
                "What happens while dough rests?", "A flat dough doubles by morning", "Gas trapped in gluten lifts the loaf"),
    "delta": ("How owls fly silently", "Serrated feathers break up turbulent air",
              "Birders wonder why owls make no sound", "Discover stealth flight",
              "Why can't mice hear owls coming?", "An owl swoops past a microphone without a trace", "Comb-like feather edges muffle noise"),
}


def topic(concept_id, mechanism, archetype, word):
    return concept(concept_id, mechanism, archetype, *TOPICS[word])


class SimilarityTests(unittest.TestCase):
    def test_a_restated_idea_is_a_near_duplicate_and_different_ideas_are_not(self):
        self.assertGreaterEqual(concept_similarity(LANDING, LANDING_RESTATED), DEFAULT_NEAR_DUPLICATE_THRESHOLD)
        # Same domain and mechanism, different idea: stays distinct.
        self.assertLess(concept_similarity(LANDING, NITROGEN), DEFAULT_NEAR_DUPLICATE_THRESHOLD)
        self.assertLess(concept_similarity(LANDING, AQUAPLANE), 0.15)
        self.assertLess(concept_similarity(LANDING, SPARKS), 0.15)
        self.assertEqual(near_duplicate_groups(ALL.values()), [["landing", "landing-2"]])

    def test_empty_concepts_are_not_similar(self):
        self.assertEqual(concept_similarity({}, {}), 0.0)


class SelectionTests(unittest.TestCase):
    def test_near_duplicates_never_take_a_slot_even_when_slots_remain(self):
        ranked = ["landing", "landing-2", "nitrogen", "aquaplane", "sparks"]
        choice = select_diverse(ranked, ALL, limit=5)
        self.assertNotIn("landing-2", choice["selected"])
        self.assertEqual(choice["excluded"]["landing-2"]["reason"], "NEAR_DUPLICATE")
        self.assertEqual(choice["excluded"]["landing-2"]["duplicate_of"], "landing")
        self.assertEqual(len(choice["selected"]), 4)

    def test_one_approach_cannot_fill_the_list_while_others_exist(self):
        same = {
            f"m1-{index}": topic(f"m1-{index}", "m1", "SCALE", word)
            for index, word in enumerate(["alpha", "bravo", "charlie", "delta"])
        }
        pool = {**same, "aquaplane": AQUAPLANE, "sparks": SPARKS}
        ranked = list(same) + ["aquaplane", "sparks"]  # m1 concepts all score higher
        choice = select_diverse(ranked, pool, limit=4, max_per_mechanism=2, max_per_archetype=2)
        self.assertEqual(choice["selected"], ["m1-0", "m1-1", "aquaplane", "sparks"])
        self.assertEqual(choice["excluded"]["m1-2"]["reason"], "APPROACH_ALREADY_REPRESENTED")

    def test_caps_relax_when_no_other_approach_is_left(self):
        pool = {
            f"m1-{word}": topic(f"m1-{word}", "m1", "MYSTERY", word)
            for word in ["alpha", "bravo", "charlie"]
        }
        choice = select_diverse(list(pool), pool, limit=3, max_per_mechanism=2, max_per_archetype=2)
        self.assertEqual(len(choice["selected"]), 3)


class ShortlistTests(unittest.TestCase):
    def test_shortfall_is_stated_not_filled(self):
        def scored(concept_id, score):
            return {"concept_id": concept_id, "overall_score": score, "dimension_scores": {},
                    "decision": "SHORTLIST" if score >= 70 else "REWORK"}

        final = {
            "decisions": [
                scored("landing", 90), scored("landing-2", 88), scored("nitrogen", 80),
                scored("aquaplane", 60), scored("sparks", 40),
            ],
            "shortlist_ids": ["landing", "landing-2", "nitrogen"],
            "summary": "",
        }
        result = apply_diverse_shortlist(final, ALL, target=5)
        self.assertEqual(result["shortlist_ids"], ["landing", "nitrogen"])
        self.assertEqual(result["selection"]["shortfall"], 3)
        self.assertIn("left empty", result["selection"]["note"])
        restated = next(item for item in result["decisions"] if item["concept_id"] == "landing-2")
        self.assertEqual(restated["decision"], "REWORK")
        self.assertEqual(restated["diversity"]["reason"], "NEAR_DUPLICATE")
        # Ineligible concepts (score < 70) never fill an empty slot.
        self.assertNotIn("aquaplane", result["shortlist_ids"])


class PoolSizingTests(unittest.TestCase):
    def allocate(self, count):
        return allocate_concept_counts(
            [f"m{index}" for index in range(count)],
            pool_minimum=15, pool_maximum=25, per_request_minimum=2, per_request_maximum=8,
        )

    def test_requests_add_up_to_the_15_to_25_pool(self):
        self.assertEqual(sum(self.allocate(2).values()), 15)
        self.assertEqual(sorted(self.allocate(2).values()), [7, 8])
        self.assertEqual(set(self.allocate(3).values()), {5})
        self.assertEqual(sum(self.allocate(5).values()), 25)
        self.assertEqual(sum(self.allocate(6).values()), 25)
        self.assertEqual(sum(self.allocate(10).values()), 25)

    def test_one_request_is_never_oversized(self):
        # One mechanism cannot reach 15 within the per-request cap; the merge
        # reports the shortfall instead.
        self.assertEqual(self.allocate(1), {"m0": 8})
        self.assertEqual(self.allocate(0), {})

    def test_pool_assessment(self):
        self.assertFalse(pool_assessment(8, pool_minimum=15, pool_maximum=25)["within_target"])
        self.assertTrue(pool_assessment(20, pool_minimum=15, pool_maximum=25)["within_target"])


if __name__ == "__main__":
    unittest.main()
