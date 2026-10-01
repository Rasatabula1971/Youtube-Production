from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import edit_preview_review as review


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class EditPreviewReviewTests(unittest.TestCase):
    def patch_paths(self, stack: ExitStack, root: Path) -> None:
        stack.enter_context(
            patch.object(review, "RESULT_DIR", root / "results")
        )
        stack.enter_context(
            patch.object(review, "REVIEW_DIR", root / "reviews")
        )
        stack.enter_context(
            patch.object(review, "APPROVED_DIR", root / "approved")
        )
        stack.enter_context(
            patch.object(review, "REWORK_DIR", root / "rework")
        )

    def make_result(self, root: Path) -> Path:
        manifest = write_json(root / "manifest.json", {"version": 1})
        preview = root / "preview.mp4"
        preview.write_bytes(b"preview")
        return write_json(
            root / "results" / "c1.short.edit_preview_result.json",
            {
                "artifact": "edit_preview_render_result",
                "concept_id": "c1",
                "format": "short",
                "status": "READY_FOR_HUMAN_EDIT_PREVIEW_GATE",
                "preview_file": str(preview),
                "preview_sha256": review.sha256_file(preview),
                "duration_seconds": 8.0,
                "placeholder_segments": 2,
                "provenance": {
                    "edit_manifest": str(manifest),
                    "edit_manifest_sha256": review.sha256_file(manifest),
                },
            },
        )

    def test_approve_is_bound_to_exact_preview_result(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            result_path = self.make_result(root)

            snapshot = review.apply_action(
                result_file=str(result_path),
                decision="APPROVE_EDIT_DIRECTION",
                note="",
            )
            approval = next(
                (root / "approved").glob("*.approved_edit_preview.json")
            )
            payload = json.loads(approval.read_text(encoding="utf-8"))

        self.assertTrue(snapshot["complete"])
        self.assertEqual(snapshot["approved"], 1)
        self.assertEqual(
            payload["source_preview_result_sha256"],
            review.sha256_file(result_path),
        )
        self.assertEqual(payload["placeholder_segments_at_approval"], 2)

    def test_return_to_visuals_requires_note_and_records_instruction(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            result_path = self.make_result(root)

            with self.assertRaisesRegex(ValueError, "require a note"):
                review.apply_action(
                    result_file=str(result_path),
                    decision="RETURN_TO_VISUALS",
                    note="",
                )

            snapshot = review.apply_action(
                result_file=str(result_path),
                decision="RETURN_TO_VISUALS",
                note="Opening image is too weak; use a more dramatic touchdown.",
            )
            rework_path = next(
                (root / "rework").glob("*.edit_preview_rework.json")
            )
            request = json.loads(rework_path.read_text(encoding="utf-8"))

        self.assertTrue(snapshot["complete"])
        self.assertEqual(snapshot["rework"], 1)
        self.assertEqual(request["target"], "VISUALS_STORYBOARD")
        self.assertIn("dramatic touchdown", request["human_instruction"])

    def test_changed_manifest_makes_old_review_disappear(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            self.patch_paths(stack, root)
            result_path = self.make_result(root)
            review.apply_action(
                result_file=str(result_path),
                decision="APPROVE_EDIT_DIRECTION",
                note="",
            )

            result = json.loads(result_path.read_text(encoding="utf-8"))
            manifest_path = Path(result["provenance"]["edit_manifest"])
            manifest_path.write_text(json.dumps({"version": 2}), encoding="utf-8")

            snapshot = review.snapshot()

        self.assertEqual(snapshot["total"], 0)
        self.assertFalse(snapshot["complete"])


if __name__ == "__main__":
    unittest.main()
