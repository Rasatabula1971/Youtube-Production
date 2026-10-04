from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import gate_autopilot as autopilot

AUTO_ALL = {"reviewer_id": "gate-policy-auto", "gates": {g: "AUTO_IF_CLEAN" for g in autopilot.RUNNERS}}
PACKAGING = {
    "title_angles": ["curiosity", "stakes", "unexpected", "mystery", "payoff"],
    "short_title_contract": {"max_words": 7, "max_chars": 48},
    "long_title_contract": {"max_words": 10, "max_chars": 70},
}


class Recorder:
    """A stand-in for the server module: snapshots in, decisions recorded."""

    def __init__(self, **snapshots):
        self.calls: list[tuple[str, dict, str | None]] = []
        self.snapshots = snapshots
        self.refuse: set[str] = set()

    def __getattr__(self, name):
        if name.startswith("apply_"):
            def apply(**kwargs):
                if name in self.refuse:
                    raise ValueError("not prepared or is stale")
                self.calls.append((name, kwargs, os.environ.get(autopilot.REVIEWER_ENV)))
            return apply
        if name in self.snapshots:
            return lambda: self.snapshots[name]
        raise AttributeError(name)


def frame(frame_id, **proposal):
    base = {"observation": "A gloved hand turns a wheel nut.", "confidence": "HIGH", "uncertainty": ""}
    base.update(proposal)
    return {"frame_id": frame_id, "decision": "PENDING", "proposal": base, "proposal_error": None}


def title(fmt, angle, text, refs=("claim.1",)):
    return {"title_id": f"{fmt}-{angle}", "title_text": text, "psychological_angle": angle,
            "evidence_refs": list(refs)}


