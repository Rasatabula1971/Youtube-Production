import json
import tempfile
import unittest
from pathlib import Path

from channel_profiles.channel_profile import (
    load_active_profile_binding,
    normalize_binding,
    validate_profile,
)


def approved_profile():
    return {
        "schema_version": 1,
        "profile_id": "engineering_nonengineers",
        "version": 1,
        "status": "APPROVED",
        "channel_id": "engineering_nonengineers",
        "channel_name": "Engineering for Non-Engineers",
        "niche": "engineering",
        "audience": {
            "knowledge_level": "non_engineer",
            "assumed_knowledge": "minimal",
            "motivation": "understand how surprising things work",
        },
        "narrator_role": {
            "identity": "curious_explainer",
            "authority_style": "informed_not_professorial",
        },
        "tone": {
            "primary": "curious",
            "secondary": ["dramatic", "conversational", "confident"],
        },
        "technical_language": {
            "jargon_policy": "translate_immediately",
            "equations": "rarely",
            "analogy_preference": "high",
        },
        "sentence_style": {
            "preferred_length": "short_to_medium",
            "complexity": "low",
            "active_voice": "preferred",
        },
        "storytelling": {
            "human_examples": "preferred",
            "mystery": "high",
            "humour": "light",
        },
        "prohibited_style": [
            "textbook introductions",
            "lets dive in",
            "in todays video",
        ],
        "evidence_style": {
            "state_uncertainty": True,
            "distinguish_fact_from_hypothesis": True,
            "numbers_require_support": True,
        },
        "provenance": {
            "created_from": "channel_setup_gate",
            "approved_by": "human",
            "approved_at": "2026-10-01T19:53:00-04:00",
        },
    }


class ChannelVoiceProfileTests(unittest.TestCase):
    def test_default_unconfigured_profile_is_inactive(self):
        binding = load_active_profile_binding()

        self.assertEqual(binding["profile"]["status"], "UNCONFIGURED")
        self.assertEqual(binding["profile"]["version"], 0)
        self.assertFalse(binding["apply_to_generation"])

    def test_approved_profile_is_active(self):
        binding = normalize_binding(
            {
                "profile": approved_profile(),
                "binding": {"profile_path": "test.json"},
                "apply_to_generation": False,
            }
        )

        self.assertTrue(binding["apply_to_generation"])
        self.assertEqual(
            binding["profile"]["profile_id"],
            "engineering_nonengineers",
        )

    def test_approved_profile_requires_voice_sections(self):
        profile = approved_profile()
        profile["tone"] = None

        validation = validate_profile(profile)

        self.assertFalse(validation["valid"])
        self.assertTrue(
            any("non-empty tone" in item for item in validation["errors"])
        )

    def test_unconfigured_profile_cannot_smuggle_voice_rules(self):
        binding = load_active_profile_binding()
        profile = dict(binding["profile"])
        profile["prohibited_style"] = ["fake rule"]

        validation = validate_profile(profile)

        self.assertFalse(validation["valid"])
        self.assertTrue(
            any("must not define prohibited_style" in item
                for item in validation["errors"])
        )

    def test_selector_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            container = Path(tmp)
            root = container / "channel_profiles"
            root.mkdir()
            selector = root / "active_profile.json"
            outside = container / "outside_profile.json"
            outside.write_text(json.dumps(approved_profile()), encoding="utf-8")
            selector.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "profile_path": "../outside_profile.json",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "must stay inside"):
                load_active_profile_binding(selector)


if __name__ == "__main__":
    unittest.main()
