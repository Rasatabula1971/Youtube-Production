from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import packaging_brief as brief


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class PackagingBriefTests(unittest.TestCase):
    def fixture(self, root: Path):
        scripts = root / "scripts"
        verified = root / "verified"
        reviewed = root / "reviewed"
        output = root / "briefs"

        concept = {
            "working_title": "Why Racing Brakes Behave Backwards",
            "premise": "Explain a counterintuitive braking effect.",
            "audience_promise": "Understand the system.",
            "viewer_problem": "Why do racing brakes need extreme heat?",
            "viewer_moment": "Watching a race and seeing glowing brakes.",
            "desired_outcome": "Understand why heat changes braking.",
            "human_framing": {
                "viewer_question": "Why do racing brakes seem wrong before they work?",
                "explanation_payoff": "Heat puts the system into its intended window.",
                "psychological_pull": {
                    "primary_pull": "CONTRADICTION",
                    "viewer_expectation": "Better brakes should work cold.",
                    "violation_or_tension": "The race brake can feel worse when cold.",
                    "stakes": "Cold grip changes the driver's braking margin.",
                    "information_gap": "Why is heat required?",
                    "desired_resolution": "Understand the intentional thermal tradeoff.",
                },
                "visual_opening_plan": {
                    "moments": [
                        {
                            "visual": "A glowing brake disc after a hard stop.",
                            "purpose": "Show the abnormal thermal condition.",
                        },
                        {
                            "visual": "Cold vs hot braking comparison.",
                            "purpose": "Create contrast.",
                        },
                        {
                            "visual": "Brake temperature trace.",
                            "purpose": "Reveal the mechanism.",
                        },
                    ],
                    "opening_narration_intent": "Start with the contradiction.",
                },
            },
        }
        claims = [
            {
                "claim_id": "clm001",
                "statement": "Brake temperature can exceed 500 C in racing conditions.",
                "role": "core",
            },
            {
                "claim_id": "clm002",
                "statement": "The friction system is designed around a hot operating window.",
                "role": "supporting",
            },
        ]
        bundle = {
            "artifact": "approved_script_bundle",
            "status": "READY_FOR_PRODUCTION",
            "concept_id": "c1",
            "title": "Internal Working Title",
            "accepted_claims": claims,
            "story_plan": {
                "story_question": "Why do racing brakes need heat to work correctly?",
                "payoff_intent": "Explain the thermal operating-window tradeoff.",
            },
            "channel_voice": {
                "profile": {
                    "audience": {"knowledge_level": "non_engineer"}
                }
            },
            "required_branches": ["short", "long_form"],
            "branch_scripts": {
                "short": {
                    "format": "short",
                    "title": "Internal Working Title",
                    "opening_hook": "Cold race brakes can be worse brakes.",
                    "opening_hook_mechanism": "CONTRADICTION",
                    "sections": [
                        {
                            "section_id": "s1",
                            "purpose": "Hook proof",
                            "narration": "Heat changes the system.",
                            "claim_ids": ["clm001"],
                        }
                    ],
                    "closing": "That heat is part of the design.",
                },
                "long_form": {
                    "format": "long_form",
                    "title": "Internal Working Title",
                    "opening_hook": "The brakes can look broken when they are simply cold.",
                    "opening_hook_mechanism": "CONTRADICTION",
                    "sections": [
                        {
                            "section_id": "l1",
                            "purpose": "Setup",
                            "narration": "Start with the cold-brake contradiction.",
                            "claim_ids": ["clm001"],
                        }
                    ],
                    "closing": "The apparent flaw is the tradeoff.",
                },
            },
        }
        script_path = write_json(
            scripts / "c1.approved_script.json",
            bundle,
        )
        research = {
            "artifact": "verified_research_package",
            "status": "READY_FOR_STORY_SCRIPT",
            "concept_id": "c1",
            "concept": concept,
            "sources": [
                {
                    "source_id": "src1",
                    "title": "Brake Technical Note",
                    "publisher": "Example Lab",
                    "source_type": "documentation",
                    "url": "https://example.com/brakes",
                }
            ],
            "claims": claims,
        }
        research_path = write_json(
            verified / "c1.verified_research_package.json",
            research,
        )
        reviewed_payload = {
            "artifact": "research_gate_reviewed",
            "concept_id": "c1",
            "accepted": claims,
            "rework": [],
            "rejected": [
                {
                    "claim_id": "clm999",
                    "statement": "These are the best brakes in the world.",
                    "research_gate": {
                        "note": "Unsupported superlative."
                    },
                }
            ],
        }
        reviewed_path = write_json(
            reviewed / "c1.research_gate_reviewed.json",
            reviewed_payload,
        )
        selection = {
            "artifact": "selected_title_direction",
            "concept_id": "c1",
            "decision": "ACCEPT",
            "selected_titles": {
                "short": {
                    "selected_title_id": "short-stakes",
                    "selected_title_text": "Why Cold Race Brakes Can Fail You",
                    "selected_psychological_angle": "stakes",
                    "selected_primary_driver": "danger_consequence",
                    "selected_secondary_driver": "curiosity_gap",
                    "core_claim": "Cold braking performance differs from the intended hot window.",
                    "evidence_refs": ["clm001", "clm002"],
                    "search_intent": "BROWSE",
                    "wording_edited": False,
                },
                "long_form": {
                    "selected_title_id": "long_form-curiosity",
                    "selected_title_text": "Why Racing Brakes Need So Much Heat",
                    "selected_psychological_angle": "curiosity",
                    "selected_primary_driver": "curiosity_gap",
                    "selected_secondary_driver": "specificity",
                    "core_claim": "Racing brakes are designed around a hot operating window.",
                    "evidence_refs": ["clm001", "clm002"],
                    "search_intent": "HYBRID",
                    "wording_edited": False,
                },
            },
        }
        selection_file = write_json(
            root / "selected_title_directions.json",
            {
                "artifact": "selected_title_directions",
                "status": "TITLE_DIRECTION_SELECTED",
                "selected": [selection],
            },
        )
        return {
            "scripts": scripts,
            "verified": verified,
            "reviewed": reviewed,
            "briefs": output,
            "bundle": bundle,
            "script_path": script_path,
            "research_path": research_path,
            "reviewed_path": reviewed_path,
            "selection": selection,
            "selection_file": selection_file,
        }

    def patches(self, fx):
        return (
            patch.object(brief, "APPROVED_SCRIPTS_DIR", fx["scripts"]),
            patch.object(brief, "VERIFIED_RESEARCH_DIR", fx["verified"]),
            patch.object(brief, "REVIEWED_RESEARCH_DIR", fx["reviewed"]),
            patch.object(brief, "BRIEF_DIR", fx["briefs"]),
            patch.object(brief, "TITLE_SELECTION_FILE", fx["selection_file"]),
            patch.object(
                brief,
                "_approved_bundle_is_current",
                return_value=True,
            ),
            patch.object(
                brief,
                "title_direction_snapshot",
                return_value={
                    "status": "TITLE_DIRECTION_SELECTED",
                    "ready": True,
                    "concepts": [
                        {"concept_id": "c1", "decision": "ACCEPT"}
                    ],
                },
            ),
        )

    def test_builds_format_specific_brief_and_viewer_promise(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = self.fixture(Path(tmp))
            ps = self.patches(fx)
            with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5], ps[6]:
                result = brief.build_brief(
                    script_path=fx["script_path"],
                    bundle=fx["bundle"],
                    selection=fx["selection"],
                    fmt="short",
                )

        self.assertEqual(result["status"], "PACKAGING_BRIEF_READY")
        self.assertEqual(result["video_id"], "c1:short")
        self.assertEqual(result["search_vs_browse_intent"], "BROWSE")
        self.assertEqual(
            result["viewer_promise_contract"]["promise_question"],
            "Why do racing brakes need heat to work correctly?",
        )
        self.assertIn(
            "expects to discover",
            result["viewer_promise_contract"]["viewer_expectation"],
        )
        self.assertEqual(
            result["strongest_visual_event"],
            "A glowing brake disc after a hard stop.",
        )
        self.assertEqual(result["approved_numbers"][0]["value"], "500")
        self.assertEqual(
            result["prohibited_or_unsupported_claims"][0]["claim_id"],
            "clm999",
        )
        self.assertEqual(result["generation_policy"]["model_calls"], 0)

    def test_short_and_long_keep_separate_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = self.fixture(Path(tmp))
            ps = self.patches(fx)
            with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5], ps[6]:
                short = brief.build_brief(
                    script_path=fx["script_path"],
                    bundle=fx["bundle"],
                    selection=fx["selection"],
                    fmt="short",
                )
                long_form = brief.build_brief(
                    script_path=fx["script_path"],
                    bundle=fx["bundle"],
                    selection=fx["selection"],
                    fmt="long_form",
                )

        self.assertEqual(short["search_vs_browse_intent"], "BROWSE")
        self.assertEqual(long_form["search_vs_browse_intent"], "HYBRID")
        self.assertNotEqual(short["video_id"], long_form["video_id"])

    def test_unknown_selected_evidence_ref_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = self.fixture(Path(tmp))
            fx["selection"]["selected_titles"]["short"][
                "evidence_refs"
            ] = ["invented"]
            ps = self.patches(fx)
            with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5], ps[6]:
                with self.assertRaisesRegex(ValueError, "UNSUPPORTED_CLAIM"):
                    brief.build_brief(
                        script_path=fx["script_path"],
                        bundle=fx["bundle"],
                        selection=fx["selection"],
                        fmt="short",
                    )

    def test_research_and_script_claim_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = self.fixture(Path(tmp))
            research = json.loads(
                fx["research_path"].read_text(encoding="utf-8")
            )
            research["claims"][0]["statement"] = "Changed claim."
            write_json(fx["research_path"], research)
            ps = self.patches(fx)
            with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5], ps[6]:
                with self.assertRaisesRegex(ValueError, "EVIDENCE_CONFLICT"):
                    brief.build_brief(
                        script_path=fx["script_path"],
                        bundle=fx["bundle"],
                        selection=fx["selection"],
                        fmt="short",
                    )

    def test_missing_hook_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = self.fixture(Path(tmp))
            fx["bundle"]["branch_scripts"]["short"]["opening_hook"] = ""
            ps = self.patches(fx)
            with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5], ps[6]:
                with self.assertRaisesRegex(ValueError, "MISSING_OPENING_HOOK"):
                    brief.build_brief(
                        script_path=fx["script_path"],
                        bundle=fx["bundle"],
                        selection=fx["selection"],
                        fmt="short",
                    )

    def test_brief_currentness_breaks_when_evidence_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = self.fixture(Path(tmp))
            ps = self.patches(fx)
            with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5], ps[6]:
                built = brief.build_brief(
                    script_path=fx["script_path"],
                    bundle=fx["bundle"],
                    selection=fx["selection"],
                    fmt="short",
                )
                path = write_json(
                    fx["briefs"] / "c1.short.packaging_brief.json",
                    built,
                )
                self.assertIsNotNone(brief.brief_is_current(path))
                research = json.loads(
                    fx["research_path"].read_text(encoding="utf-8")
                )
                research["sources"][0]["publisher"] = "Changed Publisher"
                write_json(fx["research_path"], research)
                self.assertIsNone(brief.brief_is_current(path))


if __name__ == "__main__":
    unittest.main()
