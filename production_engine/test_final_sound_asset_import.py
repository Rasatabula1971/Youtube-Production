from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import final_sound_asset_import as sound_asset


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class FinalSoundAssetImportTests(unittest.TestCase):
    def plan_payload(self) -> dict:
        requirement = {
            "requirement_id": "seg1:music",
            "segment_id": "seg1",
            "kind": "MUSIC",
            "index": 0,
            "direction": "rising tension",
            "duck_under_narration": True,
            "fingerprint": "abc123",
        }
        return {
            "artifact": "final_sound_plan",
            "concept_id": "c1",
            "format": "short",
            "status": "WAITING_FOR_FINAL_SOUND_ASSETS",
            "requirements": [requirement],
            "requirements_count": 1,
        }

    def patched(self, root: Path, plan: dict):
        return (
            patch.object(sound_asset, "PLAN_DIR", root / "plans"),
            patch.object(sound_asset, "ASSET_DIR", root / "assets"),
            patch.object(sound_asset, "REGISTRY_DIR", root / "registry"),
            patch.object(sound_asset, "plan_is_current", return_value=plan),
        )

    def test_register_copies_licensed_asset_and_records_no_app_spend(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.plan_payload()
            plan_path = write_json(
                root / "plans" / "c1.short.final_sound_plan.json",
                plan,
            )
            source = root / "licensed.wav"
            source.write_bytes(b"audio-bytes")

            with self.patched(root, plan):
                record = sound_asset.register(
                    plan_file=str(plan_path),
                    requirement_id="seg1:music",
                    asset_file=str(source),
                    licence_reference="lic-001",
                    commercial_use_confirmed=True,
                    source_name="licensed_library",
                )

        self.assertEqual(record["status"], "REGISTERED_CURRENT")
        self.assertTrue(record["rights"]["commercial_use_confirmed"])
        self.assertEqual(record["rights"]["licence_reference"], "lic-001")
        self.assertFalse(record["cost"]["app_spend_authorized"])
        self.assertFalse(record["cost"]["app_provider_call_executed"])

    def test_paid_external_asset_requires_purchase_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.plan_payload()
            plan_path = write_json(
                root / "plans" / "c1.short.final_sound_plan.json",
                plan,
            )
            source = root / "licensed.wav"
            source.write_bytes(b"audio")

            with self.patched(root, plan):
                with self.assertRaisesRegex(
                    ValueError,
                    "external purchase",
                ):
                    sound_asset.register(
                        plan_file=str(plan_path),
                        requirement_id="seg1:music",
                        asset_file=str(source),
                        licence_reference="lic-paid",
                        commercial_use_confirmed=True,
                        actual_cost_usd=5,
                        external_purchase_confirmed=False,
                    )

    def test_commercial_rights_and_licence_reference_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.plan_payload()
            plan_path = write_json(
                root / "plans" / "c1.short.final_sound_plan.json",
                plan,
            )
            source = root / "licensed.wav"
            source.write_bytes(b"audio")

            with self.patched(root, plan):
                with self.assertRaisesRegex(
                    ValueError,
                    "Commercial-use rights",
                ):
                    sound_asset.register(
                        plan_file=str(plan_path),
                        requirement_id="seg1:music",
                        asset_file=str(source),
                        licence_reference="lic-001",
                        commercial_use_confirmed=False,
                    )
                with self.assertRaisesRegex(
                    ValueError,
                    "licence_reference",
                ):
                    sound_asset.register(
                        plan_file=str(plan_path),
                        requirement_id="seg1:music",
                        asset_file=str(source),
                        licence_reference="",
                        commercial_use_confirmed=True,
                    )

    def test_omit_requires_human_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.plan_payload()
            plan_path = write_json(
                root / "plans" / "c1.short.final_sound_plan.json",
                plan,
            )

            with self.patched(root, plan):
                with self.assertRaisesRegex(ValueError, "human note"):
                    sound_asset.omit(
                        plan_file=str(plan_path),
                        requirement_id="seg1:music",
                        note="",
                    )
                record = sound_asset.omit(
                    plan_file=str(plan_path),
                    requirement_id="seg1:music",
                    note="Intentional narration-only opening.",
                )

        self.assertEqual(record["status"], "OMITTED_BY_HUMAN")

    def test_resolution_currentness_detects_asset_byte_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.plan_payload()
            plan_path = write_json(
                root / "plans" / "c1.short.final_sound_plan.json",
                plan,
            )
            source = root / "licensed.wav"
            source.write_bytes(b"audio")

            with self.patched(root, plan):
                record = sound_asset.register(
                    plan_file=str(plan_path),
                    requirement_id="seg1:music",
                    asset_file=str(source),
                    licence_reference="lic-001",
                    commercial_use_confirmed=True,
                )
                resolution_path = sound_asset._resolution_path(
                    plan,
                    plan["requirements"][0],
                )
                self.assertIsNotNone(
                    sound_asset.resolution_is_current(resolution_path)
                )
                Path(record["asset_file"]).write_bytes(b"changed")
                self.assertIsNone(
                    sound_asset.resolution_is_current(resolution_path)
                )

    def test_snapshot_ready_only_after_all_current_requirements_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.plan_payload()
            plan_path = write_json(
                root / "plans" / "c1.short.final_sound_plan.json",
                plan,
            )
            source = root / "licensed.wav"
            source.write_bytes(b"audio")

            with self.patched(root, plan):
                before = sound_asset.snapshot()
                self.assertFalse(before["ready"])
                self.assertEqual(before["pending"], 1)

                sound_asset.register(
                    plan_file=str(plan_path),
                    requirement_id="seg1:music",
                    asset_file=str(source),
                    licence_reference="lic-001",
                    commercial_use_confirmed=True,
                )
                after = sound_asset.snapshot()

        self.assertTrue(after["ready"])
        self.assertEqual(after["status"], "FINAL_SOUND_ASSETS_READY")
        self.assertEqual(after["resolved"], 1)
        self.assertEqual(after["app_provider_calls"], 0)
        self.assertEqual(after["final_renders"], 0)


if __name__ == "__main__":
    unittest.main()
