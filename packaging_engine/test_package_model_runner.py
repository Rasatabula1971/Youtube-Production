from __future__ import annotations

import unittest

import package_model_runner as runner


class PackageModelRunnerReworkTests(unittest.TestCase):
    def request(self):
        return {
            "concept_id": "c1",
            "allowed_format_intents": ["short", "long_form", "either"],
            "package_count_requested": 3,
            "human_rework_iteration": 1,
            "human_rework_note": (
                "Audience must be anyone who flies, not a specialist group."
            ),
            "human_rework_package_id": "p2",
            "human_rework_keep_criteria": ["promise_clear"],
            "human_rework_change_criteria": ["viewer_awareness_fit"],
            "human_rework_original_package": {
                "package_id": "p2",
                "expected_viewer": "Aviation hobbyists",
            },
            "human_rework_original_titles": {
                "short": [{"candidate_id": "short-curiosity", "angle": "curiosity", "title": "Keep Short"}],
                "long_form": [{"candidate_id": "long-curiosity", "angle": "curiosity", "title": "Keep Long"}],
            },
            "human_rework_original_packages": [
                {"package_id": "p1", "title": "Keep One"},
                {"package_id": "p2", "title": "Revise Me"},
                {"package_id": "p3", "title": "Keep Three"},
            ],
        }

    def test_rework_schema_targets_one_stable_package(self):
        schema = runner.response_schema(self.request())
        packages = schema["properties"]["packages"]
        package_id = packages["items"]["properties"]["package_id"]

        self.assertEqual(packages["maxItems"], 1)
        self.assertEqual(package_id["const"], "p2")

    def test_base_prompt_requires_human_first_nonlecture_angles(self):
        request = {
            "concept_id": "c1",
            "allowed_format_intents": ["short"],
            "package_count_requested": 3,
            "title_contracts": {
                "short": {
                    "max_words": 7,
                    "max_chars": 48,
                    "target_words": "3-7",
                },
                "long_form": {
                    "max_words": 10,
                    "max_chars": 70,
                    "target_words": "5-10",
                },
            },
        }
        prompt = runner.build_prompt(request, maximum_chars=95000)

        self.assertIn("exactly five Short titles", prompt)
        self.assertIn("exactly five Long-form titles", prompt)
        self.assertIn("curiosity, stakes, unexpected, mystery, payoff", prompt)
        self.assertIn("The explanation is the payoff, not the pitch", prompt)
        self.assertIn("Do not lead like a lecture", prompt)
        self.assertIn("The Physics of X", prompt)
        self.assertIn("Shorts: target 3-7 words", prompt)
        self.assertIn("Long-form: target 5-10 words", prompt)
        self.assertIn("proposed PUBLIC YouTube title", prompt)
        self.assertIn("Generate each format independently", prompt)

    def test_title_schema_uses_largest_format_character_limit(self):
        request = {
            "concept_id": "c1",
            "allowed_format_intents": ["short", "long_form"],
            "package_count_requested": 3,
            "title_contracts": {
                "short": {"max_chars": 48},
                "long_form": {"max_chars": 70},
            },
        }
        schema = runner.response_schema(request)
        title = schema["properties"]["packages"]["items"]["properties"]["title"]
        self.assertEqual(title["maxLength"], 70)

    def test_base_prompt_does_not_force_specialist_audience(self):
        request = {
            "concept_id": "c1",
            "allowed_format_intents": ["short"],
            "package_count_requested": 2,
        }
        prompt = runner.build_prompt(request, maximum_chars=95000)

        self.assertIn("Do not invent a specialist audience", prompt)
        self.assertIn("keep the audience broad", prompt)
        self.assertIn("general curious viewers", prompt)

    def test_rework_prompt_marks_human_note_authoritative(self):
        prompt = runner.build_prompt(self.request(), maximum_chars=95000)

        self.assertIn("AUTHORITATIVE human directive", prompt)
        self.assertIn("anyone who flies", prompt)
        self.assertIn("Do not silently substitute a narrower", prompt)

    def test_rework_merge_preserves_other_packages(self):
        response = {
            "concept_id": "c1",
            "titles": {
                "short": [{"candidate_id": "short-curiosity", "angle": "curiosity", "title": "Changed Short"}],
                "long_form": [{"candidate_id": "long-curiosity", "angle": "curiosity", "title": "Changed Long"}],
            },
            "packages": [
                {
                    "package_id": "p2",
                    "title": "Revised",
                    "expected_viewer": "Anyone who flies",
                }
            ],
        }

        merged = runner._merge_human_rework_response(self.request(), response)

        self.assertEqual(
            [item["package_id"] for item in merged["packages"]],
            ["p1", "p2", "p3"],
        )
        self.assertEqual(merged["packages"][0]["title"], "Keep One")
        self.assertEqual(merged["packages"][1]["expected_viewer"], "Anyone who flies")
        self.assertEqual(merged["packages"][2]["title"], "Keep Three")
        self.assertEqual(
            merged["titles"]["short"][0]["title"],
            "Keep Short",
        )
        self.assertEqual(
            merged["titles"]["long_form"][0]["title"],
            "Keep Long",
        )


    def test_title_candidate_schema_requires_five_per_format(self):
        request = {
            "concept_id": "c1",
            "allowed_format_intents": ["short", "long_form", "either"],
            "package_count_requested": 3,
            "title_contracts": {
                "short": {"max_chars": 48},
                "long_form": {"max_chars": 70},
            },
        }
        schema = runner.response_schema(request)
        titles = schema["properties"]["titles"]

        self.assertEqual(titles["properties"]["short"]["minItems"], 5)
        self.assertEqual(titles["properties"]["short"]["maxItems"], 5)
        self.assertEqual(titles["properties"]["long_form"]["minItems"], 5)
        self.assertEqual(titles["properties"]["long_form"]["maxItems"], 5)
        self.assertEqual(
            titles["properties"]["short"]["items"]["properties"]["angle"]["enum"],
            ["curiosity", "stakes", "unexpected", "mystery", "payoff"],
        )



if __name__ == "__main__":
    unittest.main()
