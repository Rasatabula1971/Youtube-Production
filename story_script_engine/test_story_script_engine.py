import json
import tempfile
import unittest
from pathlib import Path

import story_script_engine as module

from story_script_engine import build_script_request, validate_script_response


class StoryScriptTests(unittest.TestCase):
    def plan(self):
        return {
            "artifact": "story_plan",
            "status": "STORY_PLAN_READY",
            "concept_id": "c1",
            "title": "Why Racing Brakes Work Backwards",
            "package": {
                "title": "Why Racing Brakes Work Backwards",
                "one_sentence_promise": "Explain the counterintuitive behavior",
                "expected_payoff": "A clear explanation",
                "thumbnail": {"message": "Backwards?"},
            },
            "concept": {
                "premise": "Explain why race brakes can behave counterintuitively.",
                "audience_promise": "Understand the system",
            },
            "story_question": "Why can racing brakes seem backwards?",
            "opening_hook_intent": "Open on the contradiction.",
            "beats": [
                {
                    "beat_id": "b1",
                    "role": "SETUP",
                    "purpose": "Establish the puzzle.",
                    "viewer_progress": "The viewer sees the contradiction.",
                    "claim_ids": [],
                    "transition_intent": "Ask what changes.",
                },
                {
                    "beat_id": "b2",
                    "role": "EXPLANATION",
                    "purpose": "Explain heat behavior.",
                    "viewer_progress": "The viewer learns the mechanism.",
                    "claim_ids": ["clm001"],
                    "transition_intent": "Connect the mechanism to the puzzle.",
                },
                {
                    "beat_id": "b3",
                    "role": "PAYOFF",
                    "purpose": "Resolve the title promise.",
                    "viewer_progress": "The contradiction now makes sense.",
                    "claim_ids": ["clm001"],
                    "transition_intent": "Close on the resolved idea.",
                },
            ],
            "payoff_intent": "Resolve the apparent contradiction.",
            "closing_intent": "Leave one clear mental model.",
            "accepted_claims": [
                {
                    "claim_id": "clm001",
                    "statement": "Heat changes braking behavior.",
                }
            ],
        }

    def request(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(self.plan()), encoding="utf-8")
            return build_script_request(self.plan(), path)

    def valid_response(self):
        return {
            "concept_id": "c1",
            "title": "Why Racing Brakes Work Backwards",
            "opening_hook": "At first, the brakes can seem to be doing the opposite of what you expect.",
            "sections": [
                {
                    "section_id": "s1",
                    "story_beat_id": "b1",
                    "purpose": "Establish the puzzle.",
                    "narration": "The strange part is the behavior itself.",
                    "claim_ids": [],
                },
                {
                    "section_id": "s2",
                    "story_beat_id": "b2",
                    "purpose": "Explain heat behavior.",
                    "narration": "Temperature changes how the braking system behaves.",
                    "claim_ids": ["clm001"],
                },
                {
                    "section_id": "s3",
                    "story_beat_id": "b3",
                    "purpose": "Resolve the title promise.",
                    "narration": "That is why the behavior only looks backwards until you account for heat.",
                    "claim_ids": ["clm001"],
                },
            ],
            "closing": "The puzzle disappears once temperature is part of the picture.",
        }

    def test_request_preserves_story_plan_and_title(self):
        req = self.request()
        self.assertEqual(req["accepted_claim_ids"], ["clm001"])
        self.assertEqual(req["package"]["title"], "Why Racing Brakes Work Backwards")
        self.assertEqual(len(req["story_plan"]["beats"]), 3)

    def test_script_cannot_rewrite_approved_title(self):
        req = self.request()
        response = self.valid_response()
        response["title"] = "New Title"
        result = validate_script_response(response, req)
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("approved Packaging title" in error for error in result["errors"])
        )

    def test_script_must_map_every_story_beat_once(self):
        req = self.request()
        response = self.valid_response()
        response["sections"][2]["story_beat_id"] = "b2"
        result = validate_script_response(response, req)
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("duplicate story_beat_id" in error for error in result["errors"])
        )

    def test_script_claims_must_match_story_beat(self):
        req = self.request()
        response = self.valid_response()
        response["sections"][1]["claim_ids"] = []
        result = validate_script_response(response, req)
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("claim_ids must match Story Plan beat" in error for error in result["errors"])
        )

    def test_valid_story_bound_script_passes(self):
        req = self.request()
        result = validate_script_response(self.valid_response(), req)
        self.assertTrue(result["valid"])
        self.assertEqual(result["claim_usage"], ["clm001"])
        self.assertEqual(result["story_plan_beat_ids"], ["b1", "b2", "b3"])

    def test_slug_collision_is_rejected_before_script_request_writes(self):
        with self.assertRaisesRegex(ValueError, "collide"):
            module.assert_unique_slug_ids(
                ["gear/ratio", "gear ratio"],
                label="concept",
            )


if __name__ == "__main__":
    unittest.main()
