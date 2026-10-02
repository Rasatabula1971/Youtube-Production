from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import visual_spend_review as spend


class VisualSpendReviewTests(unittest.TestCase):
    def patch_paths(self, stack: ExitStack, root: Path) -> tuple[Path, Path]:
        gaps = root / "gaps"
        reviews = root / "reviews"
        gaps.mkdir()
        reviews.mkdir()
        config = root / "visual_spend_config.json"
        config.write_text(
            json.dumps(
                {
                    "currency": "USD",
                    "per_shot_hard_cap_usd": 10.0,
                    "workflow_hard_cap_usd": 10.0,
                    "human_authorization_required": True,
                    "paid_provider_calls_without_authorization": False,
                }
            ),
            encoding="utf-8",
        )
        stack.enter_context(patch.object(spend, "GAPS", gaps))
        stack.enter_context(patch.object(spend, "SPEND", reviews))
        stack.enter_context(patch.object(spend, "CONFIG", config))
        stack.enter_context(
            patch.object(
                spend,
                "gap_plan_is_current",
                side_effect=lambda path: (
                    (
                        json.loads(path.read_text(encoding="utf-8")),
                        Path("rough"),
                        Path("review"),
                    )
                    if path.exists()
                    else None
                ),
            )
        )
        return gaps, reviews

    def gap(self, shot_id: str, *, hero: bool = True, desired: str = "Hero impact") -> dict:
        return {
            "shot_id": shot_id,
            "desired_visual": desired,
            "story_purpose": "payoff",
            "cinematic_direction": {"framing": "close"},
            "visual_value_score": {"total": 19 if hero else 10},
            "premium_generation_recommended": hero,
            "premium_generation_authorized": False,
            "resolution_class": (
                "D_HERO_GENERATION"
                if hero
                else "B_OR_C_EXISTING_TREATMENT_OR_BRIDGE"
            ),
        }

    def write_plan(self, gaps: Path, values: list[dict]) -> Path:
        path = gaps / "c1.short.visual_gap_plan.json"
        path.write_text(
            json.dumps(
                {
                    "artifact": "visual_gap_plan",
                    "concept_id": "c1",
                    "format": "short",
                    "gaps": values,
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_snapshot_exposes_pending_premium_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            gaps, _ = self.patch_paths(stack, Path(tmp))
            self.write_plan(gaps, [self.gap("shot-001")])
            snapshot = spend.snapshot()

        self.assertEqual(snapshot["status"], "READY_FOR_VISUAL_SPEND_GATE")
        self.assertFalse(snapshot["complete"])
        self.assertEqual(snapshot["hero_candidates"], 1)
        self.assertEqual(snapshot["decided"], 0)
        self.assertEqual(snapshot["per_shot_hard_cap_usd"], 10.0)
        self.assertEqual(snapshot["workflow_hard_cap_usd"], 10.0)
        self.assertTrue(snapshot["human_authorization_required"])

    def test_authorize_within_cap_completes_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            gaps, _ = self.patch_paths(stack, Path(tmp))
            plan = self.write_plan(gaps, [self.gap("shot-001")])
            spend.apply_action(
                gap_plan_file=str(plan),
                shot_id="shot-001",
                decision="AUTHORIZE_GENERATION",
                max_cost_usd=4.25,
                note="Only if existing footage remains inadequate.",
            )
            snapshot = spend.snapshot()

        self.assertTrue(snapshot["complete"])
        self.assertEqual(snapshot["status"], "COMPLETE")
        self.assertEqual(snapshot["authorized"], 1)
        self.assertEqual(snapshot["authorized_max_total_usd"], 4.25)

    def test_per_shot_cap_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            gaps, _ = self.patch_paths(stack, Path(tmp))
            plan = self.write_plan(gaps, [self.gap("shot-001")])
            with self.assertRaisesRegex(ValueError, r"<= \$10\.00 USD"):
                spend.apply_action(
                    gap_plan_file=str(plan),
                    shot_id="shot-001",
                    decision="AUTHORIZE_GENERATION",
                    max_cost_usd=10.01,
                )

    def test_workflow_total_cap_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            gaps, _ = self.patch_paths(stack, Path(tmp))
            plan = self.write_plan(
                gaps,
                [self.gap("shot-001"), self.gap("shot-002")],
            )
            spend.apply_action(
                gap_plan_file=str(plan),
                shot_id="shot-001",
                decision="AUTHORIZE_GENERATION",
                max_cost_usd=6.0,
            )
            with self.assertRaisesRegex(ValueError, r"\$10\.00 USD hard cap"):
                spend.apply_action(
                    gap_plan_file=str(plan),
                    shot_id="shot-002",
                    decision="AUTHORIZE_GENERATION",
                    max_cost_usd=5.0,
                )
            snapshot = spend.snapshot()

        self.assertEqual(snapshot["authorized"], 1)
        self.assertEqual(snapshot["authorized_max_total_usd"], 6.0)
        self.assertFalse(snapshot["complete"])

    def test_nonfinite_authorization_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            gaps, _ = self.patch_paths(stack, Path(tmp))
            plan = self.write_plan(gaps, [self.gap("shot-001")])
            with self.assertRaisesRegex(ValueError, "must be finite"):
                spend.apply_action(
                    gap_plan_file=str(plan),
                    shot_id="shot-001",
                    decision="AUTHORIZE_GENERATION",
                    max_cost_usd=float("nan"),
                )

    def test_stale_gap_plan_cannot_receive_spend_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            gaps, _ = self.patch_paths(stack, Path(tmp))
            plan = self.write_plan(gaps, [self.gap("shot-001")])
            stack.enter_context(
                patch.object(
                    spend,
                    "gap_plan_is_current",
                    return_value=None,
                )
            )
            with self.assertRaisesRegex(
                ValueError,
                "STALE_VISUAL_GAP_PLAN",
            ):
                spend.apply_action(
                    gap_plan_file=str(plan),
                    shot_id="shot-001",
                    decision="KEEP_PLACEHOLDER",
                )

    def test_workflow_cap_applies_across_multiple_gap_plans(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            gaps, _ = self.patch_paths(stack, Path(tmp))
            first = self.write_plan(gaps, [self.gap("shot-001")])
            second = gaps / "c2.short.visual_gap_plan.json"
            second.write_text(
                json.dumps(
                    {
                        "artifact": "visual_gap_plan",
                        "concept_id": "c2",
                        "format": "short",
                        "gaps": [self.gap("shot-002")],
                    }
                ),
                encoding="utf-8",
            )
            spend.apply_action(
                gap_plan_file=str(first),
                shot_id="shot-001",
                decision="AUTHORIZE_GENERATION",
                max_cost_usd=6.0,
            )
            with self.assertRaisesRegex(
                ValueError,
                r"\$10\.00 USD hard cap",
            ):
                spend.apply_action(
                    gap_plan_file=str(second),
                    shot_id="shot-002",
                    decision="AUTHORIZE_GENERATION",
                    max_cost_usd=5.0,
                )

    def test_concurrent_cross_branch_authorization_cannot_exceed_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            gaps, _ = self.patch_paths(stack, Path(tmp))
            first = self.write_plan(gaps, [self.gap("shot-001")])
            second = gaps / "c2.short.visual_gap_plan.json"
            second.write_text(
                json.dumps(
                    {
                        "artifact": "visual_gap_plan",
                        "concept_id": "c2",
                        "format": "short",
                        "gaps": [self.gap("shot-002")],
                    }
                ),
                encoding="utf-8",
            )

            def authorize(args):
                plan, shot = args
                try:
                    spend.apply_action(
                        gap_plan_file=str(plan),
                        shot_id=shot,
                        decision="AUTHORIZE_GENERATION",
                        max_cost_usd=6.0,
                    )
                    return "OK"
                except ValueError:
                    return "BLOCKED"

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(
                    pool.map(
                        authorize,
                        [
                            (first, "shot-001"),
                            (second, "shot-002"),
                        ],
                    )
                )

            self.assertEqual(sorted(outcomes), ["BLOCKED", "OK"])
            snapshot = spend.snapshot()
            self.assertEqual(snapshot["authorized"], 1)
            self.assertEqual(
                snapshot["authorized_max_total_usd"],
                6.0,
            )

    def test_retry_existing_requires_human_instruction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            gaps, _ = self.patch_paths(stack, Path(tmp))
            plan = self.write_plan(gaps, [self.gap("shot-001")])
            with self.assertRaisesRegex(ValueError, "human instruction"):
                spend.apply_action(
                    gap_plan_file=str(plan),
                    shot_id="shot-001",
                    decision="RETRY_EXISTING",
                    note="",
                )

    def test_unrelated_nonhero_gap_change_preserves_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            gaps, _ = self.patch_paths(stack, Path(tmp))
            hero = self.gap("shot-001")
            plan = self.write_plan(
                gaps,
                [hero, self.gap("shot-002", hero=False, desired="Bridge A")],
            )
            spend.apply_action(
                gap_plan_file=str(plan),
                shot_id="shot-001",
                decision="KEEP_PLACEHOLDER",
            )
            self.write_plan(
                gaps,
                [hero, self.gap("shot-002", hero=False, desired="Bridge B")],
            )
            snapshot = spend.snapshot()

        self.assertTrue(snapshot["complete"])
        self.assertEqual(snapshot["decided"], 1)
        self.assertEqual(snapshot["stale_removed"], 0)

    def test_changed_hero_gap_invalidates_old_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            gaps, _ = self.patch_paths(stack, Path(tmp))
            plan = self.write_plan(gaps, [self.gap("shot-001", desired="Old hero")])
            spend.apply_action(
                gap_plan_file=str(plan),
                shot_id="shot-001",
                decision="KEEP_PLACEHOLDER",
            )
            self.write_plan(
                gaps,
                [self.gap("shot-001", desired="Changed hero")],
            )
            snapshot = spend.snapshot()

        self.assertFalse(snapshot["complete"])
        self.assertEqual(snapshot["decided"], 0)
        self.assertEqual(snapshot["stale_removed"], 1)


if __name__ == "__main__":
    unittest.main()
