import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opportunity_engine import radar_learning as rl  # noqa: E402


def packet(video_id, title, channel="UCaaaaaaaaaaaaaaaaaaaaaa"):
    return {
        "opportunity_id": "opp_viral_radar__" + video_id,
        "title": title,
        "candidate_videos": [{"video_id": video_id, "title": title, "channel_id": channel}],
    }


PICKS = [
    "How brakes stop a 2-ton car", "Why plane tyres do not burst", "How a jet engine works",
    "Why bridges sway in wind", "How glass stops a bullet", "Why tyres are black",
    "How a fridge makes cold", "Why concrete cracks", "How airbags fire so fast",
    "Why magnets stick", "How a turbine spins", "How popcorn pops",
]
REJECTS = [
    "Social security changes for seniors", "Best chest workout for muscle", "Crypto crash explained",
    "History for sleep: Atlantis", "Tax brackets 2026", "Leg day for lifters",
    "Bitcoin to the moon", "Hypertrophy training tips", "Medicare enrollment guide",
    "Templar bloodline secrets",
]


def decided_inbox(picks=PICKS, rejects=REJECTS):
    items = {}
    packets = []
    for n, title in enumerate(picks):
        vid = f"p{n:010d}"
        packets.append(packet(vid, title))
        items["opp_viral_radar__" + vid] = {"status": "SAVED"}
    for n, title in enumerate(rejects):
        vid = f"r{n:010d}"
        packets.append(packet(vid, title, channel="UCbbbbbbbbbbbbbbbbbbbbbb"))
        items["opp_viral_radar__" + vid] = {"status": "REJECTED"}
    return items, packets


class RadarLearningTests(unittest.TestCase):
    def test_tokens_drop_stopwords_and_add_channel(self):
        self.assertEqual(
            rl.tokens("How a Jet Engine Works", "UCx"),
            ["engine", "how", "jet", "works", "channel:UCx"],
        )

    def test_label_reads_status_then_history(self):
        self.assertEqual(rl.label_for({"status": "WATCHING"}), 1)
        self.assertEqual(rl.label_for({"status": "REJECTED"}), -1)
        self.assertEqual(rl.label_for({"history": [{"action": "APPROVE"}]}), 1)
        self.assertEqual(rl.label_for({"status": "NEEDS_REVIEW"}), 0)
        self.assertEqual(rl.label_for({}), 0)

    def test_model_is_quiet_until_enough_decisions_on_both_sides(self):
        items, packets = decided_inbox(picks=PICKS[:3], rejects=REJECTS[:2])
        model = rl.TasteModel(rl.examples(items, packets))
        self.assertFalse(model.active)
        self.assertIsNone(model.score("How a jet engine works"))
        self.assertEqual(model.status()["decisions"], 5)
        one_sided, packets2 = decided_inbox(picks=PICKS, rejects=REJECTS[:3])
        self.assertFalse(rl.TasteModel(rl.examples(one_sided, packets2)).active)

    def test_model_ranks_like_the_operator(self):
        items, packets = decided_inbox()
        model = rl.TasteModel(rl.examples(items, packets))
        self.assertTrue(model.active)
        like = model.score("How a brake disc cools", "UCcccccccccccccccccccccc")
        unlike = model.score("Senior tax tips for 2026", "UCcccccccccccccccccccccc")
        self.assertIsNotNone(like)
        self.assertGreater(like, 0.25)
        self.assertLess(unlike, -0.25)
        self.assertEqual(rl.taste_label(like), rl.LIKELY)
        self.assertEqual(rl.taste_label(unlike), rl.UNLIKELY)
        self.assertEqual(rl.taste_label(0.0), rl.UNSURE)
        self.assertEqual(model.score("Zzz qqq", "UCcccccccccccccccccccccc"), 0.0)
        strongest = model.status()["strongest"]
        self.assertIn("how", strongest["for"])
        self.assertTrue(set(strongest["against"]) & {"tax", "workout", "crypto", "seniors"})
        self.assertFalse(any(t.startswith("channel:") for t in strongest["for"] + strongest["against"]))

    def test_channel_counts_as_evidence(self):
        items, packets = decided_inbox()
        model = rl.TasteModel(rl.examples(items, packets))
        rejected_channel = model.score("Unknown words only", "UCbbbbbbbbbbbbbbbbbbbbbb")
        self.assertLess(rejected_channel, 0)

    def test_examples_skip_undecided_and_unknown_packets(self):
        items = {"opp_viral_radar__a": {"status": "NEEDS_REVIEW"}}
        packets = [packet("a", "Something"), packet("b", "Else")]
        self.assertEqual(rl.examples(items, packets), [])


if __name__ == "__main__":
    unittest.main()
