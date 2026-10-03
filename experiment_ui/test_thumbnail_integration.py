from __future__ import annotations

import unittest
from unittest.mock import patch

import server


class ThumbnailUiIntegrationTests(unittest.TestCase):
    def test_static_ui_contains_thumbnail_gate(self) -> None:
        html = (server.STATIC_DIR / "index.html").read_text(encoding="utf-8")
        script = (server.STATIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="thumbnailReviewPanel"', html)
        self.assertIn('id="thumbnailSubjectForm"', html)
        self.assertIn("HUMAN THUMBNAIL GATE", html)
        for name in ("renderThumbnailReview", "/api/thumbnail-gate", "/api/thumbnail-spec"):
            self.assertIn(name, script)

    def test_thumbnail_routes_are_locked_human_gate_mutations(self) -> None:
        self.assertIn("/api/thumbnail-gate", server.HUMAN_GATE_MUTATION_ROUTES)
        self.assertIn("/api/thumbnail-spec", server.HUMAN_GATE_MUTATION_ROUTES)
        with patch.object(server.JOB_MANAGER, "running", return_value=True):
            self.assertIsNotNone(server.human_gate_mutation_block_reason("/api/thumbnail-spec"))

    def test_render_actions_are_tools_not_automatic(self) -> None:
        for action_id in ("thumbnail_render", "thumbnail_render_preview"):
            self.assertIn(action_id, server.ACTION_DEFS)
            self.assertNotIn(action_id, server.AUTO_MACHINE_ACTION_ORDER)
            self.assertIn("production_engine/thumbnail_render.py", server.ACTION_DEFS[action_id]["command"])
        self.assertIn("--placeholder", server.ACTION_DEFS["thumbnail_render_preview"]["command"])

    def test_render_readiness_follows_subject_images(self) -> None:
        items = [{"subject_image": {"path": ""}}]
        with (
            patch.object(server, "thumbnail_gate_state", return_value={"items": items}),
            patch.object(server.shutil, "which", return_value="/usr/bin/tool"),
        ):
            readiness = server.action_readiness()
            self.assertFalse(readiness["thumbnail_render"]["enabled"])
            self.assertTrue(readiness["thumbnail_render_preview"]["enabled"])
            items[0]["subject_image"]["path"] = "subject.png"
            self.assertTrue(server.action_readiness()["thumbnail_render"]["enabled"])

    def test_gate_state_degrades_instead_of_raising(self) -> None:
        with patch.object(server, "thumbnail_gate_snapshot", side_effect=ValueError("bad template")):
            state = server.thumbnail_gate_state()
        self.assertEqual(state["status"], "ERROR")
        self.assertEqual(state["items"], [])

    def test_image_content_types(self) -> None:
        self.assertEqual(server.image_content_type(server.Path("a.jpg")), "image/jpeg")
        self.assertEqual(server.image_content_type(server.Path("a.png")), "image/png")


if __name__ == "__main__":
    unittest.main()
