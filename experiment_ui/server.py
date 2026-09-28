"""Local experiment control UI for the YouTube Production project.

Dependency-free HTTP server bound to 127.0.0.1. The browser UI can run only
predefined experiment actions; arbitrary shell commands are never accepted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import secrets
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
STATIC_DIR = HERE / "static"
APP_ROUTES = {"/", "/opportunity", "/analysis", "/tools"}
IS_WINDOWS = os.name == "nt"
CSRF_TOKEN = secrets.token_urlsafe(32)

UI_OUTPUT_DIR = PROJECT_ROOT / ".experiment_ui"
JOB_LOG_DIR = UI_OUTPUT_DIR / "jobs"
JOB_STATE_FILE = UI_OUTPUT_DIR / "job_state.json"

EXP1_OUTPUT = PROJECT_ROOT / "experiment_01_discovery" / "output"
EXP13_DIR = EXP1_OUTPUT / "experiment_01_3"
EXP13_CHECKPOINT = EXP1_OUTPUT / "experiment_01_3_discovery_checkpoint.json"
EXP13_CONFIG = PROJECT_ROOT / "experiment_01_discovery" / "experiment_01_3_config.json"
EXP14_DIR = EXP1_OUTPUT / "experiment_01_4"
EXP14_CONFIG = PROJECT_ROOT / "experiment_01_discovery" / "experiment_01_4_config.json"
EXP15_DIR = EXP1_OUTPUT / "experiment_01_5"
OPPORTUNITY_RESEARCH_STATE = EXP1_OUTPUT / "opportunity_research_state.json"

EXP1_MODULE_DIR = PROJECT_ROOT / "experiment_01_discovery"
if str(EXP1_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(EXP1_MODULE_DIR))

from opportunity_gate import (  # noqa: E402
    apply_gate_action,
    gate_snapshot as opportunity_gate_snapshot,
)

EXP2_DIR = PROJECT_ROOT / "experiment_02_analysis"
if str(EXP2_DIR) not in sys.path:
    sys.path.insert(0, str(EXP2_DIR))

from vision_review import (  # noqa: E402
    apply_review_action as apply_vision_review_action,
    frame_path as vision_frame_path,
    review_snapshot as vision_review_snapshot,
)
from human_review import (  # noqa: E402
    apply_review_action as apply_human_analysis_review_action,
    review_snapshot as human_analysis_review_snapshot,
)

EXP2_OUTPUT = EXP2_DIR / "output"
EXP2_PREPARED_DIR = EXP2_OUTPUT / "profiles_to_complete"
EXP2_ENRICHED_DIR = EXP2_OUTPUT / "profiles_enriched"
EXP2_REQUESTS_DIR = EXP2_OUTPUT / "analysis_requests"
EXP2_ANALYZED_DIR = EXP2_OUTPUT / "profiles_analyzed"
EXP2_MODEL_RUNS_DIR = EXP2_OUTPUT / "model_runs"
EXP2_REVIEW_REQUESTS_DIR = EXP2_OUTPUT / "human_review_requests"
EXP2_REVIEWED_DIR = EXP2_OUTPUT / "profiles_reviewed"
EXP2_SYNTHESIS_FILE = EXP2_OUTPUT / "synthesis" / "transformation_handoff.json"
SOURCE_ACQ_OUTPUT = PROJECT_ROOT / "source_acquisition" / "output"
EXP2_ACQUISITION_SUMMARY = SOURCE_ACQ_OUTPUT / "experiment_02" / "summary.json"
EXP2_VISUAL_SUMMARY = SOURCE_ACQ_OUTPUT / "experiment_02" / "visual_summary.json"

TRANSFORM_DIR = PROJECT_ROOT / "transformation_engine"
if str(TRANSFORM_DIR) not in sys.path:
    sys.path.insert(0, str(TRANSFORM_DIR))

from concept_review import (  # noqa: E402
    apply_action as apply_concept_gate_action,
    snapshot as concept_gate_snapshot,
)

TRANSFORM_OUTPUT = TRANSFORM_DIR / "output"
TRANSFORM_REQUESTS_DIR = TRANSFORM_OUTPUT / "concept_requests"
TRANSFORM_RESPONSES_DIR = TRANSFORM_OUTPUT / "concept_responses"
TRANSFORM_CANDIDATES_FILE = TRANSFORM_OUTPUT / "concept_candidates.json"
TRANSFORM_TRIAGE_FILE = TRANSFORM_OUTPUT / "concept_triage.json"
TRANSFORM_TRIAGED_CANDIDATES_FILE = TRANSFORM_OUTPUT / "concept_candidates_triaged.json"
TRANSFORM_RESEARCH_HANDOFF = TRANSFORM_OUTPUT / "research_handoff.json"

PACKAGING_DIR = PROJECT_ROOT / "packaging_engine"
if str(PACKAGING_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGING_DIR))

from package_review import (  # noqa: E402
    apply_action as apply_packaging_gate_action,
    snapshot as packaging_gate_snapshot,
)

PACKAGING_OUTPUT = PACKAGING_DIR / "output"
PACKAGING_REQUESTS_DIR = PACKAGING_OUTPUT / "package_requests"
PACKAGING_RESPONSES_DIR = PACKAGING_OUTPUT / "package_responses"
PACKAGING_CANDIDATES_FILE = PACKAGING_OUTPUT / "package_candidates.json"
PACKAGING_RESEARCH_HANDOFF = PACKAGING_OUTPUT / "research_handoff.json"

RESEARCH_DIR = PROJECT_ROOT / "research_engine"
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from research_review import (  # noqa: E402
    apply_action as apply_research_gate_action,
    snapshot as research_gate_snapshot,
)

RESEARCH_OUTPUT = RESEARCH_DIR / "output"
RESEARCH_PLANS_DIR = RESEARCH_OUTPUT / "plans"
RESEARCH_EVIDENCE_DIR = RESEARCH_OUTPUT / "acquired_evidence"
RESEARCH_RESPONSES_DIR = RESEARCH_OUTPUT / "research_responses"
RESEARCH_DRAFTS_DIR = RESEARCH_OUTPUT / "draft_packages"
RESEARCH_VERIFIED_DIR = RESEARCH_OUTPUT / "verified_packages"

STORY_DIR = PROJECT_ROOT / "story_script_engine"
if str(STORY_DIR) not in sys.path:
    sys.path.insert(0, str(STORY_DIR))

from script_review import (  # noqa: E402
    apply_action as apply_script_gate_action,
    snapshot as script_gate_snapshot,
)

STORY_OUTPUT = STORY_DIR / "output"
SCRIPT_REQUESTS_DIR = STORY_OUTPUT / "script_requests"
SCRIPT_DRAFTS_DIR = STORY_OUTPUT / "script_drafts"
SCRIPT_APPROVED_DIR = STORY_OUTPUT / "approved_scripts"

WORKFLOW_ACTION_ORDER = [
    "opportunity_research",
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
    "script_prepare",
    "script_generate",
    "script_gate_prepare",
]

ACTION_DEFS: dict[str, dict[str, Any]] = {
    "opportunity_research": {
        "label": "Run Opportunity Research",
        "stage": "OPPORTUNITY",
        "command": [
            sys.executable,
            "experiment_01_discovery/opportunity_research.py",
            "--mode",
            "start",
        ],
        "description": (
            "Automatically runs discovery, timed velocity validation, "
            "depth expansion and opportunity handoff, then stops for human review."
        ),
    },
    "agent_reach_doctor": {
        "label": "Run Agent Reach Doctor",
        "stage": "ACQ",
        "command": [
            sys.executable,
            "source_acquisition/agent_reach_adapter.py",
            "--mode",
            "doctor",
        ],
        "description": "Checks source-acquisition channels and confirms the active YouTube backend.",
    },
    "agent_reach_youtube_benchmark": {
        "label": "Run YouTube Discovery Benchmark",
        "stage": "ACQ",
        "command": [
            sys.executable,
            "source_acquisition/youtube_discovery_benchmark.py",
            "--mode",
            "collect",
            "--limit",
            "10",
            "--strategy",
            "relevance",
        ],
        "description": "Compares Agent Reach / yt-dlp discovery against the saved 01.3 API search audit without changing the cohort.",
    },
    "exp13_discover": {
        "label": "Run / Resume 01.3 Auto Discovery",
        "stage": "01.3",
        "command": [
            sys.executable,
            "experiment_01_discovery/experiment_01_3.py",
            "--mode",
            "discover",
            "--replace-cohort",
            "--discovery-backend",
            "auto",
        ],
        "description": "Uses YouTube Data API v3 search when available and automatically falls back to Agent Reach / yt-dlp when search quota is unavailable. Official API metadata and measurement remain unchanged.",
    },
    "exp13_restart": {
        "label": "Restart 01.3 Discovery Clean",
        "stage": "01.3",
        "command": [
            sys.executable,
            "experiment_01_discovery/experiment_01_3.py",
            "--mode",
            "discover",
            "--replace-cohort",
            "--restart-discovery",
            "--discovery-backend",
            "auto",
        ],
        "description": (
            "Archives the current 01.3 output, deletes the saved discovery "
            "checkpoint, and starts a completely new corrected discovery run."
        ),
    },
    "exp13_refresh": {
        "label": "Refresh 01.3 Frozen Cohort",
        "stage": "01.3",
        "command": [
            sys.executable,
            "experiment_01_discovery/experiment_01_3.py",
            "--mode",
            "refresh",
        ],
        "description": "Fetches current view counts for the same frozen video IDs. No new search discovery.",
    },
    "exp13_auto_refresh_install": {
        "label": "Install Opportunity Auto-Continue",
        "stage": "01.3",
        "command": [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/install_experiment_01_3_auto_refresh.ps1",
            "-EveryHours",
            "2",
            "-PythonPath",
            sys.executable,
        ],
        "description": (
            "Registers the Windows continuation task used by automatic "
            "Opportunity Research while velocity evidence is pending."
        ),
    },
    "exp13_auto_refresh_remove": {
        "label": "Remove Opportunity Auto-Continue",
        "stage": "01.3",
        "command": [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/remove_experiment_01_3_auto_refresh.ps1",
        ],
        "description": "Removes the Windows Opportunity Research continuation task.",
    },
    "exp14_plan": {
        "label": "Build 01.4 Expansion Plan",
        "stage": "01.4",
        "command": [
            sys.executable,
            "experiment_01_discovery/experiment_01_4.py",
            "--mode",
            "plan",
        ],
        "description": "Builds the zero-quota depth-expansion plan from completed 01.3 evidence.",
    },
    "exp14_execute": {
        "label": "Execute 01.4 Expansion",
        "stage": "01.4",
        "command": [
            sys.executable,
            "experiment_01_discovery/experiment_01_4.py",
            "--mode",
            "execute",
        ],
        "description": "Runs the frozen 01.4 depth-expansion plan with checkpoint/resume.",
    },
    "exp15_build": {
        "label": "Build 01.5 Opportunity Handoff",
        "stage": "01.5",
        "command": [
            sys.executable,
            "experiment_01_discovery/experiment_01_5.py",
            "--mode",
            "build",
        ],
        "description": "Creates PASS / REVIEW / HOLD packets and the Experiment 02 study set.",
    },
    "exp2_prepare": {
        "label": "Prepare Experiment 02 Profiles",
        "stage": "02",
        "command": [
            sys.executable,
            "experiment_02_analysis/experiment_02.py",
            "--mode",
            "prepare",
        ],
        "description": "Creates the Experiment 02 work packets and empty evidence profiles.",
    },
    "exp2_acquire": {
        "label": "Acquire Source Evidence",
        "stage": "02",
        "command": [
            sys.executable,
            "source_acquisition/experiment_02_evidence.py",
            "--mode",
            "acquire",
        ],
        "description": (
            "Uses yt-dlp to acquire English captions, thumbnail and source metadata "
            "for the approved videos. Video media is not downloaded."
        ),
    },
    "exp2_visual": {
        "label": "Acquire Visual Structure",
        "stage": "02",
        "command": [
            sys.executable,
            "source_acquisition/experiment_02_visual.py",
            "--mode",
            "acquire",
        ],
        "description": (
            "Streams a low-resolution source, saves no full video, extracts an "
            "opening frame and scene-change frames, and creates objective timing evidence."
        ),
    },
    "exp2_vision_prepare": {
        "label": "Prepare Visual Review",
        "stage": "02",
        "command": [
            sys.executable,
            "experiment_02_analysis/vision_review.py",
            "--mode",
            "prepare",
            "--provider",
            "auto",
        ],
        "description": (
            "Creates a bounded visual review set. A configured local Ollama "
            "vision model may propose descriptions, but human approval is required."
        ),
    },
    "vision_doctor": {
        "label": "Run Vision Doctor",
        "stage": "ACQ",
        "command": [
            sys.executable,
            "experiment_02_analysis/vision_review.py",
            "--mode",
            "doctor",
        ],
        "description": (
            "Checks whether local Ollama visual drafting is configured. "
            "Human-only review remains available without it."
        ),
    },
    "exp2_visual_retry": {
        "label": "Retry Visual Structure (Force)",
        "stage": "ACQ",
        "command": [
            sys.executable,
            "source_acquisition/experiment_02_visual.py",
            "--mode",
            "acquire",
            "--force",
        ],
        "description": (
            "Forces a fresh low-resolution visual-structure pass when the guided "
            "attempt failed or needs to be rebuilt."
        ),
    },
    "fair_doctor": {
        "label": "Run FAIR Doctor",
        "stage": "02",
        "command": [
            sys.executable,
            "experiment_02_analysis/analysis_model_runner.py",
            "--mode",
            "doctor",
        ],
        "description": "Checks FAIR, free-only providers and local model availability without inference.",
    },
    "analysis_batch_prepare": {
        "label": "Prepare Analysis Requests",
        "stage": "02",
        "command": [
            sys.executable,
            "experiment_02_analysis/analysis_execute.py",
            "--mode",
            "batch-prepare",
            "--profiles-dir",
            "experiment_02_analysis/output/profiles_enriched",
        ],
        "description": "Creates evidence-constrained model requests for all enriched profiles.",
    },
    "analysis_model_one": {
        "label": "Run 1 Model Analysis",
        "stage": "02",
        "command": [
            sys.executable,
            "experiment_02_analysis/analysis_model_runner.py",
            "--mode",
            "batch",
            "--requests-dir",
            "experiment_02_analysis/output/analysis_requests",
            "--max-requests",
            "1",
        ],
        "description": "Runs one FAIR-backed analysis request so results can be inspected before scaling.",
    },
    "analysis_model_remaining": {
        "label": "Run Remaining Analyses",
        "stage": "02",
        "command": [
            sys.executable,
            "experiment_02_analysis/analysis_model_runner.py",
            "--mode",
            "batch",
            "--requests-dir",
            "experiment_02_analysis/output/analysis_requests",
        ],
        "description": (
            "Runs all remaining current FAIR-backed analysis requests. "
            "Already-applied requests are skipped automatically."
        ),
    },
    "human_review_prepare": {
        "label": "Prepare Human Review Packets",
        "stage": "02",
        "command": [
            sys.executable,
            "experiment_02_analysis/human_review.py",
            "--mode",
            "batch-prepare",
        ],
        "description": "Creates review packets for analyzed profiles.",
    },
    "synthesis_build": {
        "label": "Build Experiment 02 Synthesis",
        "stage": "02",
        "command": [
            sys.executable,
            "experiment_02_analysis/synthesis_handoff.py",
            "--mode",
            "build",
        ],
        "description": "Builds the mechanism library and Transformation Engine handoff.",
    },
    "transform_prepare": {
        "label": "Prepare Concept Requests",
        "stage": "04",
        "command": [
            sys.executable,
            "transformation_engine/transformation_engine.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Turns human-confirmed Experiment 02 mechanisms into bounded, "
            "source-independent concept-generation requests."
        ),
    },
    "concept_generate": {
        "label": "Generate Concept Candidates",
        "stage": "04",
        "command": [
            sys.executable,
            "transformation_engine/concept_model_runner.py",
            "--mode",
            "batch",
            "--requests-dir",
            "transformation_engine/output/concept_requests",
        ],
        "description": (
            "Runs the prepared concept requests through FAIR free-only routing, "
            "then applies deterministic Source Dependency and schema validation."
        ),
    },
    "concept_triage": {
        "label": "Triage Concept Candidates",
        "stage": "04",
        "command": [
            sys.executable,
            "transformation_engine/concept_triage.py",
            "--mode",
            "run",
        ],
        "description": (
            "Uses FAIR free-only routing to compare all structurally valid concepts "
            "and shortlist the strongest 3-6 for human review."
        ),
    },
    "concept_gate_prepare": {
        "label": "Prepare Concept Gate",
        "stage": "04",
        "command": [
            sys.executable,
            "transformation_engine/concept_review.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Prepares the compact human Concept Gate. No concept is selected automatically."
        ),
    },
    "package_prepare": {
        "label": "Prepare Package Requests",
        "stage": "05",
        "command": [
            sys.executable,
            "packaging_engine/packaging_engine.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Turns human-accepted concepts into bounded title, thumbnail and opening-frame requests."
        ),
    },
    "package_generate": {
        "label": "Generate Package Candidates",
        "stage": "05",
        "command": [
            sys.executable,
            "packaging_engine/package_model_runner.py",
            "--mode",
            "batch",
            "--requests-dir",
            "packaging_engine/output/package_requests",
        ],
        "description": (
            "Runs package requests through FAIR free-only routing and validates the package contract."
        ),
    },
    "package_gate_prepare": {
        "label": "Prepare Packaging Gate",
        "stage": "05",
        "command": [
            sys.executable,
            "packaging_engine/package_review.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Prepares the compact human Packaging Gate. No package is selected automatically."
        ),
    },
    "research_prepare": {
        "label": "Prepare Research Plans",
        "stage": "06",
        "command": [
            sys.executable,
            "research_engine/research_engine.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Turns approved packages into bounded research questions, including package promise dependencies."
        ),
    },
    "research_acquire": {
        "label": "Acquire Research Evidence",
        "stage": "06",
        "command": [
            sys.executable,
            "research_engine/research_acquisition.py",
            "--mode",
            "batch",
        ],
        "description": (
            "Uses Agent Reach Exa search and Jina Reader to acquire real web pages for current research questions."
        ),
    },
    "research_generate": {
        "label": "Structure Research Claims",
        "stage": "06",
        "command": [
            sys.executable,
            "research_engine/research_model_runner.py",
            "--mode",
            "batch",
        ],
        "description": (
            "Uses FAIR free-only routing to structure claims strictly from acquired page evidence."
        ),
    },
    "research_gate_prepare": {
        "label": "Prepare Research Gate",
        "stage": "06",
        "command": [
            sys.executable,
            "research_engine/research_review.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Prepares the compact human claim-by-claim Research Gate before Script."
        ),
    },
    "script_prepare": {
        "label": "Prepare Script Requests",
        "stage": "07",
        "command": [
            sys.executable,
            "story_script_engine/story_script_engine.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Builds script requests from human-verified research and the approved package promise."
        ),
    },
    "script_generate": {
        "label": "Generate Script Drafts",
        "stage": "07",
        "command": [
            sys.executable,
            "story_script_engine/script_model_runner.py",
            "--mode",
            "batch",
        ],
        "description": (
            "Uses FAIR free-only routing to draft original scripts constrained to accepted claim IDs."
        ),
    },
    "script_gate_prepare": {
        "label": "Prepare Script Gate",
        "stage": "07",
        "command": [
            sys.executable,
            "story_script_engine/script_review.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Prepares the human Script Gate before production."
        ),
    },
}

OPEN_TARGETS = {
    "experiment_01_output": EXP1_OUTPUT,
    "experiment_02_output": EXP2_OUTPUT,
    "transformation_output": TRANSFORM_OUTPUT,
    "packaging_output": PACKAGING_OUTPUT,
    "research_output": RESEARCH_OUTPUT,
    "story_script_output": STORY_OUTPUT,
    "source_acquisition_output": SOURCE_ACQ_OUTPUT,
    "ui_jobs": JOB_LOG_DIR,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def json_file_status(path: Path, key: str | None = None) -> Any:
    payload = safe_load_json(path)
    if key is None:
        return payload
    return payload.get(key) if isinstance(payload, dict) else None


def has_json_files(path: Path) -> bool:
    return path.exists() and any(path.glob("*.json"))


def checkpoint_status() -> str | None:
    payload = safe_load_json(EXP13_CHECKPOINT)
    if isinstance(payload, dict):
        value = payload.get("status")
        return str(value) if value is not None else "CHECKPOINTED"
    return None


def exp13_valid_velocity_samples() -> int:
    payload = safe_load_json(EXP13_DIR / "summary.json")
    if not isinstance(payload, dict):
        return 0
    velocity = payload.get("velocity_analysis", {})
    if not isinstance(velocity, dict):
        return 0
    try:
        return int(velocity.get("valid_velocity_samples") or 0)
    except (TypeError, ValueError):
        return 0


def exp13_cohort_readiness() -> dict[str, Any]:
    manifest = safe_load_json(EXP13_DIR / "cohort_manifest.json")
    config = safe_load_json(EXP13_CONFIG)
    if not isinstance(manifest, dict):
        return {
            "frozen_size": 0,
            "required_unique_channels": 3,
            "ready_cell_count": 0,
            "max_unique_channels_in_cell": 0,
            "sufficient": False,
        }

    required = 3
    if isinstance(config, dict):
        try:
            required = int(
                config.get(
                    "minimum_unique_channels_per_topic_format",
                    3,
                )
            )
        except (TypeError, ValueError):
            required = 3

    cells: dict[tuple[str, str], set[str]] = {}
    for candidate in manifest.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        channel_id = str(candidate.get("channel_id") or "").strip()
        fmt = str(candidate.get("format_candidate") or "").strip()
        if not channel_id or not fmt:
            continue
        for topic in candidate.get("validated_topics", []):
            key = (str(topic), fmt)
            cells.setdefault(key, set()).add(channel_id)

    counts = [len(channels) for channels in cells.values()]
    ready_count = sum(count >= required for count in counts)
    frozen_size = len(manifest.get("video_ids", []))

    return {
        "frozen_size": frozen_size,
        "required_unique_channels": required,
        "ready_cell_count": ready_count,
        "max_unique_channels_in_cell": max(counts, default=0),
        "sufficient": ready_count > 0,
    }


def exp13_depth_ready_cell_count() -> int:
    topic_velocity = safe_load_json(EXP13_DIR / "topic_velocity.json")
    config = safe_load_json(EXP14_CONFIG)
    if not isinstance(topic_velocity, dict):
        return 0

    minimum_channels = 3
    minimum_velocity = 3
    if isinstance(config, dict):
        try:
            minimum_channels = int(
                config.get("minimum_unique_channels", 3)
            )
        except (TypeError, ValueError):
            minimum_channels = 3
        try:
            minimum_velocity = int(
                config.get("minimum_velocity_samples", 3)
            )
        except (TypeError, ValueError):
            minimum_velocity = 3

    ready = 0
    topics = topic_velocity.get("topics", {})
    if not isinstance(topics, dict):
        return 0

    for topic in topics.values():
        if not isinstance(topic, dict):
            continue
        by_format = topic.get("by_format", {})
        if not isinstance(by_format, dict):
            continue
        for cell in by_format.values():
            if not isinstance(cell, dict):
                continue
            try:
                channels = int(cell.get("unique_channels") or 0)
                samples = int(cell.get("velocity_sample_count") or 0)
            except (TypeError, ValueError):
                continue
            if (
                channels >= minimum_channels
                and samples >= minimum_velocity
                and cell.get("age_matched_velocity_index") is not None
            ):
                ready += 1

    return ready


def exp14_plan_status() -> str | None:
    return json_file_status(EXP14_DIR / "expansion_plan.json", "status")


def exp14_execution_status() -> str | None:
    return json_file_status(EXP14_DIR / "summary.json", "execution_status")


def exp15_status() -> str | None:
    return json_file_status(EXP15_DIR / "summary.json", "status")


def exp2_status() -> str | None:
    return json_file_status(EXP2_OUTPUT / "summary.json", "status")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_stems(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        item.stem
        for item in path.glob("*.json")
        if item.is_file()
    }


def suffixed_json_ids(path: Path, suffix: str) -> set[str]:
    if not path.exists():
        return set()
    ids: set[str] = set()
    for item in path.glob(f"*{suffix}"):
        name = item.name
        if name.endswith(suffix):
            ids.add(name[: -len(suffix)])
    return ids


def enriched_transcript_ready_ids() -> set[str]:
    ready: set[str] = set()
    if not EXP2_ENRICHED_DIR.exists():
        return ready

    for path in EXP2_ENRICHED_DIR.glob("*.json"):
        payload = safe_load_json(path)
        if not isinstance(payload, dict):
            continue
        source_inputs = payload.get("source_inputs", {})
        transcript = (
            source_inputs.get("transcript", {})
            if isinstance(source_inputs, dict)
            else {}
        )
        if (
            not isinstance(transcript, dict)
            or transcript.get("status") != "PROVIDED"
        ):
            continue
        evidence = payload.get("evidence", [])
        if not isinstance(evidence, list):
            continue
        if any(
            isinstance(item, dict)
            and item.get("type") == "transcript"
            for item in evidence
        ):
            ready.add(path.stem)
    return ready


def current_visual_report_ids(prepared_ids: set[str]) -> set[str]:
    attempted: set[str] = set()
    root = SOURCE_ACQ_OUTPUT / "experiment_02"
    for video_id in prepared_ids:
        report_path = root / video_id / "visual_analysis.json"
        prepared_path = EXP2_PREPARED_DIR / f"{video_id}.json"
        report = safe_load_json(report_path)
        if (
            prepared_path.exists()
            and isinstance(report, dict)
            and report.get("profile_sha256") == sha256_file(prepared_path)
        ):
            attempted.add(video_id)
    return attempted


def current_visual_ready_ids(prepared_ids: set[str]) -> set[str]:
    ready: set[str] = set()
    root = SOURCE_ACQ_OUTPUT / "experiment_02"
    for video_id in prepared_ids:
        report_path = root / video_id / "visual_analysis.json"
        prepared_path = EXP2_PREPARED_DIR / f"{video_id}.json"
        enriched_path = EXP2_ENRICHED_DIR / f"{video_id}.json"
        report = safe_load_json(report_path)
        enriched = safe_load_json(enriched_path)
        if (
            not prepared_path.exists()
            or not isinstance(report, dict)
            or not isinstance(enriched, dict)
        ):
            continue
        timing_present = any(
            isinstance(item, dict)
            and item.get("evidence_id") == "timing.scene_change_summary"
            and item.get("type") == "timing_note"
            for item in enriched.get("evidence", [])
        )
        if (
            timing_present
            and report.get("status") in {"READY", "READY_NO_OPENING_FRAME"}
            and report.get("profile_sha256") == sha256_file(prepared_path)
        ):
            ready.add(video_id)
    return ready


def exp2_artifact_state() -> dict[str, Any]:
    prepared_ids = json_stems(EXP2_PREPARED_DIR)
    enriched_ids = enriched_transcript_ready_ids()
    visual_report_ids = current_visual_report_ids(prepared_ids)
    visual_ready_ids = current_visual_ready_ids(prepared_ids)
    request_ids: set[str] = set()
    if EXP2_REQUESTS_DIR.exists():
        for request_path in EXP2_REQUESTS_DIR.glob("*.analysis_request.json"):
            video_id = request_path.name[: -len(".analysis_request.json")]
            enriched_path = EXP2_ENRICHED_DIR / f"{video_id}.json"
            request = safe_load_json(request_path)
            if (
                not enriched_path.exists()
                or not isinstance(request, dict)
            ):
                continue
            provenance = request.get("request_provenance", {})
            if (
                isinstance(provenance, dict)
                and provenance.get("profile_sha256")
                == sha256_file(enriched_path)
            ):
                request_ids.add(video_id)
    analyzed_ids: set[str] = set()
    for video_id in request_ids:
        analyzed_path = EXP2_ANALYZED_DIR / f"{video_id}.json"
        request_path = EXP2_REQUESTS_DIR / f"{video_id}.analysis_request.json"
        report_path = EXP2_MODEL_RUNS_DIR / f"{video_id}.model_run.json"
        report = safe_load_json(report_path)
        if (
            analyzed_path.exists()
            and request_path.exists()
            and isinstance(report, dict)
            and report.get("status") == "APPLIED"
            and report.get("request_sha256") == sha256_file(request_path)
        ):
            analyzed_ids.add(video_id)

    review_request_ids: set[str] = set()
    if EXP2_REVIEW_REQUESTS_DIR.exists():
        for request_path in EXP2_REVIEW_REQUESTS_DIR.glob(
            "*.review_request.json"
        ):
            video_id = request_path.name[: -len(".review_request.json")]
            analyzed_path = EXP2_ANALYZED_DIR / f"{video_id}.json"
            request = safe_load_json(request_path)
            if (
                not analyzed_path.exists()
                or not isinstance(request, dict)
            ):
                continue
            provenance = request.get("request_provenance", {})
            if (
                isinstance(provenance, dict)
                and provenance.get("profile_sha256")
                == sha256_file(analyzed_path)
            ):
                review_request_ids.add(video_id)

    reviewed_ids: set[str] = set()
    for video_id in analyzed_ids:
        analyzed_path = EXP2_ANALYZED_DIR / f"{video_id}.json"
        request_path = EXP2_REVIEW_REQUESTS_DIR / f"{video_id}.review_request.json"
        reviewed_path = EXP2_REVIEWED_DIR / f"{video_id}.json"
        report_path = (
            EXP2_OUTPUT / "human_review_reports"
            / f"{video_id}.human_review.json"
        )
        report = safe_load_json(report_path)
        if (
            analyzed_path.exists()
            and request_path.exists()
            and reviewed_path.exists()
            and isinstance(report, dict)
            and report.get("status") == "REVIEW_COMPLETED"
            and report.get("profile_sha256") == sha256_file(analyzed_path)
            and report.get("request_sha256") == sha256_file(request_path)
        ):
            reviewed_ids.add(video_id)

    evidence_complete = bool(prepared_ids) and prepared_ids.issubset(enriched_ids)
    requests_complete = evidence_complete and prepared_ids.issubset(request_ids)

    synthesis_payload = safe_load_json(EXP2_SYNTHESIS_FILE)
    current_review_hashes = {
        video_id: sha256_file(EXP2_REVIEWED_DIR / f"{video_id}.json")
        for video_id in reviewed_ids
        if (EXP2_REVIEWED_DIR / f"{video_id}.json").exists()
    }
    synthesis_provenance = (
        synthesis_payload.get("synthesis_provenance", {})
        if isinstance(synthesis_payload, dict)
        else {}
    )
    synthesis_ready = (
        bool(current_review_hashes)
        and isinstance(synthesis_provenance, dict)
        and synthesis_provenance.get("profile_sha256") == current_review_hashes
    )

    return {
        "prepared_ids": sorted(prepared_ids),
        "enriched_ready_ids": sorted(enriched_ids),
        "visual_attempted_ids": sorted(visual_report_ids),
        "visual_ready_ids": sorted(visual_ready_ids),
        "analysis_request_ids": sorted(request_ids),
        "analyzed_ids": sorted(analyzed_ids),
        "review_request_ids": sorted(review_request_ids),
        "reviewed_ids": sorted(reviewed_ids),
        "prepared_count": len(prepared_ids),
        "evidence_ready_count": len(prepared_ids.intersection(enriched_ids)),
        "visual_attempted_count": len(
            prepared_ids.intersection(visual_report_ids)
        ),
        "visual_attempted": bool(prepared_ids)
        and prepared_ids.issubset(visual_report_ids),
        "visual_ready_count": len(prepared_ids.intersection(visual_ready_ids)),
        "visual_complete": bool(prepared_ids)
        and prepared_ids.issubset(visual_ready_ids),
        "evidence_complete": evidence_complete,
        "requests_complete": requests_complete,
        "analyzed_current_count": len(prepared_ids.intersection(analyzed_ids)),
        "review_requests_current_count": len(
            prepared_ids.intersection(review_request_ids)
        ),
        "reviewed_current_count": len(prepared_ids.intersection(reviewed_ids)),
        "synthesis_ready": synthesis_ready,
        "acquisition_summary": safe_load_json(EXP2_ACQUISITION_SUMMARY),
        "visual_summary": safe_load_json(EXP2_VISUAL_SUMMARY),
    }


def transformation_artifact_state() -> dict[str, Any]:
    handoff_hash = (
        sha256_file(EXP2_SYNTHESIS_FILE)
        if EXP2_SYNTHESIS_FILE.exists()
        else None
    )
    request_hashes: dict[str, str] = {}
    if handoff_hash and TRANSFORM_REQUESTS_DIR.exists():
        for path in TRANSFORM_REQUESTS_DIR.glob("*.concept_request.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            provenance = payload.get("request_provenance", {})
            mechanism_id = str(payload.get("mechanism_id") or "").strip()
            if (
                mechanism_id
                and isinstance(provenance, dict)
                and provenance.get("handoff_sha256") == handoff_hash
            ):
                request_hashes[mechanism_id] = sha256_file(path)

    current_response_ids: set[str] = set()
    if TRANSFORM_RESPONSES_DIR.exists():
        for path in TRANSFORM_RESPONSES_DIR.glob("*.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            mechanism_id = str(payload.get("mechanism_id") or "").strip()
            provenance = payload.get("response_provenance", {})
            if (
                mechanism_id in request_hashes
                and isinstance(provenance, dict)
                and provenance.get("request_sha256")
                == request_hashes[mechanism_id]
            ):
                current_response_ids.add(mechanism_id)

    candidates = safe_load_json(TRANSFORM_CANDIDATES_FILE)
    candidate_count = (
        int(candidates.get("count") or 0)
        if isinstance(candidates, dict)
        else 0
    )
    candidate_hash = (
        sha256_file(TRANSFORM_CANDIDATES_FILE)
        if TRANSFORM_CANDIDATES_FILE.exists()
        else None
    )
    triage = safe_load_json(TRANSFORM_TRIAGE_FILE)
    triaged = safe_load_json(TRANSFORM_TRIAGED_CANDIDATES_FILE)
    triage_ready = (
        candidate_hash is not None
        and isinstance(triage, dict)
        and isinstance(triaged, dict)
        and triage.get("source_candidates_sha256") == candidate_hash
        and triaged.get("source_candidates_sha256") == candidate_hash
    )
    shortlist_count = (
        int(triaged.get("concept_count") or 0)
        if isinstance(triaged, dict)
        else 0
    )
    requests_ready = bool(request_hashes)
    responses_complete = (
        requests_ready
        and set(request_hashes).issubset(current_response_ids)
    )
    candidates_ready = responses_complete and candidate_count > 0
    gate = concept_gate_snapshot() if candidates_ready and triage_ready else {
        "status": (
            "WAITING_FOR_TRIAGED_CONCEPTS"
            if candidates_ready and not triage_ready
            else "WAITING_FOR_CONCEPT_CANDIDATES"
        ),
        "complete": False,
        "concepts": [],
    }
    research_handoff = safe_load_json(TRANSFORM_RESEARCH_HANDOFF)
    research_ready = (
        isinstance(research_handoff, dict)
        and research_handoff.get("status") == "READY_FOR_RESEARCH"
        and bool(gate.get("complete"))
    )
    return {
        "handoff_sha256": handoff_hash,
        "request_mechanism_ids": sorted(request_hashes),
        "current_response_mechanism_ids": sorted(current_response_ids),
        "requests_ready": requests_ready,
        "responses_complete": responses_complete,
        "candidate_count": candidate_count,
        "candidates_ready": candidates_ready,
        "triage_ready": triage_ready,
        "shortlist_count": shortlist_count,
        "concept_triage": triage if isinstance(triage, dict) else {},
        "concept_gate": gate,
        "concept_gate_complete": bool(gate.get("complete")),
        "research_ready": research_ready,
    }


def packaging_artifact_state() -> dict[str, Any]:
    upstream = transformation_artifact_state()
    handoff_hash = (
        sha256_file(TRANSFORM_RESEARCH_HANDOFF)
        if upstream.get("research_ready") and TRANSFORM_RESEARCH_HANDOFF.exists()
        else None
    )
    request_hashes: dict[str, str] = {}
    if handoff_hash and PACKAGING_REQUESTS_DIR.exists():
        for path in PACKAGING_REQUESTS_DIR.glob("*.package_request.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            provenance = payload.get("request_provenance", {})
            concept_id = str(payload.get("concept_id") or "").strip()
            if (
                concept_id
                and isinstance(provenance, dict)
                and provenance.get("concept_handoff_sha256") == handoff_hash
            ):
                request_hashes[concept_id] = sha256_file(path)

    current_response_ids: set[str] = set()
    if PACKAGING_RESPONSES_DIR.exists():
        for path in PACKAGING_RESPONSES_DIR.glob("*.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            provenance = payload.get("response_provenance", {})
            if (
                concept_id in request_hashes
                and isinstance(provenance, dict)
                and provenance.get("request_sha256") == request_hashes[concept_id]
            ):
                current_response_ids.add(concept_id)

    candidates = safe_load_json(PACKAGING_CANDIDATES_FILE)
    candidate_count = (
        int(candidates.get("count") or 0)
        if isinstance(candidates, dict)
        else 0
    )
    requests_ready = bool(request_hashes)
    responses_complete = (
        requests_ready
        and set(request_hashes).issubset(current_response_ids)
    )
    candidates_ready = responses_complete and candidate_count > 0
    gate = packaging_gate_snapshot() if candidates_ready else {
        "status": "WAITING_FOR_PACKAGE_CANDIDATES",
        "complete": False,
        "packages": [],
    }
    research_handoff = safe_load_json(PACKAGING_RESEARCH_HANDOFF)
    research_ready = (
        isinstance(research_handoff, dict)
        and research_handoff.get("status") == "READY_FOR_RESEARCH"
        and bool(gate.get("complete"))
    )
    return {
        "handoff_sha256": handoff_hash,
        "request_concept_ids": sorted(request_hashes),
        "current_response_concept_ids": sorted(current_response_ids),
        "requests_ready": requests_ready,
        "responses_complete": responses_complete,
        "candidate_count": candidate_count,
        "candidates_ready": candidates_ready,
        "packaging_gate": gate,
        "packaging_gate_complete": bool(gate.get("complete")),
        "research_ready": research_ready,
    }


def research_artifact_state() -> dict[str, Any]:
    upstream = packaging_artifact_state()
    packaging_handoff_hash = (
        sha256_file(PACKAGING_RESEARCH_HANDOFF)
        if upstream.get("research_ready") and PACKAGING_RESEARCH_HANDOFF.exists()
        else None
    )
    plan_hashes: dict[str, str] = {}
    if packaging_handoff_hash and RESEARCH_PLANS_DIR.exists():
        for path in RESEARCH_PLANS_DIR.glob("*.research_plan.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            provenance = payload.get("plan_provenance", {})
            concept_id = str(payload.get("concept_id") or "").strip()
            if (
                concept_id
                and isinstance(provenance, dict)
                and provenance.get("packaging_handoff_sha256")
                == packaging_handoff_hash
            ):
                plan_hashes[concept_id] = sha256_file(path)

    evidence_hashes: dict[str, str] = {}
    if RESEARCH_EVIDENCE_DIR.exists():
        for path in RESEARCH_EVIDENCE_DIR.glob("*.research_evidence.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            provenance = payload.get("provenance", {})
            if (
                concept_id in plan_hashes
                and isinstance(provenance, dict)
                and provenance.get("plan_sha256") == plan_hashes[concept_id]
                and payload.get("pages")
            ):
                evidence_hashes[concept_id] = sha256_file(path)

    response_hashes: dict[str, str] = {}
    if RESEARCH_RESPONSES_DIR.exists():
        for path in RESEARCH_RESPONSES_DIR.glob("*.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            provenance = payload.get("response_provenance", {})
            if (
                concept_id in plan_hashes
                and concept_id in evidence_hashes
                and isinstance(provenance, dict)
                and provenance.get("plan_sha256") == plan_hashes[concept_id]
                and provenance.get("evidence_sha256") == evidence_hashes[concept_id]
            ):
                response_hashes[concept_id] = sha256_file(path)

    current_drafts: set[str] = set()
    if RESEARCH_DRAFTS_DIR.exists():
        for path in RESEARCH_DRAFTS_DIR.glob("*.draft_research_package.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            provenance = payload.get("draft_provenance", {})
            if (
                concept_id in plan_hashes
                and concept_id in response_hashes
                and isinstance(provenance, dict)
                and provenance.get("plan_sha256") == plan_hashes[concept_id]
                and provenance.get("response_sha256") == response_hashes[concept_id]
            ):
                current_drafts.add(concept_id)

    plans_ready = bool(plan_hashes)
    evidence_complete = plans_ready and set(plan_hashes).issubset(evidence_hashes)
    responses_complete = plans_ready and set(plan_hashes).issubset(response_hashes)
    drafts_ready = responses_complete and set(plan_hashes).issubset(current_drafts)
    gate = research_gate_snapshot() if drafts_ready else {
        "status": "WAITING_FOR_DRAFT_RESEARCH_PACKAGES",
        "complete": False,
        "claims": [],
    }
    verified = gate.get("verified_packages", []) if isinstance(gate, dict) else []
    story_ready = (
        bool(gate.get("complete"))
        and bool(verified)
        and all(
            isinstance(item, dict)
            and item.get("status") == "READY_FOR_STORY_SCRIPT"
            for item in verified
        )
    )
    return {
        "packaging_handoff_sha256": packaging_handoff_hash,
        "plan_concept_ids": sorted(plan_hashes),
        "evidence_concept_ids": sorted(evidence_hashes),
        "response_concept_ids": sorted(response_hashes),
        "draft_concept_ids": sorted(current_drafts),
        "plans_ready": plans_ready,
        "evidence_complete": evidence_complete,
        "responses_complete": responses_complete,
        "drafts_ready": drafts_ready,
        "research_gate": gate,
        "research_gate_complete": bool(gate.get("complete")),
        "story_ready": story_ready,
    }


def story_script_artifact_state() -> dict[str, Any]:
    upstream = research_artifact_state()
    verified_hashes: dict[str, str] = {}
    if upstream.get("story_ready") and RESEARCH_VERIFIED_DIR.exists():
        for path in RESEARCH_VERIFIED_DIR.glob("*.verified_research_package.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict) or payload.get("status") != "READY_FOR_STORY_SCRIPT":
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            if concept_id:
                verified_hashes[concept_id] = sha256_file(path)

    request_hashes: dict[str, str] = {}
    if SCRIPT_REQUESTS_DIR.exists():
        for path in SCRIPT_REQUESTS_DIR.glob("*.script_request.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            provenance = payload.get("request_provenance", {})
            if (
                concept_id in verified_hashes
                and isinstance(provenance, dict)
                and provenance.get("verified_research_sha256") == verified_hashes[concept_id]
            ):
                request_hashes[concept_id] = sha256_file(path)

    draft_ids: set[str] = set()
    if SCRIPT_DRAFTS_DIR.exists():
        for path in SCRIPT_DRAFTS_DIR.glob("*.script_draft.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            provenance = payload.get("draft_provenance", {})
            if (
                concept_id in request_hashes
                and isinstance(provenance, dict)
                and provenance.get("request_sha256") == request_hashes[concept_id]
            ):
                draft_ids.add(concept_id)

    gate = script_gate_snapshot() if draft_ids else {
        "status": "WAITING_FOR_SCRIPT_DRAFTS",
        "complete": False,
        "scripts": [],
    }
    approved_ids = {
        str(item.get("concept_id"))
        for item in gate.get("scripts", [])
        if isinstance(item, dict) and item.get("decision") == "ACCEPT"
    }

    requests_ready = bool(verified_hashes) and set(verified_hashes).issubset(request_hashes)
    drafts_ready = requests_ready and set(verified_hashes).issubset(draft_ids)
    production_ready = drafts_ready and bool(gate.get("complete")) and set(verified_hashes).issubset(approved_ids)
    return {
        "verified_concept_ids": sorted(verified_hashes),
        "request_concept_ids": sorted(request_hashes),
        "draft_concept_ids": sorted(draft_ids),
        "requests_ready": requests_ready,
        "drafts_ready": drafts_ready,
        "script_gate": gate,
        "script_gate_complete": bool(gate.get("complete")),
        "production_ready": production_ready,
    }


def current_action_id() -> str | None:
    manager = globals().get("JOB_MANAGER")
    if manager is None:
        return None
    job = manager.current()
    if not job:
        return None
    if job.get("status") not in {"RUNNING", "STOPPING"}:
        return None
    value = job.get("action_id")
    return str(value) if value else None


def stage_statuses() -> list[dict[str, Any]]:
    exp13_manifest = EXP13_DIR / "cohort_manifest.json"
    exp13_summary = EXP13_DIR / "summary.json"
    exp13_topic = EXP13_DIR / "topic_velocity.json"

    cohort_files_ready = (
        exp13_manifest.exists()
        and exp13_summary.exists()
        and exp13_topic.exists()
    )
    cohort_info = exp13_cohort_readiness()
    cohort_sufficient = (
        cohort_files_ready
        and bool(cohort_info["sufficient"])
    )
    depth_ready_cells = exp13_depth_ready_cell_count()
    velocity_ready = cohort_sufficient and depth_ready_cells > 0
    cp_status = checkpoint_status()
    active_action = current_action_id()

    if velocity_ready:
        exp13_state = "VELOCITY_READY"
        exp13_human = "STAGE COMPLETE"
        exp13_tone = "complete"
        exp13_detail = (
            f"{depth_ready_cells} topic/format cell(s) have enough "
            "independent channels and measured velocity for 01.4."
        )
        exp13_next = "Proceed to Experiment 01.4."
    elif active_action == "exp13_refresh":
        exp13_state = "REFRESH_RUNNING"
        exp13_human = "VELOCITY REFRESH RUNNING"
        exp13_tone = "running"
        exp13_detail = "The frozen cohort is being measured for current velocity."
        exp13_next = "Wait for the refresh job to finish."
    elif active_action in {"exp13_discover", "exp13_restart"}:
        exp13_state = "DISCOVERY_RUNNING"
        exp13_human = "DISCOVERY RUNNING"
        exp13_tone = "running"
        exp13_detail = "Candidate discovery is running. The cohort is not finished yet."
        exp13_next = "Wait for discovery to finish."
    elif cohort_files_ready and not cohort_sufficient:
        exp13_state = "INSUFFICIENT_COHORT"
        exp13_human = "INSUFFICIENT COHORT — RERUN DISCOVERY"
        exp13_tone = "action"
        exp13_detail = (
            f"Frozen cohort has {cohort_info['frozen_size']} video(s). "
            f"No topic/format cell reached the required "
            f"{cohort_info['required_unique_channels']} independent channels."
        )
        exp13_next = (
            "Run / Resume 01.3 Auto Discovery again. "
            "Do not wait for a velocity refresh."
        )
    elif cohort_sufficient:
        exp13_state = "COHORT_FROZEN_AWAITING_REFRESH"
        exp13_human = "COHORT READY — VELOCITY NEEDED"
        exp13_tone = "action"
        exp13_detail = (
            f"The cohort has {cohort_info['ready_cell_count']} topic/format "
            "cell(s) with enough independent channels."
        )
        exp13_next = (
            "Run Refresh 01.3 Frozen Cohort. If an older snapshot exists, "
            "velocity can be calculated immediately."
        )
    elif EXP13_CHECKPOINT.exists():
        exp13_state = cp_status or "CHECKPOINTED"
        exp13_human = "DISCOVERY NEEDS RESUME"
        exp13_tone = "action"
        exp13_detail = "A discovery checkpoint exists, but no frozen cohort exists yet."
        exp13_next = "Run / Resume 01.3 Auto Discovery."
    else:
        exp13_state = "READY_TO_RUN"
        exp13_human = "READY TO START"
        exp13_tone = "ready"
        exp13_detail = "No corrected 01.3 cohort has been created yet."
        exp13_next = "Run / Resume 01.3 Auto Discovery."

    plan_status = exp14_plan_status()
    execution_status = exp14_execution_status()
    handoff_status = exp15_status()
    analysis_status = exp2_status()

    plan_ready = plan_status == "READY" or execution_status == "COMPLETE"
    exp14_complete = execution_status == "COMPLETE"

    if exp14_complete:
        exp14_human = "STAGE COMPLETE"
        exp14_tone = "complete"
        exp14_next = "Proceed to Experiment 01.5."
    elif active_action == "exp14_execute":
        exp14_human = "EXPANSION RUNNING"
        exp14_tone = "running"
        exp14_next = "Wait for expansion execution to finish."
    elif active_action == "exp14_plan":
        exp14_human = "BUILDING PLAN"
        exp14_tone = "running"
        exp14_next = "Wait for the expansion plan to finish."
    elif not velocity_ready:
        exp14_human = "WAITING FOR 01.3"
        exp14_tone = "blocked"
        exp14_next = "Complete Experiment 01.3 first."
    elif plan_ready:
        exp14_human = "PLAN READY — RUN EXPANSION"
        exp14_tone = "action"
        exp14_next = "Run Execute 01.4 Expansion."
    else:
        exp14_human = "READY TO PLAN"
        exp14_tone = "ready"
        exp14_next = "Run Build 01.4 Expansion Plan."

    study_set_ready = (EXP15_DIR / "study_set.json").exists()
    gate = opportunity_gate_snapshot()
    human_gate_ready = bool(gate.get("ready_for_experiment_02"))
    human_gate_complete = bool(gate.get("gate_complete"))
    human_gate_status = str(gate.get("status") or "WAITING_FOR_01_5")

    if human_gate_ready:
        exp15_human = "HUMAN APPROVED — STAGE COMPLETE"
        exp15_tone = "complete"
        exp15_next = "Proceed to Experiment 02."
    elif study_set_ready and human_gate_complete:
        exp15_human = "TOPIC NOT APPROVED"
        exp15_tone = "action"
        exp15_next = "Change the opportunity decision or return to discovery."
    elif study_set_ready:
        exp15_human = "AWAITING HUMAN OPPORTUNITY GATE"
        exp15_tone = "action"
        exp15_next = "Review the topic and selected videos below."
    elif active_action == "exp15_build":
        exp15_human = "BUILDING HANDOFF"
        exp15_tone = "running"
        exp15_next = "Wait for the opportunity handoff to finish."
    elif not exp14_complete:
        exp15_human = "WAITING FOR 01.4"
        exp15_tone = "blocked"
        exp15_next = "Complete Experiment 01.4 first."
    else:
        exp15_human = "READY TO BUILD"
        exp15_tone = "ready"
        exp15_next = "Run Build 01.5 Opportunity Handoff."

    exp2_artifacts = exp2_artifact_state()
    profiles_prepared = exp2_artifacts["prepared_count"] > 0
    evidence_ready = bool(exp2_artifacts["evidence_complete"])
    visual_ready = bool(exp2_artifacts["visual_complete"])
    visual_attempted = bool(exp2_artifacts["visual_attempted"])
    vision_review = vision_review_snapshot()
    vision_complete = bool(vision_review.get("complete"))
    visual_available = (
        shutil.which("yt-dlp") is not None
        and shutil.which("ffmpeg") is not None
    )
    visual_satisfied = (
        visual_ready
        or visual_attempted
        or not visual_available
    )
    vision_satisfied = (not visual_ready) or vision_complete
    synthesis_ready = bool(exp2_artifacts["synthesis_ready"])
    analyzed_count = exp2_artifacts["analyzed_current_count"]
    request_count = len(exp2_artifacts["analysis_request_ids"])
    reviewed_count = exp2_artifacts["reviewed_current_count"]
    analyzed = analyzed_count > 0
    analysis_complete = request_count > 0 and analyzed_count == request_count
    reviewed = reviewed_count > 0
    review_complete = request_count > 0 and reviewed_count == request_count

    if synthesis_ready:
        exp2_human = "STAGE COMPLETE"
        exp2_tone = "complete"
        exp2_next = "Proceed to the Transformation Engine."
    elif active_action == "synthesis_build":
        exp2_human = "BUILDING SYNTHESIS"
        exp2_tone = "running"
        exp2_next = "Wait for synthesis to finish."
    elif active_action in {
        "exp2_prepare",
        "exp2_acquire",
        "exp2_visual",
        "exp2_vision_prepare",
        "analysis_batch_prepare",
        "analysis_model_one",
        "analysis_model_remaining",
        "human_review_prepare",
    }:
        exp2_human = "ANALYSIS RUNNING"
        exp2_tone = "running"
        exp2_next = "Wait for the current Experiment 02 job to finish."
    elif not study_set_ready:
        exp2_human = "WAITING FOR 01.5"
        exp2_tone = "blocked"
        exp2_next = "Complete Experiment 01.5 first."
    elif not human_gate_ready:
        exp2_human = "WAITING FOR HUMAN OPPORTUNITY GATE"
        exp2_tone = "blocked"
        exp2_next = "Approve at least one opportunity before Experiment 02."
    elif not profiles_prepared:
        exp2_human = "READY TO PREPARE"
        exp2_tone = "ready"
        exp2_next = "Run Prepare Experiment 02 Profiles."
    elif not evidence_ready:
        exp2_human = "SOURCE EVIDENCE NEEDED"
        exp2_tone = "action"
        exp2_next = "Run Acquire Source Evidence."
    elif not visual_satisfied:
        exp2_human = "VISUAL STRUCTURE NEEDED"
        exp2_tone = "action"
        exp2_next = "Run Acquire Visual Structure."
    elif not vision_satisfied:
        if vision_review.get("awaiting_human_review"):
            exp2_human = "VISUAL REVIEW NEEDED"
            exp2_tone = "action"
            exp2_next = "Review the retained visual frames in Analyze & Create."
        else:
            exp2_human = "PREPARE VISUAL REVIEW"
            exp2_tone = "action"
            exp2_next = "Run Prepare Visual Review."
    elif reviewed and review_complete:
        exp2_human = "SYNTHESIS NEEDED"
        exp2_tone = "action"
        exp2_next = "Run Build Experiment 02 Synthesis."
    elif analysis_complete:
        exp2_human = "HUMAN REVIEW NEEDED"
        exp2_tone = "action"
        exp2_next = "Prepare and complete Human Review for all analyzed videos."
    elif analyzed:
        exp2_human = "MORE ANALYSIS NEEDED"
        exp2_tone = "action"
        exp2_next = "Run Remaining Analyses."
    else:
        exp2_human = "EVIDENCE READY — ANALYSIS NEEDED"
        exp2_tone = "action"
        exp2_next = "Run Prepare Analysis Requests."

    transform = transformation_artifact_state()
    transform_requests = bool(transform["requests_ready"])
    transform_candidates = bool(transform["candidates_ready"])
    transform_triage = bool(transform["triage_ready"])
    concept_gate = transform["concept_gate"]
    concept_gate_status = str(
        concept_gate.get("status") or "WAITING_FOR_CONCEPT_CANDIDATES"
    )
    concept_gate_complete = bool(transform["concept_gate_complete"])
    research_ready = bool(transform["research_ready"])

    packaging = packaging_artifact_state()
    package_requests = bool(packaging["requests_ready"])
    package_candidates = bool(packaging["candidates_ready"])
    packaging_gate = packaging["packaging_gate"]
    packaging_gate_status = str(
        packaging_gate.get("status") or "WAITING_FOR_PACKAGE_CANDIDATES"
    )
    packaging_gate_complete = bool(packaging["packaging_gate_complete"])
    packaging_research_ready = bool(packaging["research_ready"])
    research = research_artifact_state()
    research_plans = bool(research["plans_ready"])
    research_evidence = bool(research["evidence_complete"])
    research_drafts = bool(research["drafts_ready"])
    research_gate = research["research_gate"]
    research_gate_status = str(
        research_gate.get("status") or "WAITING_FOR_DRAFT_RESEARCH_PACKAGES"
    )
    research_gate_complete = bool(research["research_gate_complete"])
    story_ready = bool(research["story_ready"])

    if research_ready:
        transform_human = "CONCEPT ACCEPTED — STAGE COMPLETE"
        transform_tone = "complete"
        transform_next = "Proceed to Packaging / Research."
    elif active_action in {
        "transform_prepare",
        "concept_generate",
        "concept_triage",
        "concept_gate_prepare",
    }:
        transform_human = "CONCEPT WORK RUNNING"
        transform_tone = "running"
        transform_next = "Wait for the current Transformation job to finish."
    elif not synthesis_ready:
        transform_human = "WAITING FOR EXPERIMENT 02"
        transform_tone = "blocked"
        transform_next = "Complete Experiment 02 synthesis first."
    elif not transform_requests:
        transform_human = "READY TO PREPARE CONCEPTS"
        transform_tone = "ready"
        transform_next = "Run Prepare Concept Requests."
    elif not transform_candidates:
        transform_human = "CONCEPT GENERATION NEEDED"
        transform_tone = "action"
        transform_next = "Run Generate Concept Candidates."
    elif not transform_triage:
        transform_human = "LLM CONCEPT TRIAGE NEEDED"
        transform_tone = "action"
        transform_next = "Run Triage Concept Candidates."
    elif concept_gate_status == "READY_TO_PREPARE":
        transform_human = "PREPARE CONCEPT GATE"
        transform_tone = "action"
        transform_next = "Run Prepare Concept Gate."
    elif concept_gate_status == "AWAITING_HUMAN_DECISION":
        transform_human = "HUMAN CONCEPT DECISION NEEDED"
        transform_tone = "action"
        transform_next = "Review concept candidates in Analyze & Create."
    elif concept_gate_complete:
        transform_human = "NO ACCEPTED CONCEPT"
        transform_tone = "action"
        transform_next = "Rework or regenerate concepts before research."
    else:
        transform_human = "CONCEPT WORK NEEDS ATTENTION"
        transform_tone = "action"
        transform_next = "Inspect the Concept Gate state."

    if packaging_research_ready:
        package_human = "PACKAGE ACCEPTED — STAGE COMPLETE"
        package_tone = "complete"
        package_next = "Proceed to Research."
    elif active_action in {
        "package_prepare",
        "package_generate",
        "package_gate_prepare",
    }:
        package_human = "PACKAGING WORK RUNNING"
        package_tone = "running"
        package_next = "Wait for the current Packaging job to finish."
    elif not research_ready:
        package_human = "WAITING FOR ACCEPTED CONCEPT"
        package_tone = "blocked"
        package_next = "Accept a concept first."
    elif not package_requests:
        package_human = "READY TO PREPARE PACKAGES"
        package_tone = "ready"
        package_next = "Run Prepare Package Requests."
    elif not package_candidates:
        package_human = "PACKAGE GENERATION NEEDED"
        package_tone = "action"
        package_next = "Run Generate Package Candidates."
    elif packaging_gate_status == "READY_TO_PREPARE":
        package_human = "PREPARE PACKAGING GATE"
        package_tone = "action"
        package_next = "Run Prepare Packaging Gate."
    elif packaging_gate_status == "AWAITING_HUMAN_DECISION":
        package_human = "HUMAN PACKAGE DECISION NEEDED"
        package_tone = "action"
        package_next = "Review package candidates in Analyze & Create."
    elif packaging_gate_complete:
        package_human = "NO APPROVED PACKAGE"
        package_tone = "action"
        package_next = "Rework or regenerate packages before research."
    else:
        package_human = "PACKAGING NEEDS ATTENTION"
        package_tone = "action"
        package_next = "Inspect the Packaging Gate state."

    if story_ready:
        research_human = "RESEARCH APPROVED — STAGE COMPLETE"
        research_tone = "complete"
        research_next = "Proceed to Story / Script."
    elif active_action in {
        "research_prepare",
        "research_acquire",
        "research_generate",
        "research_gate_prepare",
    }:
        research_human = "RESEARCH WORK RUNNING"
        research_tone = "running"
        research_next = "Wait for the current Research job to finish."
    elif not packaging_research_ready:
        research_human = "WAITING FOR APPROVED PACKAGE"
        research_tone = "blocked"
        research_next = "Approve a package first."
    elif not research_plans:
        research_human = "READY TO PREPARE RESEARCH"
        research_tone = "ready"
        research_next = "Run Prepare Research Plans."
    elif not research_evidence:
        research_human = "WEB EVIDENCE NEEDED"
        research_tone = "action"
        research_next = "Run Acquire Research Evidence."
    elif not research_drafts:
        research_human = "CLAIM STRUCTURING NEEDED"
        research_tone = "action"
        research_next = "Run Structure Research Claims."
    elif research_gate_status == "READY_TO_PREPARE":
        research_human = "PREPARE RESEARCH GATE"
        research_tone = "action"
        research_next = "Run Prepare Research Gate."
    elif research_gate_status == "AWAITING_HUMAN_DECISION":
        research_human = "HUMAN RESEARCH DECISION NEEDED"
        research_tone = "action"
        research_next = "Review claims in Analyze & Create."
    elif research_gate_complete:
        research_human = "RESEARCH INCOMPLETE"
        research_tone = "action"
        research_next = "Rework unresolved research before Script."
    else:
        research_human = "RESEARCH NEEDS ATTENTION"
        research_tone = "action"
        research_next = "Inspect the Research Gate state."

    return [
        {
            "id": "01.3",
            "title": "Age-Matched Velocity",
            "state": exp13_state,
            "human_status": exp13_human,
            "tone": exp13_tone,
            "detail": exp13_detail,
            "next_action": exp13_next,
            "criteria": [
                {
                    "label": "Candidate discovery and validation finished",
                    "done": cohort_files_ready,
                },
                {
                    "label": "At least one cell has enough independent channels",
                    "done": cohort_sufficient,
                },
                {
                    "label": "Velocity evidence is ready for 01.4",
                    "done": velocity_ready,
                },
            ],
            "complete": velocity_ready,
            "ready": True,
            "current": not velocity_ready,
        },
        {
            "id": "01.4",
            "title": "Depth Expansion",
            "state": execution_status
            or plan_status
            or ("READY_TO_PLAN" if velocity_ready else "WAITING_FOR_01_3"),
            "human_status": exp14_human,
            "tone": exp14_tone,
            "detail": (
                "Depth-expansion plan and execution must both finish."
                if velocity_ready
                else "Measured 01.3 velocity evidence is required first."
            ),
            "next_action": exp14_next,
            "criteria": [
                {
                    "label": "Expansion plan ready",
                    "done": plan_ready,
                },
                {
                    "label": "Expansion executed",
                    "done": exp14_complete,
                },
            ],
            "complete": exp14_complete,
            "ready": velocity_ready,
            "current": velocity_ready and not exp14_complete,
        },
        {
            "id": "01.5",
            "title": "Opportunity Handoff",
            "state": (
                human_gate_status
                if study_set_ready
                else handoff_status
                or (
                    "READY_TO_BUILD"
                    if exp14_complete
                    else "WAITING_FOR_01_4"
                )
            ),
            "human_status": exp15_human,
            "tone": exp15_tone,
            "detail": "Creates the evidence-backed Experiment 02 study set.",
            "next_action": exp15_next,
            "criteria": [
                {
                    "label": "Opportunity handoff generated",
                    "done": handoff_status is not None,
                },
                {
                    "label": "Machine study set exists",
                    "done": study_set_ready,
                },
                {
                    "label": "Human opportunity approved",
                    "done": human_gate_ready,
                },
            ],
            "complete": human_gate_ready,
            "ready": exp14_complete,
            "current": exp14_complete and not human_gate_ready,
        },
        {
            "id": "02",
            "title": "Why Did It Work?",
            "state": (
                analysis_status
                if human_gate_ready and analysis_status
                else (
                    "READY_TO_PREPARE"
                    if human_gate_ready
                    else (
                        "WAITING_FOR_HUMAN_OPPORTUNITY_GATE"
                        if study_set_ready
                        else "WAITING_FOR_01_5"
                    )
                )
            ),
            "human_status": exp2_human,
            "tone": exp2_tone,
            "detail": "Evidence ingestion, FAIR analysis, human review and synthesis.",
            "next_action": exp2_next,
            "criteria": [
                {
                    "label": "Profiles prepared",
                    "done": profiles_prepared,
                },
                {
                    "label": "Transcript evidence acquired",
                    "done": evidence_ready,
                },
                {
                    "label": (
                        "Visual structure sampled"
                        if visual_ready
                        else (
                            "Visual structure attempted; transcript fallback active"
                            if visual_attempted
                            else (
                                "Visual structure skipped (ffmpeg unavailable)"
                                if not visual_available
                                else "Visual structure pending"
                            )
                        )
                    ),
                    "done": visual_satisfied,
                },
                {
                    "label": (
                        "Visual observations reviewed"
                        if visual_ready
                        else "Visual observations not required"
                    ),
                    "done": vision_satisfied,
                },
                {
                    "label": "Profiles analyzed",
                    "done": analyzed,
                },
                {
                    "label": "Human review available",
                    "done": reviewed,
                },
                {
                    "label": "Transformation handoff generated",
                    "done": synthesis_ready,
                },
            ],
            "complete": synthesis_ready,
            "ready": human_gate_ready,
            "current": human_gate_ready and not synthesis_ready,
        },
        {
            "id": "04",
            "title": "Transformation / Concept",
            "state": concept_gate_status,
            "human_status": transform_human,
            "tone": transform_tone,
            "detail": (
                "Turns validated mechanisms into original, source-independent "
                "video concepts and stops for human selection."
            ),
            "next_action": transform_next,
            "criteria": [
                {
                    "label": "Experiment 02 transformation handoff ready",
                    "done": synthesis_ready,
                },
                {
                    "label": "Concept requests prepared",
                    "done": transform_requests,
                },
                {
                    "label": "Valid concept candidates generated",
                    "done": transform_candidates,
                },
                {
                    "label": "Human Concept Gate complete",
                    "done": concept_gate_complete,
                },
                {
                    "label": "At least one concept accepted for packaging",
                    "done": research_ready,
                },
            ],
            "complete": research_ready,
            "ready": synthesis_ready,
            "current": synthesis_ready and not research_ready,
        },
        {
            "id": "05",
            "title": "Packaging",
            "state": packaging_gate_status,
            "human_status": package_human,
            "tone": package_tone,
            "detail": (
                "Builds title, thumbnail and opening-frame options before script "
                "drafting, then stops for human package selection."
            ),
            "next_action": package_next,
            "criteria": [
                {
                    "label": "Accepted concept handoff ready",
                    "done": research_ready,
                },
                {
                    "label": "Package requests prepared",
                    "done": package_requests,
                },
                {
                    "label": "Valid package candidates generated",
                    "done": package_candidates,
                },
                {
                    "label": "Human Packaging Gate complete",
                    "done": packaging_gate_complete,
                },
                {
                    "label": "At least one package approved for research",
                    "done": packaging_research_ready,
                },
            ],
            "complete": packaging_research_ready,
            "ready": research_ready,
            "current": research_ready and not packaging_research_ready,
        },
        {
            "id": "06",
            "title": "Research",
            "state": research_gate_status,
            "human_status": research_human,
            "tone": research_tone,
            "detail": (
                "Acquires real web evidence, structures traceable claims, and "
                "stops for human claim approval before Story / Script."
            ),
            "next_action": research_next,
            "criteria": [
                {
                    "label": "Approved package handoff ready",
                    "done": packaging_research_ready,
                },
                {
                    "label": "Research plans prepared",
                    "done": research_plans,
                },
                {
                    "label": "Web evidence acquired",
                    "done": research_evidence,
                },
                {
                    "label": "Draft research packages built",
                    "done": research_drafts,
                },
                {
                    "label": "Human Research Gate complete",
                    "done": research_gate_complete,
                },
                {
                    "label": "All research questions resolved for Script",
                    "done": story_ready,
                },
            ],
            "complete": story_ready,
            "ready": packaging_research_ready,
            "current": packaging_research_ready and not story_ready,
        },
    ]

def opportunity_research_state() -> dict[str, Any]:
    payload = safe_load_json(OPPORTUNITY_RESEARCH_STATE)
    return payload if isinstance(payload, dict) else {}


def action_readiness() -> dict[str, dict[str, Any]]:
    cohort_info = exp13_cohort_readiness()
    exp13_cohort = (
        (EXP13_DIR / "cohort_manifest.json").exists()
        and bool(cohort_info["sufficient"])
    )
    exp13_evidence = exp13_depth_ready_cell_count() > 0

    plan_ready = exp14_plan_status() == "READY"
    exp14_complete = exp14_execution_status() == "COMPLETE"
    study_set = (EXP15_DIR / "study_set.json").exists()
    research_state = opportunity_research_state()
    research_status = str(research_state.get("status") or "")
    research_waiting = research_status in {
        "WAITING_FOR_AUTOMATIC_VELOCITY_REFRESH",
        "DISCOVERY_RUNNING",
    }
    human_gate = opportunity_gate_snapshot()
    human_gate_ready = bool(human_gate.get("ready_for_experiment_02"))

    exp2_artifacts = exp2_artifact_state()
    profiles_prepared = exp2_artifacts["prepared_count"] > 0
    evidence_complete = bool(exp2_artifacts["evidence_complete"])
    visual_attempted = bool(exp2_artifacts["visual_attempted"])
    visual_complete = bool(exp2_artifacts["visual_complete"])
    vision_review = vision_review_snapshot()
    vision_complete = bool(vision_review.get("complete"))
    vision_awaiting = bool(vision_review.get("awaiting_human_review"))
    requests_complete = bool(exp2_artifacts["requests_complete"])
    analyzed_count = exp2_artifacts["analyzed_current_count"]
    request_count = len(exp2_artifacts["analysis_request_ids"])
    review_request_count = exp2_artifacts["review_requests_current_count"]
    reviewed_count = exp2_artifacts["reviewed_current_count"]
    analyzed = analyzed_count > 0
    analysis_complete = request_count > 0 and analyzed_count == request_count
    review_requests = review_request_count > 0
    review_requests_complete = request_count > 0 and review_request_count == request_count
    reviewed = reviewed_count > 0
    review_complete = request_count > 0 and reviewed_count == request_count
    synthesis_ready = bool(exp2_artifacts["synthesis_ready"])
    transform = transformation_artifact_state()
    transform_requests = bool(transform["requests_ready"])
    transform_candidates = bool(transform["candidates_ready"])
    transform_triage = bool(transform["triage_ready"])
    concept_gate = transform["concept_gate"]
    concept_gate_status = str(
        concept_gate.get("status") or "WAITING_FOR_CONCEPT_CANDIDATES"
    )
    concept_gate_complete = bool(transform["concept_gate_complete"])
    packaging = packaging_artifact_state()
    package_requests = bool(packaging["requests_ready"])
    package_candidates = bool(packaging["candidates_ready"])
    packaging_gate = packaging["packaging_gate"]
    packaging_gate_status = str(
        packaging_gate.get("status") or "WAITING_FOR_PACKAGE_CANDIDATES"
    )
    packaging_gate_complete = bool(packaging["packaging_gate_complete"])
    research = research_artifact_state()
    research_plans = bool(research["plans_ready"])
    research_evidence = bool(research["evidence_complete"])
    research_drafts = bool(research["drafts_ready"])
    research_gate = research["research_gate"]
    research_gate_status = str(
        research_gate.get("status") or "WAITING_FOR_DRAFT_RESEARCH_PACKAGES"
    )
    research_gate_complete = bool(research["research_gate_complete"])
    story = story_script_artifact_state()
    script_requests_ready = bool(story["requests_ready"])
    script_drafts_ready = bool(story["drafts_ready"])
    script_gate = story["script_gate"]
    script_gate_status = str(script_gate.get("status") or "WAITING_FOR_SCRIPT_DRAFTS")
    script_gate_complete = bool(story["script_gate_complete"])
    production_ready = bool(story["production_ready"])

    agent_reach_installed = shutil.which("agent-reach") is not None
    yt_dlp_installed = shutil.which("yt-dlp") is not None
    ffmpeg_installed = shutil.which("ffmpeg") is not None
    visual_available = yt_dlp_installed and ffmpeg_installed
    visual_satisfied = (
        visual_complete
        or visual_attempted
        or not visual_available
    )
    vision_satisfied = (not visual_complete) or vision_complete

    return {
        "opportunity_research": {
            "enabled": not study_set and not research_waiting,
            "reason": (
                "Opportunity handoff already exists; review it below."
                if study_set
                else (
                    "Automatic velocity measurement is already scheduled."
                    if research_waiting
                    else "Run the Opportunity Engine automatically through 01.5."
                )
            ),
        },
        "agent_reach_doctor": {
            "enabled": True,
            "reason": (
                "Agent Reach detected; run health checks."
                if agent_reach_installed
                else "Agent Reach is not installed; doctor will report the missing dependency."
            ),
        },
        "agent_reach_youtube_benchmark": {
            "enabled": agent_reach_installed and yt_dlp_installed,
            "reason": (
                "Agent Reach and yt-dlp are available."
                if agent_reach_installed and yt_dlp_installed
                else "Install Agent Reach and confirm yt-dlp before benchmarking."
            ),
        },
        "exp13_discover": {
            "enabled": True,
            "reason": (
                "Resume saved discovery checkpoint."
                if EXP13_CHECKPOINT.exists()
                else "Start corrected 01.3 discovery."
            ),
        },
        "exp13_restart": {
            "enabled": True,
            "reason": (
                "Discard the saved discovery checkpoint and start a clean 01.3 run."
                if EXP13_CHECKPOINT.exists()
                else "Start a completely new 01.3 discovery run."
            ),
        },
        "exp13_refresh": {
            "enabled": exp13_cohort,
            "reason": (
                "Cohort has enough independent channels for velocity measurement."
                if exp13_cohort
                else (
                    "Cohort is missing or insufficient. Rerun 01.3 discovery; "
                    "do not wait for refresh."
                )
            ),
        },
        "exp13_auto_refresh_install": {
            "enabled": IS_WINDOWS,
            "reason": (
                "Install a self-limiting Windows scheduled refresh every two hours."
                if IS_WINDOWS
                else "Windows Task Scheduler automation is available only on Windows."
            ),
        },
        "exp13_auto_refresh_remove": {
            "enabled": IS_WINDOWS,
            "reason": (
                "Remove the Windows scheduled refresh task."
                if IS_WINDOWS
                else "Windows Task Scheduler automation is available only on Windows."
            ),
        },
        "exp14_plan": {
            "enabled": exp13_evidence,
            "reason": (
                "Measured 01.3 velocity evidence available."
                if exp13_evidence
                else "Waiting for corrected 01.3 refresh with valid velocity samples."
            ),
        },
        "exp14_execute": {
            "enabled": plan_ready,
            "reason": (
                "01.4 plan is READY."
                if plan_ready
                else "Build a READY 01.4 plan first."
            ),
        },
        "exp15_build": {
            "enabled": exp14_complete,
            "reason": (
                "01.4 execution complete."
                if exp14_complete
                else "Waiting for 01.4 execution."
            ),
        },
        "exp2_prepare": {
            "enabled": human_gate_ready and not profiles_prepared,
            "reason": (
                "Human-approved opportunity set available."
                if human_gate_ready and not profiles_prepared
                else (
                    "Experiment 02 profiles are already prepared."
                    if profiles_prepared
                    else (
                        "Review and approve the 01.5 opportunity gate first."
                        if study_set
                        else "Waiting for 01.5 study set."
                    )
                )
            ),
        },
        "exp2_acquire": {
            "enabled": (
                human_gate_ready
                and profiles_prepared
                and not evidence_complete
                and yt_dlp_installed
            ),
            "reason": (
                "Prepared profiles are ready for caption/thumbnail acquisition."
                if (
                    human_gate_ready
                    and profiles_prepared
                    and not evidence_complete
                    and yt_dlp_installed
                )
                else (
                    "Source evidence is already ready."
                    if evidence_complete
                    else (
                        "yt-dlp is required for automatic source evidence acquisition."
                        if human_gate_ready and profiles_prepared and not yt_dlp_installed
                        else (
                            "Prepare Experiment 02 profiles first."
                            if human_gate_ready and not profiles_prepared
                            else "Human opportunity approval is required first."
                        )
                    )
                )
            ),
        },
        "exp2_visual": {
            "enabled": (
                human_gate_ready
                and evidence_complete
                and visual_available
                and not visual_attempted
            ),
            "reason": (
                "Transcript-backed evidence is ready for visual structure sampling."
                if (
                    human_gate_ready
                    and evidence_complete
                    and visual_available
                    and not visual_attempted
                )
                else (
                    "Visual structure evidence is already ready."
                    if visual_complete
                    else (
                        "Visual structure was attempted; transcript-only analysis may continue. "
                        "Use Tools & Diagnostics to force a retry."
                        if visual_attempted
                        else (
                            "yt-dlp and ffmpeg are required for automatic visual "
                            "structure sampling."
                            if (
                                human_gate_ready
                                and evidence_complete
                                and not visual_available
                            )
                            else (
                                "Acquire transcript-backed source evidence first."
                                if human_gate_ready and not evidence_complete
                                else "Human opportunity approval is required first."
                            )
                        )
                    )
                )
            ),
        },
        "exp2_visual_retry": {
            "enabled": (
                human_gate_ready
                and evidence_complete
                and visual_available
                and visual_attempted
            ),
            "reason": (
                "Force a fresh visual-structure pass for the current approved profiles."
                if (
                    human_gate_ready
                    and evidence_complete
                    and visual_available
                    and visual_attempted
                )
                else "A completed or failed guided visual attempt is required before force-retry."
            ),
        },
        "exp2_vision_prepare": {
            "enabled": (
                human_gate_ready
                and evidence_complete
                and visual_complete
                and not vision_complete
                and not vision_awaiting
            ),
            "reason": (
                "Visual structure frames are ready for human-gated observation review."
                if (
                    human_gate_ready
                    and evidence_complete
                    and visual_complete
                    and not vision_complete
                    and not vision_awaiting
                )
                else (
                    "Visual review is waiting for human decisions."
                    if vision_awaiting
                    else (
                        "Visual review is already complete."
                        if vision_complete
                        else (
                            "Successful visual structure evidence is required first."
                            if human_gate_ready and not visual_complete
                            else "Human opportunity approval is required first."
                        )
                    )
                )
            ),
        },
        "vision_doctor": {
            "enabled": True,
            "reason": (
                "Checks local Ollama vision configuration. "
                "Human-only visual review works without a model."
            ),
        },
        "fair_doctor": {
            "enabled": True,
            "reason": "Safe diagnostic; no inference.",
        },
        "analysis_batch_prepare": {
            "enabled": (
                human_gate_ready
                and evidence_complete
                and visual_satisfied
                and vision_satisfied
                and not requests_complete
            ),
            "reason": (
                "Current approved profiles have transcript-backed evidence."
                if (
                    human_gate_ready
                    and evidence_complete
                    and visual_satisfied
                    and vision_satisfied
                    and not requests_complete
                )
                else (
                    "Analysis requests are already prepared."
                    if requests_complete
                    else (
                        "Human opportunity approval is required first."
                        if not human_gate_ready
                        else (
                            "Acquire transcript-backed source evidence first."
                            if not evidence_complete
                            else (
                                "Run visual structure sampling before analysis requests."
                                if not visual_satisfied
                                else "Complete visual observation review before analysis requests."
                            )
                        )
                    )
                )
            ),
        },
        "analysis_model_one": {
            "enabled": (
                human_gate_ready
                and requests_complete
                and not analyzed
            ),
            "reason": (
                "Run one current analysis request as the FAIR safety check."
                if human_gate_ready and requests_complete and not analyzed
                else (
                    "The one-model safety check has already produced a current analyzed profile."
                    if analyzed
                    else (
                        "Human opportunity approval is required first."
                        if not human_gate_ready
                        else "Prepare current analysis requests first."
                    )
                )
            ),
        },
        "analysis_model_remaining": {
            "enabled": (
                human_gate_ready
                and requests_complete
                and analyzed
                and not analysis_complete
            ),
            "reason": (
                f"{analyzed_count} of {request_count} current analyses are applied. "
                "Run the remaining requests; completed requests will be skipped."
                if (
                    human_gate_ready
                    and requests_complete
                    and analyzed
                    and not analysis_complete
                )
                else (
                    "All current analysis requests are applied."
                    if analysis_complete
                    else "Complete the one-model FAIR safety check first."
                )
            ),
        },
        "human_review_prepare": {
            "enabled": (
                human_gate_ready
                and analysis_complete
                and not review_requests_complete
            ),
            "reason": (
                "All current analyzed profiles are ready for Human Review packets."
                if (
                    human_gate_ready
                    and analysis_complete
                    and not review_requests_complete
                )
                else (
                    "Human Review packets are already current for every analyzed profile."
                    if review_requests_complete
                    else (
                        "Human opportunity approval is required first."
                        if not human_gate_ready
                        else "Finish all current model analyses first."
                    )
                )
            ),
        },
        "synthesis_build": {
            "enabled": (
                human_gate_ready
                and review_complete
                and not synthesis_ready
            ),
            "reason": (
                "Human Review is complete for every current analyzed profile."
                if (
                    human_gate_ready
                    and review_complete
                    and not synthesis_ready
                )
                else (
                    "Synthesis is already built."
                    if synthesis_ready
                    else (
                        "Human opportunity approval is required first."
                        if not human_gate_ready
                        else "Waiting for complete Human Review of all current analyzed profiles."
                    )
                )
            ),
        },
        "transform_prepare": {
            "enabled": synthesis_ready and not transform_requests,
            "reason": (
                "Experiment 02 synthesis is ready for mechanism-bound concept requests."
                if synthesis_ready and not transform_requests
                else (
                    "Concept requests are already current."
                    if transform_requests
                    else "Complete Experiment 02 synthesis first."
                )
            ),
        },
        "concept_generate": {
            "enabled": (
                synthesis_ready
                and transform_requests
                and not transform_candidates
            ),
            "reason": (
                "Current concept requests are ready for FAIR free-only generation."
                if (
                    synthesis_ready
                    and transform_requests
                    and not transform_candidates
                )
                else (
                    "Valid concept candidates already exist."
                    if transform_candidates
                    else "Prepare current concept requests first."
                )
            ),
        },
        "concept_triage": {
            "enabled": transform_candidates and not transform_triage,
            "reason": (
                "Compare all current concept candidates and shortlist the strongest 3-6."
                if transform_candidates and not transform_triage
                else (
                    f"Concept triage is current with {transform['shortlist_count']} shortlisted concept(s)."
                    if transform_triage
                    else "Generate valid concept candidates first."
                )
            ),
        },
        "concept_gate_prepare": {
            "enabled": (
                transform_triage
                and (
                    concept_gate_status == "READY_TO_PREPARE"
                    or (
                        concept_gate_complete
                        and not bool(transform["research_ready"])
                    )
                )
            ),
            "reason": (
                "LLM-shortlisted concepts are ready for final human review."
                if (
                    transform_triage
                    and concept_gate_status == "READY_TO_PREPARE"
                )
                else (
                    "No concept was accepted; reopen the current Concept Gate."
                    if (
                        transform_triage
                        and concept_gate_complete
                        and not bool(transform["research_ready"])
                    )
                    else (
                        "Concept Gate is already prepared or complete."
                        if transform_triage
                        else "Run Concept Triage before preparing the Human Concept Gate."
                    )
                )
            ),
        },
        "package_prepare": {
            "enabled": bool(transform["research_ready"]) and not package_requests,
            "reason": (
                "Accepted concepts are ready for packaging requests."
                if bool(transform["research_ready"]) and not package_requests
                else (
                    "Package requests are already current."
                    if package_requests
                    else "Accept at least one concept first."
                )
            ),
        },
        "package_generate": {
            "enabled": package_requests and not package_candidates,
            "reason": (
                "Current package requests are ready for FAIR free-only generation."
                if package_requests and not package_candidates
                else (
                    "Valid package candidates already exist."
                    if package_candidates
                    else "Prepare current package requests first."
                )
            ),
        },
        "package_gate_prepare": {
            "enabled": (
                package_candidates
                and (
                    packaging_gate_status == "READY_TO_PREPARE"
                    or (
                        packaging_gate_complete
                        and not bool(packaging["research_ready"])
                    )
                )
            ),
            "reason": (
                "Validated package candidates are ready for human review."
                if package_candidates and packaging_gate_status == "READY_TO_PREPARE"
                else (
                    "No package was accepted; reopen the current Packaging Gate."
                    if (
                        package_candidates
                        and packaging_gate_complete
                        and not bool(packaging["research_ready"])
                    )
                    else (
                        "Packaging Gate is already prepared or complete."
                        if package_candidates
                        else "Generate valid package candidates first."
                    )
                )
            ),
        },
        "research_prepare": {
            "enabled": bool(packaging["research_ready"]) and not research_plans,
            "reason": (
                "Approved packages are ready to become research plans."
                if bool(packaging["research_ready"]) and not research_plans
                else (
                    "Research plans are already current."
                    if research_plans
                    else "Approve a package first."
                )
            ),
        },
        "research_acquire": {
            "enabled": research_plans and not research_evidence,
            "reason": (
                "Current research plans are ready for real web evidence acquisition."
                if research_plans and not research_evidence
                else (
                    "Current web evidence already exists."
                    if research_evidence
                    else "Prepare current research plans first."
                )
            ),
        },
        "research_generate": {
            "enabled": research_evidence and not research_drafts,
            "reason": (
                "Acquired pages are ready for FAIR claim structuring."
                if research_evidence and not research_drafts
                else (
                    "Draft research packages already exist."
                    if research_drafts
                    else "Acquire current web evidence first."
                )
            ),
        },
        "research_gate_prepare": {
            "enabled": (
                research_drafts
                and (
                    research_gate_status == "READY_TO_PREPARE"
                    or (
                        research_gate_complete
                        and not bool(research["story_ready"])
                    )
                )
            ),
            "reason": (
                "Draft research claims are ready for human review."
                if research_drafts and research_gate_status == "READY_TO_PREPARE"
                else (
                    "Research remains incomplete; reopen the Research Gate."
                    if research_drafts and research_gate_complete
                    else (
                        "Research Gate is already prepared or complete."
                        if research_drafts
                        else "Structure current research claims first."
                    )
                )
            ),
        },
        "script_prepare": {
            "enabled": bool(research["story_ready"]) and not script_requests_ready,
            "reason": (
                "Verified research and the approved package are ready for script requests."
                if bool(research["story_ready"]) and not script_requests_ready
                else (
                    "Script requests are already current."
                    if script_requests_ready
                    else "Complete the Human Research Gate first."
                )
            ),
        },
        "script_generate": {
            "enabled": script_requests_ready and not script_drafts_ready,
            "reason": (
                "Current script requests are ready for FAIR drafting."
                if script_requests_ready and not script_drafts_ready
                else (
                    "Current script drafts already exist."
                    if script_drafts_ready
                    else "Prepare current script requests first."
                )
            ),
        },
        "script_gate_prepare": {
            "enabled": (
                script_drafts_ready
                and (
                    script_gate_status == "READY_TO_PREPARE"
                    or (
                        script_gate_complete
                        and not production_ready
                    )
                )
            ),
            "reason": (
                "Validated script drafts are ready for human review."
                if script_drafts_ready and script_gate_status == "READY_TO_PREPARE"
                else (
                    "No script was approved; reopen the Script Gate."
                    if script_drafts_ready and script_gate_complete and not production_ready
                    else (
                        "Script Gate is already prepared or complete."
                        if script_drafts_ready
                        else "Generate current script drafts first."
                    )
                )
            ),
        },
    }


class JobManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._job: dict[str, Any] | None = None

    def running(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def current(self) -> dict[str, Any] | None:
        with self._lock:
            job = dict(self._job) if self._job else None
            process = self._process

        if job is None:
            return None

        if process is not None and process.poll() is not None and job.get("status") == "RUNNING":
            self._finalize(process.returncode)

        public = self.public_job()
        return public or None

    def start(self, action_id: str) -> dict[str, Any]:
        if action_id not in ACTION_DEFS:
            raise ValueError("Unknown action")

        readiness = action_readiness().get(action_id, {})
        if not readiness.get("enabled"):
            raise RuntimeError(readiness.get("reason") or "Action is blocked.")

        with self._lock:
            if self._process is not None and self._process.poll() is None:
                raise RuntimeError("Another experiment job is already running.")

            JOB_LOG_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_path = JOB_LOG_DIR / f"{stamp}_{action_id}.log"
            action = ACTION_DEFS[action_id]

            log_handle = log_path.open("w", encoding="utf-8", buffering=1)
            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

            child_env = os.environ.copy()
            child_env["PYTHONUNBUFFERED"] = "1"
            child_env["PYTHONUTF8"] = "1"
            child_env["PYTHONIOENCODING"] = "utf-8"

            process = subprocess.Popen(
                action["command"],
                cwd=PROJECT_ROOT,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
                creationflags=creationflags,
                env=child_env,
            )

            self._process = process
            self._job = {
                "id": f"{stamp}_{action_id}",
                "action_id": action_id,
                "label": action["label"],
                "status": "RUNNING",
                "pid": process.pid,
                "started_at": utc_now(),
                "finished_at": None,
                "return_code": None,
                "log_path": str(log_path),
            }
            self._job["_log_handle"] = log_handle

        payload = self.public_job()
        self._save_state(payload)
        return payload

    def _finalize(self, return_code: int | None) -> None:
        with self._lock:
            if not self._job:
                return
            log_handle = self._job.pop("_log_handle", None)
            if log_handle:
                try:
                    log_handle.close()
                except OSError:
                    pass
            self._job["return_code"] = return_code
            self._job["finished_at"] = utc_now()
            if self._job.get("status") == "STOPPING":
                self._job["status"] = "STOPPED"
            else:
                self._job["status"] = (
                    "SUCCEEDED"
                    if return_code == 0
                    else "PARTIAL"
                    if return_code == 2
                    else "FAILED"
                )
            self._process = None

        self._save_state(self.public_job())

    def stop(self) -> dict[str, Any]:
        with self._lock:
            process = self._process
            if process is None or process.poll() is not None:
                raise RuntimeError("No experiment job is currently running.")
            if self._job:
                self._job["status"] = "STOPPING"

        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        self._finalize(process.returncode)
        return self.public_job()

    def public_job(self) -> dict[str, Any]:
        with self._lock:
            if not self._job:
                return {}
            return {
                key: value
                for key, value in self._job.items()
                if key != "_log_handle"
            }

    def log_text(self, max_chars: int = 30000) -> str:
        job = self.current()
        if not job:
            return ""
        path = Path(str(job.get("log_path", "")))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return text[-max_chars:]

    def _save_state(self, payload: dict[str, Any]) -> None:
        UI_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        JOB_STATE_FILE.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


JOB_MANAGER = JobManager()


def workflow_guidance(
    readiness: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = opportunity_gate_snapshot()
    study_set = (EXP15_DIR / "study_set.json").exists()
    human_gate_ready = bool(gate.get("ready_for_experiment_02"))
    research_state = opportunity_research_state()
    research_status = str(research_state.get("status") or "")

    if study_set and not human_gate_ready:
        return {
            "state": "HUMAN_GATE",
            "current_action_id": None,
            "current_title": "Review Opportunity",
            "current_detail": (
                "Review the selected topic and examples, then approve, hold or reject."
            ),
            "next_action_id": "exp2_prepare",
            "next_title": "Prepare Experiment 02",
        }

    if research_status == "DISCOVERY_RUNNING" and not study_set:
        return {
            "state": "RUNNING_AUTOMATIC",
            "current_action_id": None,
            "current_title": "Opportunity Research running",
            "current_detail": str(
                research_state.get("message")
                or "Discovery and validation are running automatically."
            ),
            "next_action_id": None,
            "next_title": "Automatic velocity validation",
        }

    if research_status == "WAITING_FOR_AUTOMATIC_VELOCITY_REFRESH" and not study_set:
        return {
            "state": "WAITING_AUTOMATIC",
            "current_action_id": None,
            "current_title": "Automatic velocity measurement scheduled",
            "current_detail": str(
                research_state.get("message")
                or "The system will continue automatically."
            ),
            "next_action_id": None,
            "next_title": "Review Opportunity",
            "next_due_at": research_state.get("next_refresh_due_at"),
        }

    vision_review = vision_review_snapshot()
    if vision_review.get("awaiting_human_review"):
        return {
            "state": "HUMAN_VISION_GATE",
            "current_action_id": None,
            "current_title": "Review Visual Evidence",
            "current_detail": (
                "Check each retained frame. Accept or edit only observations "
                "that are directly visible; reject uncertain or unhelpful frames."
            ),
            "next_action_id": "analysis_batch_prepare",
            "next_title": "Prepare Analysis Requests",
        }

    human_analysis_review = human_analysis_review_snapshot()
    if human_analysis_review.get("status") == "AWAITING_HUMAN_DECISION":
        return {
            "state": "HUMAN_ANALYSIS_GATE",
            "current_action_id": None,
            "current_title": "Review Analysis Findings",
            "current_detail": (
                "Review each evidence-backed finding and transfer item. "
                "Accept only claims that fairly represent the cited source evidence."
            ),
            "next_action_id": "synthesis_build",
            "next_title": "Build Experiment 02 Synthesis",
        }

    transform = transformation_artifact_state()
    concept_gate = transform.get("concept_gate", {})
    if (
        transform.get("candidates_ready")
        and concept_gate.get("status") == "AWAITING_HUMAN_DECISION"
    ):
        return {
            "state": "HUMAN_CONCEPT_GATE",
            "current_action_id": None,
            "current_title": "Review Concept Candidates",
            "current_detail": (
                "Inspect each original concept against the human acceptance "
                "criteria. Accept, send for rework, or reject."
            ),
            "next_action_id": None,
            "next_title": "Packaging",
        }

    packaging = packaging_artifact_state()
    packaging_gate = packaging.get("packaging_gate", {})
    if (
        packaging.get("candidates_ready")
        and packaging_gate.get("status") == "AWAITING_HUMAN_DECISION"
    ):
        return {
            "state": "HUMAN_PACKAGING_GATE",
            "current_action_id": None,
            "current_title": "Review Package Candidates",
            "current_detail": (
                "Review title, thumbnail and opening-frame packages. Approve at "
                "most one package per concept, send it for rework, or reject it."
            ),
            "next_action_id": None,
            "next_title": "Research",
        }

    research = research_artifact_state()
    research_gate = research.get("research_gate", {})
    if (
        research.get("drafts_ready")
        and research_gate.get("status") == "AWAITING_HUMAN_DECISION"
    ):
        return {
            "state": "HUMAN_RESEARCH_GATE",
            "current_action_id": None,
            "current_title": "Review Research Claims",
            "current_detail": (
                "Check each claim against its cited acquired source evidence. "
                "Accept only wording safe to carry into the script."
            ),
            "next_action_id": None,
            "next_title": "Story / Script",
        }

    story = story_script_artifact_state()
    script_gate = story.get("script_gate", {})
    if (
        story.get("drafts_ready")
        and script_gate.get("status") == "AWAITING_HUMAN_DECISION"
    ):
        return {
            "state": "HUMAN_SCRIPT_GATE",
            "current_action_id": None,
            "current_title": "Review Script Draft",
            "current_detail": (
                "Check promise delivery, factual scope, claim mapping, originality "
                "and story payoff before production."
            ),
            "next_action_id": None,
            "next_title": "Ready for Production",
        }

    for index, action_id in enumerate(WORKFLOW_ACTION_ORDER):
        gate_info = readiness.get(action_id, {})
        if gate_info.get("enabled"):
            next_id = (
                WORKFLOW_ACTION_ORDER[index + 1]
                if index + 1 < len(WORKFLOW_ACTION_ORDER)
                else None
            )
            return {
                "state": "ACTION_REQUIRED",
                "current_action_id": action_id,
                "current_title": ACTION_DEFS[action_id]["label"],
                "current_detail": gate_info.get("reason"),
                "next_action_id": next_id,
                "next_title": (
                    ACTION_DEFS[next_id]["label"]
                    if next_id
                    else "Workflow complete"
                ),
            }

    if human_gate_ready:
        return {
            "state": "WAITING_FOR_NEXT_STAGE",
            "current_action_id": None,
            "current_title": "Waiting for the next ready production step",
            "current_detail": (
                "A downstream prerequisite is still missing. "
                "The next available action will highlight automatically."
            ),
            "next_action_id": None,
            "next_title": "Continue Experiment 02",
        }

    return {
        "state": "READY",
        "current_action_id": "opportunity_research",
        "current_title": "Run Opportunity Research",
        "current_detail": "Start automated opportunity discovery and validation.",
        "next_action_id": None,
        "next_title": "Review Opportunity",
    }


def status_payload() -> dict[str, Any]:
    readiness = action_readiness()
    workflow = workflow_guidance(readiness)
    transformation = transformation_artifact_state()
    packaging = packaging_artifact_state()
    research = research_artifact_state()
    story = story_script_artifact_state()
    actions = []
    for action_id, definition in ACTION_DEFS.items():
        gate = readiness[action_id]
        actions.append(
            {
                "id": action_id,
                "label": definition["label"],
                "stage": definition["stage"],
                "description": definition["description"],
                "enabled": bool(gate["enabled"]) and not JOB_MANAGER.running(),
                "reason": gate["reason"],
                "surface": (
                    "workflow"
                    if action_id in WORKFLOW_ACTION_ORDER
                    else "tools"
                ),
                "role": (
                    "do_now"
                    if action_id == workflow.get("current_action_id")
                    else (
                        "next"
                        if action_id == workflow.get("next_action_id")
                        else "normal"
                    )
                ),
            }
        )

    return {
        "csrf_token": CSRF_TOKEN,
        "project_root": str(PROJECT_ROOT),
        "stages": stage_statuses(),
        "actions": actions,
        "job": JOB_MANAGER.current(),
        "checkpoint": {
            "exists": EXP13_CHECKPOINT.exists(),
            "status": checkpoint_status(),
        },
        "opportunity_gate": opportunity_gate_snapshot(),
        "workflow": workflow,
        "opportunity_research": opportunity_research_state(),
        "experiment_02_artifacts": exp2_artifact_state(),
        "vision_review": vision_review_snapshot(),
        "human_analysis_review": human_analysis_review_snapshot(),
        "transformation": transformation,
        "concept_gate": transformation["concept_gate"],
        "packaging": packaging,
        "packaging_gate": packaging["packaging_gate"],
        "research": research,
        "research_gate": research["research_gate"],
        "story_script": story,
        "script_gate": story["script_gate"],
        "outputs": {
            "experiment_01": str(EXP1_OUTPUT),
            "experiment_02": str(EXP2_OUTPUT),
        },
        "updated_at": utc_now(),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "ExperimentControlUI/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        route = urlparse(self.path).path

        if route in APP_ROUTES:
            self._send_static(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if route == "/app.js":
            self._send_static(STATIC_DIR / "app.js", "text/javascript; charset=utf-8")
            return
        if route == "/styles.css":
            self._send_static(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
            return
        if route == "/api/status":
            self._send_json(status_payload())
            return
        if route == "/api/job":
            self._send_json(
                {
                    "job": JOB_MANAGER.current(),
                    "log": JOB_MANAGER.log_text(),
                }
            )
            return
        if route == "/api/opportunity-gate":
            self._send_json(opportunity_gate_snapshot())
            return
        if route == "/api/vision-review":
            self._send_json(vision_review_snapshot())
            return
        if route == "/api/human-analysis-review":
            self._send_json(human_analysis_review_snapshot())
            return
        if route == "/api/concept-gate":
            self._send_json(concept_gate_snapshot())
            return
        if route == "/api/packaging-gate":
            self._send_json(packaging_gate_snapshot())
            return
        if route == "/api/research-gate":
            self._send_json(research_gate_snapshot())
            return
        if route == "/api/script-gate":
            self._send_json(script_gate_snapshot())
            return
        if route == "/api/vision-frame":
            query = parse_qs(urlparse(self.path).query)
            video_id = str((query.get("video_id") or [""])[0])
            frame_id = str((query.get("frame_id") or [""])[0])
            try:
                path = vision_frame_path(video_id, frame_id)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, 404)
                return
            self._send_static(path, "image/jpeg")
            return

        self.send_error(404)

    def _post_security_error(self) -> str | None:
        content_type = str(self.headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            return "POST requests require Content-Type: application/json."

        port = int(self.server.server_address[1])
        allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host = str(self.headers.get("Host", "")).strip().lower()
        if host not in allowed_hosts:
            return "Invalid Host for local control UI."

        origin = str(self.headers.get("Origin", "")).strip().lower()
        if origin and origin not in {
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        }:
            return "Cross-origin POST requests are not allowed."

        if str(self.headers.get("X-CSRF-Token", "")) != CSRF_TOKEN:
            return "Missing or invalid CSRF token."
        return None

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        security_error = self._post_security_error()
        if security_error:
            self._send_json({"error": security_error}, 403)
            return

        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON body."}, 400)
            return

        try:
            if route == "/api/run":
                action_id = str(body.get("action_id", ""))
                job = JOB_MANAGER.start(action_id)
                self._send_json({"job": job}, 202)
                return

            if route == "/api/stop":
                job = JOB_MANAGER.stop()
                self._send_json({"job": job})
                return

            if route == "/api/opportunity-gate":
                payload = apply_gate_action(
                    action=str(body.get("action", "")),
                    opportunity_key=str(body.get("opportunity_id", "")),
                    video_id=(
                        str(body["video_id"])
                        if body.get("video_id") is not None
                        else None
                    ),
                )
                self._send_json(payload)
                return

            if route == "/api/vision-review":
                payload = apply_vision_review_action(
                    action=str(body.get("action", "")),
                    video_id=str(body.get("video_id", "")),
                    frame_id=(
                        str(body["frame_id"])
                        if body.get("frame_id") is not None
                        else None
                    ),
                    observation=(
                        str(body["observation"])
                        if body.get("observation") is not None
                        else None
                    ),
                )
                self._send_json(payload)
                return

            if route == "/api/human-analysis-review":
                payload = apply_human_analysis_review_action(
                    video_id=str(body.get("video_id", "")),
                    item_id=str(body.get("item_id", "")),
                    decision=str(body.get("decision", "")),
                    note=(
                        str(body["note"])
                        if body.get("note") is not None
                        else None
                    ),
                )
                self._send_json(payload)
                return

            if route == "/api/concept-gate":
                payload = apply_concept_gate_action(
                    concept_id=str(body.get("concept_id", "")),
                    decision=str(body.get("decision", "")),
                    criteria=body.get("criteria", {}),
                    note=(
                        str(body["note"])
                        if body.get("note") is not None
                        else None
                    ),
                )
                self._send_json(payload)
                return

            if route == "/api/packaging-gate":
                payload = apply_packaging_gate_action(
                    package_id=str(body.get("package_id", "")),
                    decision=str(body.get("decision", "")),
                    criteria=body.get("criteria", {}),
                    note=(
                        str(body["note"])
                        if body.get("note") is not None
                        else None
                    ),
                )
                self._send_json(payload)
                return

            if route == "/api/research-gate":
                payload = apply_research_gate_action(
                    concept_id=str(body.get("concept_id", "")),
                    claim_id=str(body.get("claim_id", "")),
                    decision=str(body.get("decision", "")),
                    criteria=body.get("criteria", {}),
                    note=(
                        str(body["note"])
                        if body.get("note") is not None
                        else None
                    ),
                )
                self._send_json(payload)
                return

            if route == "/api/script-gate":
                payload = apply_script_gate_action(
                    concept_id=str(body.get("concept_id", "")),
                    decision=str(body.get("decision", "")),
                    criteria=body.get("criteria", {}),
                    note=(
                        str(body["note"])
                        if body.get("note") is not None
                        else None
                    ),
                )
                self._send_json(payload)
                return

            if route == "/api/open":
                target_id = str(body.get("target_id", ""))
                target = OPEN_TARGETS.get(target_id)
                if target is None:
                    raise ValueError("Unknown open target.")
                target.mkdir(parents=True, exist_ok=True)
                if os.name == "nt":
                    os.startfile(str(target))
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(target)])
                else:
                    subprocess.Popen(["xdg-open", str(target)])
                self._send_json({"opened": str(target)})
                return

            self.send_error(404)
        except (ValueError, RuntimeError, OSError) as exc:
            self._send_json({"error": str(exc)}, 409)


def run_server(host: str, port: int, open_browser: bool) -> None:
    UI_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"

    print("=" * 60)
    print("YOUTUBE PRODUCTION — EXPERIMENT CONTROL")
    print("=" * 60)
    print(f"UI: {url}")
    print("Press Ctrl+C in this launcher window to stop the UI server.")
    print()

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Local experiment control UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Experiment UI is intentionally restricted to localhost.")

    run_server(args.host, args.port, not args.no_browser)


if __name__ == "__main__":
    main()
