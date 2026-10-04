"""Plain sentences for the status codes the engines emit (D-170).

The engines speak in codes such as WAITING_FOR_DRAFT_RESEARCH_PACKAGES; the
pages should speak in sentences. This is the one place that translates.
Known codes have a written sentence; any other code is turned into one by
shape (WAITING_FOR_X, READY_FOR_X, HUMAN_X_GATE, X_REQUIRED, NO_X …), so a
new code never shows up raw. The catalogue is served to the pages once
(``/api/plain-language``) and the same shape rules exist in app.js for a
code the catalogue does not carry.
"""

from __future__ import annotations

import re

SENTENCES: dict[str, str] = {
    # Shared
    "PENDING": "Waiting for a decision.",
    "ACCEPT": "Accepted.",
    "ACCEPTED": "Accepted.",
    "REJECT": "Rejected.",
    "REJECTED": "Rejected.",
    "REWORK": "Sent back for rework.",
    "APPROVED": "Approved.",
    "COMPLETE": "Done.",
    "COMPLETED": "Done.",
    "RUNNING": "Running now.",
    "STOPPING": "Stopping.",
    "STOPPED": "Stopped by you.",
    "FAILED": "Failed. Open the job log for the error.",
    "PARTIAL": "Finished part of the work; the rest needs another run or a decision.",
    "SUCCEEDED": "Finished.",
    "ORPHANED": "The UI exited while this ran; it was stopped when the UI came back.",
    "INTERRUPTED": "The UI exited while this ran and it did not finish.",
    "READY": "Ready.",
    "MISSING": "Missing.",
    "WARN": "Worth a look.",
    "UNKNOWN": "Not checked yet.",
    "STALE": "Out of date: the thing it was built on changed.",
    "BLOCKED": "Blocked until an earlier step is done.",
    "NEEDS_REVIEW": "Waiting for your review.",
    "WATCHING": "Being watched by the radar.",
    "SAVED": "Saved for later.",
    "PUBLISHED": "Published on YouTube.",
    "HELD": "Held back by you.",
    # Gates and workflow states
    "READY_TO_PREPARE": "Ready to prepare: the next automatic run builds the review items.",
    "AWAITING_HUMAN_DECISION": "Waiting for your decisions.",
    "AWAITING_HUMAN_REVIEW": "Waiting for your review.",
    "AWAITING_HUMAN_TITLE_DIRECTION": "Waiting for you to choose a title direction.",
    "AWAITING_HUMAN_PUBLISH": "Waiting for you to approve the publish package.",
    "ALL_PUBLISHED": "Every video is published.",
    "WAITING_FOR_DRAFT_RESEARCH_PACKAGES": "Waiting for the research drafts; the automatic run writes them.",
    "WAITING_FOR_RESEARCH_HANDOFF": "Waiting for accepted concepts to hand over to research.",
    "WAITING_FOR_RESEARCH_PLANS": "Waiting for the research plans.",
    "WAITING_FOR_ACQUIRED_EVIDENCE": "Waiting for web evidence to be collected.",
    "WAITING_FOR_COMPLETE_EVIDENCE": "Some research questions still have no source page.",
    "WAITING_FOR_RESEARCH_RESPONSES": "Waiting for the model's research claims.",
    "RESEARCH_INCOMPLETE": "Not ready for the script: a question is unanswered or no claim was accepted.",
    "READY_FOR_STORY_SCRIPT": "Research verified; the story and script can be written.",
    "RESEARCH_GATE_READY": "Research claims are ready for your review.",
    "WAITING_FOR_ACCEPTED_CONCEPTS": "Waiting for you to accept a concept.",
    "WAITING_FOR_CONCEPT_CANDIDATES": "Waiting for concept candidates from the model.",
    "CONCEPT_CANDIDATES_READY": "Concept candidates are ready for your review.",
    "INSUFFICIENT_CONCEPT_CANDIDATES": "Too few concept candidates came back; the next run asks again.",
    "WAITING_FOR_ANALYZED_PROFILES": "Waiting for the study videos to be analysed.",
    "WAITING_FOR_SCRIPT_DRAFTS": "Waiting for the script drafts.",
    "SCRIPT_GATE_READY": "Scripts are ready for your review.",
    "SCRIPT_REWORK_REQUIRED": "The script was sent back for rework.",
    "STORY_PLAN_READY": "The story plan is ready; the script draft is next.",
    "READY_FOR_SECTION_REVIEW": "Script sections are ready for your review.",
    "READY_FOR_PRODUCTION": "Approved for production.",
    "WAITING_FOR_TITLE_DIRECTION_CANDIDATES": "Waiting for title direction candidates.",
    "TITLE_DIRECTION_SELECTED": "A title direction is chosen.",
    "TITLE_DIRECTION_REJECTED": "The title directions were rejected; new ones are requested.",
    "TITLE_DIRECTION_REWORK_REQUESTED": "Title directions were sent back for rework.",
    "PACKAGING_BRIEF_READY": "The packaging brief is ready.",
    "WAITING_FOR_PACKAGE_CANDIDATES": "Waiting for title and thumbnail candidates.",
    "WAITING_FOR_PACKAGE_RESPONSES": "Waiting for the model's packaging answers.",
    "WAITING_FOR_PACKAGE_VALIDATION": "Waiting for the packages to be checked.",
    "WAITING_FOR_VALIDATED_PACKAGES": "Waiting for checked packages.",
    "FINAL_PACKAGE_APPROVED": "The final package is approved.",
    "FINAL_PACKAGING_REJECTED": "The final package was rejected.",
    "WAITING_FOR_FORMAT_PLANS": "Waiting for the format plans.",
    "FORMAT_GATE_READY": "Format plans are ready for your review.",
    "WAITING_FOR_VOICE_PERFORMANCE_SPECS": "Waiting for the voice performance specs.",
    "WAITING_FOR_PERFORMANCE_APPROVAL": "Waiting for you to approve the voice performance.",
    "WAITING_FOR_APPROVED_PERFORMANCE": "Waiting for an approved voice performance.",
    "PERFORMANCE_SPEC_APPROVED": "The voice performance is approved.",
    "WAITING_FOR_APPROVED_VOICE_SPECS": "Waiting for approved voice specs.",
    "FREE_PREVIEW_RENDERED": "The free narration preview is rendered; listen and decide.",
    "READY_FOR_LISTEN_GATE": "The preview is ready to listen to.",
    "READY_FOR_LOCAL_PREVIEW_RENDER": "Ready to render the free preview on this machine.",
    "NARRATION_PREPARED_WITH_BLOCKERS": "The narration request is prepared but something still blocks it.",
    "NARRATION_PROVIDER_SETUP_REQUIRED": "The narration provider is not set up yet.",
    "WAITING_NARRATION_PROVIDER_QUOTE": "Waiting for a provider quote.",
    "WAITING_FOR_PROVIDER_QUOTE": "Waiting for a provider quote.",
    "READY_FOR_PROVIDER_QUOTE": "Ready for a provider quote.",
    "READY_FOR_SPEND_GATE": "Ready for the spend decision.",
    "WAITING_FOR_SPEND_APPROVAL": "Waiting for you to approve the spend.",
    "NARRATION_SPEND_APPROVED": "Narration spend is approved.",
    "WAITING_NARRATION_RENDER_RETURN": "Waiting for the narration audio to come back.",
    "WAITING_FOR_NARRATION_RENDER_RESULTS": "Waiting for the narration audio to come back.",
    "WAITING_FOR_AUDIO_QC": "Waiting for the audio check.",
    "NARRATION_AUDIO_QC_FAILED": "The narration audio failed the quality check.",
    "NARRATION_AUDIO_READY": "The narration audio passed; visuals are next.",
    "FINAL_AUDIO_REWORK_REQUIRED": "The final audio was sent back for rework.",
    "VISUAL_PLAN_REWORK_REQUIRED": "The visual plan was sent back for rework.",
    "READY_FOR_VISUAL_GAP_REVIEW": "Ready to decide what to do about missing visuals.",
    "READY_FOR_VISUAL_SEARCH": "Ready to search for visuals.",
    "READY_FOR_CANDIDATE_REVIEW": "Visual candidates are ready for your review.",
    "READY_FOR_VISUAL_SPEND_GATE": "Ready for the visual spend decision.",
    "WAITING_FOR_COMPLETE_VISUAL_SPEND_DECISIONS": "Waiting for every visual spend decision.",
    "VISUAL_SPEND_INVALID": "A visual spend decision is out of date.",
    "VISUAL_EXISTING_RETRY_REQUIRED": "Try the existing visual sources again before paying.",
    "WAITING_FOR_VISUAL_ASSETS": "Waiting for visual assets.",
    "WAITING_FOR_LOCAL_VISUAL_ASSETS": "Waiting for visuals made on this machine.",
    "WAITING_FOR_PREMIUM_VISUAL_ASSETS": "Waiting for paid visuals.",
    "WAITING_FOR_FINAL_VISUAL_ASSETS": "Waiting for the final visual assets.",
    "WAITING_FOR_FINAL_SOUND_ASSETS": "Waiting for the final sound assets.",
    "WAITING_FOR_ROUGH_CUT": "Waiting for the rough cut.",
    "READY_FOR_ROUGH_CUT": "Ready to assemble the rough cut.",
    "READY_FOR_EDIT_ASSEMBLY": "Ready to assemble the edit.",
    "EDIT_PREVIEW_REWORK_REQUIRED": "The edit preview was sent back for rework.",
    "EDIT_DIRECTION_APPROVED": "The edit direction is approved.",
    "EDIT_RETURNED": "The finished edit is back from the editor.",
    "EXPORTED": "Exported to the editor.",
    "LOCAL_FFMPEG_REQUIRED": "FFmpeg is needed on this machine for the preview render.",
    "LOCAL_FINAL_FFMPEG_REQUIRED": "FFmpeg is needed on this machine for the final render.",
    "READY_FOR_LOCAL_FINAL_RENDER": "Ready to render the final video on this machine.",
    "RENDER_COMPLETE": "Rendered.",
    "FINAL_EXPORT_APPROVED": "The final export is approved.",
    "FINAL_EXPORT_REWORK_REQUIRED": "The final export was sent back for rework.",
    "FINAL_PRODUCTION_HANDOFF_BLOCKED": "Production cannot start: an earlier approval is missing.",
    "WAITING_FOR_UPLOAD": "Approved; waiting to be uploaded.",
    "APPROVED_FOR_UPLOAD": "Approved; ready to upload.",
    "WAITING_FOR_APPROVED_EXPORT": "Waiting for an approved final export.",
    "WAITING_FOR_HUMAN_OPPORTUNITY_GATE": "Waiting for your decision on the opportunities.",
    "WAITING_FOR_DISCOVERY_OUTPUT": "Waiting for discovery to finish.",
    "WAITING_FOR_AUTOMATIC_VELOCITY_REFRESH": "Waiting for the automatic velocity refresh.",
    "WAITING_FOR_NEXT_STAGE": "Waiting for the next stage.",
    "ACTION_REQUIRED": "A step is ready to run.",
    "RUNNING_AUTOMATIC": "The automatic run is working.",
    "WAITING_AUTOMATIC": "Waiting for the automatic run.",
    "HUMAN_GATE": "Waiting for your decision.",
    "SAFETY_STOP": "Stopped after the maximum number of automatic steps; run again to continue.",
    "NO_PROGRESS": "A step ran but nothing changed; check the job log.",
    "STOPPED_AT_BOUNDARY": "Stopped at the next decision point.",
    "MODEL_NOT_INSTALLED": "The local model is not installed.",
    "OLLAMA_UNAVAILABLE": "Ollama is not running.",
    "MODEL_OUTPUT_VALIDATION_ERROR": "The model answered, but the answer failed validation; a retry usually passes.",
    "DIRECT_GEMINI_BILLING_UNCONFIRMED": "The direct Gemini route is off until the billing attestation is set.",
}

