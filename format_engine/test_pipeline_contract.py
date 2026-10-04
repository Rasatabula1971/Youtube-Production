"""Cross-stage contract test.

Walks one accepted concept through Packaging, Research, Story / Script and
Format using each stage's real config and pure functions, so that the
artifact one stage writes is the literal input the next stage reads.

Every stage was built and tested in isolation. This is the only test that
exercises the seams between them.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
for stage in (
    "transformation_engine",
    "packaging_engine",
    "research_engine",
    "story_script_engine",
):
    stage_dir = PROJECT_ROOT / stage
    if str(stage_dir) not in sys.path:
        sys.path.insert(0, str(stage_dir))

import concept_gate
import format_review
import packaging_gate
import research_gate
import script_review

import format_engine
import packaging_engine
import research_engine
import story_plan_engine
import story_script_engine

PROMISE = (
    "This video helps curious automotive viewers understand why racing brakes "
    "need extreme heat so they can make sense of the design tradeoff."
)


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def accepted_concept_candidates() -> dict:
    return {
        "artifact": "concept_candidates",
        "concepts": [
            {
                "concept_id": "c1",
                "mechanism_id": "curiosity_gap",
                "mechanism_label": "Curiosity",
                "working_title": "Why Racing Brakes Behave Backwards",
                "premise": "Investigate a counterintuitive brake constraint.",
                "audience_promise": "Explain the hidden reason.",
                "viewer_problem": (
                    "Why do racing brakes need conditions that seem wrong for road cars?"
                ),
                "viewer_moment": (
                    "Trying to understand a surprising race-car engineering tradeoff."
                ),
                "desired_outcome": "Understand why temperature changes the brake design.",
                "human_framing": {
                    "hook_experience": {
                        "archetype": "EXPECTATION_VIOLATION",
                        "description": "A racing brake appears to need the very heat a road brake tries to avoid.",
                    },
                    "viewer_question": "Why do racing brakes need conditions that seem wrong for road cars?",
                    "psychological_pull": {
                        "primary_pull": "CONTRADICTION",
                        "viewer_expectation": "Better brakes should work best when they are cool.",
                        "violation_or_tension": "The racing system becomes useful in extreme heat.",
                        "stakes": "The wrong mental model makes the design look backwards.",
                        "information_gap": "Why does heat change the target?",
                        "desired_resolution": "Understand the engineering tradeoff behind the apparent contradiction.",
                    },
                    "explanation_payoff": "The viewer understands why the race-brake design target differs from a road car.",
                    "visual_opening_plan": {
                        "moments": [
                            {"visual": "Show a normal road-brake temperature state.", "purpose": "Establish expectation."},
                            {"visual": "Cut to a glowing racing brake.", "purpose": "Create the contradiction."},
                            {"visual": "Freeze on the heat difference.", "purpose": "Hold the unanswered question."},
                        ],
                        "opening_narration_intent": "Road brakes hate this much heat. Racing brakes are built around it. Why?",
                    },
                    "drama": {
                        "capacity": 7,
                        "target": 6,
                        "source": "A safety-critical component appears to need an extreme condition normally treated as harmful.",
                        "constraint": "Do not claim heat is always beneficial or that all race brakes behave identically.",
                        "hook_level": 6,
                        "story_curve": [6, 5, 7, 5],
                        "tempo_curve": [6, 4, 7, 5],
                    },
                },
                "content_gap": {
                    "hypothesis": "Explanations show hot brakes without the consequence.",
                    "evidence_status": "HYPOTHESIS",
                    "evidence_basis": [],
                },
                "channel_fit": {
                    "status": "FIT",
                    "rationale": "Automotive engineering explainer.",
                },
                "title_clarity_test": {
                    "options": [
                        "Why Racing Brakes Behave Backwards",
                        "Why F1 Brakes Hate Normal Temperatures",
                        "The Brake Problem Road Cars Never Face",
                    ],
                    "result": "PASS",
                    "rationale": "Clear problem across three title framings.",
                },
                "format_intent": "either",
                "mechanism_application": "One unanswered question.",
                "transformation_method": "Different system and research path.",
                "research_questions": [
                    "What thermal constraints matter?",
                    "What rules apply?",
                ],
                "source_dependency_test": {
                    "passes": True,
                    "source_assets_required": False,
                    "rationale": "Independent concept.",
                },
            }
        ],
    }


def package_candidate() -> dict:
    return {
        "package_id": "c1-pkg001",
        "title": "Why F1 Brakes Work Backwards",
        "thumbnail": {
            "message": "Race brake glowing beside road brake.",
            "visual_concept": "Split comparison showing different thermal states.",
            "text_overlay": "",
        },
        "opening_frame": {
            "purpose": "Immediately prove the temperature difference matters.",
            "visual_concept": "Glowing rotor close-up with temperature callout.",
        },
        "expected_viewer": "Curious automotive viewer",
        "awareness_level": "Knows race brakes are extreme but not why",
        "viewer_problem": (
            "Why do racing brakes need conditions that seem wrong for road cars?"
        ),
        "viewer_moment": (
            "Trying to understand a surprising race-car engineering tradeoff."
        ),
        "desired_outcome": "Understand why temperature changes the brake design.",
        "one_sentence_promise": PROMISE,
        "gap_positioning": "Focus on the design consequence of temperature.",
        "channel_fit_alignment": "Centered on automotive engineering explanation.",
        "core_promise": "Explain why race brakes need conditions road brakes cannot.",
        "curiosity_gap": "Why does the obvious road-car solution fail?",
        "expected_payoff": "Viewer understands the engineering tradeoff.",
        "format_intent": "long_form",
        "title_thumbnail_relationship": "Title asks why; thumbnail shows contrast.",
        "research_dependencies": [
            "Verify operating-temperature differences between race and road brakes."
        ],
    }



def title_candidates() -> dict:
    angles = ["curiosity", "stakes", "unexpected", "mystery", "payoff"]
    short_titles = {
        "curiosity": "Why Do F1 Brakes Need Heat?",
        "stakes": "Cold F1 Brakes Can Fail You",
        "unexpected": "F1 Brakes Hate Being Cold",
        "mystery": "Why Are F1 Brakes Glowing?",
        "payoff": "The Secret Is Brake Temperature",
    }
    long_titles = {
        "curiosity": "Why F1 Brakes Work Backwards",
        "stakes": "Why Cold F1 Brakes Can Ruin a Corner",
        "unexpected": "Why F1 Brakes Need the Heat Road Cars Avoid",
        "mystery": "Why Do F1 Brakes Need So Much Heat?",
        "payoff": "How Temperature Changes the Way F1 Brakes Work",
    }
    return {
        "short": [
            {
                "candidate_id": f"short-{angle}",
                "angle": angle,
                "title": short_titles[angle],
            }
            for angle in angles
        ],
        "long_form": [
            {
                "candidate_id": f"long-{angle}",
                "angle": angle,
                "title": long_titles[angle],
            }
            for angle in angles
        ],
    }


def all_true(criteria: list[str]) -> dict[str, bool]:
    return {criterion: True for criterion in criteria}


class PipelineContractTests(unittest.TestCase):
    """One concept, four seams, real configs, no model calls."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # ---- seam 3 → 4: Concept Gate → Packaging -------------------------------

    def concept_handoff(self) -> dict:
        config = concept_gate.load_config()
        candidates = accepted_concept_candidates()
        request = concept_gate.build_review_request(candidates, config)
        response = {
            "reviewer": "contract-test",
            "decisions": [
                {
                    "concept_id": item["concept_id"],
                    "decision": "ACCEPT",
                    "criteria": all_true(config["required_accept_criteria"]),
                    "note": "",
                }
                for item in request["items"]
            ],
            "overall_note": "",
        }
        _, handoff = concept_gate.apply_gate(candidates, request, response, config)
        self.assertEqual(handoff["status"], "READY_FOR_RESEARCH")
        self.assertEqual(handoff["concept_count"], 1)
        self.assertEqual(
            handoff["concepts"][0]["human_framing"]["drama"]["target"],
            6,
        )
        # A concept generated as 'either' leaves the gate with one format (D-132).
        self.assertEqual(handoff["concepts"][0]["format_intent"], "long_form")
        resolution = handoff["concepts"][0]["format_resolution"]
        self.assertEqual(resolution["requested_format_intent"], "either")
        self.assertEqual(resolution["decided_by"], "DEFAULT")
        return handoff

    # ---- seam 4 → 5: Packaging Gate → Research ------------------------------

    def research_handoff(self, concept_handoff: dict) -> dict:
        engine_config = packaging_engine.load_config()
        concept = concept_handoff["concepts"][0]
        request = packaging_engine.build_package_request(concept, engine_config)
        # Packages inherit the concept's resolved format.
        self.assertEqual(request["allowed_format_intents"], ["long_form"])
        result = packaging_engine.validate_response(
            {
                "concept_id": "c1",
                "titles": title_candidates(),
                "packages": [package_candidate()],
            },
            request,
            engine_config,
        )
        self.assertEqual(result["rejected"], [], result["rejected"])
        self.assertEqual(len(result["accepted"]), 1)
        accepted = result["accepted"][0]
        # The gate reads these; the engine must have attached them.
        self.assertEqual(accepted["concept_id"], "c1")
        self.assertIn("concept_context", accepted)
        self.assertIn("source_overlap", accepted)

        candidates = {"artifact": "package_candidates", "packages": [accepted]}
        gate_config = packaging_gate.load_config()
        gate_request = packaging_gate.build_review_request(candidates, gate_config)
        gate_response = {
            "reviewer": "contract-test",
            "decisions": [
                {
                    "package_id": item["package_id"],
                    "decision": "ACCEPT",
                    "criteria": all_true(gate_config["required_accept_criteria"]),
                    "note": "",
                    "selected_titles": {
                        "short": {
                            "candidate_id": "short-unexpected",
                            "title": "F1 Brakes Hate Being Cold",
                        },
                        "long_form": {
                            "candidate_id": "long-curiosity",
                            "title": "Why F1 Brakes Work Backwards",
                        },
                    },
                }
                for item in gate_request["items"]
            ],
            "overall_note": "",
        }
        _, handoff = packaging_gate.apply_gate(
            candidates, gate_request, gate_response, gate_config
        )
        self.assertEqual(handoff["concept_count"], 1)
        packaged = handoff["concepts"][0]
        self.assertEqual(packaged["packaging"]["one_sentence_promise"], PROMISE)
        self.assertEqual(packaged["packaging"]["format_intent"], "long_form")
        self.assertTrue(packaged["packaging"]["research_dependencies"])
        self.assertEqual(
            packaged["packaging"]["selected_titles"]["short"]["title"],
            "F1 Brakes Hate Being Cold",
        )
        self.assertEqual(
            packaged["packaging"]["selected_titles"]["long_form"]["title"],
            "Why F1 Brakes Work Backwards",
        )
        return handoff

    # ---- seam 5 → 6: Research Gate → Story / Script -------------------------

    def verified_research(self, research_handoff: dict) -> dict:
        engine_config = research_engine.load_config()
        concept = research_handoff["concepts"][0]
        plan = research_engine.build_research_plan(concept)
        question_ids = [item["question_id"] for item in plan["research_questions"]]
        # Concept questions and packaging dependencies both become questions.
        self.assertIn("rq001", question_ids)
        self.assertIn("pkgq001", question_ids)
        self.assertEqual(plan["packaging"]["one_sentence_promise"], PROMISE)
        self.assertEqual(plan["human_framing"]["drama"]["target"], 6)

        source = {
            "source_id": "src001",
            "title": "Technical Regulations",
            "publisher": "FIA",
            "url": "https://example.com/regulations",
            "source_type": "primary",
            "published_at": "",
            "accessed_at": "",
            "provenance_note": "Defines the technical rules.",
        }
        claims = [
            {
                "claim_id": f"clm{index:03d}",
                "statement": f"Finding {index} answers {question_id}.",
                "role": "core",
                "question_ids": [question_id],
                "evidence_links": [
                    {
                        "source_id": "src001",
                        "stance": "SUPPORTS",
                        "locator": f"Article {index}",
                        "evidence_note": "The regulation constrains the component.",
                        "evidence_quote": "The component shall be constrained.",
                    }
                ],
            }
            for index, question_id in enumerate(question_ids, start=1)
        ]
        draft = research_engine.validate_research_response(
            {"concept_id": "c1", "sources": [source], "claims": claims},
            plan,
            engine_config,
        )
        self.assertEqual(draft["rejected_claims"], [], draft["rejected_claims"])
        self.assertEqual(len(draft["claims"]), len(question_ids))
        # The script stage reads the package promise from concept.packaging.
        self.assertEqual(draft["concept"]["packaging"]["one_sentence_promise"], PROMISE)

        gate_config = research_gate.load_config()
        request = research_gate.build_review_request(draft, gate_config)
        response = {
            "concept_id": "c1",
            "reviewer": "contract-test",
            "decisions": [
                {
                    "claim_id": item["claim_id"],
                    "decision": "ACCEPT",
                    "criteria": all_true(gate_config["required_accept_criteria"]),
                    "note": "",
                }
                for item in request["items"]
            ],
            "overall_note": "",
        }
        _, verified = research_gate.apply_gate(draft, request, response, gate_config)
        self.assertEqual(verified["status"], "READY_FOR_STORY_SCRIPT")
        self.assertEqual(verified["unresolved_question_ids"], [])
        self.assertEqual(verified["concept"]["packaging"]["format_intent"], "long_form")
        self.assertEqual(verified["concept"]["format_intent"], "long_form")
        return verified

    # ---- seam 6 → 7: Script Gate → Format -----------------------------------

    def approved_script(self, verified: dict) -> Path:
        verified_path = write_json(
            self.root / "c1.verified_research_package.json", verified
        )
        story_request = story_plan_engine.build_story_plan_request(
            verified,
            verified_path,
        )
        self.assertEqual(
            story_request["package"]["title"],
            "Why Racing Brakes Behave Backwards",
        )
        self.assertEqual(story_request["package"]["one_sentence_promise"], PROMISE)
        self.assertEqual(
            story_request["psychology_contract"]["human_framing"]["drama"]["target"],
            6,
        )

        claim_ids = story_request["accepted_claim_ids"]
        story_response = {
            "concept_id": "c1",
            "title": "Why Racing Brakes Behave Backwards",
            "story_question": (
                "Why do racing brakes need conditions that seem wrong for road cars?"
            ),
            "opening_hook_intent": (
                "Open on the apparent contradiction and make the viewer want the mechanism."
            ),
            "viewer_state": {
                "awareness": "The viewer knows race brakes operate in extreme conditions.",
                "expectation": "Better brakes should behave like stronger road brakes.",
                "desired_resolution": "Understand why heat changes the design target.",
            },
            "opening_psychology": {
                "mechanism": "CONTRADICTION",
                "impact_intent": "State the apparent backwards behavior immediately.",
                "justification_intent": (
                    "Move directly into verified constraints that explain it."
                ),
                "claim_ids": [],
            },
            "beats": [
                {
                    "beat_id": "b1",
                    "role": "SETUP",
                    "purpose": "Establish the race-brake contradiction.",
                    "viewer_progress": "The viewer understands the puzzle.",
                    "claim_ids": [],
                    "transition_intent": (
                        "Move from the visible contradiction to the governing constraint."
                    ),
                    "psychology": {
                        "primary_mechanism": "CURIOSITY",
                        "viewer_expectation": (
                            "A stronger brake should simply work better."
                        ),
                        "cognitive_load_instruction": (
                            "Establish only the contradiction before explaining the mechanism."
                        ),
                        "tension_level": "HIGH",
                        "drama_level": 7,
                        "tempo_level": 7,
                        "open_loop_id": "main",
                        "loop_action": "OPEN",
                    },
                },
                {
                    "beat_id": "b2",
                    "role": "EXPLANATION",
                    "purpose": "Explain the verified constraint and temperature behavior.",
                    "viewer_progress": "The viewer understands the mechanism.",
                    "claim_ids": claim_ids[:1],
                    "transition_intent": (
                        "Use the mechanism to reframe heat as intentional."
                    ),
                    "psychology": {
                        "primary_mechanism": "CLARITY",
                        "viewer_expectation": "Heat should only be a problem to remove.",
                        "cognitive_load_instruction": (
                            "Explain one verified constraint before adding consequences."
                        ),
                        "tension_level": "MEDIUM",
                        "drama_level": 5,
                        "tempo_level": 4,
                        "open_loop_id": "main",
                        "loop_action": "ADVANCE",
                    },
                },
                {
                    "beat_id": "b3",
                    "role": "PAYOFF",
                    "purpose": "Resolve why the design only seems backwards.",
                    "viewer_progress": "The approved title promise is fulfilled.",
                    "claim_ids": claim_ids,
                    "transition_intent": (
                        "Close on the resolved engineering tradeoff."
                    ),
                    "psychology": {
                        "primary_mechanism": "PAYOFF",
                        "viewer_expectation": (
                            "The apparent contradiction should now have one coherent explanation."
                        ),
                        "cognitive_load_instruction": (
                            "Resolve the main question without introducing a new mechanism."
                        ),
                        "tension_level": "LOW",
                        "drama_level": 6,
                        "tempo_level": 5,
                        "open_loop_id": "main",
                        "loop_action": "PAYOFF",
                    },
                },
            ],
            "payoff_intent": (
                "Show that the apparently wrong behavior follows from verified constraints."
            ),
            "closing_intent": "Leave one clear mental model of the tradeoff.",
        }
        story_validation = story_plan_engine.validate_story_plan_response(
            story_response,
            story_request,
        )
        self.assertTrue(story_validation["valid"], story_validation["errors"])

        story_plan = {
            "artifact": "story_plan",
            "status": "STORY_PLAN_READY",
            **story_response,
            "package": story_request["package"],
            "concept": story_request["concept"],
            "accepted_claims": story_request["accepted_claims"],
            "accepted_claim_ids": story_request["accepted_claim_ids"],
            "psychology_contract": story_request["psychology_contract"],
            "validation": story_validation,
            "plan_provenance": {"request_sha256": "contract"},
        }
        story_plan_path = write_json(
            self.root / "c1.story_plan.json",
            story_plan,
        )

        approved_dir = self.root / "approved_scripts"
        review_requests = self.root / "script_review_requests"
        review_responses = self.root / "script_review_responses"
        approved_dir.mkdir()
        review_requests.mkdir()
        review_responses.mkdir()

        branch_drafts = {
            "long_form": {
                "opening_hook": (
                    "A road car would hate the conditions these brakes are built to need."
                ),
                "sections": [
                    {
                        "section_id": "lf1",
                        "source_story_beat_ids": ["b1"],
                        "purpose": "Establish the contradiction",
                        "psychology_mechanism": "CURIOSITY",
                        "reward_type": "NONE",
                        "narration": (
                            "At first glance, the race-car solution seems backwards."
                        ),
                        "claim_ids": [],
                    },
                    {
                        "section_id": "lf2",
                        "source_story_beat_ids": ["b2"],
                        "purpose": "Explain the verified constraint",
                        "psychology_mechanism": "CLARITY",
                        "reward_type": "PROGRESS",
                        "narration": (
                            "The verified constraint changes what the brake must tolerate."
                        ),
                        "claim_ids": claim_ids[:1],
                    },
                    {
                        "section_id": "lf3",
                        "source_story_beat_ids": ["b3"],
                        "purpose": "Deliver the full payoff",
                        "psychology_mechanism": "PAYOFF",
                        "reward_type": "NONE",
                        "narration": (
                            "Once the constraints are included, heat becomes part of "
                            "the design target rather than a contradiction."
                        ),
                        "claim_ids": claim_ids,
                    },
                ],
                "closing": (
                    "That is why the design looks wrong only until you see the "
                    "problem it is solving."
                ),
            },
            "short": {
                "opening_hook": "Race brakes can work worse when they are too cold.",
                "sections": [
                    {
                        "section_id": "sh1",
                        "source_story_beat_ids": ["b1", "b2"],
                        "purpose": "Hook plus immediate proof",
                        "psychology_mechanism": "EXPECTATION_VIOLATION",
                        "reward_type": "PROOF",
                        "narration": (
                            "The strange part is that heat is not just damage here."
                        ),
                        "claim_ids": claim_ids[:1],
                    },
                    {
                        "section_id": "sh2",
                        "source_story_beat_ids": ["b2"],
                        "purpose": "Fast mechanism reveal",
                        "psychology_mechanism": "CLARITY",
                        "reward_type": "REVEAL",
                        "narration": "The verified constraint changes the target.",
                        "claim_ids": claim_ids[:1],
                    },
                    {
                        "section_id": "sh3",
                        "source_story_beat_ids": ["b3"],
                        "purpose": "Fast payoff",
                        "psychology_mechanism": "PAYOFF",
                        "reward_type": "MICRO_PAYOFF",
                        "narration": (
                            "That is why race-brake behavior can look backwards."
                        ),
                        "claim_ids": claim_ids,
                    },
                ],
                "closing": "Heat is part of the solution, not just the problem.",
            },
        }

        with (
            patch.object(script_review, "APPROVED_DIR", approved_dir),
            patch.object(script_review, "REVIEW_REQUESTS_DIR", review_requests),
            patch.object(script_review, "RESPONSES_DIR", review_responses),
            patch.object(
                script_review,
                "SUMMARY_FILE",
                self.root / "script_summary.json",
            ),
        ):
            final_summary = None
            # One resolved format, so one script branch (D-132).
            self.assertEqual(
                story_script_engine.resolve_script_branches(
                    story_plan["package"]["format_intent"],
                    story_script_engine.load_script_psychology_config(),
                ),
                ["long_form"],
            )
            for fmt in ("long_form",):
                request = story_script_engine.build_script_request(
                    story_plan,
                    story_plan_path,
                    fmt,
                )
                self.assertEqual(request["package"]["one_sentence_promise"], PROMISE)
                self.assertEqual(request["accepted_claim_ids"], claim_ids)
                if fmt == "short":
                    self.assertEqual(
                        request["psychology_profile"]["hook_target_seconds"],
                        3,
                    )
                self.assertEqual(
                    request["package"]["title"],
                    "Why Racing Brakes Behave Backwards",
                )

                response = {
                    "concept_id": "c1",
                    "format": fmt,
                    "title": request["package"]["title"],
                    "opening_hook": branch_drafts[fmt]["opening_hook"],
                    "opening_hook_mechanism": "CONTRADICTION",
                    "opening_hook_claim_ids": [],
                    "sections": branch_drafts[fmt]["sections"],
                    "closing": branch_drafts[fmt]["closing"],
                }
                validation = story_script_engine.validate_script_response(
                    response,
                    request,
                )
                self.assertTrue(validation["valid"], validation["errors"])

                draft = {
                    **response,
                    "accepted_claims": request["accepted_claims"],
                    "package": request["package"],
                    "required_branches": request["required_branches"],
                    "story_plan": request["story_plan"],
                    "psychology_contract": request["psychology_contract"],
                    "psychology_profile": request["psychology_profile"],
                    "validation": validation,
                    "draft_provenance": {"request_sha256": "contract"},
                }
                draft_path = write_json(
                    self.root / f"c1.{fmt}.script_draft.json",
                    draft,
                )
                review_request = script_review.build_review_request(
                    draft,
                    draft_path,
                )
                request_path = write_json(
                    review_requests / f"c1.{fmt}.script_review_request.json",
                    review_request,
                )
                final_summary = script_review.apply_payload(
                    request_path,
                    {
                        "concept_id": "c1",
                        "format": fmt,
                        "reviewer": "contract-test",
                        "decision": "ACCEPT",
                        "criteria": all_true(list(script_review.CRITERIA)),
                        "note": "",
                    },
                )

        self.assertIsNotNone(final_summary)
        approved_path = Path(final_summary["approved_script"])
        self.assertTrue(approved_path.exists())
        bundle = json.loads(approved_path.read_text(encoding="utf-8"))
        self.assertEqual(sorted(bundle["branch_scripts"]), ["long_form"])
        return approved_path


    # ---- seam 7: Format Gate → Production -----------------------------------

    def approved_format_plan(self, approved_script_path: Path) -> dict:
        config = format_engine.load_config()
        approved = json.loads(approved_script_path.read_text(encoding="utf-8"))
        self.assertEqual(approved["script_gate"]["status"], "READY_FOR_PRODUCTION")

        request = format_engine.build_format_request(
            approved, approved_script_path, config
        )
        # One resolved format reaches Format as one production branch.
        self.assertEqual(request["required_branches"], ["long_form"])
        # The promise has now crossed four stages untouched.
        self.assertEqual(request["package"]["one_sentence_promise"], PROMISE)
        self.assertEqual(request["package"]["selected_titles"], {})
        self.assertEqual(
            request["package"]["title_role"],
            "INTERNAL_WORKING_TITLE",
        )
        self.assertEqual(
            request["branch_story_packages"]["long_form"]["title"],
            "Why Racing Brakes Behave Backwards",
        )
        self.assertEqual(
            request["script_section_ids_by_branch"]["long_form"],
            ["lf1", "lf2", "lf3"],
        )
        self.assertNotIn("short", request["script_section_ids_by_branch"])
        # This is the hash the Experiment UI uses to decide the request is current.
        self.assertEqual(
            request["request_provenance"]["approved_script_sha256"],
            format_engine.sha256_file(approved_script_path),
        )

        claim_ids = request["accepted_claim_ids"]

        def beat(beat_id, purpose, treatment, sections, claims):
            key = purpose.lower()
            drama = 7 if "hook" in key or "cold" in key else 8 if "reveal" in key else 6 if "payoff" in key or "close" in key else 5
            tempo = 7 if "hook" in key or "cold" in key else 6 if "reveal" in key else 4 if "payoff" in key or "close" in key else 5
            return {
                "beat_id": beat_id,
                "purpose": purpose,
                "treatment": treatment,
                "drama_level": drama,
                "tempo_level": tempo,
                "claim_ids": claims,
                "source_section_ids": sections,
            }

        response = {
            "concept_id": "c1",
            "branches": [
                {
                    "format": "long_form",
                    "duration_intent_seconds": 600,
                    "promise_delivery": "Full walk through the constraint and payoff.",
                    "payoff": "Viewer understands the whole tradeoff.",
                    "beats": [
                        beat("lf1", "hook", "Open on the corner.", ["lf1"], []),
                        beat("lf2", "context", "Normal brakes.", ["lf2"], claim_ids[:1]),
                        beat("lf3", "reveal", "The rule.", ["lf2"], claim_ids[:1]),
                        beat("lf4", "payoff", "Heat as target.", ["lf3"], claim_ids),
                    ],
                },
            ],
        }
        validation = format_engine.validate_format_response(response, request)
        self.assertTrue(validation["valid"], validation["errors"])

        plan = {
            **response,
            "format_intent": request["format_intent"],
            "required_branches": request["required_branches"],
            "branch_constraints": request["branch_constraints"],
            "package": request["package"],
            "branch_story_packages": request["branch_story_packages"],
            "story_plan": request["story_plan"],
            "psychology_contract": request["psychology_contract"],
            "script_section_ids_by_branch": request[
                "script_section_ids_by_branch"
            ],
            "accepted_claims": request["accepted_claims"],
            "validation": validation,
            "plan_provenance": {"request_sha256": "contract"},
        }
        plan_path = write_json(self.root / "c1.format_plan.json", plan)
        review_request = format_review.build_review_request(plan, plan_path)
        request_path = write_json(
            self.root / "c1.format_review_request.json", review_request
        )
        approved_dir = self.root / "approved_format_plans"
        with (
            patch.object(format_review, "APPROVED_DIR", approved_dir),
            patch.object(
                format_review, "SUMMARY_FILE", self.root / "format_summary.json"
            ),
        ):
            summary = format_review.apply_payload(
                request_path,
                {
                    "concept_id": "c1",
                    "reviewer": "contract-test",
                    "decision": "ACCEPT",
                    "criteria": all_true(list(format_review.criteria_names())),
                    "note": "",
                },
            )
        self.assertEqual(summary["status"], "READY_FOR_PRODUCTION_ENGINE")
        approved_plan = json.loads(
            Path(summary["approved_format_plan"]).read_text(encoding="utf-8")
        )
        self.assertEqual(
            approved_plan["approved_provenance"]["format_plan_sha256"],
            format_engine.sha256_file(plan_path),
        )
        return approved_plan

    # ---- the chain -----------------------------------------------------------

    def test_accepted_concept_reaches_approved_format_plan(self):
        concept_handoff = self.concept_handoff()
        research_handoff = self.research_handoff(concept_handoff)
        verified = self.verified_research(research_handoff)
        approved_script = self.approved_script(verified)
        approved_plan = self.approved_format_plan(approved_script)

        self.assertEqual(approved_plan["concept_id"], "c1")
        self.assertEqual(approved_plan["package"]["one_sentence_promise"], PROMISE)
        self.assertEqual(
            [branch["format"] for branch in approved_plan["branches"]],
            ["long_form"],
        )

    def test_format_stage_refuses_a_script_without_format_intent(self):
        """Format must not guess a branch when the intent was lost upstream."""
        concept_handoff = self.concept_handoff()
        research_handoff = self.research_handoff(concept_handoff)
        verified = self.verified_research(research_handoff)
        approved_path = self.approved_script(verified)
        approved = json.loads(approved_path.read_text(encoding="utf-8"))
        approved["package"].pop("format_intent")
        broken_path = write_json(self.root / "c1.broken_script.json", approved)

        with self.assertRaisesRegex(ValueError, "format_intent"):
            format_engine.build_format_request(
                approved, broken_path, format_engine.load_config()
            )

    def test_research_plan_advertises_the_fields_the_validator_requires(self):
        """A claim built from only the plan's advertised schema must validate.

        The plan is the contract handed downstream. If the validator demands a
        field the plan never mentions, every honest response is rejected.
        """
        concept_handoff = self.concept_handoff()
        research_handoff = self.research_handoff(concept_handoff)
        config = research_engine.load_config()
        plan = research_engine.build_research_plan(research_handoff["concepts"][0])
        advertised_source = plan["response_schema"]["sources"][0]
        advertised_claim = plan["response_schema"]["claims"][0]
        advertised_link = advertised_claim["evidence_links"][0]

        source = {key: "filled" for key in advertised_source}
        source.update(
            {
                "source_id": "src001",
                "url": "https://example.com/s",
                "source_type": "primary",
            }
        )
        link = {key: "filled" for key in advertised_link}
        link.update({"source_id": "src001", "stance": "SUPPORTS"})
        claim = {key: "filled" for key in advertised_claim}
        claim.update(
            {
                "claim_id": "clm001",
                "role": "core",
                "question_ids": [plan["research_questions"][0]["question_id"]],
                "evidence_links": [link],
            }
        )
        draft = research_engine.validate_research_response(
            {"concept_id": "c1", "sources": [source], "claims": [claim]},
            plan,
            config,
        )
        self.assertEqual(draft["rejected_sources"], [], draft["rejected_sources"])
        self.assertEqual(draft["rejected_claims"], [], draft["rejected_claims"])

    def test_every_stage_config_agrees_on_format_intents(self):
        """A concept intent must be valid at every stage that reads it."""
        packaging_intents = set(
            packaging_engine.load_config()["allowed_format_intents"]
        )
        format_intents = set(format_engine.load_config()["format_intent_branches"])
        script_intents = set(
            story_script_engine.load_script_psychology_config()[
                "format_intent_branches"
            ]
        )
        self.assertEqual(packaging_intents, format_intents)
        self.assertEqual(packaging_intents, script_intents)


if __name__ == "__main__":
    unittest.main()
