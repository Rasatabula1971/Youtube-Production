from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

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
        for state in ("HUMAN_SCRIPT_GATE", "HUMAN_CONCEPT_GATE", "HUMAN_NARRATION_SPEND_GATE", None):
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

    def test_shipped_policy_is_auto_for_phase_a_gates_only(self):
        policy = autopilot.load_policy()
        self.assertEqual(set(policy["gates"]), set(autopilot.RUNNERS))
        self.assertTrue(all(mode == "AUTO_IF_CLEAN" for mode in policy["gates"].values()))

    def test_missing_policy_file_means_every_gate_is_human(self):
        policy = autopilot.load_policy(Path("/nonexistent/gate_policy.json"))
        control = Recorder(performance_gate_snapshot={"specs": [
            {"concept_id": "c1", "format": "short", "decision": "PENDING"}]})
        self.assertEqual(autopilot.decide("HUMAN_PERFORMANCE_GATE", control, policy)["decided"], 0)


if __name__ == "__main__":
    unittest.main()
