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
    previous = os.environ.get(REVIEWER_ENV)
    os.environ[REVIEWER_ENV] = reviewer_id
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(REVIEWER_ENV, None)
        else:
            os.environ[REVIEWER_ENV] = previous


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


RUNNERS: dict[str, Callable[[Any], tuple[int, list[str]]]] = {
    "vision": _decide_vision,
    "analysis": _decide_analysis,
    "title_direction": _decide_title_direction,
    "format": _decide_format,
    "performance": _decide_performance,
    "narration_preview": _decide_narration_preview,
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
