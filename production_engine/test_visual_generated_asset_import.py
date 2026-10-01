from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import visual_generated_asset_import as importer


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class VisualGeneratedAssetImportTests(unittest.TestCase):
    def request(self, gap_path: Path, spend_path: Path) -> dict:
        return {
            "artifact": "visual_generation_request",
            "concept_id": "c1",
            "format": "short",
            "shot_id": "shot-001",
            "spend_authorization": {
                "human_authorized": True,
                "execution_authorized": False,
                "max_cost_usd": 2.5,
            },
            "provenance": {
                "gap_plan": str(gap_path.resolve()),
                "gap_plan_sha256": importer.sha256_file(gap_path),
                "visual_spend_review": str(spend_path.resolve()),
                "visual_spend_review_sha256": importer.sha256_file(spend_path),
            },
        }

    def test_register_copies_asset_and_preserves_cost_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request_dir = root / "requests"
            asset_dir = root / "assets"
            registry_dir = root / "registry"
            gap_path = write_json(root / "gap.json", {"version": 1})
            spend_path = write_json(root / "spend.json", {"version": 1})
            request_path = write_json(
                request_dir / "c1.short.shot-001.visual_generation_request.json",
                self.request(gap_path, spend_path),
            )
            source = root / "source.mp4"
            source.write_bytes(b"generated-video-bytes")

            with (
                patch.object(importer, "REQUEST_DIR", request_dir),
                patch.object(importer, "ASSET_DIR", asset_dir),
                patch.object(importer, "REGISTRY_DIR", registry_dir),
            ):
                result = importer.register(
                    request_file=str(request_path),
                    asset_file=str(source),
                    actual_cost_usd=1.75,
                    provider="higgsfield",
                    provider_job_id="job-123",
                    note="Manual provider run.",
                )
                snap = importer.snapshot()

        self.assertEqual(result["status"], "REGISTERED_CURRENT")
        self.assertEqual(result["actual_cost_usd"], 1.75)
        self.assertEqual(result["authorized_max_cost_usd"], 2.5)
        self.assertFalse(result["app_provider_call_executed"])
        self.assertEqual(
            result["execution_origin"],
            "EXTERNAL_HUMAN_PROVIDER_ACTION",
        )
        self.assertTrue(Path(result["asset_file"]).exists())
        self.assertEqual(snap["current"], 1)
        self.assertEqual(snap["actual_cost_total_usd"], 1.75)

    def test_cost_above_human_ceiling_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request_dir = root / "requests"
            gap_path = write_json(root / "gap.json", {"version": 1})
            spend_path = write_json(root / "spend.json", {"version": 1})
            request_path = write_json(
                request_dir / "c1.short.shot-001.visual_generation_request.json",
                self.request(gap_path, spend_path),
            )
            source = root / "source.png"
            source.write_bytes(b"png-bytes")

            with patch.object(importer, "REQUEST_DIR", request_dir):
                with self.assertRaisesRegex(
                    ValueError,
                    "exceeds the human-authorized",
                ):
                    importer.register(
                        request_file=str(request_path),
                        asset_file=str(source),
                        actual_cost_usd=3.0,
                        provider="higgsfield",
                    )

    def test_stale_request_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request_dir = root / "requests"
            gap_path = write_json(root / "gap.json", {"version": 1})
            spend_path = write_json(root / "spend.json", {"version": 1})
            request_path = write_json(
                request_dir / "c1.short.shot-001.visual_generation_request.json",
                self.request(gap_path, spend_path),
            )
            gap_path.write_text(json.dumps({"version": 2}), encoding="utf-8")
            source = root / "source.webp"
            source.write_bytes(b"webp-bytes")

            with patch.object(importer, "REQUEST_DIR", request_dir):
                with self.assertRaisesRegex(
                    ValueError,
                    "STALE_VISUAL_GENERATION_REQUEST",
                ):
                    importer.register(
                        request_file=str(request_path),
                        asset_file=str(source),
                        actual_cost_usd=1.0,
                        provider="higgsfield",
                    )


if __name__ == "__main__":
    unittest.main()
