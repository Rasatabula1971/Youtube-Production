from __future__ import annotations

import unittest

import thumbnail_concepts as module


class ThumbnailConceptTests(unittest.TestCase):
    def request(self):
        angles = []
        drivers = ["curiosity_gap", "danger", "consequence", "surprise", "contradiction"]
        for index, driver in enumerate(drivers):
            angles.append(
                {
                    "angle_id": f"angle-{driver}",
                    "primary_driver": driver,
                    "secondary_driver": "specificity",
                    "viewer_question": f"Question {index}",
                    "emotional_trigger": f"Trigger {index}",
                    "stakes": f"Stake {index}",
                    "information_given": "Temperature changes braking behavior.",
                    "information_withheld": f"Gap {index}",
                    "expected_click_reason": f"Reason {index}",
                    "evidence_refs": ["clm001"],
                    "selected_title_direction_alignment": (
                        "ANCHOR" if index == 0 else "ALTERNATIVE"
                    ),
                }
            )
        return {
            "video_id": "c1:short",
            "concept_id": "c1",
            "format": "short",
            "search_vs_browse_intent": "BROWSE",
            "selected_title_direction": {
                "title_text": "Why Cold Race Brakes Feel Wrong"
            },
            "approved_numbers": [
                {"value": "500", "claim_id": "clm001"}
            ],
            "approved_claims": [
                {
                    "claim_id": "clm001",
                    "statement": "Brake temperature can exceed 500 C.",
                }
            ],
            "allowed_evidence_refs": ["clm001"],
            "angles": angles,
            "thumbnail_contract": {
                "aspect_ratio": "16:9",
                "primary_focal_points": 1,
                "maximum_meaningful_visual_elements": 3,
                "preferred_text_words": 3,
                "maximum_text_words": 4,
                "require_timestamp_safe": True,
                "require_mobile_legibility_intent": True,
                "prohibit_critical_bottom_right_content": True,
            },
        }

    def response(self):
        values = []
        labels = ["HOT", "GRIP", "WHY", "COLD", "LIMIT"]
        questions = ["alpha", "bravo", "charlie", "delta", "echo"]
        for index, angle in enumerate(self.request()["angles"]):
            values.append(
                {
                    "thumbnail_id": f"thumbnail-{angle['angle_id']}",
                    "angle_id": angle["angle_id"],
                    "hero_subject": "Glowing brake disc",
                    "secondary_element": "Cold brake disc",
                    "visual_anomaly": "One disc glows while the other stays dark",
                    "visual_action": "Side-by-side thermal contrast",
                    "emotion": "Tension",
                    "composition": "Large hot disc left, small cold comparison right",
                    "background": "Dark pit-lane background",
                    "subject_separation_method": "Brightness and scale contrast",
                    "text": labels[index],
                    "text_word_count": 1,
                    "viewer_visual_question": f"Why does the {questions[index]} heat contrast matter?",
                    "timestamp_safe": True,
                    "mobile_legibility_intent": "Large disc and two-word text remain readable",
                    "evidence_refs": ["clm001"],
                    "aspect_ratio": "16:9",
                    "primary_focal_points": 1,
                    "meaningful_visual_elements": 3,
                    "critical_bottom_right_content": False,
                    "face_present": False,
                }
            )
        return {
            "video_id": "c1:short",
            "thumbnail_concepts": values,
        }

    def test_one_thumbnail_per_angle_and_stable_ids(self):
        result = module.validate_response(self.response(), self.request())
        self.assertEqual(result["artifact"], "thumbnail_concept_set")
        self.assertEqual(len(result["thumbnail_concepts"]), 5)
        for item in result["thumbnail_concepts"]:
            self.assertEqual(
                item["thumbnail_id"],
                f"thumbnail-{item['angle_id']}",
            )

    def test_thumbnail_word_count_is_computed_and_limited(self):
        response = self.response()
        response["thumbnail_concepts"][0]["text"] = "THIS HAS FIVE WORDS NOW"
        response["thumbnail_concepts"][0]["text_word_count"] = 5
        with self.assertRaisesRegex(ValueError, "exceeds 4 words"):
            module.validate_response(response, self.request())

    def test_incorrect_word_count_is_rejected(self):
        response = self.response()
        response["thumbnail_concepts"][0]["text_word_count"] = 1
        with self.assertRaisesRegex(ValueError, "text_word_count is incorrect"):
            module.validate_response(response, self.request())

    def test_timestamp_zone_violation_is_rejected(self):
        response = self.response()
        response["thumbnail_concepts"][0]["timestamp_safe"] = False
        with self.assertRaisesRegex(ValueError, "timestamp zone"):
            module.validate_response(response, self.request())

    def test_too_many_visual_elements_is_rejected(self):
        response = self.response()
        response["thumbnail_concepts"][0]["meaningful_visual_elements"] = 4
        with self.assertRaisesRegex(ValueError, "too many"):
            module.validate_response(response, self.request())

    def test_thumbnail_text_that_repeats_selected_title_is_rejected(self):
        response = self.response()
        response["thumbnail_concepts"][0]["text"] = "COLD RACE BRAKES"
        response["thumbnail_concepts"][0]["text_word_count"] = 3
        with self.assertRaisesRegex(ValueError, "repeats selected title"):
            module.validate_response(response, self.request())

    def test_invented_evidence_ref_is_rejected(self):
        response = self.response()
        response["thumbnail_concepts"][0]["evidence_refs"] = ["invented"]
        with self.assertRaisesRegex(ValueError, "invents evidence_refs"):
            module.validate_response(response, self.request())

    def test_angle_evidence_link_is_required(self):
        request = self.request()
        request["approved_claims"].append(
            {"claim_id": "clm002", "statement": "Another supported fact."}
        )
        request["allowed_evidence_refs"].append("clm002")
        response = self.response()
        response["thumbnail_concepts"][0]["evidence_refs"] = ["clm002"]
        with self.assertRaisesRegex(ValueError, "not evidence-linked"):
            module.validate_response(response, request)

    def test_unsupported_number_is_rejected(self):
        response = self.response()
        response["thumbnail_concepts"][0]["text"] = "900 C"
        response["thumbnail_concepts"][0]["text_word_count"] = 2
        with self.assertRaisesRegex(ValueError, "unsupported number"):
            module.validate_response(response, self.request())

    def test_supported_number_is_allowed(self):
        response = self.response()
        response["thumbnail_concepts"][0]["text"] = "500 C"
        response["thumbnail_concepts"][0]["text_word_count"] = 2
        result = module.validate_response(response, self.request())
        self.assertEqual(result["thumbnail_concepts"][0]["text"], "500 C")


if __name__ == "__main__":
    unittest.main()