class GateAutopilotTests(unittest.TestCase):
    def test_human_gate_is_never_decided(self):
        control = Recorder(format_gate_snapshot={"plans": [{"concept_id": "c1", "decision": "PENDING"}]})
        policy = {"gates": {"format": "HUMAN"}}
        outcome = autopilot.decide("HUMAN_FORMAT_GATE", control, policy)
        self.assertEqual(outcome["decided"], 0)
        self.assertEqual(control.calls, [])

    def test_unlisted_and_unknown_states_are_left_alone(self):
        control = Recorder()
        for state in ("HUMAN_SCRIPT_GATE", "HUMAN_CONCEPT_GATE", "HUMAN_VISUAL_RIGHTS_GATE",
                      "HUMAN_FINAL_PACKAGING_GATE", "HUMAN_FINAL_EXPORT_GATE", "HUMAN_PUBLISH_GATE", None):
            self.assertEqual(autopilot.decide(state, control, AUTO_ALL)["decided"], 0)
        self.assertEqual(control.calls, [])

    def test_vision_accepts_confident_frames_and_holds_the_rest(self):
        packet = {"video_id": "v1", "frames": [
            frame("f1"),
            frame("f2", confidence="MODERATE"),
            frame("f3", confidence="LOW"),
            frame("f4", uncertainty="text partly hidden"),
            {"frame_id": "f5", "decision": "PENDING", "proposal": None, "proposal_error": "ollama down"},
            {**frame("f6"), "decision": "ACCEPT"},
        ]}
        control = Recorder(vision_review_snapshot={"packets": [packet]})
        outcome = autopilot.decide("HUMAN_VISION_GATE", control, AUTO_ALL)
        self.assertEqual(outcome["decided"], 2)
        self.assertEqual([c[1]["frame_id"] for c in control.calls], ["f1", "f2"])
        self.assertEqual(len(outcome["held"]), 3)
        self.assertTrue(all(c[2] == "gate-policy-auto" for c in control.calls))

    def test_reviewer_id_is_restored_after_deciding(self):
        os.environ[autopilot.REVIEWER_ENV] = "me"
        self.addCleanup(os.environ.pop, autopilot.REVIEWER_ENV, None)
        control = Recorder(vision_review_snapshot={"packets": [{"video_id": "v", "frames": [frame("f1")]}]})
        autopilot.decide("HUMAN_VISION_GATE", control, AUTO_ALL)
        self.assertEqual(os.environ[autopilot.REVIEWER_ENV], "me")

    def test_analysis_holds_low_confidence_and_unresolved_evidence(self):
        good = {"item_id": "a", "video_id": "v", "decision": "PENDING", "confidence": "HIGH",
                "evidence_refs": ["e1"], "supporting_evidence": [{"evidence_id": "e1"}]}
        low = {**good, "item_id": "b", "confidence": "LOW"}
        unresolved = {**good, "item_id": "c", "evidence_refs": ["e1", "e2"]}
        none = {**good, "item_id": "d", "supporting_evidence": []}
        control = Recorder(human_analysis_review_snapshot={"items": [good, low, unresolved, none]})
        outcome = autopilot.decide("HUMAN_ANALYSIS_GATE", control, AUTO_ALL)
        self.assertEqual([c[1]["item_id"] for c in control.calls], ["a"])
        self.assertEqual(control.calls[0][1]["decision"], "ACCEPT")
        self.assertTrue(control.calls[0][1]["note"].startswith(autopilot.NOTE))
        self.assertEqual(len(outcome["held"]), 3)

    def test_title_direction_picks_first_angle_that_fits_each_contract(self):
        concept = {"concept_id": "c1", "decision": "PENDING", "titles": {
            "short": [
                title("short", "stakes", "Your wheel is lying to you"),
                title("short", "curiosity", "This four gram weight decides whether your whole car shakes at speed"),
                title("short", "unexpected", "Four grams", refs=()),
            ],
            "long_form": [title("long_form", "payoff", "Why 4 grams makes your steering wheel shake")],
        }}
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "packaging_config.json"
            config.write_text(json.dumps(PACKAGING), encoding="utf-8")
            control = Recorder(title_direction_gate_snapshot={"concepts": [concept]})
            control.PACKAGING_CONFIG_FILE = config
            outcome = autopilot.decide("HUMAN_TITLE_DIRECTION_GATE", control, AUTO_ALL)
        self.assertEqual(outcome["decided"], 1)
        selected = control.calls[0][1]["selected_titles"]
        # curiosity comes first but is too long; stakes is next and fits.
        self.assertEqual(selected["short"], {"title_id": "short-stakes"})
        self.assertEqual(selected["long_form"], {"title_id": "long_form-payoff"})

    def test_title_direction_holds_concept_when_a_format_has_no_fitting_title(self):
        concept = {"concept_id": "c1", "decision": "PENDING", "titles": {
            "short": [title("short", "stakes", "x " * 30)],
            "long_form": [title("long_form", "payoff", "Fine long title here")],
        }}
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "packaging_config.json"
            config.write_text(json.dumps(PACKAGING), encoding="utf-8")
            control = Recorder(title_direction_gate_snapshot={"concepts": [concept]})
            control.PACKAGING_CONFIG_FILE = config
            outcome = autopilot.decide("HUMAN_TITLE_DIRECTION_GATE", control, AUTO_ALL)
        self.assertEqual(outcome["decided"], 0)
        self.assertEqual(control.calls, [])
        self.assertIn("no title fits", outcome["held"][0])

    def test_format_holds_overlap_and_inseparable_branches(self):
        clean = {"concept_id": "c1", "decision": "PENDING", "source_overlap": {"matches": []},
                 "branch_separation": {"identical": False, "truncation": False}}
        overlap = {**clean, "concept_id": "c2", "source_overlap": {"matches": [{"word_count": 9}]}}
        truncated = {**clean, "concept_id": "c3", "branch_separation": {"truncation": True}}
        done = {**clean, "concept_id": "c4", "decision": "ACCEPT"}
        control = Recorder(format_gate_snapshot={"plans": [clean, overlap, truncated, done]})
        outcome = autopilot.decide("HUMAN_FORMAT_GATE", control, AUTO_ALL)
        self.assertEqual([c[1]["concept_id"] for c in control.calls], ["c1"])
        self.assertEqual(len(outcome["held"]), 2)

    def test_performance_accepts_validated_specs(self):
        specs = [{"concept_id": "c1", "format": "short", "decision": "PENDING"},
                 {"concept_id": "c1", "format": "long", "decision": "REWORK"}]
        control = Recorder(performance_gate_snapshot={"specs": specs})
        outcome = autopilot.decide("HUMAN_PERFORMANCE_GATE", control, AUTO_ALL)
        self.assertEqual(outcome["decided"], 1)
        self.assertEqual(control.calls[0][1]["format"], "short")

    def test_preview_needs_audio_and_a_clean_engagement_check(self):
        items = [
            {"concept_id": "c1", "format": "short", "decision": "PENDING", "audio_ready": True},
            {"concept_id": "c1", "format": "long", "decision": "PENDING", "audio_ready": True},
            {"concept_id": "c2", "format": "short", "decision": "PENDING", "audio_ready": False},
        ]
        engagement = {"items": [
            {"concept_id": "c1", "format": "short", "status": "PASS", "warnings": []},
            {"concept_id": "c1", "format": "long", "status": "PASS",
             "warnings": ["LONG_FORM_HAS_LOW_STRUCTURAL_VARIETY"]},
            {"concept_id": "c2", "format": "short", "status": "PASS", "warnings": []},
        ]}
        control = Recorder(narration_preview_gate_snapshot={"items": items},
                           pre_render_engagement_snapshot=engagement)
        outcome = autopilot.decide("HUMAN_NARRATION_PREVIEW_GATE", control, AUTO_ALL)
        self.assertEqual(outcome["decided"], 1)
        self.assertEqual(control.calls[0][1]["decision"], "APPROVE_FINAL")
        self.assertEqual(len(outcome["held"]), 2)
        self.assertTrue(any("LOW_STRUCTURAL_VARIETY" in h for h in outcome["held"]))

    def test_a_refused_decision_holds_only_that_item(self):
        control = Recorder(format_gate_snapshot={"plans": [
            {"concept_id": "c1", "decision": "PENDING"}, {"concept_id": "c2", "decision": "PENDING"}]})
        control.refuse.add("apply_format_gate_action")
        outcome = autopilot.decide("HUMAN_FORMAT_GATE", control, AUTO_ALL)
        self.assertEqual(outcome["decided"], 0)
        self.assertEqual(len(outcome["held"]), 2)
        self.assertIn("not decided automatically", outcome["held"][0])

    def test_shipped_policy_is_auto_for_every_runner(self):
        policy = autopilot.load_policy()
        self.assertEqual(set(policy["gates"]), set(autopilot.RUNNERS))
        self.assertTrue(all(mode == "AUTO_IF_CLEAN" for mode in policy["gates"].values()))

    def test_missing_policy_file_means_every_gate_is_human(self):
        policy = autopilot.load_policy(Path("/nonexistent/gate_policy.json"))
        control = Recorder(performance_gate_snapshot={"specs": [
            {"concept_id": "c1", "format": "short", "decision": "PENDING"}]})
        self.assertEqual(autopilot.decide("HUMAN_PERFORMANCE_GATE", control, policy)["decided"], 0)


