import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import productions  # noqa: E402

CID = "c1"


def concept_gate(*decisions: tuple[str, str]) -> dict:
    return {
        "concepts": [
            {
                "concept_id": cid,
                "decision": decision,
                "working_title": f"Title {cid}",
                "premise": "Why plane tyres don't burst",
            }
            for cid, decision in decisions
        ]
    }


def derive(**overrides):
    state: dict[str, Any] = {
        "concept_gate": concept_gate((CID, "ACCEPT")),
        "research": {},
        "story": {},
        "title_direction": {},
        "fmt": {},
        "voice": {},
        "narration": {},
        "final_render_keys": set(),
    }
    state.update(overrides)
    return productions.derive(**state)


def only(result):
    assert result["count"] == 1, result
    return result["productions"][0]


VERIFIED = {
    "research_gate": {
        "verified_packages": [{"concept_id": CID, "status": "READY_FOR_STORY_SCRIPT"}]
    }
}
SCRIPTED = {"script_gate": {"production_ready_concept_ids": [CID]}}
FORMATTED = {"format_gate": {"plans": [{"concept_id": CID, "decision": "ACCEPT"}]}}
BRANCHES = {
    "expected_branches": [
        {"concept_id": CID, "format": "long"},
        {"concept_id": CID, "format": "short"},
    ]
}


