import json
import tempfile
import unittest
from pathlib import Path

from story_plan_engine import (
    build_story_plan_request,
    validate_story_plan_response,
)


class StoryPlanEngineTests(unittest.TestCase):
    def package(self):
        return {
            "status": "READY_FOR_STORY_SCRIPT",
            "concept_id": "c1",
            "concept": {
                "working_title": "Old Working Title",
                "premise": "Explain a counterintuitive braking effect.",
                "audience_promise": "Understand the system",
                "viewer_problem": "Confusing behavior",
                "viewer_moment": "Watching a race",
                "desired_outcome": "Understand why",
                "packaging": {
                    "title": "Why Racing Brakes Work Backwards",
                    "one_sentence_promise": "Explain the counterintuitive behavior",
                    "expected_payoff": "A clear explanation",
                    "thumbnail": {"message": "Backwards?"},
                },
            },
            "claims": [
                {
                    "claim_id": "clm001",
                    "statement": "Heat changes braking behavior.",
                    "role": "core",
                    "question_ids": ["rq001"],
                    "coverage": {"state": "MULTI_SOURCE"},
                }
            ],
        }

    def valid_response(self):
        return {
            "concept_id": "c1",
            "title": "Why Racing Brakes Work Backwards",
            "story_question": "Why can racing brakes feel wrong before they work correctly?",
            "opening_hook_intent": "Create tension around the apparently backwards behavior.",
            "beats": [
                {
                    "beat_id": "b1",
                    "role": "SETUP",
                    "purpose": "Establish the confusing behavior.",
                    "viewer_progress": "The viewer understands the puzzle.",
                    "claim_ids": [],
                    "transition_intent": "Move from observation to mechanism.",
                },
                {
                    "beat_id": "b2",
                    "role": "EXPLANATION",
                    "purpose": "Explain the heat-dependent mechanism.",
                    "viewer_progress": "The viewer learns what changes with temperature.",
                    "claim_ids": ["clm001"],
                    "transition_intent": "Turn mechanism into the apparent contradiction.",
                },
                {
                    "beat_id": "b3",
                    "role": "PAYOFF",
                    "purpose": "Resolve why the behavior makes sense.",
                    "viewer_progress": "The title promise is resolved.",
                    "claim_ids": ["clm001"],
                    "transition_intent": "Close on the resolved mental model.",
                },
            ],
            "payoff_intent": "Resolve the backwards-looking behavior with the heat explanation.",
            "closing_intent": "Leave the viewer with one clear mental model.",
        }

    def request(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "verified.json"
            path.write_text(json.dumps(self.package()), encoding="utf-8")
            return build_story_plan_request(self.package(), path)

    def test_request_locks_approved_packaging_title(self):
        request = self.request()
        self.assertEqual(
            request["package"]["title"],
            "Why Racing Brakes Work Backwards",
        )
        self.assertEqual(request["accepted_claim_ids"], ["clm001"])

    def test_story_plan_accepts_structural_plan(self):
        request = self.request()
        result = validate_story_plan_response(self.valid_response(), request)
        self.assertTrue(result["valid"])
        self.assertEqual(result["claim_usage"], ["clm001"])

    def test_story_plan_cannot_rewrite_title(self):
        request = self.request()
        response = self.valid_response()
        response["title"] = "A Better Clickier Title"
        result = validate_story_plan_response(response, request)
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("approved Packaging title" in error for error in result["errors"])
        )

    def test_story_plan_requires_payoff_beat(self):
        request = self.request()
        response = self.valid_response()
        response["beats"][-1]["role"] = "REVEAL"
        result = validate_story_plan_response(response, request)
        self.assertFalse(result["valid"])
        self.assertIn("story plan requires a PAYOFF beat", result["errors"])

    def test_story_plan_rejects_unapproved_claim(self):
        request = self.request()
        response = self.valid_response()
        response["beats"][1]["claim_ids"] = ["not-approved"]
        result = validate_story_plan_response(response, request)
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("unapproved claim_id" in error for error in result["errors"])
        )


if __name__ == "__main__":
    unittest.main()
