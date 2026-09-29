import json
import tempfile
import unittest
from pathlib import Path

import story_script_engine as module

from story_script_engine import build_script_request, validate_script_response


class StoryScriptTests(unittest.TestCase):
    def psychology(self, primary, action, loop_id):
        return {
            "primary_mechanism": primary,
            "viewer_expectation": "The obvious explanation should be enough.",
            "cognitive_load_instruction": "Introduce one primary new idea.",
            "tension_level": "HIGH" if action == "OPEN" else "MEDIUM",
            "open_loop_id": loop_id,
            "loop_action": action,
        }

    def plan(self, format_intent="either"):
        return {
            "artifact": "story_plan",
            "status": "STORY_PLAN_READY",
            "concept_id": "c1",
            "title": "Why Racing Brakes Work Backwards",
            "package": {
                "title": "Why Racing Brakes Work Backwards",
                "one_sentence_promise": "Explain the counterintuitive behavior",
                "expected_payoff": "A clear explanation",
                "format_intent": format_intent,
                "thumbnail": {"message": "Backwards?"},
            },
            "concept": {
                "premise": "Explain why race brakes can behave counterintuitively.",
                "audience_promise": "Understand the system",
            },
            "psychology_contract": {
                "opening_line": {
                    "required": True,
                    "allowed_mechanisms": [
                        "CONTRADICTION",
                        "SURPRISING_FACT",
                        "STAKES",
                        "EXPECTATION_VIOLATION",
                        "SPECIFIC_CURIOSITY",
                        "BOLD_PROMISE",
                    ],
                },
                "beat_mechanisms": [
                    "CURIOSITY",
                    "PREDICTION",
                    "TENSION",
                    "STAKES",
                    "NOVELTY",
                    "EXPECTATION_VIOLATION",
                    "CLARITY",
                    "PAYOFF",
                ],
            },
            "story_question": "Why can racing brakes seem backwards?",
            "opening_hook_intent": "Open on the contradiction.",
            "viewer_state": {
                "awareness": "The viewer knows race brakes are extreme.",
                "expectation": "Better brakes should work better in ordinary conditions.",
                "desired_resolution": "Understand why heat changes the design target.",
            },
            "opening_psychology": {
                "mechanism": "CONTRADICTION",
                "impact_intent": "State the backwards behavior immediately.",
                "justification_intent": "Move straight into the heat mechanism.",
                "claim_ids": [],
            },
            "beats": [
                {
                    "beat_id": "b1",
                    "role": "SETUP",
                    "purpose": "Establish the puzzle.",
                    "viewer_progress": "The viewer sees the contradiction.",
                    "claim_ids": [],
                    "transition_intent": "Ask what changes.",
                    "psychology": self.psychology("CURIOSITY", "OPEN", "main"),
                },
                {
                    "beat_id": "b2",
                    "role": "EXPLANATION",
                    "purpose": "Explain heat behavior.",
                    "viewer_progress": "The viewer learns the mechanism.",
                    "claim_ids": ["clm001"],
                    "transition_intent": "Connect the mechanism to the puzzle.",
                    "psychology": self.psychology("CLARITY", "ADVANCE", "main"),
                },
                {
                    "beat_id": "b3",
                    "role": "PAYOFF",
                    "purpose": "Resolve the title promise.",
                    "viewer_progress": "The contradiction now makes sense.",
                    "claim_ids": ["clm001"],
                    "transition_intent": "Close on the resolved idea.",
                    "psychology": self.psychology("PAYOFF", "PAYOFF", "main"),
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

    def request(self, fmt="long_form", format_intent="either"):
        plan = self.plan(format_intent)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            return build_script_request(plan, path, fmt)

    def valid_response(self, fmt="long_form"):
        rewards = (
            ["PROGRESS", "PROOF", "MICRO_PAYOFF"]
            if fmt == "short"
            else ["NONE", "PROGRESS", "NONE"]
        )
        return {
            "concept_id": "c1",
            "format": fmt,
            "title": "Why Racing Brakes Work Backwards",
            "opening_hook": (
                "The better these racing brakes get, the worse they can feel at the wrong temperature."
            ),
            "opening_hook_mechanism": "CONTRADICTION",
            "opening_hook_claim_ids": [],
            "sections": [
                {
                    "section_id": "s1",
                    "source_story_beat_ids": ["b1"],
                    "purpose": "Establish the puzzle.",
                    "psychology_mechanism": "CURIOSITY",
                    "reward_type": rewards[0],
                    "narration": "That apparent contradiction is the puzzle we need to explain.",
                    "claim_ids": [],
                },
                {
                    "section_id": "s2",
                    "source_story_beat_ids": ["b2"],
                    "purpose": "Explain heat behavior.",
                    "psychology_mechanism": "CLARITY",
                    "reward_type": rewards[1],
                    "narration": "Temperature changes how the braking system behaves.",
                    "claim_ids": ["clm001"],
                },
                {
                    "section_id": "s3",
                    "source_story_beat_ids": ["b3"],
                    "purpose": "Resolve the title promise.",
                    "psychology_mechanism": "PAYOFF",
                    "reward_type": rewards[2],
                    "narration": "That is why the behavior only looks backwards until you account for heat.",
                    "claim_ids": ["clm001"],
                },
            ],
            "closing": "The puzzle disappears once temperature is part of the picture.",
        }

    def test_requests_split_by_format_psychology(self):
        long_req = self.request("long_form")
        short_req = self.request("short")
        self.assertEqual(long_req["required_branches"], ["long_form", "short"])
        self.assertEqual(long_req["format"], "long_form")
        self.assertEqual(short_req["format"], "short")
        self.assertIsNone(long_req["psychology_profile"]["hook_target_seconds"])
        self.assertEqual(short_req["psychology_profile"]["hook_target_seconds"], 3)
        self.assertEqual(
            short_req["psychology_profile"]["attention_refresh_window_seconds"],
            [4, 6],
        )

    def test_single_format_intent_rejects_unrequested_branch(self):
        with self.assertRaisesRegex(ValueError, "Unrequested script branch"):
            self.request("long_form", format_intent="short")

    def test_script_cannot_rewrite_approved_title(self):
        response = self.valid_response()
        response["title"] = "New Title"
        result = validate_script_response(response, self.request())
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("approved Packaging title" in error for error in result["errors"])
        )

    def test_format_identity_is_locked(self):
        response = self.valid_response("short")
        response["format"] = "long_form"
        result = validate_script_response(response, self.request("short"))
        self.assertFalse(result["valid"])
        self.assertIn("format mismatch", result["errors"])

    def test_long_form_must_cover_all_story_beats(self):
        response = self.valid_response("long_form")
        response["sections"] = response["sections"][1:]
        result = validate_script_response(response, self.request("long_form"))
        self.assertFalse(result["valid"])
        self.assertTrue(any("missing Story Plan beat" in e for e in result["errors"]))

    def test_short_requires_reward_event_in_every_section(self):
        response = self.valid_response("short")
        response["sections"][1]["reward_type"] = "NONE"
        result = validate_script_response(response, self.request("short"))
        self.assertFalse(result["valid"])
        self.assertTrue(any("reward/progress event" in e for e in result["errors"]))

    def test_claim_must_come_from_cited_story_beat(self):
        response = self.valid_response("short")
        response["sections"][1]["source_story_beat_ids"] = ["b1"]
        result = validate_script_response(response, self.request("short"))
        self.assertFalse(result["valid"])
        self.assertTrue(any("not available from its source" in e for e in result["errors"]))

    def test_branch_must_include_payoff(self):
        response = self.valid_response("short")
        response["sections"][2]["source_story_beat_ids"] = ["b2"]
        result = validate_script_response(response, self.request("short"))
        self.assertFalse(result["valid"])
        self.assertTrue(any("PAYOFF beat" in e for e in result["errors"]))

    def test_valid_long_and_short_scripts_pass(self):
        for fmt in ("long_form", "short"):
            result = validate_script_response(
                self.valid_response(fmt),
                self.request(fmt),
            )
            self.assertTrue(result["valid"], result["errors"])
            self.assertEqual(result["claim_usage"], ["clm001"])
            self.assertEqual(result["format"], fmt)

    def test_slug_collision_is_rejected_before_script_request_writes(self):
        with self.assertRaisesRegex(ValueError, "collide"):
            module.assert_unique_slug_ids(
                ["gear/ratio", "gear ratio"],
                label="concept-format",
            )


if __name__ == "__main__":
    unittest.main()
