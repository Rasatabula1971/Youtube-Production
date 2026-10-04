"""Automatic deterministic workflow runner.

Runs enabled machine-only steps in the established pipeline order and stops as
soon as the next boundary is a human gate, a prerequisite wait, or an error.

The individual commands remain available in Tools & Diagnostics for debugging;
this runner is the normal workflow path.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from typing import Any

import gate_autopilot
import server as control
from pipeline_integrity import atomic_write_json

LAST_RUN_FILE = control.UI_OUTPUT_DIR / "last_auto_run.json"

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
    "research_prepare",
    "research_acquire",
    "research_generate",
    "research_gate_prepare",
    "story_prepare",
    "story_generate",
    "script_prepare",
    "script_generate",
    "script_gate_prepare",
    "title_direction_prepare",
    "title_direction_generate",
    "title_direction_gate_prepare",
    "packaging_brief_prepare",
    "psychological_angle_prepare",
    "psychological_angle_generate",
    "thumbnail_concept_prepare",
    "thumbnail_concept_generate",
    "package_pairing_prepare",
    "package_pairing_generate",
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
    "visual_asset_acquire",
    "visual_rough_cut_prepare",
    "visual_gap_prepare",
    "visual_generation_handoff_prepare",
    "visual_assembly_prepare",
    "edit_manifest_prepare",
    "edit_preview_render",
    "final_production_handoff_prepare",
    "final_sound_plan_prepare",
    "final_render_manifest_prepare",
    "final_render_local",
]

MAX_STEPS_PER_RUN = 40

RESEARCH_ACQUISITION_SUMMARY = (
    control.PROJECT_ROOT / "research_engine" / "output" / "research_acquisition_summary.json"
)

RESEARCH_MODEL_SUMMARY = (
    control.PROJECT_ROOT / "research_engine" / "output" / "research_model_batch_summary.json"
)

PARTIAL_MESSAGES = {
    "_default": (
        "Current artifacts were preserved, but the active "
        "provider/model did not produce new validated output. "
        "Retry Continue Automatically later."
    ),
    "concept_generate": (
        "Concept generation is not complete: at least one mechanism has no valid "
        "concept yet, either because the active provider/model did not answer or "
        "because its output failed validation. Validated concepts were kept and "
        "triage waits for every mechanism (D-129). Retry Continue Automatically "
        "later; it reruns only the missing mechanisms. If one keeps failing, its "
        "model run report lists the validation errors."
    ),
    "narration_preview_render": (
        "The zero-cost local narration preview could not be rendered. "
        "Install/configure the local Kokoro preview dependencies and "
        "retry; paid fallback is forbidden."
    ),
    "edit_preview_render": (
        "The free local structural edit preview could not "
        "be rendered. Check/configure local FFmpeg and current "
        "manifest media, then retry; paid/cloud fallback is forbidden."
    ),
    "final_render_local": (
        "The local final candidate could not be rendered. "
        "Check/configure local FFmpeg and the current final "
        "render manifest media, then retry; cloud/paid "
        "render fallback is forbidden."
    ),
}


def research_acquisition_message() -> str:
    """Explain a research evidence failure with the real backend error."""
    first_error = ""
    incomplete: list[str] = []
    try:
        summary = json.loads(RESEARCH_ACQUISITION_SUMMARY.read_text(encoding="utf-8"))
        for item in summary.get("results", []):
            if isinstance(item, dict) and (item.get("first_error") or item.get("message")):
                first_error = first_error or str(item.get("first_error") or item.get("message"))
            if isinstance(item, dict) and item.get("status") == "PARTIAL" and int(item.get("pages") or 0) > 0:
                incomplete.append(
                    f"{item.get('concept_id')} ({item.get('pages')} pages, "
                    f"{item.get('errors')} question search(es) failed)"
                )
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    if incomplete:
        # Pages were found; only some questions have no source yet (D-152).
        return (
            "Source pages were found, but some research questions still have no source: "
            + "; ".join(incomplete[:3])
            + ". The Research Gate needs every question covered, so research stops here (D-129)."
            + (f" First error: {first_error[:400]}" if first_error else "")
            + " Retry Continue Automatically: those questions are searched again, also as short "
            "keywords; a question still without a source after the configured rounds is set "
            "aside and waived at the Research Gate with a note (D-163). If it keeps failing, "
            "check the search backends with: python "
            "source_acquisition/agent_reach_adapter.py --mode doctor (Exa needs Agent Reach's "
            "mcporter on PATH)."
        )
    return (
        "Research web search and page reading returned no usable source pages, so "
        "there is nothing for the Research Gate yet. This is a network/search "
        "problem, not an AI model problem."
        + (f" First error: {first_error[:400]}" if first_error else "")
        + " Check it with: python source_acquisition/agent_reach_adapter.py "
        "--mode doctor (and --mode web-search --query \"test\"), fix the search "
        "backend or network, then retry Continue Automatically."
    )


def research_claims_message() -> str:
    """Distinguish "no model answered" from "answers failed validation"."""
    validation_error = ""
    try:
        summary = json.loads(RESEARCH_MODEL_SUMMARY.read_text(encoding="utf-8"))
        for item in summary.get("results", []):
            if isinstance(item, dict) and item.get("status") == "MODEL_OUTPUT_VALIDATION_ERROR":
                validation_error = str(item.get("message") or "")
                break
    except (OSError, ValueError, AttributeError):
        pass
    if not validation_error:
        return PARTIAL_MESSAGES["_default"]
    return (
        "A free model answered, but its research claims failed validation against "
        f"the acquired source pages: {validation_error[:400]} Nothing unverified was "
        "saved. Retry Continue Automatically; a fresh model answer usually passes."
    )


CONCEPT_BATCH_SUMMARY = control.PROJECT_ROOT / "transformation_engine" / "output" / "concept_model_batch_summary.json"


def concept_generation_message() -> str:
    """Name the one setup problem a retry cannot fix: the Gemini billing attestation (D-161)."""
    try:
        text = CONCEPT_BATCH_SUMMARY.read_text(encoding="utf-8")
    except OSError:
        text = ""
    if "DIRECT_GEMINI_BILLING_UNCONFIRMED" in text:
        return (
            "Concept generation made no model call: the direct Gemini route is off until you "
            "confirm that the Google Cloud project behind DIRECT_GEMINI_API_KEY has no billing "
            "account. Check Billing for that project in Google Cloud Console, then set "
            "billing_disabled_confirmed to true (and confirmed_on to today) in "
            "experiment_02_analysis/direct_gemini_billing.json and retry Continue Automatically."
        )
    return PARTIAL_MESSAGES["concept_generate"]


def partial_message(action_id: str) -> str:
    if action_id == "concept_generate":
        return concept_generation_message()
    if action_id == "research_acquire":
        return research_acquisition_message()
    if action_id == "research_generate":
        return research_claims_message()
    return PARTIAL_MESSAGES.get(action_id, PARTIAL_MESSAGES["_default"])


def next_enabled_action(
    readiness: dict[str, dict[str, Any]],
    skip: set[str] | frozenset[str] = frozenset(),
) -> str | None:
    for action_id in AUTO_MACHINE_ACTION_ORDER:
        if action_id not in skip and readiness.get(action_id, {}).get("enabled"):
            return action_id
    return None


def _with_stuck(result: dict[str, Any], stuck: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Report a stuck step as PARTIAL even when later work went ahead (D-154).

    A step that keeps returning partial (for example research for one concept
    whose questions have no source yet) is set aside so later steps that are
    already allowed (for example the script of a concept whose research is
    verified) still run. The run still ends PARTIAL and names the stuck step.
    """
    if not stuck:
        return result
    if result.get("status") in {"FAILED", "NO_PROGRESS", "SAFETY_STOP"}:
        # A real failure later on stays the headline; the stuck step is listed.
        return {**result, "stuck_actions": list(stuck)}
    action_id, first = next(iter(stuck.items()))
    combined = dict(first)
    combined["completed_actions"] = result.get("completed_actions", [])
    combined["stuck_actions"] = list(stuck)
    if result.get("workflow_state"):
        combined["workflow_state"] = result["workflow_state"]
    if result.get("message") and result.get("status") != "PARTIAL":
        combined["message"] = (
            f"{first['message']} Other work went ahead and stopped at: {result['message']}"
        )
    combined["failed_action"] = action_id
    return combined


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
    stuck: dict[str, dict[str, Any]] = {}
    held: dict[str, list[str]] = {}
    result = _with_stuck(_run_steps(completed_actions, stuck, held), stuck)
    if stuck:
        result["stuck_messages"] = {
            action_id: str(item.get("message") or "") for action_id, item in stuck.items()
        }
    return _with_held(result, held)


