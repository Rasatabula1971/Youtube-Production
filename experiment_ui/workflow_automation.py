"""Automatic deterministic workflow runner.

Runs enabled machine-only steps in the established pipeline order and stops as
soon as the next boundary is a human gate, a prerequisite wait, or an error.

The individual commands remain available in Tools & Diagnostics for debugging;
this runner is the normal workflow path.
"""

from __future__ import annotations

import subprocess
from typing import Any

import server as control

AUTO_MACHINE_ACTION_ORDER = [
    "exp2_prepare",
    "exp2_acquire",
    "exp2_visual",
    "exp2_vision_prepare",
    "analysis_batch_prepare",
    "analysis_model_one",
    "analysis_model_remaining",
    "human_review_prepare",
    "synthesis_build",
    "transform_prepare",
    "concept_generate",
    "concept_triage",
    "concept_gate_prepare",
    "package_prepare",
    "package_generate",
    "package_gate_prepare",
    "research_prepare",
    "research_acquire",
    "research_generate",
    "research_gate_prepare",
    "story_prepare",
    "story_generate",
    "script_prepare",
    "script_generate",
    "script_gate_prepare",
    "format_prepare",
    "format_generate",
    "format_gate_prepare",
    "voice_prepare",
    "voice_generate",
    "voice_gate_prepare",
    "pre_render_engagement",
    "narration_preview_prepare",
    "prototype_sound_prepare",
    "narration_preview_render",
    "sound_design_brief_prepare",
    "narration_prepare",
    "narration_spend_gate_prepare",
    "narration_audio_qc",
    "production_visual_prepare",
    "storyboard_prepare",
    "visual_search_prepare",
    "visual_search_acquire",
    "visual_rough_cut_prepare",
    "visual_gap_prepare",
]

MAX_STEPS_PER_RUN = 40


def next_enabled_action(
    readiness: dict[str, dict[str, Any]],
) -> str | None:
    for action_id in AUTO_MACHINE_ACTION_ORDER:
        if readiness.get(action_id, {}).get("enabled"):
            return action_id
    return None


def run_action(action_id: str) -> int:
    action = control.ACTION_DEFS[action_id]
    print()
    print("=" * 72)
    print(f"AUTOMATIC MACHINE STEP — {action['label']}")
    print("=" * 72)
    completed = subprocess.run(
        action["command"],
        cwd=control.PROJECT_ROOT,
        check=False,
    )
    return int(completed.returncode)


