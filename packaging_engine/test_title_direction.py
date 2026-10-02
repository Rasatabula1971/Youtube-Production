from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import title_direction as module


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TitleDirectionTests(unittest.TestCase):
    def bundle(self):
        return {
            "artifact": "approved_script_bundle",
            "status": "READY_FOR_PRODUCTION",
            "concept_id": "c1",
            "title": "Internal Working Title",
            "package": {
                "title": "Internal Working Title",
                "one_sentence_promise": "Explain the braking contradiction.",
                "viewer_problem": "Why do racing brakes seem backwards?",
                "viewer_moment": "Watching an F1 braking zone.",
                "desired_outcome": "Understand the heat tradeoff.",
                "format_intent": "either",
            },
            "story_plan": {
                "story_question": "Why can better brakes feel worse when cold?",
                "opening_hook_intent": "Lead on the contradiction.",
                "payoff_intent": "Show why heat changes the design target.",
            },
            "accepted_claims": [
                {
                    "claim_id": "clm001",
                    "statement": "Temperature changes braking behavior.",
                    "role": "core",
                },
                {
                    "claim_id": "clm002",
                    "statement": "Standing water can reduce tyre contact.",
                    "role": "supporting",
                },
            ],
            "branch_scripts": {
                "short": {
                    "opening_hook": "Cold race brakes can feel worse.",
                    "opening_hook_mechanism": "CONTRADICTION",
                    "opening_hook_claim_ids": ["clm001"],
                    "sections": [
                        {
                            "section_id": "s1",
                            "purpose": "Hook",
                            "narration": "Cold race brakes can feel worse.",
                            "claim_ids": ["clm001"],
                        },
                        {
                            "section_id": "s2",
                            "purpose": "Payoff",
                            "narration": "Heat changes the target.",
                            "claim_ids": ["clm001"],
                        },
                    ],
                    "closing": "Temperature resolves the contradiction.",
                },
                "long_form": {
                    "opening_hook": "The better the brake, the stranger it can feel cold.",
                    "opening_hook_mechanism": "CONTRADICTION",
                    "opening_hook_claim_ids": ["clm001"],
                    "sections": [
                        {
                            "section_id": "l1",
                            "purpose": "Setup",
                            "narration": "Start with the cold-brake contradiction.",
                            "claim_ids": ["clm001"],
                        },
                        {
                            "section_id": "l2",
                            "purpose": "Payoff",
                            "narration": "Explain the thermal design tradeoff.",
                            "claim_ids": ["clm001"],
                        },
                    ],
                    "closing": "The contradiction disappears once heat is included.",
                },
            },
        }

    def request(self, root: Path):
        approved_dir = root / "approved"
        path = write_json(
            approved_dir / "c1.approved_script.json",
            self.bundle(),
        )
        with (
            patch.object(module, "APPROVED_SCRIPTS_DIR", approved_dir),
            patch.object(
                module,
                "_approved_bundle_is_current",
                return_value=True,
            ),
        ):
            request = module.build_request(path, self.bundle())
        return path, request

    def response(self, request):
        titles = {}
        for fmt in ("short", "long_form"):
            titles[fmt] = []
            for angle in request["psychological_angles"]:
                titles[fmt].append(
                    {
                        "title_id": f"{fmt}-{angle}",
                        "title_text": f"{angle.title()} Brake Mystery",
                        "psychological_angle": angle,
                        "primary_driver": angle,
                        "secondary_driver": "specificity",
                        "core_claim": "Temperature changes braking behavior.",
                        "evidence_refs": ["clm001"],
                        "search_intent": "HYBRID",
                    }
                )
        return {"concept_id": "c1", "titles": titles}

    def test_request_is_post_script_and_preserves_5_plus_5_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            _path, request = self.request(Path(tmp))

        self.assertEqual(request["title_count_per_format"], 5)
        self.assertEqual(request["formats"], ["short", "long_form"])
        self.assertEqual(
            request["title_role"],
            "PREFERRED_DIRECTION_NOT_FINAL_WORDING",
        )
        self.assertTrue(
            request["title_guidance"]["final_wording_editable_later"]
        )
        self.assertEqual(
            set(request["allowed_evidence_refs"]),
            {"clm001", "clm002"},
        )
        self.assertEqual(
            request["story_context"]["branches"][0]["format"],
            "long_form",
        )

    def test_response_requires_exact_stable_ids_and_preserves_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            _path, request = self.request(Path(tmp))
            result = module.validate_response(
                self.response(request),
                request,
            )

        self.assertEqual(result["artifact"], "title_direction_candidate_set")
        self.assertEqual(len(result["titles"]["short"]), 5)
        self.assertEqual(len(result["titles"]["long_form"]), 5)
        sample = result["titles"]["short"][0]
        self.assertEqual(
            sample["title_id"],
            f"short-{sample['psychological_angle']}",
        )
        self.assertEqual(
            sample["character_count"],
            len(sample["title_text"]),
        )

    def test_invented_evidence_ref_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _path, request = self.request(Path(tmp))
            response = self.response(request)
            response["titles"]["short"][0]["evidence_refs"] = ["invented"]

            with self.assertRaisesRegex(ValueError, "invents evidence_refs"):
                module.validate_response(response, request)

    def test_duplicate_or_mutated_title_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _path, request = self.request(Path(tmp))
            response = self.response(request)
            response["titles"]["short"][1]["title_id"] = "short-curiosity"

            with self.assertRaisesRegex(ValueError, "stable ID|Duplicate"):
                module.validate_response(response, request)

    def test_stale_approved_script_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approved_dir = root / "approved"
            path = write_json(
                approved_dir / "c1.approved_script.json",
                self.bundle(),
            )
            with (
                patch.object(module, "APPROVED_SCRIPTS_DIR", approved_dir),
                patch.object(
                    module,
                    "_approved_bundle_is_current",
                    return_value=False,
                ),
                self.assertRaisesRegex(
                    ValueError,
                    "STALE_APPROVED_SCRIPT_BUNDLE",
                ),
            ):
                module.build_request(path, self.bundle())


if __name__ == "__main__":
    unittest.main()
