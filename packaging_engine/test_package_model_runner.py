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

    def test_rework_prompt_marks_human_note_authoritative(self):
        prompt = runner.build_prompt(self.request(), maximum_chars=95000)

        self.assertIn("AUTHORITATIVE human directive", prompt)
        self.assertIn("anyone who flies", prompt)
        self.assertIn("Do not silently substitute a narrower", prompt)

    def test_rework_merge_preserves_other_packages(self):
        response = {
            "concept_id": "c1",
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


if __name__ == "__main__":
    unittest.main()
