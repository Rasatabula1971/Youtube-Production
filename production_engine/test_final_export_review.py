from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import final_export_review as export_review


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class FinalExportReviewTests(unittest.TestCase):
    def result_fixture(self, root: Path):
        result_dir = root / "results"
        render = root / "renders" / "c1.short.final_candidate.mp4"
        render.parent.mkdir(parents=True, exist_ok=True)
        render.write_bytes(b"candidate")
        result = {
            "artifact": "final_render_result",
            "concept_id": "c1",
            "format": "short",
            "status": "READY_FOR_HUMAN_FINAL_EXPORT_GATE",
            "render_file": str(render),
            "render_sha256": export_review.sha256_file(render),
            "render_bytes": render.stat().st_size,
            "duration_seconds": 4.0,
            "sound_assets_mixed": 1,
            "sound_omissions": 0,
        }
        result_path = write_json(
            result_dir / "c1.short.final_render_result.json",
            result,
        )
        return result_dir, result_path, result, render

    def test_approve_export_binds_exact_render_without_publish_permission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_dir, result_path, result, _render = self.result_fixture(
                root
            )
            with (
                patch.object(export_review, "RESULT_DIR", result_dir),
                patch.object(export_review, "REVIEW_DIR", root / "reviews"),
                patch.object(export_review, "APPROVED_DIR", root / "approved"),
                patch.object(export_review, "REWORK_DIR", root / "rework"),
                patch.object(
                    export_review,
                    "result_is_current",
                    return_value=result,
                ),
            ):
                snapshot = export_review.apply_action(
                    result_file=str(result_path),
                    decision="APPROVE_EXPORT",
                    note="",
                )
                approval_path = (
                    root
                    / "approved"
                    / "c1.short.approved_final_export.json"
                )
                approval = json.loads(
                    approval_path.read_text(encoding="utf-8")
                )

        self.assertEqual(snapshot["approved"], 1)
        self.assertEqual(approval["status"], "FINAL_EXPORT_APPROVED")
        self.assertFalse(approval["upload_authorized"])
        self.assertFalse(approval["publish_authorized"])
        self.assertEqual(
            approval["render_sha256"],
            result["render_sha256"],
        )

    def test_rework_requires_note_and_removes_export_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_dir, result_path, result, _render = self.result_fixture(
                root
            )
            with (
                patch.object(export_review, "RESULT_DIR", result_dir),
                patch.object(export_review, "REVIEW_DIR", root / "reviews"),
                patch.object(export_review, "APPROVED_DIR", root / "approved"),
                patch.object(export_review, "REWORK_DIR", root / "rework"),
                patch.object(
                    export_review,
                    "result_is_current",
                    return_value=result,
                ),
            ):
                export_review.apply_action(
                    result_file=str(result_path),
                    decision="APPROVE_EXPORT",
                    note="",
                )
                with self.assertRaisesRegex(ValueError, "require a note"):
                    export_review.apply_action(
                        result_file=str(result_path),
                        decision="RETURN_TO_SOUND",
                        note="",
                    )
                snapshot = export_review.apply_action(
                    result_file=str(result_path),
                    decision="RETURN_TO_SOUND",
                    note="Music is masking the reveal.",
                )
                approval_path = (
                    root
                    / "approved"
                    / "c1.short.approved_final_export.json"
                )

        self.assertEqual(snapshot["rework"], 1)
        self.assertFalse(approval_path.exists())

    def test_missing_approval_reopens_approved_review_as_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_dir, result_path, result, _render = self.result_fixture(
                root
            )
            review_dir = root / "reviews"
            approved_dir = root / "approved"
            with (
                patch.object(export_review, "RESULT_DIR", result_dir),
                patch.object(export_review, "REVIEW_DIR", review_dir),
                patch.object(export_review, "APPROVED_DIR", approved_dir),
                patch.object(export_review, "REWORK_DIR", root / "rework"),
                patch.object(
                    export_review,
                    "result_is_current",
                    return_value=result,
                ),
            ):
                export_review.apply_action(
                    result_file=str(result_path),
                    decision="APPROVE_EXPORT",
                    note="",
                )
                approval_path = (
                    approved_dir / "c1.short.approved_final_export.json"
                )
                approval_path.unlink()
                snapshot = export_review.snapshot()

        self.assertFalse(snapshot["complete"])
        self.assertEqual(snapshot["pending"], 1)
        self.assertEqual(snapshot["approved"], 0)
        self.assertEqual(
            snapshot["items"][0]["decision"],
            "PENDING",
        )

    def test_changed_render_invalidates_saved_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_dir, result_path, result, render = self.result_fixture(
                root
            )
            approved_dir = root / "approved"
            with (
                patch.object(export_review, "RESULT_DIR", result_dir),
                patch.object(export_review, "REVIEW_DIR", root / "reviews"),
                patch.object(export_review, "APPROVED_DIR", approved_dir),
                patch.object(export_review, "REWORK_DIR", root / "rework"),
                patch.object(
                    export_review,
                    "result_is_current",
                    return_value=result,
                ),
            ):
                export_review.apply_action(
                    result_file=str(result_path),
                    decision="APPROVE_EXPORT",
                    note="",
                )
                approval_path = (
                    approved_dir / "c1.short.approved_final_export.json"
                )
                self.assertIsNotNone(
                    export_review.approval_is_current(approval_path)
                )
                render.write_bytes(b"changed")
                with patch.object(
                    export_review,
                    "result_is_current",
                    return_value=None,
                ):
                    self.assertIsNone(
                        export_review.approval_is_current(approval_path)
                    )


if __name__ == "__main__":
    unittest.main()