class FakeBudget:
    def __init__(self, committed=0.0, confirmed=True, target=5.0, ceiling=10.0):
        self.committed, self.confirmed, self.target, self.ceiling = committed, confirmed, target, ceiling

    @staticmethod
    def video_id(concept_id, fmt):
        return f"{concept_id}:{fmt}"

    def summary(self, video):
        return {"video_id": video, "committed_usd": self.committed, "confirmed_by_human": self.confirmed,
                "target_usd": self.target, "ceiling_usd": self.ceiling}


class PhaseBTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.production = Path(tmp.name)

    def write(self, name, payload):
        (self.production / name).write_text(json.dumps(payload), encoding="utf-8")

    def control(self, budget=None, plan_approved=True, **snapshots):
        control = Recorder(**snapshots)
        control.PRODUCTION_DIR = self.production
        control.video_budget = budget or FakeBudget()
        approvals = []
        control.visual_plan_review = SimpleNamespace(
            apply_action=lambda **kw: approvals.append(("visual_plan", kw)),
            is_approved=lambda concept_id, fmt: plan_approved,
        )
        control.narration_final_review = SimpleNamespace(
            apply_action=lambda **kw: approvals.append(("final_audio", kw)))
        control.module_calls = approvals
        return control

    def ready_narration(self, verified=True, voice=True):
        self.write("narration_render_config.json", {"provider_contract": {"schema_verified": verified}})
        self.write("voice_performance_config.json", {"voice_identity": {
            "voice_id": "science-inside" if voice else None, "license_reference": "LIC-1" if voice else None}})

    def spend_item(self, worst):
        return {"concept_id": "c1", "format": "long", "decision": "PENDING", "worst_case_estimate_usd": worst,
                "required_accept_criteria": ["provider_quote_is_current", "worst_case_cost_is_accepted"]}

    def test_spend_within_target_is_accepted_with_every_criterion(self):
        self.ready_narration()
        control = self.control(budget=FakeBudget(committed=1.0),
                               narration_spend_gate_snapshot={"items": [self.spend_item(3.5)]})
        outcome = autopilot.decide("HUMAN_NARRATION_SPEND_GATE", control, AUTO_ALL)
        self.assertEqual(outcome["decided"], 1)
        call = control.calls[0][1]
        self.assertEqual(call["decision"], "ACCEPT")
        self.assertTrue(all(call["criteria"].values()))
        self.assertEqual(len(call["criteria"]), 2)

    def test_spend_above_target_or_unconfirmed_budget_is_held(self):
        self.ready_narration()
        for budget, phrase in ((FakeBudget(committed=2.0), "above the $5.00 target"),
                               (FakeBudget(confirmed=False), "not confirmed")):
            control = self.control(budget=budget, narration_spend_gate_snapshot={"items": [self.spend_item(3.5)]})
            outcome = autopilot.decide("HUMAN_NARRATION_SPEND_GATE", control, AUTO_ALL)
            self.assertEqual(outcome["decided"], 0)
            self.assertIn(phrase, outcome["held"][0])

    def test_spend_needs_verified_provider_voice_licence_and_visual_plan(self):
        cases = (
            (dict(verified=False), True, "contract is not verified"),
            (dict(voice=False), True, "voice and its licence"),
            ({}, False, "visual plan is not approved"),
        )
        for setup, plan_approved, phrase in cases:
            self.ready_narration(**setup)
            control = self.control(plan_approved=plan_approved,
                                   narration_spend_gate_snapshot={"items": [self.spend_item(1.0)]})
            outcome = autopilot.decide("HUMAN_NARRATION_SPEND_GATE", control, AUTO_ALL)
            self.assertEqual(outcome["decided"], 0, phrase)
            self.assertIn(phrase, outcome["held"][0])

    def test_visual_spend_needs_a_verified_priced_provider(self):
        item = {"concept_id": "c1", "format": "long", "gap_plan_file": "g.json",
                "hero_candidates": [{"shot_id": "s1"}, {"shot_id": "s2"}], "decisions": {"s2": {}}}
        self.write("visual_provider_config.json", {"active_provider": "", "variants_per_shot": 2, "providers": {}})
        control = self.control(visual_spend_review_snapshot={"items": [item]})
        outcome = autopilot.decide("HUMAN_VISUAL_SPEND_GATE", control, AUTO_ALL)
        self.assertEqual(outcome["decided"], 0)
        self.assertIn("no verified image provider", outcome["held"][0])

        self.write("visual_provider_config.json", {"active_provider": "p", "variants_per_shot": 2, "providers": {
            "p": {"contract_verified": True, "price_per_image_usd": 0.04}}})
        control = self.control(visual_spend_review_snapshot={"items": [item]})
        outcome = autopilot.decide("HUMAN_VISUAL_SPEND_GATE", control, AUTO_ALL)
        self.assertEqual(outcome["decided"], 1)
        call = control.calls[0][1]
        self.assertEqual((call["shot_id"], call["decision"], call["max_cost_usd"]), ("s1", "AUTHORIZE_GENERATION", 0.08))

    def test_visual_plan_holds_errors_untimed_shots_and_over_budget(self):
        items = [
            {"concept_id": "c1", "format": "long", "decision": "PENDING", "untimed_shots": 0, "budget": {}},
            {"concept_id": "c2", "format": "long", "decision": "BLOCKED", "error": "no storyboard"},
            {"concept_id": "c3", "format": "long", "decision": "PENDING", "untimed_shots": 2, "budget": {}},
            {"concept_id": "c4", "format": "long", "decision": "PENDING", "budget": {"over_target": True}},
            {"concept_id": "c5", "format": "long", "decision": "APPROVE_VISUAL_PLAN"},
        ]
        control = self.control(visual_plan_gate_state={"items": items})
        outcome = autopilot.decide("HUMAN_VISUAL_PLAN_GATE", control, AUTO_ALL)
        self.assertEqual(outcome["decided"], 1)
        self.assertEqual(control.module_calls[0][1]["concept_id"], "c1")
        self.assertEqual(len(outcome["held"]), 3)

    def test_final_audio_approves_qc_passed_items(self):
        control = self.control(final_audio_gate_state={"items": [
            {"concept_id": "c1", "format": "short", "decision": "PENDING"},
            {"concept_id": "c1", "format": "long", "decision": "APPROVE_FINAL_AUDIO"}]})
        outcome = autopilot.decide("HUMAN_FINAL_AUDIO_GATE", control, AUTO_ALL)
        self.assertEqual(outcome["decided"], 1)
        self.assertEqual(control.module_calls[0][1]["decision"], "APPROVE_FINAL_AUDIO")

    def test_candidates_select_first_eligible_gap_when_none_and_hold_editorial(self):
        shots = [
            {"shot_id": "s1", "candidates": [
                {"candidate_id": "y1", "state": "HUMAN_REVIEW_REQUIRED"},
                {"candidate_id": "p1", "state": "ELIGIBLE"}, {"candidate_id": "p2", "state": "ELIGIBLE"}]},
            {"shot_id": "s2", "candidates": [{"candidate_id": "y2", "state": "HUMAN_REVIEW_REQUIRED"}]},
            {"shot_id": "s3", "candidates": [{"candidate_id": "b1", "state": "BLOCKED"}]},
            {"shot_id": "s4", "candidates": []},
        ]
        packet = {"concept_id": "c1", "format": "long", "result_file": "r.json", "shots": shots,
                  "decisions": {"s4": {"action": "SELECT"}}, "stale_shot_ids": []}
        control = self.control(visual_candidate_review_snapshot={"packets": [packet]})
        outcome = autopilot.decide("HUMAN_VISUAL_CANDIDATE_GATE", control, AUTO_ALL)
        calls = [(c[1]["shot_id"], c[1]["action"], c[1].get("candidate_id")) for c in control.calls]
        self.assertEqual(calls, [("s1", "SELECT", "p1"), ("s3", "NEEDS_BETTER_VISUAL", None)])
        self.assertEqual(len(outcome["held"]), 1)
        self.assertIn("editorial", outcome["held"][0])

    def test_candidates_with_stale_results_are_held(self):
        packet = {"concept_id": "c1", "format": "long", "result_file": "r.json", "decisions": {},
                  "shots": [{"shot_id": "s1", "candidates": [{"candidate_id": "p", "state": "ELIGIBLE"}]}],
                  "stale_shot_ids": ["s1"]}
        control = self.control(visual_candidate_review_snapshot={"packets": [packet]})
        self.assertEqual(autopilot.decide("HUMAN_VISUAL_CANDIDATE_GATE", control, AUTO_ALL)["decided"], 0)

    def test_rough_cut_and_edit_preview(self):
        control = self.control(
            visual_rough_cut_review_snapshot={"items": [
                {"rough_cut_file": "a.json", "decision": None, "review_current": False, "summary": {"placeholders": 2}},
                {"rough_cut_file": "b.json", "decision": {"decision": "APPROVE_WITH_GAPS"}, "review_current": True}]},
            edit_preview_review_snapshot={"items": [
                {"result_file": "e1.json", "decision": "PENDING", "preview_file": "p.mp4", "placeholder_segments": 1},
                {"result_file": "e2.json", "decision": "PENDING", "preview_file": None}]},
        )
        rough = autopilot.decide("HUMAN_ROUGH_CUT_GATE", control, AUTO_ALL)
        preview = autopilot.decide("HUMAN_EDIT_PREVIEW_GATE", control, AUTO_ALL)
        self.assertEqual(rough["decided"], 1)
        self.assertEqual(control.calls[0][1]["decision"], "APPROVE_WITH_GAPS")
        self.assertEqual(preview["decided"], 1)
        self.assertEqual(control.calls[1][1]["decision"], "APPROVE_EDIT_DIRECTION")
        self.assertIn("missing", preview["held"][0])

    def test_rights_gate_always_stays_human(self):
        self.assertNotIn("HUMAN_VISUAL_RIGHTS_GATE", autopilot.STATE_GATES)

    def test_shipped_budget_is_confirmed_at_five_and_ten(self):
        config = json.loads((Path(__file__).resolve().parent.parent / "production_engine"
                             / "video_budget_config.json").read_text(encoding="utf-8"))
        self.assertEqual((config["target_usd"], config["ceiling_usd"], config["confirmed_by_human"]),
                         (5.0, 10.0, True))


if __name__ == "__main__":
    unittest.main()