def _with_held(result: dict[str, Any], held: dict[str, list[str]]) -> dict[str, Any]:
    """Name the items an automatic gate left for a person (D-156)."""
    held = {gate: items for gate, items in held.items() if items}
    if not held:
        return result
    lines = [f"{gate.replace('_', ' ')}: " + "; ".join(items[:3]) for gate, items in held.items()]
    return {
        **result,
        "auto_held": held,
        "message": (str(result.get("message") or "") + " Held for you by the gate policy: "
                    + " | ".join(lines)).strip(),
    }


def run_gate_policy(state: str | None, completed_actions: list[str], held: dict[str, list[str]]) -> bool:
    """Decide the clean items of an automatic gate; True when anything was decided."""
    outcome = gate_autopilot.decide(state, control)
    if outcome.get("gate"):
        held[outcome["gate"]] = list(outcome.get("held") or [])
    if not outcome.get("decided"):
        return False
    print()
    print("=" * 72)
    print(f"AUTOMATIC MACHINE STEP — Gate policy: {outcome['gate'].replace('_', ' ')}")
    print("=" * 72)
    print(f"Decided automatically: {outcome['decided']}; left for you: {len(outcome.get('held') or [])}")
    for line in outcome.get("held") or []:
        print(f"  held: {line}")
    completed_actions.append(f"gate_policy:{outcome['gate']}")
    return True


