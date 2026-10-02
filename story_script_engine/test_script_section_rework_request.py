import unittest

from script_section_rework_request import build_section_rework_request
from script_section_review import (
    apply_target_action,
    build_section_review_state,
)


class ScriptSectionReworkRequestTests(unittest.TestCase):
    def draft(self):
        return {
            "concept_id": "c1",
            "format": "short",
            "title": "Why Race Brakes Feel Wrong Cold",
            "opening_hook": "Cold race brakes can feel worse on purpose.",
            "opening_hook_mechanism": "CONTRADICTION",
            "opening_hook_claim_ids": ["clm001"],
            "sections": [
                {
                    "section_id": "s1",
                    "source_story_beat_ids": ["b1"],
                    "purpose": "Set up the puzzle.",
                    "psychology_mechanism": "CURIOSITY",
                    "reward_type": "PROGRESS",
                    "narration": "At low temperature, the behavior feels wrong.",
                    "claim_ids": ["clm001"],
                },
                {
                    "section_id": "s2",
                    "source_story_beat_ids": ["b2"],
                    "purpose": "Explain the mechanism.",
                    "psychology_mechanism": "CLARITY",
                    "reward_type": "PROOF",
                    "narration": "Heat changes how the braking system behaves.",
                    "claim_ids": ["clm001"],
                },
            ],
            "closing": "Temperature is the missing piece.",
            "package": {
                "title": "Why Race Brakes Feel Wrong Cold",
                "one_sentence_promise": "Explain the cold-brake contradiction.",
                "expected_payoff": "Temperature explains the behavior.",
                "desired_outcome": "Viewer understands the mechanism.",
            },
            "story_plan": {
                "title": "Why Race Brakes Feel Wrong Cold",
                "story_question": "Why can cold race brakes feel worse?",
                "opening_hook_intent": "Expose the contradiction.",
                "beats": [
                    {
                        "beat_id": "b1",
                        "purpose": "Set up the puzzle.",
                        "claim_ids": ["clm001"],
                    },
                    {
                        "beat_id": "b2",
                        "purpose": "Explain heat behavior.",
                        "claim_ids": ["clm001"],
                    },
                ],
                "payoff_intent": "Resolve the contradiction.",
                "closing_intent": "Leave one clear mental model.",
            },
            "psychology_contract": {
                "opening_line": {"required": True},
            },
            "psychology_profile": {
                "reward_density": "HIGH",
            },
            "channel_voice": {
                "profile": {
                    "profile_id": "engineering_nonengineers",
                    "version": 1,
                    "status": "APPROVED",
                },
                "binding": {"profile_sha256": "voice-v1"},
                "apply_to_generation": True,
            },
            "accepted_claims": [
                {
                    "claim_id": "clm001",
                    "statement": "Heat changes braking behavior.",
                },
                {
                    "claim_id": "clm999",
                    "statement": "Unrelated accepted fact.",
                },
            ],
        }

    def provenance(self):
        return {
            "script_draft": "/tmp/c1.short.script_draft.json",
            "script_draft_sha256": "draft-sha",
            "section_state": "/tmp/c1.short.state.json",
            "section_state_sha256": "state-sha",
            "script_review_request": "/tmp/c1.short.review.json",
            "script_review_request_sha256": "review-sha",
            "script_request": "/tmp/c1.short.script_request.json",
            "script_request_sha256": "request-sha",
        }

    def rework_state(self, target_id="section:s1"):
        state = build_section_review_state(
            self.draft(),
            source_draft_sha256="draft-sha",
        )
        result = apply_target_action(
            state,
            source_draft_sha256="draft-sha",
            target_id=target_id,
            action="REWORK",
            reviewer="r",
            updated_at="2026-10-01T21:15:00-04:00",
            reason="TOO_TECHNICAL",
            note="Use plain language.",
        )
        return result["state"]

    def review_request(self):
        return {"concept_id": "c1", "format": "short"}

    def test_builds_bounded_request_for_one_section(self):
        request = build_section_rework_request(
            draft=self.draft(),
            review_request=self.review_request(),
            section_state=self.rework_state(),
            target_id="section:s1",
            provenance=self.provenance(),
        )

        self.assertEqual(request["artifact"], "script_section_rework_request")
        self.assertEqual(request["request_mode"], "SELECTIVE_SECTION_REWORK")
        self.assertEqual(request["target"]["target_id"], "section:s1")
        self.assertEqual(
            request["target"]["text"],
            "At low temperature, the behavior feels wrong.",
        )
        self.assertEqual(
            request["target"]["immutable_metadata"]["source_story_beat_ids"],
            ["b1"],
        )
        self.assertEqual(
            [item["relationship"] for item in request["adjacent_context"]],
            ["PREVIOUS", "NEXT"],
        )
        self.assertEqual(
            [item["target_id"] for item in request["adjacent_context"]],
            ["opening_hook", "section:s2"],
        )
        self.assertTrue(
            all(item["read_only"] for item in request["adjacent_context"])
        )

    def test_request_keeps_only_claims_already_mapped_to_target(self):
        request = build_section_rework_request(
            draft=self.draft(),
            review_request=self.review_request(),
            section_state=self.rework_state(),
            target_id="section:s1",
            provenance=self.provenance(),
        )

        self.assertEqual(
            [claim["claim_id"] for claim in request["allowed_claims"]],
            ["clm001"],
        )
        self.assertEqual(
            [beat["beat_id"] for beat in request["story_context"]["relevant_beats"]],
            ["b1"],
        )

    def test_preserves_bound_channel_voice_and_psychology(self):
        request = build_section_rework_request(
            draft=self.draft(),
            review_request=self.review_request(),
            section_state=self.rework_state(),
            target_id="section:s1",
            provenance=self.provenance(),
        )

        self.assertEqual(
            request["channel_voice"]["binding"]["profile_sha256"],
            "voice-v1",
        )
        self.assertEqual(
            request["psychology_profile"]["reward_density"],
            "HIGH",
        )
        self.assertEqual(
            request["human_rework"]["reason"],
            "TOO_TECHNICAL",
        )
        self.assertEqual(
            request["human_rework"]["note"],
            "Use plain language.",
        )

    def test_provenance_binds_state_and_target_revision(self):
        state = self.rework_state()
        request = build_section_rework_request(
            draft=self.draft(),
            review_request=self.review_request(),
            section_state=state,
            target_id="section:s1",
            provenance=self.provenance(),
        )

        target = next(
            item for item in state["targets"]
            if item["target_id"] == "section:s1"
        )
        provenance = request["request_provenance"]
        self.assertEqual(provenance["state_revision"], 1)
        self.assertEqual(provenance["script_revision"], 0)
        self.assertEqual(provenance["target_revision"], 1)
        self.assertEqual(
            provenance["target_content_sha256"],
            target["content_sha256"],
        )

    def test_hook_uses_only_next_neighbor_and_hook_claims(self):
        request = build_section_rework_request(
            draft=self.draft(),
            review_request=self.review_request(),
            section_state=self.rework_state("opening_hook"),
            target_id="opening_hook",
            provenance=self.provenance(),
        )

        self.assertEqual(
            [item["target_id"] for item in request["adjacent_context"]],
            ["section:s1"],
        )
        self.assertEqual(
            request["target"]["immutable_metadata"]["opening_hook_mechanism"],
            "CONTRADICTION",
        )
        self.assertEqual(
            [claim["claim_id"] for claim in request["allowed_claims"]],
            ["clm001"],
        )

    def test_closing_uses_only_previous_neighbor_and_no_new_fact_allowance(self):
        request = build_section_rework_request(
            draft=self.draft(),
            review_request=self.review_request(),
            section_state=self.rework_state("closing"),
            target_id="closing",
            provenance=self.provenance(),
        )

        self.assertEqual(
            [item["target_id"] for item in request["adjacent_context"]],
            ["section:s2"],
        )
        self.assertEqual(request["allowed_claims"], [])
        self.assertEqual(request["story_context"]["relevant_beats"], [])

    def test_non_rework_target_fails_closed(self):
        state = build_section_review_state(
            self.draft(),
            source_draft_sha256="draft-sha",
        )

        with self.assertRaisesRegex(ValueError, "REWORK_REQUESTED"):
            build_section_rework_request(
                draft=self.draft(),
                review_request=self.review_request(),
                section_state=state,
                target_id="section:s1",
                provenance=self.provenance(),
            )

    def test_missing_provenance_fails_closed(self):
        provenance = self.provenance()
        provenance.pop("section_state_sha256")

        with self.assertRaisesRegex(ValueError, "section_state_sha256"):
            build_section_rework_request(
                draft=self.draft(),
                review_request=self.review_request(),
                section_state=self.rework_state(),
                target_id="section:s1",
                provenance=provenance,
            )

    def test_missing_story_beat_or_claim_fails_closed(self):
        draft = self.draft()
        draft["sections"][0]["source_story_beat_ids"] = ["missing"]
        state = build_section_review_state(
            draft,
            source_draft_sha256="draft-sha",
        )
        state = apply_target_action(
            state,
            source_draft_sha256="draft-sha",
            target_id="section:s1",
            action="REWORK",
            reviewer="r",
            updated_at="2026-10-01T21:15:00-04:00",
            reason="TOO_TECHNICAL",
        )["state"]

        with self.assertRaisesRegex(ValueError, "Story Plan beats"):
            build_section_rework_request(
                draft=draft,
                review_request=self.review_request(),
                section_state=state,
                target_id="section:s1",
                provenance=self.provenance(),
            )

        draft = self.draft()
        draft["sections"][0]["claim_ids"] = ["missing"]
        state = build_section_review_state(
            draft,
            source_draft_sha256="draft-sha",
        )
        state = apply_target_action(
            state,
            source_draft_sha256="draft-sha",
            target_id="section:s1",
            action="REWORK",
            reviewer="r",
            updated_at="2026-10-01T21:15:00-04:00",
            reason="TOO_TECHNICAL",
        )["state"]

        with self.assertRaisesRegex(ValueError, "accepted claims"):
            build_section_rework_request(
                draft=draft,
                review_request=self.review_request(),
                section_state=state,
                target_id="section:s1",
                provenance=self.provenance(),
            )


if __name__ == "__main__":
    unittest.main()
