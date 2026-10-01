import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import packaging_engine as module

from packaging_engine import (
    build_package_request,
    run_apply,
    validate_response,
)


class PackagingEngineTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "packages_per_concept": 3,
            "allowed_format_intents": [
                "long_form",
                "short",
                "either",
            ],
            "minimum_research_dependencies": 0,
            "title_max_words": 8,
            "title_max_chars": 56,
            "title_style_contract": "human_hook_v2",
        }
        self.concept = {
            "concept_id": "c1",
            "working_title": "Why Racing Brakes Behave Backwards",
            "premise": "Investigate a counterintuitive brake design constraint.",
            "audience_promise": "Explain the hidden engineering reason.",
            "viewer_problem": "Why do racing brakes need conditions that seem wrong for road cars?",
            "viewer_moment": "Trying to understand a counterintuitive engineering tradeoff.",
            "desired_outcome": "Understand why temperature changes the brake design.",
            "content_gap": {
                "hypothesis": "Many explanations show hot brakes without explaining the design consequence.",
                "evidence_status": "HYPOTHESIS",
                "evidence_basis": [],
            },
            "channel_fit": {
                "status": "FIT",
                "rationale": "Matches the automotive engineering audience.",
            },
            "title_clarity_test": {
                "options": [
                    "Why Racing Brakes Behave Backwards",
                    "Why F1 Brakes Hate Normal Temperatures",
                    "The Brake Problem Road Cars Never Face",
                ],
                "result": "PASS",
                "rationale": "Clear across multiple title framings.",
            },
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
            "viewer_problem": "Why do racing brakes need conditions that seem wrong for road cars?",
            "viewer_moment": "Trying to understand a counterintuitive engineering tradeoff.",
            "desired_outcome": "Understand why temperature changes the brake design.",
            "one_sentence_promise": "This video helps curious automotive viewers understand why racing brakes need extreme heat so they can make sense of the design tradeoff.",
            "gap_positioning": "Focus on the design consequence of temperature rather than merely showing glowing brakes.",
            "channel_fit_alignment": "Keeps the package centered on automotive engineering explanation.",
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
            3,
        )
        self.assertNotIn("score", request)
        self.assertNotIn("rank", request)

    def test_long_public_title_is_rejected(self):
        request = build_package_request(self.concept, self.config)
        package = self.valid_package()
        package["title"] = "Why This Airplane Tire Somehow Survives Every Violent Runway Impact"
        result = validate_response(
            {"concept_id": "c1", "packages": [package]},
            request,
            self.config,
        )
        self.assertEqual(len(result["accepted"]), 0)
        self.assertIn(
            "title must be at most 8 words",
            result["rejected"][0]["errors"],
        )

    def test_lecture_style_public_title_is_rejected(self):
        request = build_package_request(self.concept, self.config)
        package = self.valid_package()
        package["title"] = "The Physics of Racing Brakes"
        result = validate_response(
            {"concept_id": "c1", "packages": [package]},
            request,
            self.config,
        )
        self.assertEqual(len(result["accepted"]), 0)
        self.assertIn(
            "title uses lecture-style framing",
            result["rejected"][0]["errors"],
        )

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

    def test_request_preserves_viewer_problem_and_gap(self):
        request = build_package_request(
            self.concept,
            self.config,
        )

        self.assertEqual(
            request["concept"]["viewer_problem"],
            self.concept["viewer_problem"],
        )
        self.assertIn("content_gap", request["concept"])
        self.assertIn("channel_fit", request["concept"])

    def test_missing_one_sentence_promise_rejects(self):
        request = build_package_request(
            self.concept,
            self.config,
        )
        package = self.valid_package()
        package["one_sentence_promise"] = ""

        result = validate_response(
            {
                "concept_id": "c1",
                "packages": [package],
            },
            request,
            self.config,
        )

        self.assertEqual(len(result["accepted"]), 0)

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


    def test_cross_response_duplicate_package_ids_are_namespaced_not_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requests = root / "requests"
            responses = root / "responses"
            requests.mkdir()
            responses.mkdir()

            for concept_id in ("c1", "c2"):
                request_path = requests / f"{concept_id}.package_request.json"
                request_path.write_text(
                    json.dumps({"concept_id": concept_id}),
                    encoding="utf-8",
                )
                response = {
                    "concept_id": concept_id,
                    "response_provenance": {
                        "request_sha256": module.sha256_file(request_path),
                    },
                    "packages": [
                        {
                            "package_id": "package-1",
                            "title": concept_id,
                        }
                    ],
                }
                (responses / f"{concept_id}.json").write_text(
                    json.dumps(response),
                    encoding="utf-8",
                )

            with (
                patch.object(module, "OUTPUT_DIR", root),
                patch.object(module, "REQUESTS_DIR", requests),
                patch.object(module, "RESPONSES_DIR", responses),
                patch.object(module, "CANDIDATES_FILE", root / "candidates.json"),
                patch.object(module, "REJECTED_FILE", root / "rejected.json"),
                patch.object(module, "SUMMARY_FILE", root / "summary.json"),
                patch.object(module, "load_config", return_value=self.config),
                patch.object(
                    module,
                    "validate_response",
                    side_effect=lambda response, request, config: {
                        "accepted": response["packages"],
                        "rejected": [],
                    },
                ),
            ):
                result = run_apply()
                candidates = json.loads(
                    (root / "candidates.json").read_text(encoding="utf-8")
                )

        self.assertEqual(result["accepted_packages"], 2)
        self.assertEqual(result["rejected_packages"], 0)
        self.assertEqual(
            {item["package_id"] for item in candidates["packages"]},
            {"package-1", "c2--package-1"},
        )
        renamed = next(
            item for item in candidates["packages"]
            if item["package_id"] != "package-1"
        )
        self.assertEqual(renamed["model_package_id"], "package-1")


    def test_slug_collision_is_rejected_before_request_writes(self):
        with self.assertRaisesRegex(ValueError, "collide"):
            module.assert_unique_slug_ids(
                ["gear/ratio", "gear ratio"],
                label="concept",
            )


if __name__ == "__main__":
    unittest.main()
