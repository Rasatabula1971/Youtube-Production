"""One budget per video (D-136)."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import video_budget as budget


class VideoBudgetTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        config = root / "config.json"
        config.write_text(json.dumps({"target_usd": 5.0, "ceiling_usd": 10.0, "confirmed_by_human": False}))
        for item in (
            patch.object(budget, "CONFIG_FILE", config),
            patch.object(budget, "LEDGER_FILE", root / "ledger.jsonl"),
        ):
            item.start()
            self.addCleanup(item.stop)

    def test_reservations_count_before_spend_and_overruns_after(self):
        budget.reserve(video="c1:short", category="narration", ref="narration", amount_usd=4)
        summary = budget.record_actual(video="c1:short", category="narration", ref="narration", total_usd=3)
        self.assertEqual((summary["committed_usd"], summary["actual_usd"]), (4.0, 3.0))
        summary = budget.record_actual(video="c1:short", category="narration", ref="narration", total_usd=4.5)
        self.assertEqual(summary["committed_usd"], 4.5)
        self.assertFalse(summary["over_target"])
        summary = budget.reserve(video="c1:short", category="visual", ref="shot:s1", amount_usd=2)
        self.assertTrue(summary["over_target"])
        self.assertEqual(summary["by_category"]["visual"]["committed_usd"], 2.0)

    def test_the_ceiling_refuses_new_authorizations_across_categories(self):
        budget.reserve(video="c1:short", category="narration", ref="narration", amount_usd=6)
        budget.reserve(video="c1:short", category="visual", ref="shot:s1", amount_usd=3)
        with self.assertRaisesRegex(ValueError, "above the per-video ceiling"):
            budget.reserve(video="c1:short", category="visual", ref="shot:s2", amount_usd=1.5)
        # Raising an item's own reservation counts only the difference.
        budget.reserve(video="c1:short", category="visual", ref="shot:s1", amount_usd=4)
        # Another video has its own budget.
        budget.reserve(video="c2:short", category="visual", ref="shot:s1", amount_usd=9)

    def test_release_frees_the_reservation_but_not_actual_spend(self):
        budget.reserve(video="v:f", category="visual", ref="shot:s1", amount_usd=5)
        self.assertEqual(budget.release(video="v:f", category="visual", ref="shot:s1")["committed_usd"], 0)
        budget.record_actual(video="v:f", category="sound", ref="sound:m", total_usd=1.25)
        summary = budget.release(video="v:f", category="sound", ref="sound:m")
        self.assertEqual(summary["committed_usd"], 1.25)

    def test_actual_spend_is_recorded_even_past_the_ceiling(self):
        summary = budget.record_actual(video="v:f", category="sound", ref="sound:m", total_usd=12)
        self.assertTrue(summary["over_ceiling"])
        with self.assertRaisesRegex(ValueError, "ceiling"):
            budget.reserve(video="v:f", category="visual", ref="shot:s1", amount_usd=0.5)

    def test_concurrent_reservations_cannot_both_pass_the_ceiling(self):
        errors = []

        def attempt(ref):
            try:
                budget.reserve(video="v:f", category="visual", ref=ref, amount_usd=6)
            except ValueError as exc:
                errors.append(exc)

        threads = [threading.Thread(target=attempt, args=(f"shot:{i}",)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(errors), 3)
        self.assertEqual(budget.summary("v:f")["committed_usd"], 6.0)

    def test_ledger_follows_a_stage_output_folder_and_snapshot_lists_videos(self):
        with tempfile.TemporaryDirectory() as other:
            ledger = budget.ledger_in(Path(other))
            budget.reserve(video="x:y", category="visual", ref="shot:a", amount_usd=1, ledger=ledger)
            self.assertTrue(ledger.exists())
        budget.reserve(video="a:b", category="visual", ref="shot:a", amount_usd=1)
        snap = budget.snapshot()
        self.assertEqual([v["video_id"] for v in snap["videos"]], ["a:b"])
        self.assertFalse(snap["confirmed_by_human"])
        with self.assertRaisesRegex(ValueError, "category"):
            budget.reserve(video="a:b", category="snacks", ref="x", amount_usd=1)

    def test_nan_and_infinity_never_reach_the_ledger(self):
        for bad in (float("nan"), float("inf"), -1, "abc", True):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "US dollars"):
                    budget.reserve(video="v:f", category="visual", ref="x", amount_usd=bad)
                with self.assertRaisesRegex(ValueError, "US dollars"):
                    budget.record_actual(video="v:f", category="visual", ref="x", total_usd=bad)
        self.assertEqual(budget.summary("v:f")["committed_usd"], 0)

    def test_a_corrupt_ledger_amount_blocks_rather_than_loosens(self):
        budget.LEDGER_FILE.write_text(
            json.dumps({"video_id": "v:f", "category": "visual", "ref": "x", "event": "RESERVE", "amount_usd": "NaN"}) + "\n"
        )
        with self.assertRaisesRegex(ValueError, "ceiling"):
            budget.reserve(video="v:f", category="visual", ref="y", amount_usd=1)

    def test_a_torn_ledger_line_blocks_rather_than_loosens(self):
        budget.LEDGER_FILE.write_text('{"event":"RESERVE","video_id":"v:f","category":"visual","ref":"x","amount_usd":9.0' + "\n")
        with self.assertRaisesRegex(ValueError, "ceiling"):
            budget.reserve(video="v:f", category="visual", ref="y", amount_usd=0.5)
        self.assertTrue(budget.summary("v:f")["over_ceiling"])


if __name__ == "__main__":
    unittest.main()
