from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fresh_start  # noqa: E402


class FreshStartTests(unittest.TestCase):
    def test_moves_choice_and_production_outputs_and_keeps_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            moved = [
                "experiment_01_discovery/output/experiment_01_5/human_opportunity_decision.json",
                "opportunity_engine/output/active_study_source.json",
                "research_engine/output/plans/c1.research_plan.json",
                "production_engine/output/video_budget_ledger.jsonl",
            ]
            kept = [
                "experiment_01_discovery/output/experiment_01_5/study_set.json",
                "opportunity_engine/output/inbox_state.json",
                ".idea_bank/saved_ideas.json",
                "transformation_engine/concept_model_route.json",
                ".experiment_ui/jobs/x.log",
            ]
            for rel in moved + kept:
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text("{}", encoding="utf-8")

            destination = fresh_start.archive(root, stamp="t1")

            for rel in moved:
                self.assertFalse((root / rel).exists(), rel)
                self.assertTrue((destination / rel).exists(), rel)
            for rel in kept:
                self.assertTrue((root / rel).exists(), rel)
            self.assertEqual(fresh_start.present(root), [])

    def test_refuses_to_overwrite_an_existing_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".archive" / "fresh_start_t1").mkdir(parents=True)
            with self.assertRaises(SystemExit):
                fresh_start.archive(root, stamp="t1")


if __name__ == "__main__":
    unittest.main()
