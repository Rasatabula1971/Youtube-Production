"""Leftover story/script work stops being drafted and reviewed (D-182)."""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from core.hashing import sha256_file
from story_script_engine import leftovers, script_model_runner, script_review


class LeftoverTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.story_requests = root / "story_plan_requests"
        self.story_plans = root / "story_plans"
        self.script_requests = root / "script_requests"
        self.drafts = root / "script_drafts"
        self.review_requests = root / "script_review_requests"
        for path in (self.story_requests, self.story_plans, self.script_requests, self.drafts):
            path.mkdir()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(leftovers, "STORY_PLANS_DIR", self.story_plans))
        stack.enter_context(patch.object(leftovers, "STORY_PLAN_REQUESTS_DIR", self.story_requests))
        stack.enter_context(patch.object(leftovers, "REQUESTS_DIR", self.script_requests))
        # "cur" is in the batch; "old" is a previous study set's concept whose
        # story plan request the story stage already removed.
        self.concept("cur", keep_story_request=True)
        self.concept("old", keep_story_request=False)

    def concept(self, concept_id: str, *, keep_story_request: bool) -> None:
        story_request = self.story_requests / f"{concept_id}.story_plan_request.json"
        story_request.write_text(json.dumps({"concept_id": concept_id}), encoding="utf-8")
        (self.story_plans / f"{concept_id}.story_plan.json").write_text(
            json.dumps(
                {
                    "concept_id": concept_id,
                    "plan_provenance": {
                        # Written on Windows: only the file name is used.
                        "request_source": "C:\\Youtube Production\\story_script_engine\\output"
                        f"\\story_plan_requests\\{concept_id}.story_plan_request.json",
                        "request_sha256": sha256_file(story_request),
                    },
                }
            ),
            encoding="utf-8",
        )
        if not keep_story_request:
            story_request.unlink()
        script_request = self.script_requests / f"{concept_id}.short.script_request.json"
        script_request.write_text(
            json.dumps({"concept_id": concept_id, "format": "short"}), encoding="utf-8"
        )
        (self.drafts / f"{concept_id}.short.script_draft.json").write_text(
            json.dumps(
                {
                    "concept_id": concept_id,
                    "format": "short",
                    "draft_provenance": {
                        "request_source": str(script_request),
                        "request_sha256": sha256_file(script_request),
                    },
                }
            ),
            encoding="utf-8",
        )

    def test_a_changed_or_missing_request_is_not_current(self):
        path = self.story_requests / "cur.story_plan_request.json"
        provenance = {"request_source": str(path), "request_sha256": sha256_file(path)}
        self.assertTrue(leftovers.made_from_current_request(provenance, self.story_requests))
        self.assertFalse(
            leftovers.made_from_current_request(
                {**provenance, "request_sha256": "0" * 64}, self.story_requests
            )
        )
        self.assertFalse(leftovers.made_from_current_request({}, self.story_requests))

    def test_only_the_leftover_script_request_is_removed(self):
        removed = leftovers.prune_leftover_script_requests()
        self.assertEqual(removed, ["old.short.script_request.json"])
        self.assertTrue((self.script_requests / "cur.short.script_request.json").exists())
        self.assertEqual(
            [path.name for path in leftovers.current_script_drafts(self.drafts)],
            ["cur.short.script_draft.json"],
        )

    def test_the_script_gate_shows_only_current_drafts(self):
        """The old study set's scripts used to appear at the Script Gate."""
        with (
            patch.object(script_review, "DRAFTS_DIR", self.drafts),
            patch.object(script_review, "REQUESTS_DIR", self.script_requests),
            patch.object(script_review, "REVIEW_REQUESTS_DIR", self.review_requests),
            patch.object(script_review, "build_review_request", side_effect=lambda draft, path: dict(draft)),
        ):
            result = script_review.prepare()
        self.assertEqual([item["concept_id"] for item in result["requests"]], ["cur"])

    def test_the_drafting_run_skips_a_leftover_concept(self):
        """The bicycle script from the F1 set was drafted again and used Groq's per-minute quota."""
        drafted: list[str] = []

        def run_one(path, force, config):
            drafted.append(path.name)
            return {"status": "SKIPPED_ALREADY_VALIDATED"}

        with (
            patch.object(script_model_runner, "run_one", side_effect=run_one),
            patch.object(script_model_runner, "BATCH_SUMMARY_FILE", self.script_requests.parent / "summary.json"),
        ):
            summary = script_model_runner.run_batch(
                self.script_requests, False, None, {"runner": {"max_requests_per_batch": 4}}
            )
        self.assertEqual(drafted, ["cur.short.script_request.json"])
        self.assertEqual(summary["leftover_requests_removed"], ["old.short.script_request.json"])


if __name__ == "__main__":
    unittest.main()
