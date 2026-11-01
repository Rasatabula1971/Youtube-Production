"""Two lanes, Short and long-form, with fewer owner decisions (D-188, PR 1)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from experiment_ui import gate_autopilot as autopilot
from transformation_engine import topic_guard

STUDY = [{"topic": "tyres_tires", "title": "Why F1 Tires Look Like This After a Race!"}]


def concept(concept_id, title, score, fmt="short", premise=""):
    return {
        "concept_id": concept_id, "working_title": title, "premise": premise,
        "format_intent": fmt, "decision": "PENDING",
        "llm_triage": {"overall_score": score, "dimension_scores": {}},
    }


# The Aviation Tires shortlist, as triage ranked it (31 Oct 2026).
TYRE_SHORTLIST = [
    concept("c_tread", "Why Aviation Tires Lack Deep Treads", 81),
    concept("c_blowout", "What Happens Inside a Tire One Millisecond Before Failure", 88),
    concept("c_water", "How a Single Cup of Water Destroys Your Stopping Distance", 85,
            premise="How tire contact patches displace water."),
    concept("c_ev", "Why EV Battery Packs Fail in Extreme Heat", 82),
    concept("c_carbon", "Why Carbon Fiber Bike Frames Snap Without Warning", 80),
]


class Control:
    """A stand-in for the server module."""

    def __init__(self, root: Path, concepts=None, research=None):
        self.EXP15_DIR = root
        (root / "approved_study_set.json").write_text(json.dumps(STUDY), encoding="utf-8")
        self.concepts = concepts or []
        self.research = research or {}
        self.calls: list[tuple[str, dict, str | None]] = []
        self.reserve: list[str] | None = None
        self.dropped: dict[str, dict] = {}
        self.next_concept: str | None = None

    def _log(self, name, kwargs):
        self.calls.append((name, kwargs, os.environ.get(autopilot.DECIDED_BY_ENV)))

    def concept_gate_snapshot(self):
        return {"concepts": self.concepts}

    def apply_concept_gate_action(self, **kwargs):
        self._log("concept", kwargs)

    def record_concept_lane_reserve(self, ids):
        self.reserve = list(ids)

    def leave_out_unconfirmed_research(self):
        self._log("leave_out", {})
        return self.research

    def drop_concept_everywhere(self, **kwargs):
        self._log("drop", kwargs)
        self.dropped[kwargs["concept_id"]] = {"note": kwargs["note"]}

    def dropped_research_concepts(self):
        return self.dropped

    def promote_concept_reserve(self, **kwargs):
        self._log("promote", kwargs)
        return self.next_concept


class TopicGuardTests(unittest.TestCase):
    def test_the_off_topic_finalists_are_caught(self):
        terms = topic_guard.topic_terms(STUDY)["terms"]
        self.assertEqual(terms, ["tire"])
        verdicts = {item["concept_id"]: topic_guard.on_topic(item, terms)["on_topic"] for item in TYRE_SHORTLIST}
        self.assertEqual(verdicts, {"c_tread": True, "c_blowout": True, "c_water": True, "c_ev": False, "c_carbon": False})

    def test_british_and_american_spellings_match(self):
        terms = topic_guard.topic_terms([{"topic": "tyres"}])["terms"]
        self.assertTrue(topic_guard.on_topic({"working_title": "Why Tires Squeal"}, terms)["on_topic"])

    def test_a_submitted_video_uses_its_seed_topic_not_the_source_slug(self):
        rows = [{"topic": "human_video", "opportunity_context": {"seed_topic": "jet engines"}}]
        self.assertEqual(topic_guard.topic_terms(rows)["terms"], ["engine", "jet"])

    def test_no_topic_words_means_nothing_is_on_topic(self):
        self.assertFalse(topic_guard.on_topic({"working_title": "Anything"}, [])["on_topic"])


class ShortLaneConceptTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_the_top_on_topic_concept_is_picked_and_the_rest_wait_in_reserve(self):
        control = Control(self.root, concepts=[dict(item) for item in TYRE_SHORTLIST])
        outcome = autopilot.decide("HUMAN_CONCEPT_GATE", control, autopilot.load_policy())
        self.assertEqual(outcome["lane"], "short")
        self.assertEqual(outcome["held"], [])
        decisions = {kwargs["concept_id"]: kwargs["decision"] for name, kwargs, _ in control.calls}
        self.assertEqual(decisions, {"c_blowout": "ACCEPT", "c_water": "REJECT", "c_tread": "REJECT",
                                     "c_ev": "REJECT", "c_carbon": "REJECT"})
        self.assertEqual(control.reserve, ["c_water", "c_tread"])
        self.assertTrue(all(decided_by == autopilot.POLICY_DECIDER for _, _, decided_by in control.calls))
        notes = {kwargs["concept_id"]: kwargs["note"] for _, kwargs, _ in control.calls}
        self.assertIn("Not about the approved topic", notes["c_ev"])
        self.assertIn("reserve (next 1)", notes["c_water"])

    def test_an_off_topic_concept_is_never_picked_even_with_the_top_score(self):
        concepts = [concept("c_helmet", "Why Cycling Helmets Have Hidden Tunnels", 99),
                    concept("c_tire", "Why Tractor Tires Have Massive Lugs", 71)]
        control = Control(self.root, concepts=concepts)
        autopilot.decide("HUMAN_CONCEPT_GATE", control, autopilot.load_policy())
        accepted = [kwargs["concept_id"] for _, kwargs, _ in control.calls if kwargs["decision"] == "ACCEPT"]
        self.assertEqual(accepted, ["c_tire"])

    def test_with_no_on_topic_concept_the_owner_picks(self):
        control = Control(self.root, concepts=[concept("c_ev", "Why EV Battery Packs Fail", 90)])
        outcome = autopilot.decide("HUMAN_CONCEPT_GATE", control, autopilot.load_policy())
        self.assertEqual(outcome["decided"], 0)
        self.assertEqual(control.calls, [])
        self.assertIn("none is about the approved topic", outcome["held"][0])

    def test_the_long_form_lane_leaves_the_concept_to_the_owner(self):
        concepts = [concept("c1", "Why Aviation Tires Lack Deep Treads", 90, fmt="long_form")]
        control = Control(self.root, concepts=concepts)
        outcome = autopilot.decide("HUMAN_CONCEPT_GATE", control, autopilot.load_policy())
        self.assertEqual(outcome["lane"], "long_form")
        self.assertEqual(control.calls, [])

    def test_a_gate_the_owner_started_is_left_to_the_owner(self):
        concepts = [dict(item) for item in TYRE_SHORTLIST]
        concepts[0]["decision"] = "ACCEPT"
        control = Control(self.root, concepts=concepts)
        outcome = autopilot.decide("HUMAN_CONCEPT_GATE", control, autopilot.load_policy())
        self.assertEqual(control.calls, [])
        self.assertEqual(outcome["decided"], 0)


class ResearchAutoTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_unconfirmed_claims_are_left_out_and_a_ready_concept_moves_on(self):
        research = {"left_out": [{"claim_id": "cl2"}], "waived": [],
                    "packages": [{"concept_id": "c1", "status": "READY_FOR_STORY_SCRIPT", "accepted": 3}]}
        control = Control(self.root, research=research)
        outcome = autopilot.decide("HUMAN_RESEARCH_GATE", control, autopilot.load_policy())
        self.assertEqual(outcome["decided"], 1)
        self.assertEqual(outcome["held"], [])
        self.assertEqual([name for name, _, _ in control.calls], ["leave_out"])
        self.assertIn("1 unconfirmed claim(s) left out", outcome["notes"][0])

    def test_a_thin_concept_is_dropped_with_its_reason_and_the_next_is_tried(self):
        research = {"left_out": [], "waived": [], "packages": [{
            "concept_id": "c_blowout", "working_title": "Inside a Tire", "status": "RESEARCH_TOO_THIN",
            "accepted": 1, "evidence_shortfalls": ["1 accepted claim; at least 2 are needed"]}]}
        control = Control(self.root, research=research)
        control.next_concept = "c_water"
        outcome = autopilot.decide("HUMAN_RESEARCH_GATE", control, autopilot.load_policy())
        names = [name for name, _, _ in control.calls]
        self.assertEqual(names, ["leave_out", "drop", "promote"])
        drop = control.calls[1]
        self.assertIn("Dropped automatically: research too thin (1 accepted claim", drop[1]["note"])
        self.assertEqual(drop[2], autopilot.POLICY_DECIDER)
        self.assertEqual(control.calls[2][1]["exclude"], {"c_blowout"})
        self.assertIn("Next concept tried: c_water.", outcome["notes"])

    def test_with_the_reserve_used_up_the_drop_is_held_for_the_owner(self):
        research = {"left_out": [], "waived": [], "packages": [
            {"concept_id": "c1", "status": "RESEARCH_INCOMPLETE", "accepted": 0, "evidence_shortfalls": []}]}
        control = Control(self.root, research=research)
        outcome = autopilot.decide("HUMAN_RESEARCH_GATE", control, autopilot.load_policy())
        self.assertIn("no claim could be confirmed", control.calls[1][1]["note"])
        self.assertIn("no on-topic concept is left to try", outcome["held"][0])

    def test_open_questions_the_owner_kept_stop_for_the_owner(self):
        research = {"left_out": [], "waived": [], "packages": [
            {"concept_id": "c1", "status": "RESEARCH_INCOMPLETE", "accepted": 2}]}
        control = Control(self.root, research=research)
        outcome = autopilot.decide("HUMAN_RESEARCH_GATE", control, autopilot.load_policy())
        self.assertEqual(outcome["decided"], 0)
        self.assertEqual([name for name, _, _ in control.calls], ["leave_out"])
        self.assertIn("questions you kept open", outcome["held"][0])


# The owner decisions in the accepted contract (claude/Two_Lanes_Contract.md).
CONTRACT = {
    # The owner added the thumbnail he makes from its prompt and uploads (D-191).
    "short": {"topic", "script", "thumbnail_upload", "finished_video"},
    "long_form": {"topic", "concept", "script", "package", "thumbnail_upload", "finished_video"},
}
AS_CONTRACT = {"final_packaging": "package", "final_export": "finished_video"}
# Stops still on the owner until the later PRs of the contract land.
LATER = {
    "short": {"narration_preview": "PR 3", "rough_cut": "PR 3",
              "visual_rights": "PR 3", "publish": "PR 3 (one decision with export)"},
    "long_form": {"narration_preview": "PR 3", "rough_cut": "PR 3", "visual_rights": "PR 3",
                  "publish": "PR 3 (one decision with export)"},
}


class OwnerStopsTests(unittest.TestCase):
    def test_per_lane_the_owner_stops_match_the_contract(self):
        policy = autopilot.load_policy()
        for lane, expected in CONTRACT.items():
            with self.subTest(lane=lane):
                stops = [gate for gate in autopilot.owner_stops(lane, policy) if gate not in LATER[lane]]
                self.assertEqual({AS_CONTRACT.get(gate, gate) for gate in stops}, expected)

    def test_concept_research_and_packaging_no_longer_stop_a_short(self):
        stops = autopilot.owner_stops("short", autopilot.load_policy())
        self.assertNotIn("concept", stops)
        self.assertNotIn("research", stops)
        self.assertNotIn("final_packaging", stops)
        self.assertIn("final_packaging", autopilot.owner_stops("long_form", autopilot.load_policy()))
        self.assertIn("concept", autopilot.owner_stops("long_form", autopilot.load_policy()))


class ScriptScreenTests(unittest.TestCase):
    def test_each_script_lists_the_claims_left_out(self):
        from unittest.mock import patch

        from experiment_ui import server

        rows = [{"claim_id": "clm2", "statement": "Treads hold water.", "reason": "single source."}]
        with patch.object(server, "research_left_out_claims", side_effect=lambda cid: rows if cid == "c1" else []):
            payload = server.with_left_out_claims({"scripts": [{"concept_id": "c1"}, {"concept_id": "c2"}]})
        self.assertEqual(payload["scripts"][0]["left_out_claims"], rows)
        self.assertEqual(payload["scripts"][1]["left_out_claims"], [])


class ShortPackagingPathTests(unittest.TestCase):
    """PR 2 (D-190): a Short skips angles, thumbnails, the matrix and the Final Package gate."""

    def guidance(self, lanes, final_state=None):
        from contextlib import ExitStack
        from unittest.mock import patch

        from experiment_ui import server

        not_ready = {"ready": False}
        patches = {
            "opportunity_gate_snapshot": {"ready_for_experiment_02": True, "opportunities": []},
            "opportunity_research_state": {},
            "vision_review_snapshot": {"awaiting_human_review": False, "complete": True},
            "human_analysis_review_snapshot": {"status": "COMPLETE"},
            "transformation_artifact_state": {"candidates_ready": True, "concept_gate": {"status": "COMPLETE"}},
            "packaging_artifact_state": {"candidates_ready": True, "packaging_gate": {"status": "COMPLETE"}},
            "research_artifact_state": {"drafts_ready": True, "research_gate": {"status": "COMPLETE"}},
            "story_script_artifact_state": {
                "drafts_ready": True, "production_ready": True, "script_gate": {"status": "COMPLETE"},
            },
            "title_direction_artifact_state": {
                "requests_ready": True, "candidates_ready": True, "gate": {"status": "TITLE_DIRECTION_SELECTED"},
            },
            "packaging_brief_snapshot": {"ready": True},
            # The long-form steps have nothing current: a Short must not wait on them.
            "psychological_angle_request_snapshot": not_ready,
            "psychological_angle_snapshot": not_ready,
            "thumbnail_concept_request_snapshot": not_ready,
            "thumbnail_concept_snapshot": not_ready,
            "package_pairing_request_snapshot": not_ready,
            "package_validation_snapshot": not_ready,
            "final_packaging_gate_state": final_state or {"status": "WAITING_FOR_PACKAGE_VALIDATION", "ready": False},
            "short_package_lane_state": lanes,
            "format_artifact_state": {"plans_ready": False, "format_gate": {"status": "WAITING_FOR_FORMAT_PLANS"}},
        }
        with ExitStack() as stack:
            for name, value in patches.items():
                stack.enter_context(patch.object(server, name, return_value=value))
            return server.workflow_guidance({}), server.final_packaging_overview()

    def patched_upstream(self):
        """Every stage up to packaging complete, as in guidance()."""
        from contextlib import ExitStack
        from unittest.mock import patch

        from experiment_ui import server

        done = {
            "opportunity_gate_snapshot": {"ready_for_experiment_02": True, "opportunities": []},
            "opportunity_research_state": {},
            "vision_review_snapshot": {"awaiting_human_review": False, "complete": True},
            "human_analysis_review_snapshot": {"status": "COMPLETE"},
            "transformation_artifact_state": {"candidates_ready": True, "concept_gate": {"status": "COMPLETE"}},
            "packaging_artifact_state": {"candidates_ready": True, "packaging_gate": {"status": "COMPLETE"}},
            "research_artifact_state": {"drafts_ready": True, "research_gate": {"status": "COMPLETE"}},
            "story_script_artifact_state": {
                "drafts_ready": True, "production_ready": True, "script_gate": {"status": "COMPLETE"},
            },
            "title_direction_artifact_state": {
                "requests_ready": True, "candidates_ready": True, "gate": {"status": "TITLE_DIRECTION_SELECTED"},
            },
            "packaging_brief_snapshot": {"ready": True},
        }
        stack = ExitStack()
        for name, value in done.items():
            stack.enter_context(patch.object(server, name, return_value=value))
        return stack

    def test_a_short_goes_from_title_to_format_planning(self):
        """The Aviation Tires Short sat at the Final Package gate with no thumbnail image."""
        workflow, overview = self.guidance({"chain_needed": False, "short_ready": True})
        self.assertNotIn("Psychological", workflow["current_title"])
        self.assertNotEqual(workflow["state"], "HUMAN_FINAL_PACKAGING_GATE")
        self.assertTrue(overview["ready"])
        self.assertEqual(overview["status"], "SHORT_LANE_PACKAGED")

    def test_a_short_without_a_chosen_title_stops_and_says_why(self):
        workflow, overview = self.guidance(
            {"chain_needed": False, "short_ready": False, "short_missing": ["c_tyre"]}
        )
        self.assertEqual(workflow["state"], "SHORT_PACKAGE_BLOCKED")
        self.assertIn("c_tyre", workflow["current_detail"])
        self.assertFalse(overview["ready"])

    def test_long_form_still_takes_every_step(self):
        workflow, overview = self.guidance({"chain_needed": True, "short_ready": True})
        self.assertEqual(workflow["current_title"], "Prepare Psychological Packaging Angles")
        self.assertFalse(overview["ready"])

    def test_with_both_lanes_packaging_is_done_only_when_both_are(self):
        accepted = {"status": "FINAL_PACKAGING_APPROVED", "ready": True}
        from unittest.mock import patch

        from experiment_ui import server

        with (
            patch.object(server, "short_package_lane_state", return_value={"chain_needed": True, "short_ready": False}),
            patch.object(server, "final_packaging_gate_state", return_value=accepted),
        ):
            self.assertFalse(server.final_packaging_overview(package_validation_ready=True)["ready"])


class ThumbnailUploadStateTests(unittest.TestCase):
    def test_each_packaged_video_shows_its_prompt_and_upload(self):
        from unittest.mock import patch

        from experiment_ui import server

        rows = [
            {"video_id": "c1:short", "uploaded": True, "upload": {"image_sha256": "abcdef1234567890"}, "prompt": "P"},
            {"video_id": "c2:long_form", "uploaded": False, "upload": None, "prompt": "Q"},
        ]
        with patch.object(server.thumbnail_upload, "items", return_value=rows):
            state = server.thumbnail_uploads_state()
        self.assertIn("video_id=c1%3Ashort", state[0]["image_url"])
        self.assertIsNone(state[1]["image_url"])


class BlockedCheckIsVisibleTests(unittest.TestCase):
    def test_a_blocked_pre_render_check_says_what_and_why(self):
        """D-194: it showed "Waiting for the next ready production step"."""
        from unittest.mock import patch

        from experiment_ui import server

        blocked = {"status": "BLOCKED", "items": [{"status": "BLOCKED", "errors": ["NO_EXPLICIT_PAYOFF_OR_RESOLUTION_BEAT"]}]}
        done = {"status": "COMPLETE", "complete": True}
        with ShortPackagingPathTests.patched_upstream(self), \
                patch.object(server, "short_package_lane_state", return_value={"chain_needed": False, "short_ready": True}), \
                patch.object(server, "format_artifact_state", return_value={"plans_ready": True, "format_gate": done}), \
                patch.object(server, "voice_performance_artifact_state", return_value={"specs_ready": True, "performance_gate": done}), \
                patch.object(server, "pre_render_engagement_snapshot", return_value=blocked):
            workflow = server.workflow_guidance({})
        self.assertEqual(workflow["state"], "PRE_RENDER_CHECK_BLOCKED")
        self.assertIn("no explicit payoff or resolution beat", workflow["current_detail"])


if __name__ == "__main__":
    unittest.main()
