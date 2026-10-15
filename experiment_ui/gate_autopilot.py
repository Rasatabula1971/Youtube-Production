"""Decide clean gate items automatically when the gate policy allows it (D-156).

Continue Automatically calls :func:`decide` when the workflow stops at a human
gate. For a gate set to ``AUTO_IF_CLEAN`` in ``gate_policy.json`` it decides,
through the same functions the review pages call, every pending item that
passes the gate's machine checks. Items that fail a check stay pending, so
the gate still stops for a person, who sees only the flagged items.

Every automatic decision is recorded under the reviewer id from the policy
(``gate-policy-auto``) with a note naming the checks that passed, so it can
be told apart from a person's decision and changed from the review page.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

POLICY_FILE = Path(__file__).resolve().parent / "gate_policy.json"
REVIEWER_ENV = "YOUTUBE_REVIEWER_ID"
DECIDED_BY_ENV = "YOUTUBE_DECIDED_BY"
POLICY_DECIDER = "GATE_POLICY"
AUTO = "AUTO_IF_CLEAN"
NOTE = "Automatic (gate policy D-156): "

# Workflow state -> gate key in gate_policy.json.
STATE_GATES = {
    "HUMAN_VISION_GATE": "vision",
    "HUMAN_ANALYSIS_GATE": "analysis",
    "HUMAN_TITLE_DIRECTION_GATE": "title_direction",
    "HUMAN_FORMAT_GATE": "format",
    "HUMAN_PERFORMANCE_GATE": "performance",
    "HUMAN_NARRATION_PREVIEW_GATE": "narration_preview",
    # Phase B (D-158).
    "HUMAN_VISUAL_PLAN_GATE": "visual_plan",
    "HUMAN_NARRATION_SPEND_GATE": "narration_spend",
    "HUMAN_FINAL_AUDIO_GATE": "final_audio",
    "HUMAN_VISUAL_CANDIDATE_GATE": "visual_candidate",
    "HUMAN_ROUGH_CUT_GATE": "rough_cut",
    "HUMAN_VISUAL_SPEND_GATE": "visual_spend",
    "HUMAN_EDIT_PREVIEW_GATE": "edit_preview",
}

CLEAN_VISION_CONFIDENCE = {"HIGH", "MODERATE"}


def load_policy(path: Path | None = None) -> dict[str, Any]:
    try:
        payload = json.loads((path or POLICY_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"gates": {}}
    return payload if isinstance(payload, dict) else {"gates": {}}


def gate_mode(gate: str, policy: dict[str, Any]) -> str:
    gates = policy.get("gates")
    value = gates.get(gate) if isinstance(gates, dict) else None
    return str(value or "HUMAN").upper()


@contextmanager
def _reviewer(reviewer_id: str) -> Iterator[None]:
    """Gate modules read the reviewer and the decider from the environment.

    Every gate records the reviewer id; the ones that keep a decided_by field
    (vision, analysis) read YOUTUBE_DECIDED_BY so automatic decisions are never
    logged as HUMAN (audit 2026-10-04).
    """
    previous = {name: os.environ.get(name) for name in (REVIEWER_ENV, DECIDED_BY_ENV)}
    os.environ[REVIEWER_ENV] = reviewer_id
    os.environ[DECIDED_BY_ENV] = POLICY_DECIDER
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


# --- per-gate checks -------------------------------------------------------
# Each returns (decisions to apply, items left for a person with reasons).


def vision_frame_problem(frame: dict[str, Any]) -> str | None:
    proposal = frame.get("proposal")
    if not isinstance(proposal, dict) or frame.get("proposal_error"):
        return "no machine observation for this frame"
    if str(proposal.get("confidence") or "").upper() not in CLEAN_VISION_CONFIDENCE:
        return "the observation has low confidence"
    if str(proposal.get("uncertainty") or "").strip():
        return "the observation notes something ambiguous"
    if not str(proposal.get("observation") or "").strip():
        return "the observation is empty"
    return None


def analysis_item_problem(item: dict[str, Any]) -> str | None:
    if str(item.get("confidence") or "").upper() == "LOW":
        return "the analysis marks it low confidence"
    evidence = item.get("supporting_evidence") or []
    refs = item.get("evidence_refs") or []
    if not evidence:
        return "no supporting evidence"
    if len(evidence) < len(refs):
        return "an evidence reference does not resolve"
    return None


def _title_fits(candidate: dict[str, Any], contract: dict[str, Any]) -> bool:
    text = str(candidate.get("title_text") or "").strip()
    if not text or not candidate.get("evidence_refs"):
        return False
    max_chars = int(contract.get("max_chars") or 0)
    max_words = int(contract.get("max_words") or 0)
    if max_chars and len(text) > max_chars:
        return False
    return not (max_words and len(text.split()) > max_words)


def pick_titles(concept: dict[str, Any], packaging_config: dict[str, Any]) -> dict[str, Any] | None:
    """The first title per format, in configured angle order, that fits its contract."""
    angles = [str(a) for a in packaging_config.get("title_angles") or []]
    contracts = {
        "short": packaging_config.get("short_title_contract") or {},
        "long_form": packaging_config.get("long_title_contract") or {},
    }
    titles = concept.get("titles") or {}
    selected: dict[str, Any] = {}
    for fmt, contract in contracts.items():
        candidates = [c for c in titles.get(fmt) or [] if isinstance(c, dict)]
        candidates.sort(
            key=lambda c: angles.index(str(c.get("psychological_angle")))
            if str(c.get("psychological_angle")) in angles
            else len(angles)
        )
        choice = next((c for c in candidates if _title_fits(c, contract)), None)
        if choice is None:
            return None
        selected[fmt] = {"title_id": choice.get("title_id")}
    return selected


def format_plan_problem(plan: dict[str, Any]) -> str | None:
    overlap = plan.get("source_overlap") or {}
    if isinstance(overlap, dict) and overlap.get("matches"):
        return "wording overlaps the source video"
    separation = plan.get("branch_separation") or {}
    if isinstance(separation, dict) and (separation.get("identical") or separation.get("truncation")):
        return "the Short and Long-form edits are not separate"
    return None


def preview_problem(item: dict[str, Any], engagement: dict[tuple[str, str], dict[str, Any]]) -> str | None:
    if not item.get("audio_ready"):
        return "the preview audio is not ready"
    check = engagement.get((str(item.get("concept_id")), str(item.get("format"))))
    if not check or check.get("status") != "PASS":
        return "the engagement check has not passed"
    if check.get("warnings"):
        return "the engagement check has warnings: " + ", ".join(map(str, check["warnings"]))[:200]
    return None


# --- gate runners ----------------------------------------------------------


def _apply(action: Callable[..., Any], kwargs: dict[str, Any], label: str, held: list[str]) -> int:
    """Apply one decision; a refusal holds that item for a person instead."""
    try:
        action(**kwargs)
    except (ValueError, RuntimeError, OSError) as exc:
        held.append(f"{label}: not decided automatically ({exc})"[:300])
        return 0
    return 1


def _decide_vision(control: Any) -> tuple[int, list[str]]:
    decided, held = 0, list[str]()
    for packet in control.vision_review_snapshot().get("packets", []):
        video_id = str(packet.get("video_id"))
        for frame in packet.get("frames", []):
            if frame.get("decision") != "PENDING":
                continue
            frame_id = str(frame.get("frame_id"))
            problem = vision_frame_problem(frame)
            if problem:
                held.append(f"frame {frame_id}: {problem}")
                continue
            decided += _apply(
                control.apply_vision_review_action, dict(
                    action="ACCEPT_FRAME", video_id=video_id, frame_id=frame_id
                ),
                f"frame {frame_id}", held,
            )
    return decided, held


def _decide_analysis(control: Any) -> tuple[int, list[str]]:
    decided, held = 0, list[str]()
    for item in control.human_analysis_review_snapshot().get("items", []):
        if item.get("decision") != "PENDING":
            continue
        item_id = str(item.get("item_id"))
        problem = analysis_item_problem(item)
        if problem:
            held.append(f"{item_id}: {problem}")
            continue
        decided += _apply(
            control.apply_human_analysis_review_action, dict(
                video_id=str(item.get("video_id")), item_id=item_id, decision="ACCEPT",
                note=NOTE + "confidence not low and every evidence reference resolves.",
            ),
            item_id, held,
        )
    return decided, held


def _decide_title_direction(control: Any) -> tuple[int, list[str]]:
    decided, held = 0, list[str]()
    try:
        config = json.loads(Path(control.PACKAGING_CONFIG_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError, AttributeError):
        config = {}
    for concept in control.title_direction_gate_snapshot().get("concepts", []):
        if concept.get("decision") not in {None, "", "PENDING"}:
            continue
        concept_id = str(concept.get("concept_id"))
        selected = pick_titles(concept, config)
        if selected is None:
            held.append(f"{concept_id}: no title fits the length contract")
            continue
        decided += _apply(
            control.apply_title_direction_gate_action, dict(
                concept_id=concept_id, decision="ACCEPT", selected_titles=selected,
                note=NOTE + "first title per format in angle order that fits the length "
                "contract; you choose the final title with the thumbnail at the Final "
                "Packaging Gate.",
            ),
            concept_id, held,
        )
    return decided, held


def _decide_format(control: Any) -> tuple[int, list[str]]:
    decided, held = 0, list[str]()
    for plan in control.format_gate_snapshot().get("plans", []):
        if plan.get("decision") not in {None, "", "PENDING"}:
            continue
        concept_id = str(plan.get("concept_id"))
        problem = format_plan_problem(plan)
        if problem:
            held.append(f"{concept_id}: {problem}")
            continue
        decided += _apply(
            control.apply_format_gate_action, dict(
                concept_id=concept_id, decision="ACCEPT", criteria={},
                note=NOTE + "plan passed validation with no source overlap and separate branches.",
            ),
            concept_id, held,
        )
    return decided, held


def _decide_performance(control: Any) -> tuple[int, list[str]]:
    decided, held = 0, list[str]()
    for spec in control.performance_gate_snapshot().get("specs", []):
        if spec.get("decision") not in {None, "", "PENDING"}:
            continue
        concept_id, fmt = str(spec.get("concept_id")), str(spec.get("format"))
        # Specs reach this gate only after deterministic validation passed.
        decided += _apply(
            control.apply_performance_gate_action, dict(
                concept_id=concept_id, format=fmt, decision="ACCEPT", criteria={},
                note=NOTE + "performance spec passed deterministic validation.",
            ),
            f"{concept_id} {fmt}", held,
        )
    return decided, held


def _decide_narration_preview(control: Any) -> tuple[int, list[str]]:
    decided, held = 0, list[str]()
    engagement = {
        (str(i.get("concept_id")), str(i.get("format"))): i
        for i in control.pre_render_engagement_snapshot().get("items", [])
        if isinstance(i, dict)
    }
    for item in control.narration_preview_gate_snapshot().get("items", []):
        if item.get("decision") not in {None, "", "PENDING"}:
            continue
        concept_id, fmt = str(item.get("concept_id")), str(item.get("format"))
        problem = preview_problem(item, engagement)
        if problem:
            held.append(f"{concept_id} {fmt}: {problem}")
            continue
        decided += _apply(
            control.apply_narration_preview_gate_action, dict(
                concept_id=concept_id, format=fmt, decision="APPROVE_FINAL",
                note=NOTE + "preview rendered and the engagement check passed with no warnings.",
            ),
            f"{concept_id} {fmt}", held,
        )
    return decided, held


# --- Phase B: visual gates and spend (D-158) -------------------------------


def _json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def spend_problem(control: Any, concept_id: str, fmt: str, cost_usd: float | None) -> str | None:
    """Spend is automatic only on a confirmed budget and while the video stays at or under its target."""
    if cost_usd is None or cost_usd <= 0:
        return "the cost is not known"
    budget = control.video_budget
    try:
        summary = budget.summary(budget.video_id(concept_id, fmt))
    except (OSError, ValueError) as exc:
        return f"the budget could not be read ({exc})"
    if not summary.get("confirmed_by_human"):
        return "the per-video budget is not confirmed"
    after = round(float(summary.get("committed_usd") or 0) + float(cost_usd), 4)
    if after > float(summary.get("target_usd") or 0):
        return (
            f"${cost_usd:.2f} would bring this video to ${after:.2f}, above the "
            f"${float(summary.get('target_usd') or 0):.2f} target"
        )
    return None


def visual_plan_problem(item: dict[str, Any]) -> str | None:
    if item.get("error"):
        return "the plan cannot be built: " + str(item["error"])[:200]
    if int(item.get("untimed_shots") or 0):
        return f"{item['untimed_shots']} shot(s) have no timing"
    budget = item.get("budget") or {}
    if budget.get("over_target") or budget.get("over_ceiling"):
        return "the video is already over its budget target"
    return None


def best_candidate(shot: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """The first ELIGIBLE candidate (results are pre-sorted best first)."""
    candidates = [c for c in shot.get("candidates") or [] if isinstance(c, dict)]
    eligible = next((c for c in candidates if c.get("state") == "ELIGIBLE"), None)
    if eligible is not None:
        return eligible, None
    if any(c.get("state") == "HUMAN_REVIEW_REQUIRED" for c in candidates):
        return None, "only editorial or unverified footage was found"
    return None, None


def _decide_visual_plan(control: Any) -> tuple[int, list[str]]:
    decided, held = 0, list[str]()
    snapshot = control.visual_plan_gate_state()
    for item in snapshot.get("items", []):
        if item.get("decision") not in {"PENDING", "BLOCKED"}:
            continue
        concept_id, fmt = str(item.get("concept_id")), str(item.get("format"))
        problem = visual_plan_problem(item)
        if problem:
            held.append(f"{concept_id} {fmt}: {problem}")
            continue
        decided += _apply(
            control.visual_plan_review.apply_action, dict(
                concept_id=concept_id, format=fmt, decision="APPROVE_VISUAL_PLAN",
                note=NOTE + "every shot is timed and the video is within its budget target.",
            ),
            f"{concept_id} {fmt}", held,
        )
    return decided, held


def _decide_narration_spend(control: Any) -> tuple[int, list[str]]:
    decided, held = 0, list[str]()
    production = Path(control.PRODUCTION_DIR)
    render = _json_file(production / "narration_render_config.json")
    identity = _json_file(production / "voice_performance_config.json").get("voice_identity") or {}
    for item in control.narration_spend_gate_snapshot().get("items", []):
        if item.get("decision") != "PENDING":
            continue
        concept_id, fmt = str(item.get("concept_id")), str(item.get("format"))
        label = f"{concept_id} {fmt}"
        if not (render.get("provider_contract") or {}).get("schema_verified"):
            held.append(f"{label}: the narration provider's contract is not verified")
            continue
        if not identity.get("voice_id") or not identity.get("license_reference"):
            held.append(f"{label}: the voice and its licence are not set")
            continue
        if not control.visual_plan_review.is_approved(concept_id, fmt):
            held.append(f"{label}: the visual plan is not approved")
            continue
        worst = item.get("worst_case_estimate_usd")
        problem = spend_problem(control, concept_id, fmt, float(worst) if worst is not None else None)
        if problem:
            held.append(f"{label}: {problem}")
            continue
        criteria = {name: True for name in item.get("required_accept_criteria") or []}
        decided += _apply(
            control.apply_narration_spend_gate_action, dict(
                concept_id=concept_id, format=fmt, decision="ACCEPT", criteria=criteria,
                note=NOTE + f"worst case ${float(worst):.2f} keeps the video within its confirmed "
                "budget target; provider contract verified; voice and licence set.",
            ),
            label, held,
        )
    return decided, held


def _decide_final_audio(control: Any) -> tuple[int, list[str]]:
    decided, held = 0, list[str]()
    # Only videos whose audio QC passed are listed at this gate.
    for item in control.final_audio_gate_state().get("items", []):
        if item.get("decision") != "PENDING":
            continue
        concept_id, fmt = str(item.get("concept_id")), str(item.get("format"))
        decided += _apply(
            control.narration_final_review.apply_action, dict(
                concept_id=concept_id, format=fmt, decision="APPROVE_FINAL_AUDIO",
                note=NOTE + "audio QC passed (duration, silence and clipping).",
            ),
            f"{concept_id} {fmt}", held,
        )
    return decided, held


def _decide_visual_candidate(control: Any) -> tuple[int, list[str]]:
    decided, held = 0, list[str]()
    for packet in control.visual_candidate_review_snapshot().get("packets", []):
        result_file = str(packet.get("result_file"))
        if packet.get("stale_shot_ids"):
            held.append(f"{packet.get('concept_id')} {packet.get('format')}: search results are out of date")
            continue
        decisions = packet.get("decisions") or {}
        for shot in packet.get("shots", []):
            shot_id = str(shot.get("shot_id") or "")
            if not shot_id or shot_id in decisions:
                continue
            candidate, problem = best_candidate(shot)
            if problem:
                held.append(f"shot {shot_id}: {problem}")
                continue
            if candidate is None:
                kwargs = dict(result_file=result_file, shot_id=shot_id, action="NEEDS_BETTER_VISUAL",
                              note=NOTE + "no usable footage found; left as a gap.")
            else:
                kwargs = dict(result_file=result_file, shot_id=shot_id, action="SELECT",
                              candidate_id=str(candidate.get("candidate_id")),
                              note=NOTE + "best licensed candidate with verified reuse rights.")
            decided += _apply(control.apply_visual_candidate_review_action, kwargs, f"shot {shot_id}", held)
    return decided, held


def _decide_rough_cut(control: Any) -> tuple[int, list[str]]:
    decided, held = 0, list[str]()
    for item in control.visual_rough_cut_review_snapshot().get("items", []):
        if item.get("decision") is not None and item.get("review_current"):
            continue
        summary = item.get("summary") or {}
        decided += _apply(
            control.apply_visual_rough_cut_review_action, dict(
                rough_cut_file=str(item.get("rough_cut_file")), decision="APPROVE_WITH_GAPS",
                note=NOTE + f"{summary.get('placeholders', 0)} placeholder(s) go on to gap planning; "
                "approving authorizes no spend.",
            ),
            f"{item.get('concept_id')} {item.get('format')}", held,
        )
    return decided, held


def _decide_visual_spend(control: Any) -> tuple[int, list[str]]:
    decided, held = 0, list[str]()
    providers = _json_file(Path(control.PRODUCTION_DIR) / "visual_provider_config.json")
    active = str(providers.get("active_provider") or "")
    provider = (providers.get("providers") or {}).get(active) or {}
    price = provider.get("price_per_image_usd")
    variants = int(providers.get("variants_per_shot") or 1)
    for item in control.visual_spend_review_snapshot().get("items", []):
        concept_id, fmt = str(item.get("concept_id")), str(item.get("format"))
        decisions = item.get("decisions") or {}
        for gap in item.get("hero_candidates") or []:
            shot_id = str(gap.get("shot_id") or "")
            if not shot_id or shot_id in decisions:
                continue
            label = f"{concept_id} {fmt} shot {shot_id}"
            if not active or not provider.get("contract_verified"):
                held.append(f"{label}: no verified image provider is set")
                continue
            cost = float(price) * variants if isinstance(price, (int, float)) else None
            problem = spend_problem(control, concept_id, fmt, cost)
            if problem:
                held.append(f"{label}: {problem}")
                continue
            decided += _apply(
                control.apply_visual_spend_review_action, dict(
                    gap_plan_file=str(item.get("gap_plan_file")), shot_id=shot_id,
                    decision="AUTHORIZE_GENERATION", max_cost_usd=cost,
                    note=NOTE + f"${cost:.2f} ({variants} variant(s)) keeps the video within its "
                    "confirmed budget target.",
                ),
                label, held,
            )
    return decided, held


def _decide_edit_preview(control: Any) -> tuple[int, list[str]]:
    decided, held = 0, list[str]()
    for item in control.edit_preview_review_snapshot().get("items", []):
        if item.get("decision") != "PENDING":
            continue
        label = str(item.get("result_file"))
        if not item.get("preview_file"):
            held.append(f"{label}: the preview video is missing")
            continue
        decided += _apply(
            control.apply_edit_preview_action, dict(
                result_file=label, decision="APPROVE_EDIT_DIRECTION",
                note=NOTE + f"preview rendered with {item.get('placeholder_segments', 0)} placeholder "
                "segment(s); you review the finished video at the Final Export Gate.",
            ),
            label, held,
        )
    return decided, held


RUNNERS: dict[str, Callable[[Any], tuple[int, list[str]]]] = {
    "vision": _decide_vision,
    "analysis": _decide_analysis,
    "title_direction": _decide_title_direction,
    "format": _decide_format,
    "performance": _decide_performance,
    "narration_preview": _decide_narration_preview,
    "visual_plan": _decide_visual_plan,
    "narration_spend": _decide_narration_spend,
    "final_audio": _decide_final_audio,
    "visual_candidate": _decide_visual_candidate,
    "rough_cut": _decide_rough_cut,
    "visual_spend": _decide_visual_spend,
    "edit_preview": _decide_edit_preview,
}


def decide(state: str | None, control: Any, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Decide the clean items of the gate the workflow stopped at.

    Returns ``{"gate", "decided", "held"}``; ``decided`` is 0 when the gate is
    not automatic or nothing passed its checks.
    """
    gate = STATE_GATES.get(str(state or ""))
    policy = policy if policy is not None else load_policy()
    if gate is None or gate_mode(gate, policy) != AUTO:
        return {"gate": gate, "decided": 0, "held": []}
    with _reviewer(str(policy.get("reviewer_id") or "gate-policy-auto")):
        decided, held = RUNNERS[gate](control)
    return {"gate": gate, "decided": decided, "held": held}
