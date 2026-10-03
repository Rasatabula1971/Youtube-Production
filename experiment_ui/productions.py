"""Productions derived from files (UI Patch 1, D-115).

A production is one concept the human accepted at the Concept Gate. Nothing
here is stored: each production's stage and status are recomputed on every
call from the artifact state the server already builds (the per-stage
``*_artifact_state`` dicts and the gate snapshots inside them). Deleting or
invalidating an artifact therefore moves a production back a stage; there is
no second source of truth to drift.

Statuses:
  HUMAN_REVIEW  a gate decision for this concept waits on the human
  READY         the next automatic step can run (from the guided workflow)
  BLOCKED       the concept was sent for rework or rejected at a gate
  COMPLETE      every branch has a current final render
"""

from __future__ import annotations

from typing import Any

STAGES: list[tuple[str, str]] = [
    ("CONCEPT", "Concept"),
    ("RESEARCH", "Research"),
    ("SCRIPT", "Script"),
    ("PACKAGE", "Package"),
    ("FORMAT", "Format"),
    ("PRODUCE", "Produce"),
    ("DONE", "Done"),
]
STAGE_INDEX = {stage_id: index for index, (stage_id, _) in enumerate(STAGES)}
STAGE_LABEL = dict(STAGES)

STATUS_LABEL = {
    "HUMAN_REVIEW": "Needs your review",
    "READY": "Ready to run",
    "BLOCKED": "Blocked",
    "COMPLETE": "Complete",
}

BLOCKING_DECISIONS = {"REWORK": "sent for rework", "REJECT": "rejected"}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _ids(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def _cid(item: dict[str, Any]) -> str:
    return str(item.get("concept_id") or "").strip()


def _decisions(items: list[dict[str, Any]], concept_id: str) -> list[str]:
    return [
        str(item.get("decision") or "PENDING").upper()
        for item in items
        if _cid(item) == concept_id
    ]


def _blocked(decisions: list[str]) -> str | None:
    for decision, label in BLOCKING_DECISIONS.items():
        if decision in decisions:
            return label
    return None


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _research(concept_id: str, research: dict[str, Any]) -> tuple[str, str] | None:
    """Return (status, detail) while research is unfinished, else None."""
    gate = _dict(research.get("research_gate"))
    verified = {
        _cid(item)
        for item in _items(gate.get("verified_packages"))
        if item.get("status") == "READY_FOR_STORY_SCRIPT"
    }
    if concept_id in verified:
        return None
    claims = _decisions(_items(gate.get("claims")), concept_id)
    pending = claims.count("PENDING")
    if pending:
        return "HUMAN_REVIEW", f"{_plural(pending, 'research claim')} to verify"
    blocked = _blocked(claims)
    if blocked:
        return "BLOCKED", f"Research claims {blocked}"
    if concept_id in _ids(research.get("draft_concept_ids")):
        return "READY", "Research draft ready; verification package next"
    if concept_id in _ids(research.get("evidence_concept_ids")):
        return "READY", "Evidence collected; research response next"
    if concept_id in _ids(research.get("plan_concept_ids")):
        return "READY", "Research plan ready; evidence collection next"
    return "READY", "Waiting to plan research"


def _script(concept_id: str, story: dict[str, Any]) -> tuple[str, str] | None:
    gate = _dict(story.get("script_gate"))
    if concept_id in _ids(gate.get("production_ready_concept_ids")):
        return None
    scripts = _decisions(_items(gate.get("scripts")), concept_id)
    pending = scripts.count("PENDING")
    if pending:
        return "HUMAN_REVIEW", f"{_plural(pending, 'script')} to review"
    blocked = _blocked(scripts)
    if blocked:
        return "BLOCKED", f"Script {blocked}"
    if scripts:
        return "READY", "Script approved; approved bundle next"
    if concept_id in _ids(story.get("draft_concept_ids")):
        return "READY", "Script drafted; review request next"
    if concept_id in _ids(story.get("story_plan_concept_ids")):
        return "READY", "Story plan ready; script draft next"
    return "READY", "Waiting to plan the story"


def _package(
    concept_id: str,
    title_direction: dict[str, Any],
    fmt: dict[str, Any],
) -> tuple[str, str] | None:
    reached_format = concept_id in (
        _ids(fmt.get("request_concept_ids")) | _ids(fmt.get("plan_concept_ids"))
    ) or bool(_decisions(_items(_dict(fmt.get("format_gate")).get("plans")), concept_id))
    if reached_format:
        return None
    if concept_id in _ids(title_direction.get("candidate_concept_ids")) and not (
        title_direction.get("selected")
    ):
        return "HUMAN_REVIEW", "Title direction to choose"
    if concept_id in _ids(title_direction.get("response_concept_ids")):
        return "READY", "Title directions returned; candidates next"
    return "READY", "Waiting to build the package"


def _format(concept_id: str, fmt: dict[str, Any]) -> tuple[str, str] | None:
    plans = _decisions(_items(_dict(fmt.get("format_gate")).get("plans")), concept_id)
    if "ACCEPT" in plans:
        return None
    if plans.count("PENDING"):
        return "HUMAN_REVIEW", "Format plan to review"
    blocked = _blocked(plans)
    if blocked:
        return "BLOCKED", f"Format plan {blocked}"
    if concept_id in _ids(fmt.get("plan_concept_ids")):
        return "READY", "Format plan drafted; review next"
    return "READY", "Waiting to plan formats"


def _branches(concept_id: str, voice: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(item.get("format") or "").strip()
            for item in _items(voice.get("expected_branches"))
            if _cid(item) == concept_id and str(item.get("format") or "").strip()
        }
    )


