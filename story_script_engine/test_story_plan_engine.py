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


    def approved_voice_binding(self):
        return {
            "profile": {
                "schema_version": 1,
                "profile_id": "engineering_nonengineers",
                "version": 1,
                "status": "APPROVED",
                "channel_id": "engineering_nonengineers",
                "channel_name": "Engineering for Non-Engineers",
                "niche": "engineering",
                "audience": {"knowledge_level": "non_engineer"},
                "narrator_role": {"identity": "curious_explainer"},
                "tone": {"primary": "curious"},
                "technical_language": {"jargon_policy": "translate_immediately"},
                "sentence_style": {"preferred_length": "short_to_medium"},
                "storytelling": {"mystery": "high"},
                "prohibited_style": ["textbook introductions"],
                "evidence_style": {
                    "state_uncertainty": True,
                    "distinguish_fact_from_hypothesis": True,
                    "numbers_require_support": True,
                },
                "provenance": {
                    "created_from": "channel_setup_gate",
                    "approved_by": "human",
                    "approved_at": "2026-10-01T19:53:00-04:00",
                },
            },
            "binding": {
                "profile_path": "channel_profiles/profiles/engineering.json",
                "profile_sha256": "abc123",
            },
            "apply_to_generation": True,
        }

    def psychology(self, primary, action, loop_id):
        drama_by_action = {"OPEN": 7, "ADVANCE": 5, "PAYOFF": 6, "NONE": 5}
        tempo_by_action = {"OPEN": 7, "ADVANCE": 4, "PAYOFF": 5, "NONE": 5}
        return {
            "primary_mechanism": primary,
            "viewer_expectation": "The obvious explanation should be enough.",
            "cognitive_load_instruction": "Introduce one new idea and connect it to the puzzle.",
            "tension_level": "HIGH" if action == "OPEN" else "MEDIUM",
            "drama_level": drama_by_action[action],
            "tempo_level": tempo_by_action[action],
            "open_loop_id": loop_id,
            "loop_action": action,
        }

    def valid_response(self):
        return {
            "concept_id": "c1",
            "title": "Why Racing Brakes Work Backwards",
            "story_question": "Why can racing brakes feel wrong before they work correctly?",
            "opening_hook_intent": "Create immediate tension around the apparently backwards behavior.",
            "viewer_state": {
                "awareness": "The viewer expects better brakes to feel better immediately.",
                "expectation": "Race brakes should behave like stronger road brakes.",
                "desired_resolution": "Understand why the apparently wrong behavior is intentional.",
            },
            "opening_psychology": {
                "mechanism": "CONTRADICTION",
                "impact_intent": "State the apparent backwards behavior immediately.",
                "justification_intent": "Move straight into the verified heat mechanism that explains it.",
                "claim_ids": [],
            },
            "beats": [
                {
                    "beat_id": "b1",
                    "role": "SETUP",
                    "purpose": "Establish the confusing behavior.",
                    "viewer_progress": "The viewer understands the puzzle.",
                    "claim_ids": [],
                    "transition_intent": "Move from observation to mechanism.",
                    "psychology": self.psychology("CURIOSITY", "OPEN", "loop-main"),
                },
                {
                    "beat_id": "b2",
                    "role": "EXPLANATION",
                    "purpose": "Explain the heat-dependent mechanism.",
                    "viewer_progress": "The viewer learns what changes with temperature.",
                    "claim_ids": ["clm001"],
                    "transition_intent": "Turn mechanism into the apparent contradiction.",
                    "psychology": self.psychology("CLARITY", "ADVANCE", "loop-main"),
                },
                {
                    "beat_id": "b3",
                    "role": "PAYOFF",
                    "purpose": "Resolve why the behavior makes sense.",
                    "viewer_progress": "The title promise is resolved.",
                    "claim_ids": ["clm001"],
                    "transition_intent": "Close on the resolved mental model.",
                    "psychology": self.psychology("PAYOFF", "PAYOFF", "loop-main"),
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

    def test_request_locks_title_and_advertises_psychology_contract(self):
        request = self.request()
        self.assertEqual(
            request["package"]["title"],
            "Why Racing Brakes Work Backwards",
        )
        self.assertEqual(request["accepted_claim_ids"], ["clm001"])
        self.assertTrue(request["psychology_contract"]["opening_line"]["required"])
        self.assertIn(
            "CONTRADICTION",
            request["psychology_contract"]["opening_line"]["allowed_mechanisms"],
        )

    def test_story_plan_accepts_psychology_annotated_structure(self):
        result = validate_story_plan_response(self.valid_response(), self.request())
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["claim_usage"], ["clm001"])

    def test_story_plan_cannot_rewrite_title(self):
        response = self.valid_response()
        response["title"] = "A Better Clickier Title"
        result = validate_story_plan_response(response, self.request())
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("approved Packaging title" in error for error in result["errors"])
        )

    def test_story_plan_requires_payoff_beat(self):
        response = self.valid_response()
        response["beats"][-1]["role"] = "REVEAL"
        result = validate_story_plan_response(response, self.request())
        self.assertFalse(result["valid"])
        self.assertIn("story plan requires a PAYOFF beat", result["errors"])

    def test_story_plan_rejects_unapproved_claim(self):
        response = self.valid_response()
        response["beats"][1]["claim_ids"] = ["not-approved"]
        result = validate_story_plan_response(response, self.request())
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("unapproved claim_id" in error for error in result["errors"])
        )

    def test_story_plan_rejects_unresolved_open_loop(self):
        response = self.valid_response()
        response["beats"][-1]["psychology"]["loop_action"] = "ADVANCE"
        result = validate_story_plan_response(response, self.request())
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("unresolved" in error for error in result["errors"])
        )

    def test_opening_beat_must_use_high_impact_mechanism(self):
        response = self.valid_response()
        response["beats"][0]["psychology"]["primary_mechanism"] = "CLARITY"
        result = validate_story_plan_response(response, self.request())
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("high-impact" in error for error in result["errors"])
        )

    def test_opening_psychology_claims_must_be_verified(self):
        response = self.valid_response()
        response["opening_psychology"]["claim_ids"] = ["not-approved"]
        result = validate_story_plan_response(response, self.request())
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("opening_psychology uses unapproved claim_id" in error for error in result["errors"])
        )


    def test_unconfigured_channel_voice_does_not_invent_personality(self):
        request = self.request()

        self.assertEqual(
            request["channel_voice"]["profile"]["status"],
            "UNCONFIGURED",
        )
        self.assertFalse(request["channel_voice"]["apply_to_generation"])
        self.assertTrue(
            any(
                "Do not infer a persistent channel personality" in item
                for item in request["instructions"]
            )
        )

    def test_approved_channel_voice_is_bound_into_story_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "verified.json"
            package = self.package()
            path.write_text(json.dumps(package), encoding="utf-8")
            request = build_story_plan_request(
                package,
                path,
                channel_voice=self.approved_voice_binding(),
            )

        self.assertTrue(request["channel_voice"]["apply_to_generation"])
        self.assertEqual(
            request["channel_voice"]["profile"]["profile_id"],
            "engineering_nonengineers",
        )
        self.assertEqual(request["channel_voice"]["profile"]["version"], 1)
        self.assertTrue(
            any(
                "Apply the approved Channel Voice Profile" in item
                for item in request["instructions"]
            )
        )



if __name__ == "__main__":
    unittest.main()
