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
            "shots": [shot],
        }
        result_path = result_dir / "c1.short.visual_search_results.json"
        result_path.write_text(json.dumps(result), encoding="utf-8")

        review = {
            "artifact": "visual_candidate_review",
            "concept_id": "c1",
            "format": "short",
            "source_result": str(result_path),
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

    def test_rights_decision_survives_unrelated_review_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_dir, review_dir, rights_dir, _, review_path = self.fixture(root)
            with (
                patch.object(rights, "SEARCH_RESULT_DIR", result_dir),
                patch.object(rights, "CANDIDATE_REVIEW_DIR", review_dir),
                patch.object(rights, "RIGHTS_DIR", rights_dir),
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

    def test_selected_candidate_change_invalidates_old_rights_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_dir, review_dir, rights_dir, result_path, review_path = self.fixture(root)
            with (
                patch.object(rights, "SEARCH_RESULT_DIR", result_dir),
                patch.object(rights, "CANDIDATE_REVIEW_DIR", review_dir),
                patch.object(rights, "RIGHTS_DIR", rights_dir),
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


if __name__ == "__main__":
    unittest.main()