class ProductionsDerivationTests(unittest.TestCase):
    def test_only_accepted_concepts_become_productions(self) -> None:
        result = derive(
            concept_gate=concept_gate(
                (CID, "ACCEPT"), ("c2", "PENDING"), ("c3", "REJECT")
            )
        )
        self.assertEqual([p["concept_id"] for p in result["productions"]], [CID])
        self.assertEqual(result["source"], "derived_from_files")

    def test_no_artifacts_waits_to_plan_research(self) -> None:
        item = only(derive())
        self.assertEqual((item["stage"], item["status"]), ("RESEARCH", "READY"))
        self.assertEqual(item["detail"], "Waiting to plan research")
        states = {s["id"]: s["state"] for s in item["stages"]}
        self.assertEqual(states["CONCEPT"], "done")
        self.assertEqual(states["RESEARCH"], "current")
        self.assertEqual(states["SCRIPT"], "todo")

    def test_pending_research_claims_need_review(self) -> None:
        research = {
            "draft_concept_ids": [CID],
            "research_gate": {
                "claims": [
                    {"concept_id": CID, "decision": "PENDING"},
                    {"concept_id": CID, "decision": "PENDING"},
                    {"concept_id": "other", "decision": "PENDING"},
                ]
            },
        }
        item = only(derive(research=research))
        self.assertEqual(item["status"], "HUMAN_REVIEW")
        self.assertEqual(item["detail"], "2 research claims to verify")

    def test_decided_but_incomplete_research_needs_review_and_says_why(self) -> None:
        research = {
            "draft_concept_ids": [CID],
            "research_gate": {
                "claims": [{"concept_id": CID, "decision": "ACCEPT"}],
                "verified_packages": [
                    {"concept_id": CID, "status": "RESEARCH_INCOMPLETE", "unresolved_question_ids": ["rq002"]}
                ],
                "question_coverage": [
                    {"concept_id": CID, "summary": "Not ready for the script: 1 question unanswered."}
                ],
            },
        }
        item = only(derive(research=research))
        self.assertEqual(item["status"], "HUMAN_REVIEW")
        self.assertEqual(item["detail"], "Not ready for the script: 1 question unanswered.")
        self.assertFalse(item["can_continue"])

        del research["research_gate"]["question_coverage"]
        item = only(derive(research=research))
        self.assertEqual(item["status"], "HUMAN_REVIEW")
        self.assertIn("1 research question unanswered", item["detail"])

        research["research_gate"]["verified_packages"][0]["unresolved_question_ids"] = []
        research["research_gate"]["claims"][0]["decision"] = "REJECT"
        item = only(derive(research=research))
        self.assertEqual(item["status"], "HUMAN_REVIEW")
        self.assertIn("no research claim was accepted", item["detail"])

    def test_blocker_names_the_step_that_stopped_the_last_run_at_this_stage(self) -> None:
        last_run = {
            "status": "PARTIAL",
            "failed_action": "research_acquire",
            "stuck": {"research_acquire": "Source pages were found, but some questions have no source."},
        }
        labels = {"research_acquire": "Acquire Research Evidence"}
        item = only(derive(last_run=last_run, action_labels=labels))
        self.assertEqual(item["status"], "READY")
        self.assertTrue(item["can_continue"])
        self.assertEqual(
            item["blocker"],
            "Last run stopped at Acquire Research Evidence: Source pages were found, but some questions have no source.",
        )
        # A stuck step of another stage is not this production's blocker.
        scripted = only(derive(research=VERIFIED, last_run=last_run, action_labels=labels))
        self.assertEqual(scripted["stage"], "SCRIPT")
        self.assertEqual(scripted["blocker"], "")
        # A failed step with no message points at the job log.
        failed = only(derive(last_run={"status": "FAILED", "failed_action": "research_prepare", "return_code": 1}))
        self.assertEqual(failed["blocker"], "Last run failed at research prepare (exit code 1). Open the job log for the error.")
        # A production waiting on a person carries no blocker: its detail says why.
        pending = {"research_gate": {"claims": [{"concept_id": CID, "decision": "PENDING"}]}}
        self.assertEqual(only(derive(research=pending, last_run=last_run))["blocker"], "")

    def test_action_stage_maps_step_prefixes(self) -> None:
        self.assertEqual(productions.action_stage("research_generate"), "RESEARCH")
        self.assertEqual(productions.action_stage("script_gate_prepare"), "SCRIPT")
        self.assertEqual(productions.action_stage("thumbnail_concept_generate"), "PACKAGE")
        self.assertEqual(productions.action_stage("format_generate"), "FORMAT")
        self.assertEqual(productions.action_stage("narration_prepare"), "PRODUCE")
        self.assertIsNone(productions.action_stage("concept_generate"))

    def test_reworked_script_is_blocked(self) -> None:
        story = {"script_gate": {"scripts": [{"concept_id": CID, "decision": "REWORK"}]}}
        item = only(derive(research=VERIFIED, story=story))
        self.assertEqual((item["stage"], item["status"]), ("SCRIPT", "BLOCKED"))
        self.assertIn("rework", item["detail"])

    def test_title_direction_choice_needs_review(self) -> None:
        item = only(
            derive(
                research=VERIFIED,
                story=SCRIPTED,
                title_direction={"candidate_concept_ids": [CID], "selected": False},
            )
        )
        self.assertEqual((item["stage"], item["status"]), ("PACKAGE", "HUMAN_REVIEW"))

    def test_pending_format_plan_needs_review(self) -> None:
        fmt = {"format_gate": {"plans": [{"concept_id": CID, "decision": "PENDING"}]}}
        item = only(derive(research=VERIFIED, story=SCRIPTED, fmt=fmt))
        self.assertEqual((item["stage"], item["status"]), ("FORMAT", "HUMAN_REVIEW"))

    def test_partial_final_render_stays_in_produce(self) -> None:
        item = only(
            derive(
                research=VERIFIED,
                story=SCRIPTED,
                fmt=FORMATTED,
                voice=BRANCHES,
                final_render_keys={(CID, "long")},
            )
        )
        self.assertEqual((item["stage"], item["status"]), ("PRODUCE", "READY"))
        self.assertEqual(item["detail"], "1 of 2 branches rendered")
        self.assertEqual([b["format"] for b in item["branches"]], ["long", "short"])

    def test_all_branches_rendered_is_done(self) -> None:
        result = derive(
            research=VERIFIED,
            story=SCRIPTED,
            fmt=FORMATTED,
            voice=BRANCHES,
            final_render_keys={(CID, "long"), (CID, "short")},
        )
        item = only(result)
        self.assertEqual((item["stage"], item["status"]), ("DONE", "COMPLETE"))
        self.assertTrue(all(s["state"] == "done" for s in item["stages"]))
        self.assertEqual(result["active_count"], 0)
        self.assertEqual(result["by_stage"]["DONE"], 1)

    def test_pending_voice_performance_needs_review(self) -> None:
        voice = {
            **BRANCHES,
            "performance_gate": {
                "specs": [{"concept_id": CID, "format": "long", "decision": "PENDING"}]
            },
        }
        item = only(derive(research=VERIFIED, story=SCRIPTED, fmt=FORMATTED, voice=voice))
        self.assertEqual((item["stage"], item["status"]), ("PRODUCE", "HUMAN_REVIEW"))

    def test_review_items_sort_first(self) -> None:
        research = {
            "research_gate": {
                "verified_packages": [
                    {"concept_id": "a", "status": "READY_FOR_STORY_SCRIPT"}
                ],
                "claims": [{"concept_id": "b", "decision": "PENDING"}],
            }
        }
        result = derive(
            concept_gate=concept_gate(("a", "ACCEPT"), ("b", "ACCEPT")),
            research=research,
        )
        self.assertEqual(
            [p["concept_id"] for p in result["productions"]], ["b", "a"]
        )
        self.assertEqual(result["by_status"]["HUMAN_REVIEW"], 1)

    def test_malformed_state_does_not_raise(self) -> None:
        result = productions.derive(
            concept_gate={"concepts": [None, {"decision": "ACCEPT"}, "x"]},
            research={"research_gate": "bad"},
            story={"script_gate": None},
            title_direction=None,  # type: ignore[arg-type]
            fmt={},
            voice={"expected_branches": "bad"},
            narration={},
        )
        self.assertEqual(result["count"], 0)