def _run_steps(
    completed_actions: list[str], stuck: dict[str, dict[str, Any]], held: dict[str, list[str]]
) -> dict[str, Any]:
    for _ in range(MAX_STEPS_PER_RUN):
        readiness = control.action_readiness()
        guidance = control.workflow_guidance(readiness)
        if run_gate_policy(guidance.get("state"), completed_actions, held):
            continue
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
            "HUMAN_FINAL_AUDIO_GATE",
            "HUMAN_VISUAL_PLAN_GATE",
            "VISUAL_PLAN_REWORK_REQUIRED",
            "FINAL_AUDIO_REWORK_REQUIRED",
            "HUMAN_VISUAL_CANDIDATE_GATE",
            "HUMAN_VISUAL_RIGHTS_GATE",
            "HUMAN_ROUGH_CUT_GATE",
            "HUMAN_VISUAL_SPEND_GATE",
            "VISUAL_SPEND_INVALID",
            "VISUAL_EXISTING_RETRY_REQUIRED",
            "WAITING_FOR_VISUAL_ASSETS",
            "WAITING_FOR_PREMIUM_VISUAL_ASSETS",
            "WAITING_FOR_LOCAL_VISUAL_ASSETS",
            "LOCAL_FFMPEG_REQUIRED",
            "HUMAN_EDIT_PREVIEW_GATE",
            "EDIT_PREVIEW_REWORK_REQUIRED",
            "WAITING_FOR_FINAL_VISUAL_ASSETS",
            "FINAL_PRODUCTION_HANDOFF_BLOCKED",
            "WAITING_FOR_FINAL_SOUND_ASSETS",
            "HUMAN_TITLE_DIRECTION_GATE",
            "TITLE_DIRECTION_REJECTED",
            "TITLE_DIRECTION_SELECTED",
            "LOCAL_FINAL_FFMPEG_REQUIRED",
            "HUMAN_FINAL_EXPORT_GATE",
            "FINAL_EXPORT_REWORK_REQUIRED",
            "FINAL_EXPORT_APPROVED",
            "HUMAN_PUBLISH_GATE",
            "WAITING_FOR_UPLOAD",
            "PUBLISHED",
            "HUMAN_FINAL_PACKAGING_GATE",
            "FINAL_PACKAGING_REJECTED",
        }:
            return {
                "status": "STOPPED_AT_BOUNDARY",
                "completed_actions": completed_actions,
                "workflow_state": guidance.get("state"),
                "message": guidance.get("current_title")
                or "Workflow reached the current production boundary.",
            }

        action_id = next_enabled_action(readiness, skip=set(stuck))
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
        next_id = next_enabled_action(after, skip=set(stuck))
        if next_id == action_id:
            after_reason = str(after[action_id].get("reason") or "")
            if after_reason == before_reason:
                if code == 2:
                    # Set it aside and let later steps that are already
                    # allowed run; the run still ends PARTIAL (D-154).
                    stuck[action_id] = {
                        "status": "PARTIAL",
                        "failed_action": action_id,
                        "return_code": code,
                        "completed_actions": completed_actions,
                        "before_reason": before_reason,
                        "after_reason": after_reason,
                        "message": partial_message(action_id),
                    }
                    continue
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


def record_last_run(result: dict[str, Any]) -> None:
    """Keep the outcome of the latest run for the Productions page (D-163).

    Each production shows the step that stopped the last run and why, so
    the reason a concept is not moving is on its own row, not only in the
    job log. Best effort: a failed write never fails the run.
    """
    stuck_value = result.get("stuck_messages")
    stuck: dict[str, Any] = stuck_value if isinstance(stuck_value, dict) else {}
    payload = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": str(result.get("status") or ""),
        "workflow_state": result.get("workflow_state"),
        "message": str(result.get("message") or ""),
        "failed_action": result.get("failed_action"),
        "return_code": result.get("return_code"),
        "completed_actions": list(result.get("completed_actions") or []),
        "stuck": {str(action_id): str(message) for action_id, message in stuck.items()},
        "auto_held": result.get("auto_held") or {},
    }
    try:
        atomic_write_json(LAST_RUN_FILE, payload)
    except OSError:
        pass


def main() -> None:
    result = run_until_human_gate()
    record_last_run(result)
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
