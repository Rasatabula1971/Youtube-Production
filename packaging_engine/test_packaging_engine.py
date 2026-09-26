import unittest

from packaging_engine import (
    build_package_request,
    validate_response,
)


class PackagingEngineTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "packages_per_concept": 5,
            "allowed_format_intents": [
                "long_form",
                "short",
                "either",
            ],
            "minimum_research_dependencies": 0,
        }
        self.concept = {
            "concept_id": "c1",
            "working_title": "Why Racing Brakes Behave Backwards",
            "premise": "Investigate a counterintuitive brake design constraint.",
            "audience_promise": "Explain the hidden engineering reason.",
            "format_intent": "long_form",
            "mechanism_id": "curiosity_gap",
            "mechanism_label": "Curiosity",
            "mechanism_application": "Open with a concrete unanswered question.",
            "transformation_method": "Independent subsystem and research path.",
            "research_questions": [
                "What thermal limits drive the design?",
            ],
            "source_dependency_test": {
                "passes": True,
                "source_assets_required": False,
            },
            "concept_gate": {
                "decision": "ACCEPT",
            },
        }

    def valid_package(self):
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
            "core_promise": "Explain why race brakes need conditions that would damage road brakes.",
            "curiosity_gap": "Why does the obvious road-car solution fail?",
            "expected_payoff": "Viewer understands the engineering tradeoff.",
            "format_intent": "long_form",
            "title_thumbnail_relationship": "Title asks why; thumbnail shows the surprising physical contrast.",
            "research_dependencies": [
                "Verify operating-temperature differences between representative race and road brakes."
            ],
        }

    def test_request_preserves_concept_and_no_ranking(self):
        request = build_package_request(
            self.concept,
            self.config,
        )

        self.assertEqual(request["concept_id"], "c1")
        self.assertEqual(
            request["package_count_requested"],
            5,
        )
        self.assertNotIn("score", request)
        self.assertNotIn("rank", request)

    def test_valid_package_passes(self):
        request = build_package_request(
            self.concept,
            self.config,
        )
        result = validate_response(
            {
                "concept_id": "c1",
                "packages": [self.valid_package()],
            },
            request,
            self.config,
        )

        self.assertEqual(len(result["accepted"]), 1)
        self.assertEqual(len(result["rejected"]), 0)

    def test_missing_thumbnail_message_rejects(self):
        request = build_package_request(
            self.concept,
            self.config,
        )
        package = self.valid_package()
        package["thumbnail"]["message"] = ""

        result = validate_response(
            {
                "concept_id": "c1",
                "packages": [package],
            },
            request,
            self.config,
        )

        self.assertEqual(len(result["accepted"]), 0)

    def test_empty_research_dependencies_are_allowed(self):
        request = build_package_request(
            self.concept,
            self.config,
        )
        package = self.valid_package()
        package["research_dependencies"] = []

        result = validate_response(
            {
                "concept_id": "c1",
                "packages": [package],
            },
            request,
            self.config,
        )

        self.assertEqual(len(result["accepted"]), 1)

    def test_blank_research_dependency_is_rejected(self):
        request = build_package_request(
            self.concept,
            self.config,
        )
        package = self.valid_package()
        package["research_dependencies"] = [""]

        result = validate_response(
            {
                "concept_id": "c1",
                "packages": [package],
            },
            request,
            self.config,
        )

        self.assertEqual(len(result["accepted"]), 0)

    def test_duplicate_package_id_is_rejected(self):
        request = build_package_request(
            self.concept,
            self.config,
        )
        package = self.valid_package()

        result = validate_response(
            {
                "concept_id": "c1",
                "packages": [package, dict(package)],
            },
            request,
            self.config,
        )

        self.assertEqual(len(result["accepted"]), 1)
        self.assertEqual(len(result["rejected"]), 1)


if __name__ == "__main__":
    unittest.main()
