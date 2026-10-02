from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import visual_rights_review as rights


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def current_result_state(path: Path):
    if not path.exists():
        return None
    return (
        json.loads(path.read_text(encoding="utf-8")),
        Path("request"),
        {},
    )


class VisualRightsReviewTests(unittest.TestCase):
    def fixture(self, root: Path):
        result_dir = root / "results"
        review_dir = root / "candidate_reviews"
        rights_dir = root / "rights"
        result_dir.mkdir()
        review_dir.mkdir()
        rights_dir.mkdir()

        candidate = {
            "candidate_id": "creator-1",
            "shot_id": "shot-001",
            "title": "Creator clip",
            "source_tier": "CREATOR_EDITORIAL",
            "source_url": "https://example.test/creator-1",
            "creator": "Example Creator",
            "license": "Context review required",
            "rights_status": "DISCOVERY_ONLY",
            "commercial_use_allowed": None,
            "human_review_required": True,
            "state": "HUMAN_REVIEW_REQUIRED",
        }
        shot = {
            "shot_id": "shot-001",
            "shot_fingerprint": "shot-fp",
            "candidates": [candidate],
        }
        result = {
            "artifact": "visual_search_results",
            "concept_id": "c1",
            "format": "short",
            "status": "READY_FOR_CANDIDATE_REVIEW",
            "shots": [shot],
        }
        result_path = result_dir / "c1.short.visual_search_results.json"
        result_path.write_text(json.dumps(result), encoding="utf-8")

        review = {
            "artifact": "visual_candidate_review",
            "concept_id": "c1",
            "format": "short",
            "status": "READY_FOR_ROUGH_CUT",
            "source_result": str(result_path),
            "source_result_sha256": rights.sha256_file(result_path),
            "decisions": {
                "shot-001": {
                    "action": "SELECT",
                    "status": "SELECTED_PENDING_RIGHTS_CONTEXT_GATE",
                    "candidate_id": "creator-1",
                    "candidate_fingerprint": digest(candidate),
                    "result_fingerprint": digest(shot),
                }
            },
        }
        review_path = review_dir / "c1.short.visual_candidate_review.json"
        review_path.write_text(json.dumps(review), encoding="utf-8")
        return result_dir, review_dir, rights_dir, result_path, review_path

    def patch_dirs(self, result_dir: Path, review_dir: Path, rights_dir: Path):
        return (
            patch.object(rights, "SEARCH_RESULT_DIR", result_dir),
            patch.object(rights, "CANDIDATE_REVIEW_DIR", review_dir),
            patch.object(rights, "RIGHTS_DIR", rights_dir),
            patch.object(
                rights,
                "search_result_is_current",
                side_effect=current_result_state,
            ),
        )

    def test_rights_decision_survives_unrelated_review_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_dir, review_dir, rights_dir, _, review_path = self.fixture(root)
            with (
                self.patch_dirs(result_dir, review_dir, rights_dir)[0],
                self.patch_dirs(result_dir, review_dir, rights_dir)[1],
                self.patch_dirs(result_dir, review_dir, rights_dir)[2],
                self.patch_dirs(result_dir, review_dir, rights_dir)[3],
            ):
                saved = rights.apply_action(
                    candidate_review_file=str(review_path),
                    shot_id="shot-001",
                    decision="APPROVE_CONTEXT_USE",
                    transformative_purpose=(
                        "Brief excerpt used as the event being analyzed "
                        "under original explanatory narration."
                    ),
                )
                self.assertEqual(saved["status"], "COMPLETE")

                review = json.loads(review_path.read_text(encoding="utf-8"))
                review["decisions"]["shot-002"] = {
                    "action": "REJECT_ALL",
                    "status": "REJECT_ALL",
                    "candidate_id": None,
                }
                review_path.write_text(json.dumps(review), encoding="utf-8")
                snapshot = rights.snapshot()

            self.assertTrue(snapshot["complete"])
            self.assertEqual(snapshot["required"], 1)
            self.assertEqual(snapshot["decided"], 1)
            self.assertEqual(snapshot["approved"], 1)
            self.assertEqual(snapshot["stale_removed"], 0)

    def test_stale_search_result_blocks_rights_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_dir, review_dir, rights_dir, _, review_path = self.fixture(root)
            with (
                patch.object(rights, "SEARCH_RESULT_DIR", result_dir),
                patch.object(rights, "CANDIDATE_REVIEW_DIR", review_dir),
                patch.object(rights, "RIGHTS_DIR", rights_dir),
                patch.object(
                    rights,
                    "search_result_is_current",
                    return_value=None,
                ),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "STALE_VISUAL_CANDIDATE_REVIEW",
                ):
                    rights.apply_action(
                        candidate_review_file=str(review_path),
                        shot_id="shot-001",
                        decision="APPROVE_CONTEXT_USE",
                        transformative_purpose="Explain the event.",
                    )
                snapshot = rights.snapshot()

            self.assertEqual(snapshot["required"], 0)
            self.assertEqual(snapshot["stale_reviews"], 1)
            self.assertEqual(snapshot["items"], [])

    def test_selected_candidate_change_invalidates_old_rights_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_dir, review_dir, rights_dir, result_path, review_path = self.fixture(root)
            with (
                patch.object(rights, "SEARCH_RESULT_DIR", result_dir),
                patch.object(rights, "CANDIDATE_REVIEW_DIR", review_dir),
                patch.object(rights, "RIGHTS_DIR", rights_dir),
                patch.object(
                    rights,
                    "search_result_is_current",
                    side_effect=current_result_state,
                ),
            ):
                rights.apply_action(
                    candidate_review_file=str(review_path),
                    shot_id="shot-001",
                    decision="APPROVE_CONTEXT_USE",
                    transformative_purpose="Analyze the event under original narration.",
                )

                result = json.loads(result_path.read_text(encoding="utf-8"))
                replacement = {
                    **result["shots"][0]["candidates"][0],
                    "candidate_id": "creator-2",
                    "source_url": "https://example.test/creator-2",
                }
                result["shots"][0]["candidates"] = [replacement]
                result_path.write_text(json.dumps(result), encoding="utf-8")

                review = json.loads(review_path.read_text(encoding="utf-8"))
                review["source_result_sha256"] = rights.sha256_file(result_path)
                review["decisions"]["shot-001"].update(
                    {
                        "candidate_id": "creator-2",
                        "candidate_fingerprint": digest(replacement),
                        "result_fingerprint": digest(result["shots"][0]),
                    }
                )
                review_path.write_text(json.dumps(review), encoding="utf-8")
                snapshot = rights.snapshot()

            self.assertFalse(snapshot["complete"])
            self.assertEqual(snapshot["required"], 1)
            self.assertEqual(snapshot["decided"], 0)
            self.assertEqual(snapshot["stale_removed"], 1)

    def test_verified_stock_forged_into_rights_route_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_dir, review_dir, rights_dir, result_path, review_path = self.fixture(root)

            result = json.loads(result_path.read_text(encoding="utf-8"))
            stock = {
                "candidate_id": "stock-1",
                "shot_id": "shot-001",
                "source_tier": "FREE_COMMERCIAL_LICENSE",
                "source_url": "https://example.test/stock-1",
                "rights_status": "VERIFIED",
                "commercial_use_allowed": True,
                "state": "ELIGIBLE",
            }
            result["shots"][0]["candidates"] = [stock]
            result_path.write_text(json.dumps(result), encoding="utf-8")

            review = json.loads(review_path.read_text(encoding="utf-8"))
            review["source_result_sha256"] = rights.sha256_file(result_path)
            review["decisions"]["shot-001"].update(
                {
                    "status": "SELECTED_PENDING_RIGHTS_CONTEXT_GATE",
                    "candidate_id": "stock-1",
                    "candidate_fingerprint": digest(stock),
                    "result_fingerprint": digest(result["shots"][0]),
                }
            )
            review_path.write_text(json.dumps(review), encoding="utf-8")

            with (
                patch.object(rights, "SEARCH_RESULT_DIR", result_dir),
                patch.object(rights, "CANDIDATE_REVIEW_DIR", review_dir),
                patch.object(rights, "RIGHTS_DIR", rights_dir),
                patch.object(
                    rights,
                    "search_result_is_current",
                    side_effect=current_result_state,
                ),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "unavailable or stale",
                ):
                    rights.apply_action(
                        candidate_review_file=str(review_path),
                        shot_id="shot-001",
                        decision="APPROVE_CONTEXT_USE",
                        transformative_purpose="Explain the event.",
                    )


if __name__ == "__main__":
    unittest.main()
