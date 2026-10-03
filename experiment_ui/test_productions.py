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


if __name__ == "__main__":
    unittest.main()