class ProductionDetailTests(unittest.TestCase):
    def build(self, **overrides):
        state: dict[str, Any] = {
            "research": VERIFIED,
            "story": {
                **SCRIPTED,
                "story_plan_concept_ids": [CID],
                "draft_concept_ids": [CID],
            },
            "title_direction": {},
            "fmt": {},
            "voice": {},
        }
        state.update(overrides)
        production = only(
            productions.derive(
                concept_gate=concept_gate((CID, "ACCEPT")),
                narration={},
                **state,
            )
        )
        concept = {
            "concept_id": CID,
            "premise": "Why plane tyres don't burst",
            "mechanism_label": "Hidden mechanism",
            "viewer_need_evidence": {"level": "OBSERVED", "summary": "question titles"},
            "research_questions": ["What gas is used?"],
        }
        return productions.detail(production, concept=concept, **state)

    def test_eight_sections_in_order_with_stage_states(self) -> None:
        result = self.build()
        ids = [s["id"] for s in result["sections"]]
        self.assertEqual(
            ids,
            ["EVIDENCE", "ANALYSIS", "CONCEPT", "RESEARCH", "SCRIPT", "PACKAGE", "FORMAT", "PRODUCE"],
        )
        states = {s["id"]: s["state"] for s in result["sections"]}
        self.assertEqual(states["CONCEPT"], "done")
        self.assertEqual(states["RESEARCH"], "done")
        self.assertEqual(states["SCRIPT"], "done")
        self.assertEqual(states["PACKAGE"], "current")
        self.assertEqual(states["PRODUCE"], "todo")

    def test_concept_facts_flatten_nested_values(self) -> None:
        sections = {s["id"]: s for s in self.build()["sections"]}
        facts = {f["label"]: f["value"] for f in sections["EVIDENCE"]["facts"]}
        self.assertEqual(facts["Viewer need evidence"], "question titles")
        concept_facts = {f["label"]: f["value"] for f in sections["CONCEPT"]["facts"]}
        self.assertEqual(concept_facts["Premise"], "Why plane tyres don't burst")
        research = {f["label"]: f["value"] for f in sections["RESEARCH"]["facts"]}
        self.assertEqual(research["Research questions"], "What gas is used?")

    def test_script_sections_show_decisions_locks_and_alternatives(self) -> None:
        story = {
            "script_gate": {"scripts": [{"concept_id": CID, "format": "long", "decision": "PENDING"}]},
        }
        branch = {
            "format": "long",
            "targets": [
                {"target_type": "OPENING_HOOK", "decision": "ACCEPT", "locked": True},
                {
                    "target_type": "SECTION",
                    "section_id": "s2",
                    "decision": "REWORK",
                    "rework_reason": "TOO_TECHNICAL",
                    "metadata": {"purpose": "Open loop"},
                    "alternatives": {"alternatives": [{"text": "a"}, {"text": "b"}]},
                },
                {"target_type": "CLOSING", "decision": "PENDING"},
            ],
        }
        production = only(
            productions.derive(
                concept_gate=concept_gate((CID, "ACCEPT")),
                research=VERIFIED,
                story=story,
                title_direction={},
                fmt={},
                voice={},
                narration={},
            )
        )
        result = productions.detail(
            production,
            concept={},
            research=VERIFIED,
            story=story,
            title_direction={},
            fmt={},
            voice={},
            script_sections=[branch],
        )
        script = next(s for s in result["sections"] if s["id"] == "SCRIPT")
        self.assertEqual(script["state"], "current")
        rows = [(r["label"], r["status"], r["detail"]) for r in script["rows"]]
        self.assertEqual(
            rows,
            [
                ("long script", "pending", ""),
                ("long · Opening hook", "locked", ""),
                ("long · s2: Open loop", "rework", "too technical, 2 alternatives ready"),
                ("long · Closing", "pending", ""),
            ],
        )

    def test_done_production_marks_every_section_done(self) -> None:
        production = only(
            productions.derive(
                concept_gate=concept_gate((CID, "ACCEPT")),
                research=VERIFIED,
                story=SCRIPTED,
                title_direction={},
                fmt=FORMATTED,
                voice=BRANCHES,
                narration={},
                final_render_keys={(CID, "long"), (CID, "short")},
            )
        )
        result = productions.detail(
            production, concept={}, research=VERIFIED, story=SCRIPTED,
            title_direction={}, fmt=FORMATTED, voice=BRANCHES,
        )
        self.assertTrue(all(s["state"] == "done" for s in result["sections"]))
        produce = next(s for s in result["sections"] if s["id"] == "PRODUCE")
        self.assertEqual([r["status"] for r in produce["rows"]], ["accept", "accept"])


if __name__ == "__main__":
    unittest.main()