def run_until_human_gate() -> dict[str, Any]:
    completed_actions: list[str] = []

    for _ in range(MAX_STEPS_PER_RUN):
        readiness = control.action_readiness()
        guidance = control.workflow_guidance(readiness)
        preview_machine_pending = any(
            readiness.get(action_id, {}).get("enabled")
            for action_id in (
                "pre_render_engagement",
                "narration_preview_prepare",
                "prototype_sound_prepare",
                "narration_preview_render",
            )
        )
        if (
            guidance.get("state") == "HUMAN_NARRATION_PREVIEW_GATE"
            and not preview_machine_pending
        ):
            return {
                "status": "STOPPED_AT_BOUNDARY",
                "completed_actions": completed_actions,
                "workflow_state": guidance.get("state"),
                "message": guidance.get("current_title")
                or "Listen to the free narration preview before continuing.",
            }

        narration_boundary_machine_pending = any(
            readiness.get(action_id, {}).get("enabled")
            for action_id in (
                "sound_design_brief_prepare",
                "narration_prepare",
                "narration_spend_gate_prepare",
            )
        )
        if guidance.get("state") == "HUMAN_NARRATION_SPEND_GATE":
            return {
                "status": "STOPPED_AT_BOUNDARY",
                "completed_actions": completed_actions,
                "workflow_state": guidance.get("state"),
                "message": guidance.get("current_title")
                or "Review narration spend before any paid narration call.",
            }
        if (
            guidance.get("state")
            in {
                "WAITING_NARRATION_PROVIDER_QUOTE",
                "NARRATION_PROVIDER_SETUP_REQUIRED",
            }
            and not narration_boundary_machine_pending
        ):
            return {
                "status": "STOPPED_AT_BOUNDARY",
                "completed_actions": completed_actions,
                "workflow_state": guidance.get("state"),
                "message": guidance.get("current_title")
                or "Narration provider prerequisites are not ready.",
            }

        if guidance.get("state") in {
            "WAITING_NARRATION_RENDER_RETURN",
            "NARRATION_AUDIO_QC_FAILED",
            "NARRATION_AUDIO_READY",
            "HUMAN_VISUAL_CANDIDATE_GATE",
        }:
            return {
                "status": "STOPPED_AT_BOUNDARY",
                "completed_actions": completed_actions,
                "workflow_state": guidance.get("state"),
                "message": guidance.get("current_title")
                or "Workflow reached the current production boundary.",
            }

        action_id = next_enabled_action(readiness)
        if action_id is None:
            return {
                "status": "STOPPED_AT_BOUNDARY",
                "completed_actions": completed_actions,
                "workflow_state": guidance.get("state"),
                "message": guidance.get("current_title")
                or "No deterministic machine step is currently ready.",
            }

        before_reason = str(readiness[action_id].get("reason") or "")
        code = run_action(action_id)
        if code not in {0, 2}:
            return {
                "status": "FAILED",
                "failed_action": action_id,
                "return_code": code,
                "completed_actions": completed_actions,
            }

        after = control.action_readiness()
        next_id = next_enabled_action(after)
        if next_id == action_id:
            after_reason = str(after[action_id].get("reason") or "")
            if after_reason == before_reason:
                if code == 2:
                    message = (
                        "The zero-cost local narration preview could not be rendered. "
                        "Install/configure the local Kokoro preview dependencies and "
                        "retry; paid fallback is forbidden."
                        if action_id == "narration_preview_render"
                        else (
                            "Current artifacts were preserved, but the active "
                            "provider/model did not produce new validated output. "
                            "Retry Continue Automatically later."
                        )
                    )
                    return {
                        "status": "PARTIAL",
                        "failed_action": action_id,
                        "return_code": code,
                        "completed_actions": completed_actions,
                        "before_reason": before_reason,
                        "after_reason": after_reason,
                        "message": message,
                    }
                return {
                    "status": "NO_PROGRESS",
                    "failed_action": action_id,
                    "return_code": code,
                    "completed_actions": completed_actions,
                    "before_reason": before_reason,
                    "after_reason": after_reason,
                }
            # The same batched action is still ready, but its readiness reason
            # changed (for example 0/5 -> 2/5 current concept responses).
            # That is measurable progress, so allow the bounded loop to run the
            # next batch rather than misclassifying it as a stall.
            completed_actions.append(action_id)
            continue

        # A partial command may still have produced enough durable artifacts to
        # unlock the next machine step or a human boundary. Re-evaluate rather
        # than converting exit code 2 into a red workflow failure.
        completed_actions.append(action_id)

    return {
        "status": "SAFETY_STOP",
        "completed_actions": completed_actions,
        "message": f"Stopped after {MAX_STEPS_PER_RUN} automatic steps.",
    }


def main() -> None:
    result = run_until_human_gate()
    print()
    print("=" * 72)
    print("AUTOMATIC WORKFLOW")
    print("=" * 72)
    print(f"Status: {result['status']}")
    if result.get("workflow_state"):
        print(f"Boundary: {result['workflow_state']}")
    if result.get("message"):
        print(f"Message: {result['message']}")
    if result.get("completed_actions"):
        print("Completed:")
        for action_id in result["completed_actions"]:
            print(f"  - {action_id}")

    if result["status"] == "PARTIAL":
        raise SystemExit(2)
    if result["status"] in {"FAILED", "NO_PROGRESS", "SAFETY_STOP"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
