from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import visual_asset_acquire as acquire


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class VisualAssetAcquireTests(unittest.TestCase):
    def stock_candidate(self) -> dict:
        return {
            "candidate_id": "pexels-1",
            "shot_id": "shot-001",
            "title": "Pexels clip",
            "media_type": "video",
            "source_tier": "FREE_COMMERCIAL_LICENSE",
            "source_url": "https://www.pexels.com/video/1",
            "asset_url": "https://videos.pexels.com/video-files/1.mp4",
            "local_path": None,
            "creator": "Creator",
            "license": "Pexels License",
            "rights_status": "VERIFIED",
            "commercial_use_allowed": True,
            "duration_seconds": 5,
            "thumbnail_url": None,
            "search_provider": "pexels",
            "state": "ELIGIBLE",
            "reason": "VERIFIED_REUSE_RIGHTS",
            "estimated_cost_usd": 0.0,
        }

    def editorial_candidate(self) -> dict:
        candidate = self.stock_candidate()
        candidate.update({
            "candidate_id": "youtube-abc",
            "source_tier": "EDITORIAL_EXCERPT",
            "source_url": "https://www.youtube.com/watch?v=abc",
            "asset_url": None,
            "license": "UNKNOWN",
            "rights_status": "DISCOVERY_ONLY",
            "commercial_use_allowed": None,
            "search_provider": "youtube_data_api",
            "state": "HUMAN_REVIEW_REQUIRED",
            "reason": "CREATOR_EXCERPT_RIGHTS_CONTEXT_REVIEW",
        })
        return candidate

    def setup_packet(
        self,
        root: Path,
        candidate: dict,
        decision_status: str,
    ) -> tuple[Path, Path, Path]:
        result_dir = root / "results"
        review_dir = root / "reviews"
        rights_dir = root / "rights"
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
                "source_result_sha256": acquire.sha256_file(result_path),
                "decisions": {
                    "shot-001": {
                        "status": decision_status,
                        "candidate_id": candidate["candidate_id"],
                        "candidate_fingerprint": acquire._hash_json(candidate),
                    }
                },
            },
        )
        return result_dir, review_dir, rights_dir

    def test_verified_stock_selection_is_acquired_locally(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = self.stock_candidate()
            result_dir, review_dir, rights_dir = self.setup_packet(
                root,
                candidate,
                "SELECTED",
            )
            asset_dir = root / "assets"
            registry_dir = root / "registry"
            summary = root / "summary.json"

            def fake_download(*, url, provider, destination):
                self.assertEqual(provider, "pexels")
                self.assertTrue(url.startswith("https://videos.pexels.com/"))
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"stock-video")

            with (
                patch.object(acquire, "RESULT_DIR", result_dir),
                patch.object(acquire, "REVIEW_DIR", review_dir),
                patch.object(acquire, "RIGHTS_DIR", rights_dir),
                patch.object(acquire, "ASSET_DIR", asset_dir),
                patch.object(acquire, "REGISTRY_DIR", registry_dir),
                patch.object(acquire, "SUMMARY_FILE", summary),
                patch.object(
                    acquire,
                    "search_result_is_current",
                    side_effect=lambda path: (
                        (
                            json.loads(path.read_text(encoding="utf-8")),
                            Path("request"),
                            {},
                        )
                        if path.exists()
                        else None
                    ),
                ),
                patch.object(acquire, "_download_stock", side_effect=fake_download),
            ):
                result = acquire.acquire()

        self.assertEqual(result["acquired"], 1)
        self.assertEqual(result["manual_required"], 0)
        self.assertEqual(result["failures"], 0)
        record = result["items"][0]
        self.assertEqual(
            record["acquisition_method"],
            "VERIFIED_STOCK_DIRECT_DOWNLOAD",
        )
        self.assertFalse(record["paid_provider_call_executed"])
        self.assertTrue(Path(record["asset_file"]).exists())

    def test_editorial_selection_is_never_auto_downloaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = self.editorial_candidate()
            result_dir, review_dir, rights_dir = self.setup_packet(
                root,
                candidate,
                "SELECTED_PENDING_RIGHTS_CONTEXT_GATE",
            )
            review_path = review_dir / "c1.short.visual_candidate_review.json"
            write_json(
                rights_dir / "c1.short.visual_rights_review.json",
                {
                    "source_candidate_review_sha256": acquire.sha256_file(
                        review_path
                    ),
                    "decisions": {
                        "shot-001": {
                            "approved_for_rough_cut": True,
                            "candidate_id": "youtube-abc",
                            "selection_candidate_fingerprint": (
                                json.loads(
                                    review_path.read_text(encoding="utf-8")
                                )["decisions"]["shot-001"][
                                    "candidate_fingerprint"
                                ]
                            ),
                            "selection_result_fingerprint": (
                                json.loads(
                                    review_path.read_text(encoding="utf-8")
                                )["decisions"]["shot-001"].get(
                                    "result_fingerprint",
                                    "",
                                )
                            ),
                        }
                    },
                },
            )

            with (
                patch.object(acquire, "RESULT_DIR", result_dir),
                patch.object(acquire, "REVIEW_DIR", review_dir),
                patch.object(acquire, "RIGHTS_DIR", rights_dir),
                patch.object(acquire, "ASSET_DIR", root / "assets"),
                patch.object(acquire, "REGISTRY_DIR", root / "registry"),
                patch.object(acquire, "SUMMARY_FILE", root / "summary.json"),
                patch.object(
                    acquire,
                    "search_result_is_current",
                    side_effect=lambda path: (
                        (
                            json.loads(path.read_text(encoding="utf-8")),
                            Path("request"),
                            {},
                        )
                        if path.exists()
                        else None
                    ),
                ),
                patch.object(acquire, "_download_stock") as downloader,
            ):
                result = acquire.acquire()

        downloader.assert_not_called()
        self.assertEqual(result["acquired"], 0)
        self.assertEqual(result["manual_required"], 1)
        item = result["manual_items"][0]
        self.assertEqual(
            item["reason"],
            "EDITORIAL_EXCERPT_REQUIRES_MANUAL_ASSET_SUPPLY",
        )
        self.assertEqual(
            item["candidate_review_file"],
            str(review_path),
        )

    def test_stale_rights_review_is_not_treated_as_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = self.editorial_candidate()
            result_dir, review_dir, rights_dir = self.setup_packet(
                root,
                candidate,
                "SELECTED_PENDING_RIGHTS_CONTEXT_GATE",
            )
            review_path = review_dir / "c1.short.visual_candidate_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8"))
            review["decisions"]["shot-001"]["result_fingerprint"] = "result-fp"
            review_path.write_text(json.dumps(review), encoding="utf-8")
            rights_path = rights_dir / "c1.short.visual_rights_review.json"
            write_json(
                rights_path,
                {
                    "source_candidate_review_sha256": "stale-review-hash",
                    "decisions": {
                        "shot-001": {
                            "approved_for_rough_cut": True,
                            "candidate_id": "youtube-abc",
                            "selection_candidate_fingerprint": review[
                                "decisions"
                            ]["shot-001"]["candidate_fingerprint"],
                            "selection_result_fingerprint": "result-fp",
                        }
                    },
                },
            )
            result_path = result_dir / "c1.short.visual_search_results.json"
            current_result = json.loads(
                result_path.read_text(encoding="utf-8")
            )

            with (
                patch.object(acquire, "RESULT_DIR", result_dir),
                patch.object(acquire, "REVIEW_DIR", review_dir),
                patch.object(acquire, "RIGHTS_DIR", rights_dir),
                patch.object(acquire, "ASSET_DIR", root / "assets"),
                patch.object(acquire, "REGISTRY_DIR", root / "registry"),
                patch.object(acquire, "SUMMARY_FILE", root / "summary.json"),
                patch.object(
                    acquire,
                    "search_result_is_current",
                    return_value=(current_result, Path("request"), {}),
                ),
            ):
                result = acquire.acquire()

        self.assertEqual(result["acquired"], 0)
        self.assertEqual(result["manual_required"], 0)
        self.assertEqual(result["failures"], 1)
        self.assertEqual(
            result["failure_items"][0]["error"],
            "STALE_OR_MISSING_RIGHTS_CONTEXT_APPROVAL",
        )

    def test_stock_download_host_allowlist_rejects_wrong_host(self):
        with self.assertRaisesRegex(ValueError, "not allowed"):
            acquire._assert_stock_url_allowed(
                "https://evil.example/video.mp4",
                "pexels",
            )


if __name__ == "__main__":
    unittest.main()
