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
                        "status": "MANAGED_EXISTING_ASSET",
                        "candidate_id": "cand-1",
                        "source_url": "https://example.com/asset",
                        "reason": "CURRENT_MANAGED_ASSET",
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
            "artifact": "visual_rough_cut_review",
            "concept_id": "c1",
            "format": "short",
            "decision": "APPROVE_WITH_GAPS",
            "approved_for_gap_planning": True,
            "source_rough_cut": str(rough_path.resolve()),
            "source_rough_cut_sha256": assembly.sha256_file(rough_path),
        }

    def gap(
        self,
        rough_path: Path,
        review_path: Path,
        hero: bool,
    ) -> dict:
        gap_item = {
            "shot_id": "shot-002",
            "time_range": {"start_seconds": 2, "end_seconds": 5},
            "story_purpose": "payoff",
            "desired_visual": "Extreme tire deformation on landing",
            "cinematic_direction": {
                "camera_angle": "low",
                "camera_movement": "controlled_push_in",
            },
            "visual_value_score": {"total": 19 if hero else 10},
            "resolution_class": (
                "D_HERO_GENERATION"
                if hero
                else "B_OR_C_EXISTING_TREATMENT_OR_BRIDGE"
            ),
            "generation_priority": "HIGH" if hero else "LOW",
            "premium_generation_recommended": hero,
            "premium_generation_authorized": False,
            "reason": "UNRESOLVED_VISUAL_GAP",
        }
        return {
            "artifact": "visual_gap_plan",
            "concept_id": "c1",
            "format": "short",
            "status": "READY_FOR_VISUAL_GAP_REVIEW",
            "premium_generation_authorized": False,
            "gaps": [gap_item],
            "summary": {
                "unresolved": 1,
                "hero_generation_candidates": 1 if hero else 0,
            },
            "policy": {
                "retry_existing_or_treatment_before_paid_generation": True,
                "higgsfield_last_resort": True,
                "human_visual_spend_gate_required": True,
            },
            "provenance": {
                "rough_cut": str(rough_path.resolve()),
                "rough_cut_sha256": assembly.sha256_file(rough_path),
                "rough_cut_review": str(review_path.resolve()),
                "rough_cut_review_sha256": assembly.sha256_file(review_path),
            },
        }

    def managed_registry(
        self,
        root: Path,
        managed_dir: Path,
    ) -> tuple[Path, Path]:
        result_path = write_json(root / "result.json", {"result": True})
        candidate_review = write_json(
            root / "candidate_review.json",
            {"review": True},
        )
        asset = root / "managed.mp4"
        asset.write_bytes(b"managed-stock")
        record = {
            "artifact": "managed_visual_asset",
            "candidate_id": "cand-1",
            "asset_file": str(asset),
            "asset_sha256": assembly.sha256_file(asset),
            "license": "verified",
            "creator": "stock creator",
            "source_url": "https://example.com/asset",
            "acquisition_method": "download",
            "provenance": {
                "search_result": str(result_path),
                "search_result_sha256": assembly.sha256_file(result_path),
                "candidate_review": str(candidate_review),
                "candidate_review_sha256": assembly.sha256_file(
                    candidate_review
                ),
            },
        }
        registry = write_json(
            managed_dir
            / "c1.short.shot-001.managed_visual_asset.json",
            record,
        )
        return registry, asset

    def patch_common(
        self,
        root: Path,
        rough_dir: Path,
        review_dir: Path,
        gap_dir: Path,
        spend_dir: Path,
        gen_dir: Path,
        managed_dir: Path,
        generated_dir: Path,
        out_dir: Path,
        summary: Path,
        gap_payload: dict,
    ):
        return (
            patch.object(assembly, "ROUGH_DIR", rough_dir),
            patch.object(assembly, "ROUGH_REVIEW_DIR", review_dir),
            patch.object(assembly, "GAP_DIR", gap_dir),
            patch.object(assembly, "SPEND_DIR", spend_dir),
            patch.object(assembly, "GEN_REQUEST_DIR", gen_dir),
            patch.object(
                assembly,
                "MANAGED_REGISTRY_DIR",
                managed_dir,
            ),
            patch.object(
                assembly,
                "GENERATED_REGISTRY_DIR",
                generated_dir,
            ),
            patch.object(assembly, "ASSEMBLY_DIR", out_dir),
            patch.object(assembly, "SUMMARY_FILE", summary),
            patch.object(
                assembly,
                "gap_plan_is_current",
                side_effect=lambda path: (
                    (
                        gap_payload,
                        rough_dir / "c1.short.visual_rough_cut.json",
                        review_dir
                        / "c1.short.visual_rough_cut_review.json",
                    )
                    if path.exists()
                    else None
                ),
            ),
        )

    def test_no_premium_generation_builds_edit_ready_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rough_dir = root / "rough"
            review_dir = root / "reviews"
            gap_dir = root / "gaps"
            spend_dir = root / "spend"
            gen_dir = root / "generation"
            managed_dir = root / "managed_registry"
            generated_dir = root / "generated_registry"
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
            gap_payload = self.gap(
                rough_path,
                review_path,
                False,
            )
            write_json(
                gap_dir / "c1.short.visual_gap_plan.json",
                gap_payload,
            )
            self.managed_registry(root, managed_dir)

            contexts = self.patch_common(
                root,
                rough_dir,
                review_dir,
                gap_dir,
                spend_dir,
                gen_dir,
                managed_dir,
                generated_dir,
                out_dir,
                summary,
                gap_payload,
            )
            with contexts[0], contexts[1], contexts[2], contexts[3], contexts[4], contexts[5], contexts[6], contexts[7], contexts[8], contexts[9]:
                result = assembly.prepare()
                plan_path = next(
                    out_dir.glob("*.visual_assembly_plan.json")
                )
                plan = json.loads(
                    plan_path.read_text(encoding="utf-8")
                )

        self.assertEqual(result["prepared"], 1)
        self.assertEqual(plan["status"], "READY_FOR_EDIT_ASSEMBLY")
        self.assertEqual(
            plan["timeline"][0]["visual_status"],
            "MANAGED_EXISTING_ASSET",
        )
        self.assertEqual(
            plan["timeline"][1]["visual_status"],
            "EXISTING_TREATMENT_OR_BRIDGE_REQUIRED",
        )
        self.assertEqual(plan["summary"]["resolved_existing"], 1)
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
            managed_dir = root / "managed_registry"
            generated_dir = root / "generated_registry"
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
            gap_payload = self.gap(
                rough_path,
                review_path,
                True,
            )
            gap_path = write_json(
                gap_dir / "c1.short.visual_gap_plan.json",
                gap_payload,
            )
            gap_item = gap_payload["gaps"][0]
            decision = {
                "decision": "AUTHORIZE_GENERATION",
                "paid_generation_authorized": True,
                "max_cost_usd": 2.5,
                "note": "Use only for the hero impact.",
                "gap_fingerprint": assembly._gap_fingerprint(gap_item),
            }
            spend_path = write_json(
                spend_dir / "c1.short.visual_spend_review.json",
                {
                    "artifact": "visual_spend_review",
                    "status": "COMPLETE",
                    "source_gap_plan": str(gap_path.resolve()),
                    "source_gap_plan_sha256": assembly.sha256_file(gap_path),
                    "decisions": {"shot-002": decision},
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
                        "visual_spend_decision_sha256": assembly._fingerprint(
                            decision
                        ),
                    },
                },
            )
            self.managed_registry(root, managed_dir)

            contexts = self.patch_common(
                root,
                rough_dir,
                review_dir,
                gap_dir,
                spend_dir,
                gen_dir,
                managed_dir,
                generated_dir,
                out_dir,
                summary,
                gap_payload,
            )
            with contexts[0], contexts[1], contexts[2], contexts[3], contexts[4], contexts[5], contexts[6], contexts[7], contexts[8], contexts[9]:
                result = assembly.prepare()
                plan_path = next(
                    out_dir.glob("*.visual_assembly_plan.json")
                )
                plan = json.loads(
                    plan_path.read_text(encoding="utf-8")
                )

        self.assertEqual(result["waiting_for_premium_assets"], 1)
        self.assertEqual(
            plan["status"],
            "WAITING_FOR_PREMIUM_GENERATED_ASSETS",
        )
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
            str(request_path.resolve()),
        )
        self.assertFalse(plan["policy"]["paid_provider_called"])

    def test_hero_gap_without_completed_spend_review_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rough_dir = root / "rough"
            review_dir = root / "reviews"
            gap_dir = root / "gaps"
            spend_dir = root / "spend"
            gen_dir = root / "generation"
            managed_dir = root / "managed_registry"
            generated_dir = root / "generated_registry"
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
            gap_payload = self.gap(
                rough_path,
                review_path,
                True,
            )
            gap_path = write_json(
                gap_dir / "c1.short.visual_gap_plan.json",
                gap_payload,
            )
            self.managed_registry(root, managed_dir)

            contexts = self.patch_common(
                root,
                rough_dir,
                review_dir,
                gap_dir,
                spend_dir,
                gen_dir,
                managed_dir,
                generated_dir,
                out_dir,
                summary,
                gap_payload,
            )
            with contexts[0], contexts[1], contexts[2], contexts[3], contexts[4], contexts[5], contexts[6], contexts[7], contexts[8], contexts[9], self.assertRaisesRegex(
                ValueError,
                "CURRENT_VISUAL_SPEND_REVIEW_REQUIRED",
            ):
                assembly.build_plan(
                    rough_path,
                    self.rough(),
                    review_path,
                    gap_path,
                )

    def test_retry_existing_blocks_edit_preview_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rough_dir = root / "rough"
            review_dir = root / "reviews"
            gap_dir = root / "gaps"
            spend_dir = root / "spend"
            gen_dir = root / "generation"
            managed_dir = root / "managed_registry"
            generated_dir = root / "generated_registry"
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
            gap_payload = self.gap(
                rough_path,
                review_path,
                True,
            )
            gap_path = write_json(
                gap_dir / "c1.short.visual_gap_plan.json",
                gap_payload,
            )
            gap_item = gap_payload["gaps"][0]
            write_json(
                spend_dir / "c1.short.visual_spend_review.json",
                {
                    "artifact": "visual_spend_review",
                    "status": "COMPLETE",
                    "source_gap_plan": str(gap_path.resolve()),
                    "source_gap_plan_sha256": assembly.sha256_file(gap_path),
                    "decisions": {
                        "shot-002": {
                            "decision": "RETRY_EXISTING",
                            "paid_generation_authorized": False,
                            "max_cost_usd": 0,
                            "note": "Search for a tighter free landing shot.",
                            "gap_fingerprint": assembly._gap_fingerprint(
                                gap_item
                            ),
                        }
                    },
                },
            )
            self.managed_registry(root, managed_dir)

            contexts = self.patch_common(
                root,
                rough_dir,
                review_dir,
                gap_dir,
                spend_dir,
                gen_dir,
                managed_dir,
                generated_dir,
                out_dir,
                summary,
                gap_payload,
            )
            with contexts[0], contexts[1], contexts[2], contexts[3], contexts[4], contexts[5], contexts[6], contexts[7], contexts[8], contexts[9]:
                result = assembly.prepare()
                plan_path = next(
                    out_dir.glob("*.visual_assembly_plan.json")
                )
                plan = json.loads(
                    plan_path.read_text(encoding="utf-8")
                )

        self.assertEqual(result["waiting_for_existing_retry"], 1)
        self.assertEqual(
            plan["status"],
            "WAITING_FOR_EXISTING_VISUAL_RETRY",
        )
        self.assertEqual(
            plan["timeline"][1]["visual_status"],
            "RETRY_EXISTING_REQUIRED",
        )


if __name__ == "__main__":
    unittest.main()