_GATE_WORDS = {
    "VISION": "visual evidence", "ANALYSIS": "analysis", "CONCEPT": "concept", "RESEARCH": "research",
    "SCRIPT": "script", "TITLE_DIRECTION": "title direction", "FINAL_PACKAGING": "final package",
    "FORMAT": "format", "PERFORMANCE": "voice performance", "NARRATION_PREVIEW": "narration preview",
    "NARRATION_SPEND": "narration spend", "FINAL_AUDIO": "final audio", "VISUAL_PLAN": "visual plan",
    "VISUAL_CANDIDATE": "visual candidate", "VISUAL_RIGHTS": "footage rights", "ROUGH_CUT": "rough cut",
    "VISUAL_SPEND": "visual spend", "EDIT_PREVIEW": "edit preview", "FINAL_EXPORT": "final export",
    "PUBLISH": "publish",
}


def _words(code: str) -> str:
    return re.sub(r"\s+", " ", code.replace("_", " ").strip().lower())


def sentence(code: object) -> str:
    """A sentence for any status code; known codes are written, others built by shape."""
    text = str(code or "").strip()
    if not text:
        return ""
    key = text.upper()
    if key in SENTENCES:
        return SENTENCES[key]
    if not re.fullmatch(r"[A-Z0-9_]+", key):
        return text
    gate = re.fullmatch(r"HUMAN_([A-Z_]+)_GATE", key)
    if gate:
        return f"Waiting for your decision at the {_GATE_WORDS.get(gate.group(1), _words(gate.group(1)))} gate."
    for prefix, template in (
        ("WAITING_FOR_", "Waiting for {}."),
        ("WAITING_", "Waiting for {}."),
        ("READY_FOR_", "Ready for {}."),
        ("READY_TO_", "Ready to {}."),
        ("NO_", "No {} yet."),
        ("SKIPPED_", "Skipped: {}."),
        ("FAIL_CLOSED_", "Stopped safely: {}."),
    ):
        if key.startswith(prefix) and len(key) > len(prefix):
            return template.format(_words(key[len(prefix):]))
    for suffix, template in (
        ("_REWORK_REQUIRED", "{} was sent back for rework."),
        ("_REQUIRED", "{} is required."),
        ("_APPROVED", "{} is approved."),
        ("_REJECTED", "{} was rejected."),
        ("_READY", "{} is ready."),
        ("_FAILED", "{} failed."),
        ("_COMPLETE", "{} is done."),
        ("_UNAVAILABLE", "{} is not available."),
        ("_ERROR", "{} hit an error."),
    ):
        if key.endswith(suffix) and len(key) > len(suffix):
            body = _words(key[: -len(suffix)])
            return template.format(body[:1].upper() + body[1:])
    body = _words(key)
    return body[:1].upper() + body[1:] + "."


def catalogue() -> dict[str, str]:
    return dict(SENTENCES)