def _produce(
    concept_id: str,
    voice: dict[str, Any],
    narration: dict[str, Any],
    final_render_keys: set[tuple[str, str]],
) -> tuple[str, str, list[dict[str, Any]]]:
    """Return (status, detail, branches) for the production stage."""
    formats = _branches(concept_id, voice)
    audio_pass = {
        str(item.get("format") or "").strip()
        for item in _items(_dict(narration.get("audio_qc")).get("items"))
        if _cid(item) == concept_id and item.get("status") == "PASS"
    }
    spec_formats = {
        str(item.get("format") or "").strip()
        for item in _items(voice.get("spec_branches"))
        if _cid(item) == concept_id
    }
    branches = [
        {
            "format": branch,
            "voice_spec": branch in spec_formats,
            "narration_audio": branch in audio_pass,
            "final_render": (concept_id, branch) in final_render_keys,
        }
        for branch in formats
    ]
    if branches and all(item["final_render"] for item in branches):
        return "COMPLETE", f"{_plural(len(branches), 'final render')} current", branches
    performance = _items(_dict(voice.get("performance_gate")).get("specs"))
    perf_decisions = _decisions(performance, concept_id)
    pending = perf_decisions.count("PENDING")
    if pending:
        return (
            "HUMAN_REVIEW",
            f"{_plural(pending, 'voice performance')} to review",
            branches,
        )
    blocked = _blocked(perf_decisions)
    if blocked:
        return "BLOCKED", f"Voice performance {blocked}", branches
    if not branches:
        return "READY", "Waiting for production branches", branches
    rendered = sum(1 for item in branches if item["final_render"])
    if rendered:
        return (
            "READY",
            f"{rendered} of {len(branches)} branches rendered",
            branches,
        )
    narrated = sum(1 for item in branches if item["narration_audio"])
    if narrated:
        return (
            "READY",
            f"Narration passed for {narrated} of {len(branches)}; visuals and edit next",
            branches,
        )
    specced = sum(1 for item in branches if item["voice_spec"])
    if specced:
        return "READY", "Voice specs ready; narration next", branches
    return "READY", "Waiting for voice performance specs", branches


def _stage_track(stage_id: str) -> list[dict[str, str]]:
    current = STAGE_INDEX[stage_id]
    track = []
    for index, (sid, label) in enumerate(STAGES):
        if sid == "DONE":
            continue
        if stage_id == "DONE" or index < current:
            state = "done"
        elif index == current:
            state = "current"
        else:
            state = "todo"
        track.append({"id": sid, "label": label, "state": state})
    return track


def derive(
    *,
    concept_gate: dict[str, Any],
    research: dict[str, Any],
    story: dict[str, Any],
    title_direction: dict[str, Any],
    fmt: dict[str, Any],
    voice: dict[str, Any],
    narration: dict[str, Any],
    final_render_keys: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Derive every production from the current artifact state."""
    final_keys = final_render_keys or set()
    concept_gate, research, story = _dict(concept_gate), _dict(research), _dict(story)
    title_direction, fmt = _dict(title_direction), _dict(fmt)
    voice, narration = _dict(voice), _dict(narration)
    productions: list[dict[str, Any]] = []
    for concept in _items(concept_gate.get("concepts")):
        concept_id = _cid(concept)
        if not concept_id or str(concept.get("decision") or "").upper() != "ACCEPT":
            continue
        branches: list[dict[str, Any]] = []
        stage = "RESEARCH"
        found = _research(concept_id, research)
        if found is None:
            stage = "SCRIPT"
            found = _script(concept_id, story)
        if found is None:
            stage = "PACKAGE"
            found = _package(concept_id, title_direction, fmt)
        if found is None:
            stage = "FORMAT"
            found = _format(concept_id, fmt)
        if found is None:
            stage = "PRODUCE"
            status, detail, branches = _produce(
                concept_id, voice, narration, final_keys
            )
            if status == "COMPLETE":
                stage = "DONE"
        else:
            status, detail = found
        productions.append(
            {
                "concept_id": concept_id,
                "title": str(concept.get("working_title") or concept_id),
                "premise": str(concept.get("premise") or ""),
                "mechanism_label": str(concept.get("mechanism_label") or ""),
                "stage": stage,
                "stage_label": STAGE_LABEL[stage],
                "stage_index": STAGE_INDEX[stage],
                "status": status,
                "status_label": STATUS_LABEL[status],
                "detail": detail,
                "stages": _stage_track(stage),
                "branches": branches,
            }
        )
    # Human review first, then blocked, then furthest along.
    order = {"HUMAN_REVIEW": 0, "BLOCKED": 1, "READY": 2, "COMPLETE": 3}
    productions.sort(
        key=lambda item: (order[item["status"]], -item["stage_index"], item["title"])
    )
    by_status = {key: 0 for key in order}
    by_stage = {stage_id: 0 for stage_id, _ in STAGES}
    for item in productions:
        by_status[item["status"]] += 1
        by_stage[item["stage"]] += 1
    return {
        "source": "derived_from_files",
        "count": len(productions),
        "active_count": len(productions) - by_status["COMPLETE"],
        "by_status": by_status,
        "by_stage": by_stage,
        "stages": [{"id": sid, "label": label} for sid, label in STAGES],
        "productions": productions,
    }
