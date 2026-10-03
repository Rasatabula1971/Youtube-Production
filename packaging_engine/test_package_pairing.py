from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import package_pairing as module


class PackagePairingTests(unittest.TestCase):
    def brief(self):
        return {
            "video_id": "c1:short",
            "concept_id": "c1",
            "format": "short",
            "search_vs_browse_intent": "BROWSE",
            "selected_title": {
                "title_id": "short-curiosity",
                "title_text": "Why Cold Race Brakes Feel Wrong",
            },
            "viewer_promise_contract": {
                "viewer_expectation": (
                    "A viewer expects to understand why race brakes need heat."
                ),
                "promise_subject": "Race brakes",
                "promise_question": "Why do race brakes need heat?",
                "promise_stakes": "Cold braking changes driver margin.",
                "promise_payoff": "Explain the hot operating window.",
            },
            "opening_hook": "Cold race brakes can feel worse.",
            "central_question": "Why do race brakes need heat?",
            "video_payoff": "Explain the hot operating window.",
            "approved_claims": [
                {
                    "claim_id": "clm001",
                    "statement": "Brake temperature can exceed 500 C.",
                },
                {
                    "claim_id": "clm002",
                    "statement": "Cold braking differs from the hot operating window.",
                },
            ],
            "approved_numbers": [
                {"value": "500", "claim_id": "clm001"}
            ],
            "prohibited_or_unsupported_claims": [
                {
                    "claim_id": "bad001",
                    "claim": "These are the best brakes in the world.",
                    "status": "REJECTED",
                }
            ],
        }

    def titles(self):
        angles = ["curiosity", "stakes", "unexpected", "mystery", "payoff"]
        values = []
        for index, angle in enumerate(angles):
            text = [
                "Why Cold Race Brakes Feel Wrong",
                "Cold Brakes Change Your Stopping Margin",
                "The Strange Reason Race Brakes Need Heat",
                "What Happens Before Race Brakes Wake Up",
                "How Heat Puts Race Brakes in Their Window",
            ][index]
            values.append(
                {
                    "title_id": f"short-{angle}",
                    "title_text": text,
                    "psychological_angle": angle,
                    "primary_driver": angle,
                    "secondary_driver": "specificity",
                    "core_claim": "Cold and hot braking behavior differ.",
                    "evidence_refs": ["clm002"],
                    "character_count": len(text),
                    "search_intent": "BROWSE",
                }
            )
        return values

    def angles(self):
        drivers = [
            "curiosity_gap",
            "danger",
            "consequence",
            "surprise",
            "contradiction",
        ]
        return [
            {
                "angle_id": f"angle-{driver}",
                "primary_driver": driver,
                "secondary_driver": "specificity",
                "viewer_question": f"Question {index}",
                "expected_click_reason": f"Reason {index}",
                "evidence_refs": ["clm001", "clm002"],
            }
            for index, driver in enumerate(drivers)
        ]

    def thumbnails(self):
        values = []
        for index, angle in enumerate(self.angles()):
            values.append(
                {
                    "thumbnail_id": f"thumbnail-{angle['angle_id']}",
                    "angle_id": angle["angle_id"],
                    "hero_subject": "Glowing brake disc",
                    "secondary_element": "Cold brake disc",
                    "visual_anomaly": "One disc glows while the other stays dark",
                    "visual_action": "Hot versus cold contrast",
                    "viewer_visual_question": f"Why does contrast {index} matter?",
                    "text": ["NO GRIP", "TOO COLD", "500 C", "WHY HEAT?", "HOT WINDOW"][index],
                    "text_word_count": 2,
                    "evidence_refs": ["clm001", "clm002"],
                }
            )
        return values

    def input_fixture(self, root: Path):
        brief_path = root / "c1.short.packaging_brief.json"
        brief_path.write_text("{}", encoding="utf-8")
        angle_item = {
            "video_id": "c1:short",
            "concept_id": "c1",
            "format": "short",
            "angles": self.angles(),
        }
        thumb_item = {
            "video_id": "c1:short",
            "concept_id": "c1",
            "format": "short",
            "thumbnail_concepts": self.thumbnails(),
        }
        title_item = {
            "concept_id": "c1",
            "titles": {"short": self.titles(), "long_form": []},
        }
        return brief_path, angle_item, thumb_item, title_item

    def test_full_cross_product_builds_25_pairs_not_one_to_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief_path, angle_item, thumb_item, title_item = self.input_fixture(root)
            with (
                patch.object(
                    module,
                    "_current_briefs",
                    return_value={"c1:short": (brief_path, self.brief())},
                ),
                patch.object(
                    module,
                    "_current_angle_items",
                    return_value={"c1:short": angle_item},
                ),
                patch.object(
                    module,
                    "_current_thumbnail_items",
                    return_value={"c1:short": thumb_item},
                ),
                patch.object(
                    module,
                    "_title_concepts",
                    return_value={"c1": title_item},
                ),
            ):
                inputs = module.build_inputs()

        pairs = inputs[0]["pairs"]
        self.assertEqual(len(pairs), 25)
        self.assertEqual(len(inputs[0]["chunks"]), 5)
        self.assertTrue(
            any(
                p["title_id"] == "short-curiosity"
                and p["thumbnail_id"]
                == "thumbnail-angle-contradiction"
                for p in pairs
            )
        )

    def test_lexical_redundancy_detects_significant_duplication(self):
        result = module.lexical_redundancy(
            "How F1 Rain Tyres Work",
            "F1 RAIN TYRES",
        )
        self.assertEqual(result["level"], "HIGH")
        self.assertEqual(set(result["shared_tokens"]), {"f1", "rain", "tyres"})

    def request_and_pairs(self):
        brief = self.brief()
        angle = self.angles()[0]
        thumb = self.thumbnails()[0]
        pairs = [
            module._pair(
                brief=brief,
                title=title,
                thumbnail=thumb,
                angle=angle,
            )
            for title in self.titles()
        ]
        return {
            "video_id": "c1:short",
            "thumbnail_id": thumb["thumbnail_id"],
            "approved_claims": brief["approved_claims"],
            "diagnostic_dimensions": [
                "scroll_stop",
                "clarity",
                "curiosity",
                "stakes",
                "specificity",
                "visual_simplicity",
                "title_strength",
                "complementarity",
                "credibility",
                "promise_alignment",
                "hook_alignment",
            ],
            "hard_reject_codes": [
                "unsupported_material_claim",
                "factually_false_claim",
                "thumbnail_misrepresents_video",
                "title_misrepresents_video",
                "evidence_conflict",
                "prohibited_claim",
            ],
            "rework_codes": [
                "title_thumbnail_redundancy",
                "weak_hook_alignment",
                "promise_not_addressed_early",
                "thumbnail_too_complex",
                "thumbnail_text_too_long",
                "critical_content_in_timestamp_zone",
                "unclear_primary_subject",
                "selected_title_no_longer_matches_final_script",
            ],
            "pair_candidates": pairs,
        }, pairs

    def response(self):
        request, pairs = self.request_and_pairs()
        evaluations = []
        for pair in pairs:
            evaluations.append(
                {
                    "package_id": pair["package_id"],
                    "semantic_redundancy": "LOW",
                    "semantic_redundancy_reason": "Title adds context while visual adds contrast.",
                    "visual_text_redundancy": "LOW",
                    "psychological_complementarity": 4,
                    "information_gain": 4,
                    "promise_consistency": "PASS",
                    "promise_alignment_reason": "The pair stays inside the approved heat tradeoff.",
                    "hook_alignment_status": "PASS",
                    "hook_alignment_reason": "The cold-brake hook immediately confirms the click reason.",
                    "title_claim_validation": {
                        "status": "VERIFIED",
                        "reason": "The title claim is supported by clm002.",
                        "evidence_refs": ["clm002"],
                    },
                    "thumbnail_claim_validation": {
                        "status": "VERIFIED",
                        "reason": "The visual and text are supported by approved brake evidence.",
                        "evidence_refs": ["clm001"],
                    },
                    "hard_validation_findings": [],
                    "rework_findings": [],
                    "diagnostics": {
                        "scroll_stop": 4,
                        "clarity": 4,
                        "curiosity": 4,
                        "stakes": 4,
                        "specificity": 4,
                        "visual_simplicity": 4,
                        "title_strength": 4,
                        "complementarity": 4,
                        "credibility": 5,
                        "promise_alignment": 5,
                        "hook_alignment": 5,
                    },
                }
            )
        return request, {
            "video_id": "c1:short",
            "thumbnail_id": request["thumbnail_id"],
            "evaluations": evaluations,
        }

    def test_validated_packages_store_diagnostics_without_viral_score(self):
        request, response = self.response()
        values = module.validate_response(response, request)
        self.assertEqual(len(values), 5)
        self.assertTrue(all(x["validation_status"] == "PASS" for x in values))
        self.assertTrue(all(x["viral_score"] is None for x in values))
        self.assertTrue(
            all(x["diagnostics_are_predictions"] is False for x in values)
        )

    def test_high_scores_cannot_override_unsupported_claim(self):
        request, response = self.response()
        item = response["evaluations"][0]
        item["title_claim_validation"] = {
            "status": "UNSUPPORTED",
            "reason": "The title claim is not established.",
            "evidence_refs": [],
        }
        item["diagnostics"] = {
            key: 5 for key in request["diagnostic_dimensions"]
        }
        values = module.validate_response(response, request)
        self.assertEqual(values[0]["validation_status"], "REJECT")
        self.assertIn(
            "unsupported_material_claim",
            {
                x["code"]
                for x in values[0]["hard_validation_findings"]
            },
        )

    def test_overpromise_is_rejected(self):
        request, response = self.response()
        response["evaluations"][0]["promise_consistency"] = "OVERPROMISE"
        values = module.validate_response(response, request)
        self.assertEqual(values[0]["validation_status"], "REJECT")
        self.assertIn(
            "title_misrepresents_video",
            {
                x["code"]
                for x in values[0]["hard_validation_findings"]
            },
        )

    def test_weak_hook_alignment_requires_rework(self):
        request, response = self.response()
        response["evaluations"][0]["hook_alignment_status"] = "REWORK"
        values = module.validate_response(response, request)
        self.assertEqual(values[0]["validation_status"], "REWORK")
        self.assertIn(
            "weak_hook_alignment",
            {x["code"] for x in values[0]["rework_findings"]},
        )

    def test_high_semantic_redundancy_requires_rework(self):
        request, response = self.response()
        response["evaluations"][0]["semantic_redundancy"] = "HIGH"
        values = module.validate_response(response, request)
        self.assertEqual(values[0]["validation_status"], "REWORK")
        self.assertIn(
            "title_thumbnail_redundancy",
            {x["code"] for x in values[0]["rework_findings"]},
        )

    def test_missing_diagnostic_dimension_fails_closed(self):
        request, response = self.response()
        response["evaluations"][0]["diagnostics"].pop("credibility")
        with self.assertRaisesRegex(ValueError, "exactly the configured"):
            module.validate_response(response, request)

    def test_claim_validation_cannot_invent_evidence_ref(self):
        request, response = self.response()
        response["evaluations"][0]["title_claim_validation"]["evidence_refs"] = [
            "invented"
        ]
        with self.assertRaisesRegex(ValueError, "invents evidence"):
            module.validate_response(response, request)

    def test_claim_validation_cannot_borrow_other_component_evidence(self):
        request, response = self.response()
        response["evaluations"][0]["title_claim_validation"]["evidence_refs"] = [
            "clm001"
        ]
        with self.assertRaisesRegex(ValueError, "outside the paired component"):
            module.validate_response(response, request)

    def test_64_character_title_is_guidance_not_hard_rejection(self):
        brief = self.brief()
        title = self.titles()[0]
        title["title_text"] = (
            "Why Cold Racing Brakes Can Feel Wrong Before They Finally Work"
        )
        title["character_count"] = len(title["title_text"])
        self.assertGreater(title["character_count"], 60)
        pair = module._pair(
            brief=brief,
            title=title,
            thumbnail=self.thumbnails()[0],
            angle=self.angles()[0],
        )
        self.assertFalse(
            pair["title_length_guidance"]["within_preferred_range"]
        )
        self.assertFalse(pair["title_length_guidance"]["hard_rejection"])


if __name__ == "__main__":
    unittest.main()
