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


# ---------------------------------------------------------------------------
# Production workspace (UI-08, D-117): one concept, eight sections.
# ---------------------------------------------------------------------------

WORKSPACE_SECTIONS: list[tuple[str, str, str]] = [
    # (section id, label, pipeline stage it belongs to)
    ("EVIDENCE", "Evidence", "CONCEPT"),
    ("ANALYSIS", "Analysis", "CONCEPT"),
    ("CONCEPT", "Concept", "CONCEPT"),
    ("RESEARCH", "Research", "RESEARCH"),
    ("SCRIPT", "Script", "SCRIPT"),
    ("PACKAGE", "Package", "PACKAGE"),
    ("FORMAT", "Format", "FORMAT"),
    ("PRODUCE", "Produce", "PRODUCE"),
]

DECISION_TONE = {
    "ACCEPT": "complete",
    "ACCEPTED": "complete",
    "LOCKED": "complete",
    "PENDING": "human",
    "REWORK": "blocked",
    "REJECT": "blocked",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(_text(item) for item in value if _text(item))
    if isinstance(value, dict):
        for key in ("summary", "rationale", "label", "text", "statement", "level", "status"):
            if value.get(key):
                return _text(value.get(key))
        return ""
    return str(value).strip()


def _facts(*pairs: tuple[str, Any]) -> list[dict[str, str]]:
    return [{"label": label, "value": _text(value)} for label, value in pairs if _text(value)]


def _row(label: str, decision: str, detail: str = "") -> dict[str, str]:
    decision = (decision or "PENDING").upper()
    return {
        "label": label,
        "status": decision.replace("_", " ").lower(),
        "tone": DECISION_TONE.get(decision, "ready"),
        "detail": detail,
    }


def _flag_rows(pairs: list[tuple[str, bool]]) -> list[dict[str, str]]:
    return [
        {
            "label": label,
            "status": "done" if done else "not yet",
            "tone": "complete" if done else "ready",
            "detail": "",
        }
        for label, done in pairs
    ]


def _target_label(target: dict[str, Any]) -> str:
    kind = str(target.get("target_type") or "")
    if kind == "OPENING_HOOK":
        return "Opening hook"
    if kind == "CLOSING":
        return "Closing"
    meta = _dict(target.get("metadata"))
    purpose = _text(meta.get("purpose"))
    section = str(target.get("section_id") or "section")
    return f"{section}: {purpose}" if purpose else section


def detail(
    production: dict[str, Any],
    *,
    concept: dict[str, Any],
    research: dict[str, Any],
    story: dict[str, Any],
    title_direction: dict[str, Any],
    fmt: dict[str, Any],
    voice: dict[str, Any],
    script_sections: list[dict[str, Any]] | None = None,
    format_branches: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Everything the workspace shows for one production, read from current state."""
    concept_id = str(production.get("concept_id") or "")
    concept, research, story = _dict(concept), _dict(research), _dict(story)
    title_direction, fmt, voice = _dict(title_direction), _dict(fmt), _dict(voice)
    track = {step["id"]: step["state"] for step in production.get("stages") or []}
    sections: list[dict[str, Any]] = []

    def add(section_id: str, label: str, stage: str, **body: Any) -> None:
        state = "done" if stage == "CONCEPT" else track.get(stage, "todo")
        if production.get("stage") == "DONE":
            state = "done"
        sections.append({"id": section_id, "label": label, "state": state, **body})

    # Evidence: why this concept was believed to have an audience.
    add(
        "EVIDENCE",
        "Evidence",
        "CONCEPT",
        summary="The audience evidence the concept was accepted on.",
        facts=_facts(
            ("Viewer need evidence", concept.get("viewer_need_evidence")),
            ("Content gap", concept.get("content_gap")),
            ("Channel fit", concept.get("channel_fit")),
            ("Source overlap", concept.get("source_overlap")),
            ("Source dependency test", concept.get("source_dependency_test")),
        ),
        rows=[],
        empty="No audience evidence was recorded on this concept.",
    )
    add(
        "ANALYSIS",
        "Analysis",
        "CONCEPT",
        summary="The mechanism from Experiment 02 this concept applies.",
        facts=_facts(
            ("Mechanism", concept.get("mechanism_label") or concept.get("mechanism_id")),
            ("How it is applied", concept.get("mechanism_application")),
            ("Transformation method", concept.get("transformation_method")),
        ),
        rows=[],
        empty="No analysis details were recorded on this concept.",
    )
    add(
        "CONCEPT",
        "Concept",
        "CONCEPT",
        summary="Accepted at the Concept Gate.",
        facts=_facts(
            ("Premise", concept.get("premise")),
            ("Audience promise", concept.get("audience_promise")),
            ("Viewer problem", concept.get("viewer_problem")),
            ("Viewer moment", concept.get("viewer_moment")),
            ("Desired outcome", concept.get("desired_outcome")),
            ("Title clarity test", concept.get("title_clarity_test")),
            ("Format intent", concept.get("format_intent")),
            ("Your note", concept.get("note")),
        ),
        rows=[],
        empty="",
    )

    # Research: plan, evidence, draft, then the claims you verify.
    gate = _dict(research.get("research_gate"))
    claims = [c for c in _items(gate.get("claims")) if _cid(c) == concept_id]
    verified = next(
        (v for v in _items(gate.get("verified_packages")) if _cid(v) == concept_id),
        None,
    )
    questions = [_text(q) for q in concept.get("research_questions") or [] if _text(q)]
    add(
        "RESEARCH",
        "Research",
        "RESEARCH",
        summary=(
            "Verified and ready for the script."
            if verified and verified.get("status") == "READY_FOR_STORY_SCRIPT"
            else f"{len(claims)} claim(s) at the Research Gate." if claims else "Research has not reached the gate yet."
        ),
        facts=_facts(("Research questions", questions)),
        progress=_flag_rows(
            [
                ("Research plan", concept_id in _ids(research.get("plan_concept_ids"))),
                ("Evidence collected", concept_id in _ids(research.get("evidence_concept_ids"))),
                ("Research response", concept_id in _ids(research.get("response_concept_ids"))),
                ("Draft package", concept_id in _ids(research.get("draft_concept_ids"))),
                ("Verified package", bool(verified and verified.get("status") == "READY_FOR_STORY_SCRIPT")),
            ]
        ),
        rows=[
            _row(
                str(c.get("claim_id") or "claim"),
                str(c.get("decision") or "PENDING"),
                _text(c.get("statement")),
            )
            for c in claims
        ],
        empty="No claims yet.",
    )

    # Script: per format branch, the section-by-section review state.
    script_gate = _dict(story.get("script_gate"))
    scripts = [s for s in _items(script_gate.get("scripts")) if _cid(s) == concept_id]
    script_rows: list[dict[str, str]] = []
    for script in scripts:
        script_rows.append(
            _row(
                f"{script.get('format') or 'branch'} script",
                str(script.get("decision") or "PENDING"),
                _text(script.get("title")),
            )
        )
    for branch in script_sections or []:
        for target in _items(_dict(branch).get("targets")):
            decision = "LOCKED" if target.get("locked") else str(target.get("decision") or "PENDING")
            alternatives = _dict(target.get("alternatives"))
            extra = []
            if target.get("rework_reason"):
                extra.append(str(target.get("rework_reason")).replace("_", " ").lower())
            ready = [a for a in alternatives.get("alternatives") or [] if a]
            if ready:
                extra.append(f"{len(ready)} alternatives ready")
            script_rows.append(
                _row(f"{branch.get('format')} · {_target_label(target)}", decision, ", ".join(extra))
            )
    add(
        "SCRIPT",
        "Script",
        "SCRIPT",
        summary=(
            "Approved for production."
            if concept_id in _ids(script_gate.get("production_ready_concept_ids"))
            else f"{len(scripts)} script branch(es) at the Script Gate." if scripts else "No script yet."
        ),
        facts=[],
        progress=_flag_rows(
            [
                ("Story plan", concept_id in _ids(story.get("story_plan_concept_ids"))),
                ("Script drafted", concept_id in _ids(story.get("draft_concept_ids"))),
                ("Approved", concept_id in _ids(script_gate.get("production_ready_concept_ids"))),
            ]
        ),
        rows=script_rows,
        empty="Sections appear here once a script is drafted.",
    )

    add(
        "PACKAGE",
        "Package",
        "PACKAGE",
        summary="Title direction, thumbnail and final package.",
        facts=[],
        progress=_flag_rows(
            [
                ("Script approved for packaging", concept_id in _ids(title_direction.get("approved_script_concept_ids"))),
                ("Title directions requested", concept_id in _ids(title_direction.get("request_concept_ids"))),
                ("Title directions returned", concept_id in _ids(title_direction.get("response_concept_ids"))),
                ("Candidates ready", concept_id in _ids(title_direction.get("candidate_concept_ids"))),
                ("Final package (format started)", concept_id in _ids(fmt.get("request_concept_ids")) | _ids(fmt.get("plan_concept_ids"))),
            ]
        ),
        rows=[],
        empty="",
    )

    plans = [p for p in _items(_dict(fmt.get("format_gate")).get("plans")) if _cid(p) == concept_id]
    add(
        "FORMAT",
        "Format",
        "FORMAT",
        summary="Which versions get made (long-form, Shorts).",
        facts=[],
        progress=_flag_rows(
            [
                ("Format plan drafted", concept_id in _ids(fmt.get("plan_concept_ids"))),
                ("Format plan accepted", any(str(p.get("decision") or "").upper() == "ACCEPT" for p in plans)),
            ]
        ),
        rows=[_row("Format plan", str(p.get("decision") or "PENDING"), _text(p.get("note"))) for p in plans]
        + [
            _row(f"Branch: {b.get('format')}", "ACCEPT", _text(b.get("duration_target") or b.get("target_duration_seconds")))
            for b in format_branches or []
            if b.get("format")
        ],
        empty="",
    )

    perf = [s for s in _items(_dict(voice.get("performance_gate")).get("specs")) if _cid(s) == concept_id]
    perf_by_format = {str(s.get("format") or ""): str(s.get("decision") or "PENDING") for s in perf}
    produce_rows = []
    for branch in production.get("branches") or []:
        steps = [
            ("voice spec", branch.get("voice_spec")),
            ("narration audio", branch.get("narration_audio")),
            ("final render", branch.get("final_render")),
        ]
        done = [name for name, ok in steps if ok]
        decision = "ACCEPT" if branch.get("final_render") else perf_by_format.get(str(branch.get("format")), "PENDING")
        produce_rows.append(
            _row(
                f"{branch.get('format')} version",
                "ACCEPT" if branch.get("final_render") else decision,
                ("done: " + ", ".join(done)) if done else "not started",
            )
        )
    add(
        "PRODUCE",
        "Produce",
        "PRODUCE",
        summary="Voice, narration, visuals, edit and final render for each version.",
        facts=[],
        rows=produce_rows,
        empty="Production starts once a format plan is accepted.",
    )

    for section in sections:
        section.setdefault("progress", [])
    return {"production": production, "sections": sections}
