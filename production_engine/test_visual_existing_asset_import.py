from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import visual_existing_asset_import as importer


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class VisualExistingAssetImportTests(unittest.TestCase):
    def packet(self, root: Path, *, editorial: bool = True):
        result_dir = root / "results"
        review_dir = root / "reviews"
        rights_dir = root / "rights"

        candidate = {
            "candidate_id": "youtube-abc" if editorial else "pexels-1",
            "shot_id": "shot-001",
            "media_type": "video",
            "source_tier": (
                "EDITORIAL_EXCERPT"
                if editorial
                else "FREE_COMMERCIAL_LICENSE"
            ),
            "source_url": (
                "https://www.youtube.com/watch?v=abc"
                if editorial
                else "https://www.pexels.com/video/1"
            ),
            "asset_url": None,
            "local_path": None,
            "creator": "Creator",
            "license": "UNKNOWN" if editorial else "Pexels License",
            "rights_status": "DISCOVERY_ONLY" if editorial else "VERIFIED",
            "commercial_use_allowed": None if editorial else True,
            "search_provider": "youtube_data_api" if editorial else "pexels",
            "state": "HUMAN_REVIEW_REQUIRED" if editorial else "ELIGIBLE",
            "reason": (
                "CREATOR_EXCERPT_RIGHTS_CONTEXT_REVIEW"
                if editorial
                else "VERIFIED_REUSE_RIGHTS"
            ),
        }
        result_path = write_json(
            result_dir / "c1.short.visual_search_results.json",
            {
                "concept_id": "c1",
                "format": "short",
                "shots": [{
                    "shot_id": "shot-001",
                    "candidates": [candidate],
                }],
            },
        )
        review_path = write_json(
            review_dir / "c1.short.visual_candidate_review.json",
            {
                "status": "READY_FOR_ROUGH_CUT",
                "source_result": str(result_path.resolve()),
                "source_result_sha256": importer.sha256_file(result_path),
                "decisions": {
                    "shot-001": {
                        "status": (
                            "SELECTED_PENDING_RIGHTS_CONTEXT_GATE"
                            if editorial
                            else "SELECTED"
                        ),
                        "candidate_id": candidate["candidate_id"],
                        "candidate_fingerprint": importer._hash_json(candidate),
                    }
                },
            },
        )
        rights_path = rights_dir / "c1.short.visual_rights_review.json"
        if editorial:
            write_json(
                rights_path,
                {
                    "source_candidate_review_sha256": importer.sha256_file(
                        review_path
                    ),
                    "decisions": {
                        "shot-001": {
                            "approved_for_rough_cut": True,
                            "candidate_id": candidate["candidate_id"],
                        }
                    },
                },
            )
        return result_dir, review_dir, rights_dir, review_path, rights_path

    def test_human_supplied_editorial_asset_is_registered_with_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_dir, review_dir, rights_dir, review_path, _ = self.packet(
                root,
                editorial=True,
            )
            source = root / "editorial.mp4"
            source.write_bytes(b"editorial-clip")
            assembly_dir = root / "assembly"
            assembly_dir.mkdir()
            assembly = write_json(
                assembly_dir / "c1.short.visual_assembly_plan.json",
                {"status": "WAITING_FOR_LOCAL_VISUAL_ASSETS"},
            )

            with (
                patch.object(importer, "RESULT_DIR", result_dir),
                patch.object(importer, "REVIEW_DIR", review_dir),
                patch.object(importer, "RIGHTS_DIR", rights_dir),
                patch.object(importer, "ASSET_DIR", root / "assets"),
                patch.object(importer, "REGISTRY_DIR", root / "registry"),
                patch.object(importer, "ASSEMBLY_DIR", assembly_dir),
                patch.object(importer, "ROUGH_DIR", root / "rough"),
                patch.object(importer, "SUMMARY_FILE", root / "summary.json"),
            ):
                record = importer.register(
                    candidate_review_file=str(review_path),
                    shot_id="shot-001",
                    asset_file=str(source),
                    note="Short transformed excerpt.",
                )
                snap = importer.snapshot()

        self.assertEqual(
            record["acquisition_method"],
            "MANUAL_HUMAN_SUPPLIED_FILE",
        )
        self.assertEqual(record["actual_cost_usd"] if "actual_cost_usd" in record else 0, 0)
        self.assertFalse(record["paid_provider_call_executed"])
        self.assertIn("rights_review", record["provenance"])
        self.assertTrue(Path(record["asset_file"]).exists())
        self.assertFalse(assembly.exists())
        self.assertEqual(snap["current"], 1)
        self.assertEqual(snap["manual"], 1)

    def test_manual_asset_registration_invalidates_placeholder_rough_cut(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_dir, review_dir, rights_dir, review_path, _ = self.packet(
                root,
                editorial=True,
            )
            source = root / "editorial.mp4"
            source.write_bytes(b"editorial-clip")
            rough_dir = root / "rough"
            rough_dir.mkdir()
            rough_path = write_json(
                rough_dir / "c1.short.visual_rough_cut.json",
                {"status": "READY_FOR_HUMAN_ROUGH_CUT_GATE"},
            )

            with (
                patch.object(importer, "RESULT_DIR", result_dir),
                patch.object(importer, "REVIEW_DIR", review_dir),
                patch.object(importer, "RIGHTS_DIR", rights_dir),
                patch.object(importer, "ASSET_DIR", root / "assets"),
                patch.object(importer, "REGISTRY_DIR", root / "registry"),
                patch.object(importer, "ASSEMBLY_DIR", root / "assembly"),
                patch.object(importer, "ROUGH_DIR", rough_dir),
            ):
                importer.register(
                    candidate_review_file=str(review_path),
                    shot_id="shot-001",
                    asset_file=str(source),
                )

            self.assertFalse(rough_path.exists())

    def test_editorial_asset_without_rights_approval_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_dir, review_dir, rights_dir, review_path, rights_path = self.packet(
                root,
                editorial=True,
            )
            rights_path.unlink()
            source = root / "editorial.mp4"
            source.write_bytes(b"editorial-clip")

            with (
                patch.object(importer, "RESULT_DIR", result_dir),
                patch.object(importer, "REVIEW_DIR", review_dir),
                patch.object(importer, "RIGHTS_DIR", rights_dir),
                patch.object(importer, "ASSET_DIR", root / "assets"),
                patch.object(importer, "REGISTRY_DIR", root / "registry"),
                patch.object(importer, "ASSEMBLY_DIR", root / "assembly"),
                patch.object(importer, "ROUGH_DIR", root / "rough"),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "Rights/Context Gate approval is required",
                ):
                    importer.register(
                        candidate_review_file=str(review_path),
                        shot_id="shot-001",
                        asset_file=str(source),
                    )

    def test_non_editorial_selected_asset_can_be_supplied_manually(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_dir, review_dir, rights_dir, review_path, _ = self.packet(
                root,
                editorial=False,
            )
            source = root / "stock.mp4"
            source.write_bytes(b"stock-clip")

            with (
                patch.object(importer, "RESULT_DIR", result_dir),
                patch.object(importer, "REVIEW_DIR", review_dir),
                patch.object(importer, "RIGHTS_DIR", rights_dir),
                patch.object(importer, "ASSET_DIR", root / "assets"),
                patch.object(importer, "REGISTRY_DIR", root / "registry"),
                patch.object(importer, "ASSEMBLY_DIR", root / "assembly"),
                patch.object(importer, "ROUGH_DIR", root / "rough"),
            ):
                record = importer.register(
                    candidate_review_file=str(review_path),
                    shot_id="shot-001",
                    asset_file=str(source),
                )

        self.assertEqual(record["source_tier"], "FREE_COMMERCIAL_LICENSE")
        self.assertNotIn("rights_review", record["provenance"])


if __name__ == "__main__":
    unittest.main()
