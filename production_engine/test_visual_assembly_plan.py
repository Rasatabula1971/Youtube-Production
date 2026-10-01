from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import visual_assembly_plan as assembly


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class VisualAssemblyPlanTests(unittest.TestCase):
    def rough(self) -> dict:
        return {
            "artifact": "visual_rough_cut_manifest",
            "concept_id": "c1",
            "format": "short",
            "status": "READY_FOR_HUMAN_ROUGH_CUT_GATE",
            "scenes": [
                {
                    "scene_index": 0,
                    "shot_id": "shot-001",
                    "beat_id": "b1",
                    "time_range": {"start_seconds": 0, "end_seconds": 2},
                    "story_purpose": "hook",
                    "desired_visual": "Airliner wheel touchdown",
                    "cinematic_direction": {"camera_angle": "low"},
                    "visual_assignment": {
                        "status": "APPROVED_EXISTING_ASSET",
                        "candidate_id": "cand-1",
                        "source_url": "https://example.com/asset",
                        "reason": "VERIFIED_REUSE_RIGHTS",
                    },
                },
                {
                    "scene_index": 1,
                    "shot_id": "shot-002",
                    "beat_id": "b2",
                    "time_range": {"start_seconds": 2, "end_seconds": 5},
                    "story_purpose": "payoff",
                    "desired_visual": "Extreme tire deformation on landing",
                    "cinematic_direction": {
                        "camera_angle": "low",
                        "camera_movement": "controlled_push_in",
                    },
                    "visual_assignment": {
                        "status": "PLACEHOLDER",
                        "candidate_id": None,
                        "source_url": None,
                        "reason": "UNRESOLVED_VISUAL_GAP",
                    },
                },
            ],
        }

    def review(self, rough_path: Path) -> dict:
        return {
            "decision": "APPROVE_WITH_GAPS",
            "approved_for_gap_planning": True,
            "source_rough_cut": str(rough_path.resolve()),
            "source_rough_cut_sha256": assembly.sha256_file(rough_path),
        }

    def gap(self, rough_path: Path, review_path: Path, hero: bool) -> dict:
        return {
            "artifact": "visual_gap_plan",
            "concept_id": "c1",
            "format": "short",
            "gaps": [
                {
                    "shot_id": "shot-002",
                    "premium_generation_recommended": hero,
                }
            ],
            "provenance": {
                "rough_cut": str(rough_path.resolve()),
                "rough_cut_sha256": assembly.sha256_file(rough_path),
                "rough_cut_review": str(review_path.resolve()),
                "rough_cut_review_sha256": assembly.sha256_file(review_path),
            },
        }

    def test_no_premium_generation_builds_edit_ready_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rough_dir = root / "rough"
            review_dir = root / "reviews"
            gap_dir = root / "gaps"
            spend_dir = root / "spend"
            gen_dir = root / "generation"
            out_dir = root / "assembly"
            summary = root / "summary.json"

            rough_path = write_json(
                rough_dir / "c1.short.visual_rough_cut.json",
                self.rough(),
            )
            review_path = write_json(
                review_dir / "c1.short.visual_rough_cut_review.json",
                self.review(rough_path),
            )
            write_json(
                gap_dir / "c1.short.visual_gap_plan.json",
                self.gap(rough_path, review_path, False),
            )

            with (
                patch.object(assembly, "ROUGH_DIR", rough_dir),
                patch.object(assembly, "ROUGH_REVIEW_DIR", review_dir),
                patch.object(assembly, "GAP_DIR", gap_dir),
                patch.object(assembly, "SPEND_DIR", spend_dir),
                patch.object(assembly, "GEN_REQUEST_DIR", gen_dir),
                patch.object(assembly, "ASSEMBLY_DIR", out_dir),
                patch.object(assembly, "SUMMARY_FILE", summary),
            ):
                result = assembly.prepare()
                plan_path = next(out_dir.glob("*.visual_assembly_plan.json"))
                plan = json.loads(plan_path.read_text(encoding="utf-8"))

        self.assertEqual(result["prepared"], 1)
        self.assertEqual(plan["status"], "READY_FOR_EDIT_ASSEMBLY")
        self.assertEqual(
            plan["timeline"][0]["visual_status"],
            "APPROVED_EXISTING_ASSET",
        )
        self.assertEqual(
            plan["timeline"][1]["visual_status"],
            "EXISTING_TREATMENT_OR_BRIDGE_REQUIRED",
        )
        self.assertFalse(plan["policy"]["paid_provider_called"])
        self.assertFalse(plan["policy"]["media_rendered"])

    def test_authorized_premium_slot_remains_pending_until_asset_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rough_dir = root / "rough"
            review_dir = root / "reviews"
            gap_dir = root / "gaps"
            spend_dir = root / "spend"
            gen_dir = root / "generation"
            out_dir = root / "assembly"
            summary = root / "summary.json"

            rough_path = write_json(
                rough_dir / "c1.short.visual_rough_cut.json",
                self.rough(),
            )
            review_path = write_json(
                review_dir / "c1.short.visual_rough_cut_review.json",
                self.review(rough_path),
            )
            gap_path = write_json(
                gap_dir / "c1.short.visual_gap_plan.json",
                self.gap(rough_path, review_path, True),
            )
            spend_path = write_json(
                spend_dir / "c1.short.visual_spend_review.json",
                {
                    "artifact": "visual_spend_review",
                    "status": "COMPLETE",
                    "source_gap_plan": str(gap_path.resolve()),
                    "source_gap_plan_sha256": assembly.sha256_file(gap_path),
                    "decisions": {
                        "shot-002": {
                            "decision": "AUTHORIZE_GENERATION",
                            "paid_generation_authorized": True,
                            "max_cost_usd": 2.5,
                        }
                    },
                },
            )
            request_path = write_json(
                gen_dir / "c1.short.shot-002.visual_generation_request.json",
                {
                    "artifact": "visual_generation_request",
                    "concept_id": "c1",
                    "format": "short",
                    "shot_id": "shot-002",
                    "provider_handoff": {
                        "preferred_provider": "higgsfield",
                    },
                    "spend_authorization": {
                        "human_authorized": True,
                        "execution_authorized": False,
                        "max_cost_usd": 2.5,
                    },
                    "provenance": {
                        "gap_plan": str(gap_path.resolve()),
                        "gap_plan_sha256": assembly.sha256_file(gap_path),
                        "visual_spend_review": str(spend_path.resolve()),
                        "visual_spend_review_sha256": assembly.sha256_file(
                            spend_path
                        ),
                    },
                },
            )

            with (
                patch.object(assembly, "ROUGH_DIR", rough_dir),
                patch.object(assembly, "ROUGH_REVIEW_DIR", review_dir),
                patch.object(assembly, "GAP_DIR", gap_dir),
                patch.object(assembly, "SPEND_DIR", spend_dir),
                patch.object(assembly, "GEN_REQUEST_DIR", gen_dir),
                patch.object(assembly, "ASSEMBLY_DIR", out_dir),
                patch.object(assembly, "SUMMARY_FILE", summary),
            ):
                result = assembly.prepare()
                plan_path = next(out_dir.glob("*.visual_assembly_plan.json"))
                plan = json.loads(plan_path.read_text(encoding="utf-8"))

        self.assertEqual(result["waiting_for_premium_assets"], 1)
        self.assertEqual(plan["status"], "WAITING_FOR_PREMIUM_GENERATED_ASSETS")
        premium = plan["timeline"][1]
        self.assertEqual(
            premium["visual_status"],
            "PREMIUM_GENERATION_PENDING",
        )
        self.assertEqual(
            premium["generation"]["preferred_provider"],
            "higgsfield",
        )
        self.assertEqual(
            premium["generation"]["generation_request"],
            str(request_path),
        )
        self.assertFalse(plan["policy"]["paid_provider_called"])


if __name__ == "__main__":
    unittest.main()
