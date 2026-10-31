"""Dropping a concept also clears it from Story / Script (D-182)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from experiment_ui import server


class DropConceptTests(unittest.TestCase):
    def test_drop_clears_story_and_script_requests_in_order(self):
        calls: list[str] = []
        with (
            patch.object(
                server,
                "drop_research_concept",
                side_effect=lambda **kwargs: calls.append(f"drop:{kwargs['concept_id']}") or {"status": "COMPLETE"},
            ),
            patch.object(
                server, "run_story_plan_prepare", side_effect=lambda: calls.append("story") or {}
            ),
            patch.object(
                server,
                "prune_leftover_script_requests",
                side_effect=lambda: calls.append("script") or ["c1.short.script_request.json"],
            ),
        ):
            payload = server.drop_concept_everywhere(concept_id="c1", note="Too thin.")
        # The verified research goes first, so the story stage drops its request,
        # which in turn makes the concept's script request a leftover.
        self.assertEqual(calls, ["drop:c1", "story", "script"])
        self.assertEqual(payload["dropped_concept_id"], "c1")
        self.assertEqual(payload["leftover_script_requests_removed"], ["c1.short.script_request.json"])


if __name__ == "__main__":
    unittest.main()
