"""Local experiment control UI for the YouTube Production project.

Dependency-free HTTP server bound to 127.0.0.1. The browser UI can run only
predefined experiment actions; arbitrary shell commands are never accepted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
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
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline_integrity import atomic_write_json

STATIC_DIR = HERE / "static"
APP_ROUTES = {"/", "/opportunity", "/analysis", "/tools"}
IS_WINDOWS = os.name == "nt"
CSRF_TOKEN = secrets.token_urlsafe(32)
HUMAN_GATE_MUTATION_ROUTES = {
    "/api/opportunity-gate",
    "/api/vision-review",
    "/api/human-analysis-review",
    "/api/concept-gate",
    "/api/packaging-gate",
    "/api/research-gate",
    "/api/script-gate",
    "/api/script-section-review",
    "/api/format-gate",
    "/api/performance-gate",
    "/api/narration-preview-gate",
    "/api/narration-spend-gate",
    "/api/narration-render-return",
    "/api/visual-candidate-review",
    "/api/visual-rights-review",
    "/api/visual-rough-cut-review",
    "/api/visual-spend-review",
    "/api/generated-visual-asset",
    "/api/managed-visual-asset",
    "/api/edit-preview-review",
    "/api/storyboard-review",
    "/api/narration-performance-review",
}

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

from opportunity_gate import (
    apply_gate_action,
)
from opportunity_gate import (
    gate_snapshot as opportunity_gate_snapshot,
)

EXP2_DIR = PROJECT_ROOT / "experiment_02_analysis"
if str(EXP2_DIR) not in sys.path:
    sys.path.insert(0, str(EXP2_DIR))

from human_review import (
    apply_review_action as apply_human_analysis_review_action,
)
from human_review import (
    review_snapshot as human_analysis_review_snapshot,
)
from vision_review import (
    apply_review_action as apply_vision_review_action,
)
from vision_review import (
    frame_path as vision_frame_path,
)
from vision_review import (
    review_snapshot as vision_review_snapshot,
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

from concept_review import (
    apply_action as apply_concept_gate_action,
)
from concept_review import (
    snapshot as concept_gate_snapshot,
)
from transformation_engine import (
    safe_slug as transformation_safe_slug,
    validation_contract_sha256 as transformation_validation_contract_sha256,
)

TRANSFORM_OUTPUT = TRANSFORM_DIR / "output"
TRANSFORM_REQUESTS_DIR = TRANSFORM_OUTPUT / "concept_requests"
TRANSFORM_RESPONSES_DIR = TRANSFORM_OUTPUT / "concept_responses"
TRANSFORM_MODEL_RUNS_DIR = TRANSFORM_OUTPUT / "concept_model_runs"
TRANSFORM_CANDIDATES_FILE = TRANSFORM_OUTPUT / "concept_candidates.json"
TRANSFORM_TRIAGE_FILE = TRANSFORM_OUTPUT / "concept_triage.json"
TRANSFORM_TRIAGED_CANDIDATES_FILE = TRANSFORM_OUTPUT / "concept_candidates_triaged.json"
TRANSFORM_RESEARCH_HANDOFF = TRANSFORM_OUTPUT / "research_handoff.json"

PACKAGING_DIR = PROJECT_ROOT / "packaging_engine"
if str(PACKAGING_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGING_DIR))

from package_review import (
    apply_action as apply_packaging_gate_action,
)
from package_review import (
    snapshot as packaging_gate_snapshot,
)

PACKAGING_CONFIG_FILE = PACKAGING_DIR / "packaging_config.json"
PACKAGING_OUTPUT = PACKAGING_DIR / "output"
PACKAGING_REQUESTS_DIR = PACKAGING_OUTPUT / "package_requests"
PACKAGING_RESPONSES_DIR = PACKAGING_OUTPUT / "package_responses"
PACKAGING_CANDIDATES_FILE = PACKAGING_OUTPUT / "package_candidates.json"
PACKAGING_RESEARCH_HANDOFF = PACKAGING_OUTPUT / "research_handoff.json"

RESEARCH_DIR = PROJECT_ROOT / "research_engine"
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from research_review import (
    apply_action as apply_research_gate_action,
)
from research_review import (
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

from script_review import (
    apply_action as apply_script_gate_action,
)
from script_review import (
    snapshot as script_gate_snapshot,
)
from script_section_service import (
    apply_action as apply_script_section_review_action,
    snapshot as script_section_review_snapshot,
)
from story_plan_engine import (
    validation_contract_sha256 as story_plan_validation_contract_sha256,
)
from story_script_engine import (
    load_script_psychology_config,
    resolve_script_branches,
    validation_contract_sha256 as script_validation_contract_sha256,
)

STORY_OUTPUT = STORY_DIR / "output"
STORY_PLAN_REQUESTS_DIR = STORY_OUTPUT / "story_plan_requests"
STORY_PLANS_DIR = STORY_OUTPUT / "story_plans"
SCRIPT_REQUESTS_DIR = STORY_OUTPUT / "script_requests"
SCRIPT_DRAFTS_DIR = STORY_OUTPUT / "script_drafts"
SCRIPT_APPROVED_DIR = STORY_OUTPUT / "approved_scripts"

FORMAT_DIR = PROJECT_ROOT / "format_engine"
if str(FORMAT_DIR) not in sys.path:
    sys.path.insert(0, str(FORMAT_DIR))

from format_review import (
    apply_action as apply_format_gate_action,
)
from format_review import (
    snapshot as format_gate_snapshot,
)

FORMAT_OUTPUT = FORMAT_DIR / "output"
FORMAT_REQUESTS_DIR = FORMAT_OUTPUT / "format_requests"
FORMAT_PLANS_DIR = FORMAT_OUTPUT / "format_plans"
FORMAT_APPROVED_DIR = FORMAT_OUTPUT / "approved_format_plans"

PRODUCTION_DIR = PROJECT_ROOT / "production_engine"
if str(PRODUCTION_DIR) not in sys.path:
    sys.path.insert(0, str(PRODUCTION_DIR))

from voice_performance import (
    validation_contract_sha256 as voice_validation_contract_sha256,
)
from voice_review import (
    apply_action as apply_performance_gate_action,
)
from voice_review import (
    snapshot as performance_gate_snapshot,
)
from narration_render import snapshot as narration_render_snapshot
from narration_render_import import (
    register as register_narration_render_return,
    snapshot as narration_render_return_snapshot,
)
from narration_audio_qc import snapshot as narration_audio_qc_snapshot
from pre_render_engagement import snapshot as pre_render_engagement_snapshot
from narration_preview import snapshot as narration_preview_prepare_snapshot
from sound_design_brief import snapshot as sound_design_brief_snapshot
from narration_performance_review import (
    revise as revise_narration_performance,
    snapshot as narration_performance_revision_snapshot,
)
from narration_preview_review import (
    apply_action as apply_narration_preview_gate_action,
    snapshot as narration_preview_gate_snapshot,
)
from narration_cost_review import (
    apply_action as apply_narration_spend_gate_action,
    snapshot as narration_spend_gate_snapshot,
)
from visual_candidate_review import (
    apply_action as apply_visual_candidate_review_action,
    snapshot as visual_candidate_review_snapshot,
)
from visual_rights_review import (
    apply_action as apply_visual_rights_review_action,
    snapshot as visual_rights_review_snapshot,
)
from visual_rough_cut_review import (
    apply_action as apply_visual_rough_cut_review_action,
    snapshot as visual_rough_cut_review_snapshot,
)
from visual_spend_review import (
    apply_action as apply_visual_spend_review_action,
    snapshot as visual_spend_review_snapshot,
)
from visual_generated_asset_import import (
    register as register_generated_visual_asset,
    snapshot as generated_visual_asset_snapshot,
)
from visual_existing_asset_import import (
    register as register_existing_visual_asset,
    snapshot as managed_visual_asset_snapshot,
)
from edit_preview_review import (
    apply_action as apply_edit_preview_action,
    snapshot as edit_preview_review_snapshot,
)
from storyboard_review import (
    revise as revise_storyboard_shot,
    snapshot as storyboard_review_snapshot,
)
from storyboard import snapshot as production_storyboard_snapshot
from visual_search import snapshot as visual_search_prepare_snapshot
from visual_search_acquire import snapshot as visual_search_acquire_snapshot

PRODUCTION_OUTPUT = PRODUCTION_DIR / "output"
PRODUCTION_VOICE_REQUESTS_DIR = PRODUCTION_OUTPUT / "voice_performance_requests"
PRODUCTION_VOICE_SPECS_DIR = PRODUCTION_OUTPUT / "voice_performance_specs"
PRODUCTION_ENGAGEMENT_SUMMARY = PRODUCTION_OUTPUT / "pre_render_engagement_summary.json"
PRODUCTION_PREVIEW_SUMMARY = PRODUCTION_OUTPUT / "narration_preview_summary.json"
PRODUCTION_PREVIEW_RENDER_SUMMARY = PRODUCTION_OUTPUT / "narration_preview_render_summary.json"
PRODUCTION_SOUND_REFERENCE_SUMMARY = PRODUCTION_OUTPUT / "prototype_sound_summary.json"
PRODUCTION_SOUND_BRIEF_SUMMARY = PRODUCTION_OUTPUT / "sound_design_brief_summary.json"
PRODUCTION_PREVIEW_AUDIO_DIR = PRODUCTION_OUTPUT / "narration_preview_audio"
PRODUCTION_NARRATION_RENDER_RESULTS_DIR = PRODUCTION_OUTPUT / "narration_render_results"
PRODUCTION_NARRATION_QC_SUMMARY = PRODUCTION_OUTPUT / "narration_audio_qc_summary.json"
PRODUCTION_VISUAL_MANIFESTS_DIR = PRODUCTION_OUTPUT / "visual_manifests"
PRODUCTION_STORYBOARD_DIR = PRODUCTION_OUTPUT / "storyboards"
PRODUCTION_VISUAL_SEARCH_RESULT_DIR = PRODUCTION_OUTPUT / "visual_search_results"
PRODUCTION_VISUAL_CANDIDATE_REVIEW_DIR = PRODUCTION_OUTPUT / "visual_candidate_reviews"
PRODUCTION_VISUAL_ASSET_ACQUISITION_SUMMARY = (
    PRODUCTION_OUTPUT / "visual_asset_acquisition_summary.json"
)
PRODUCTION_MANAGED_VISUAL_ASSET_DIR = (
    PRODUCTION_OUTPUT / "managed_visual_assets"
)
PRODUCTION_MANAGED_VISUAL_REGISTRY_DIR = (
    PRODUCTION_OUTPUT / "managed_visual_asset_registry"
)
PRODUCTION_VISUAL_RIGHTS_REVIEW_DIR = PRODUCTION_OUTPUT / "visual_rights_reviews"
PRODUCTION_VISUAL_ROUGH_CUT_DIR = PRODUCTION_OUTPUT / "visual_rough_cuts"
PRODUCTION_VISUAL_ROUGH_REVIEW_DIR = PRODUCTION_OUTPUT / "visual_rough_cut_reviews"
PRODUCTION_VISUAL_GAP_PLAN_DIR = PRODUCTION_OUTPUT / "visual_gap_plans"
PRODUCTION_VISUAL_GENERATION_REQUEST_DIR = (
    PRODUCTION_OUTPUT / "visual_generation_requests"
)
PRODUCTION_VISUAL_GENERATION_HANDOFF_SUMMARY = (
    PRODUCTION_OUTPUT / "visual_generation_handoff_summary.json"
)
PRODUCTION_VISUAL_ASSEMBLY_PLAN_DIR = (
    PRODUCTION_OUTPUT / "visual_assembly_plans"
)
PRODUCTION_VISUAL_ASSEMBLY_SUMMARY = (
    PRODUCTION_OUTPUT / "visual_assembly_plan_summary.json"
)
PRODUCTION_EDIT_MANIFEST_DIR = PRODUCTION_OUTPUT / "edit_manifests"
PRODUCTION_EDIT_MANIFEST_SUMMARY = PRODUCTION_OUTPUT / "edit_manifest_summary.json"
PRODUCTION_EDIT_PREVIEW_DIR = PRODUCTION_OUTPUT / "edit_previews"
PRODUCTION_EDIT_PREVIEW_RESULT_DIR = PRODUCTION_OUTPUT / "edit_preview_results"
PRODUCTION_EDIT_PREVIEW_SUMMARY = (
    PRODUCTION_OUTPUT / "edit_preview_render_summary.json"
)
PRODUCTION_FINAL_HANDOFF_DIR = (
    PRODUCTION_OUTPUT / "final_production_handoffs"
)
PRODUCTION_FINAL_HANDOFF_SUMMARY = (
    PRODUCTION_OUTPUT / "final_production_handoff_summary.json"
)

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
    "visual_asset_acquire",
    "visual_rough_cut_prepare",
    "visual_gap_prepare",
    "visual_generation_handoff_prepare",
    "visual_assembly_prepare",
    "edit_manifest_prepare",
    "edit_preview_render",
    "final_production_handoff_prepare",
]

WORKFLOW_ACTION_ORDER = [
    "opportunity_research",
    "auto_continue",
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
    "auto_continue": {
        "label": "Continue Automatically to Human Gate",
        "stage": "AUTO",
        "command": [
            sys.executable,
            "experiment_ui/workflow_automation.py",
        ],
        "description": (
            "Runs every currently ready deterministic machine step in order and "
            "stops automatically at the next human gate, prerequisite wait, or error."
        ),
    },
    "vidiq_doctor": {
        "label": "Connect / Check vidIQ (0 paid credits)",
        "stage": "OPPORTUNITY",
        "command": [
            sys.executable,
            "experiment_01_discovery/vidiq_opportunity_enrichment.py",
            "--mode",
            "doctor",
        ],
        "description": (
            "Uses vidIQ's OAuth MCP connection, opens browser authorization on "
            "first use, then checks required research tools and the free credit "
            "balance without calling any paid research tool."
        ),
    },
    "vidiq_enrich": {
        "label": "Run vidIQ Opportunity Check",
        "stage": "OPPORTUNITY",
        "command": [
            sys.executable,
            "experiment_01_discovery/vidiq_opportunity_enrichment.py",
            "--mode",
            "enrich",
        ],
        "description": (
            "Adds keyword, outlier and trending evidence to the current 01.5 "
            "opportunities. The adapter checks provider balance before every paid "
            "call, preserves a reserve, caches results, and hard-stops at 149 credits."
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
            "Uses FAIR free-only routing in resumable 5-concept chunks, advances "
            "up to 10 finalists, then produces a final 0-6 shortlist for human review."
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
    "story_prepare": {
        "label": "Prepare Story Plan Requests",
        "stage": "07",
        "command": [
            sys.executable,
            "story_script_engine/story_plan_engine.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Builds story-structure requests from verified research and the "
            "approved title/package before any narration is written."
        ),
    },
    "story_generate": {
        "label": "Generate Story Plans",
        "stage": "07",
        "command": [
            sys.executable,
            "story_script_engine/story_plan_model_runner.py",
            "--mode",
            "batch",
        ],
        "description": (
            "Uses FAIR free-only routing to plan the hook, viewer journey, "
            "reveal and payoff while keeping the approved title immutable."
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
        "description": ("Prepares the human Script Gate before production."),
    },
    "format_prepare": {
        "label": "Prepare Format Requests",
        "stage": "08",
        "command": [
            sys.executable,
            "format_engine/format_engine.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Builds per-branch format requests from human-approved scripts. "
            "Long-form and Shorts are planned as separate productions."
        ),
    },
    "format_generate": {
        "label": "Generate Format Plans",
        "stage": "08",
        "command": [
            sys.executable,
            "format_engine/format_model_runner.py",
            "--mode",
            "batch",
        ],
        "description": (
            "Uses FAIR free-only routing to plan each required branch, "
            "rejecting identical or truncated timelines."
        ),
    },
    "format_gate_prepare": {
        "label": "Prepare Format Gate",
        "stage": "08",
        "command": [
            sys.executable,
            "format_engine/format_review.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Prepares the human Format Gate before the Production Engine."
        ),
    },
    "voice_prepare": {
        "label": "Prepare Voice Performance Requests",
        "stage": "09",
        "command": [
            sys.executable,
            "production_engine/voice_performance.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Binds each accepted format beat to immutable approved narration "
            "before any voice rendering or paid provider call."
        ),
    },
    "voice_generate": {
        "label": "Generate Voice Performance Plans",
        "stage": "09",
        "command": [
            sys.executable,
            "production_engine/voice_model_runner.py",
            "--mode",
            "batch",
        ],
        "description": (
            "Uses FAIR free-only routing to annotate emotion, pace, pauses and "
            "emphasis without changing spoken words."
        ),
    },
    "voice_gate_prepare": {
        "label": "Prepare Performance Gate",
        "stage": "09",
        "command": [
            sys.executable,
            "production_engine/voice_review.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Prepares the mandatory Human Performance Gate before any paid "
            "narration render can be introduced."
        ),
    },
    "pre_render_engagement": {
        "label": "Validate Pre-Render Engagement",
        "stage": "09",
        "command": [sys.executable, "production_engine/pre_render_engagement.py", "--mode", "batch"],
        "description": "Deterministically checks hook, problem/tension, payoff, exposition length and delivery variation before narration spend.",
    },
    "narration_preview_prepare": {
        "label": "Prepare Free Narration Prototype",
        "stage": "09",
        "command": [sys.executable, "production_engine/narration_preview.py", "--mode", "prepare"],
        "description": "Builds a zero-cost narration prototype with delivery plus music/SFX suggestions; no paid provider is allowed.",
    },
    "prototype_sound_prepare": {
        "label": "Prepare Reference Music + SFX",
        "stage": "09",
        "command": [sys.executable, "production_engine/prototype_sound.py", "--mode", "prepare"],
        "description": "Prepares local AudioGen/MusicGen reference prompts only. Generated media is quarantined and forbidden from final export.",
    },
    "narration_preview_render": {
        "label": "Render Free Narration Prototype",
        "stage": "09",
        "command": [sys.executable, "production_engine/narration_preview_render.py", "--mode", "batch"],
        "description": "Renders the listenable prototype locally with Kokoro. Missing local TTS stops fail-closed; there is no paid fallback.",
    },
    "sound_design_brief_prepare": {
        "label": "Build Approved Sound Design Brief",
        "stage": "09",
        "command": [sys.executable, "production_engine/sound_design_brief.py", "--mode", "prepare"],
        "description": "After the free listen gate, transfers descriptive sound intent only; no prototype AudioGen/MusicGen media crosses into final production.",
    },
    "narration_prepare": {
        "label": "Prepare Narration Render + Cost Boundary",
        "stage": "09",
        "command": [sys.executable, "production_engine/narration_render.py", "--mode", "prepare"],
        "description": "Builds immutable narration render requests and quote templates without making a paid provider call.",
    },
    "narration_spend_gate_prepare": {
        "label": "Prepare Narration Spend Gate",
        "stage": "09",
        "command": [sys.executable, "production_engine/narration_cost_review.py", "--mode", "prepare"],
        "description": "Prepares human approval of the current provider quote and worst-case narration cost.",
    },
    "narration_audio_qc": {
        "label": "Run Narration Audio QC + Timing Map",
        "stage": "09",
        "command": [sys.executable, "production_engine/narration_audio_qc.py", "--mode", "batch"],
        "description": "Runs local deterministic audio checks and writes narration timing maps.",
    },
    "storyboard_prepare": {
        "label": "Build Cinematic Storyboard",
        "stage": "09",
        "command": [sys.executable, "production_engine/storyboard.py", "--mode", "prepare"],
        "description": "Turns final narration timing into search-first shot cards with cinematic direction; no paid generation is authorized.",
    },
    "visual_search_prepare": {
        "label": "Prepare Visual Search",
        "stage": "09",
        "command": [sys.executable, "production_engine/visual_search.py", "--mode", "prepare"],
        "description": "Builds rights-aware search requests from storyboard shots.",
    },
    "visual_search_acquire": {
        "label": "Search Free / Existing Visuals",
        "stage": "09",
        "command": [sys.executable, "production_engine/visual_search_acquire.py", "--mode", "acquire"],
        "description": "Searches configured zero-cost stock and creator-discovery adapters, then stops for human candidate review.",
    },
    "visual_asset_acquire": {
        "label": "Acquire Approved Free Visual Assets",
        "stage": "09",
        "command": [
            sys.executable,
            "production_engine/visual_asset_acquire.py",
            "--mode",
            "acquire",
        ],
        "description": (
            "Copies approved local-library assets and downloads only verified "
            "zero-cost stock media from allow-listed Pexels/Pixabay hosts. "
            "Creator/editorial footage is never auto-downloaded."
        ),
    },
    "visual_rough_cut_prepare": {
        "label": "Build Visual Rough Cut",
        "stage": "09",
        "command": [sys.executable, "production_engine/visual_rough_cut.py"],
        "description": (
            "Builds a storyboard-aware rough-cut manifest only after current "
            "visual selections and any required rights/context decisions are complete."
        ),
    },
    "visual_gap_prepare": {
        "label": "Plan Remaining Visual Gaps",
        "stage": "09",
        "command": [sys.executable, "production_engine/visual_gap_planner.py"],
        "description": (
            "Plans unresolved visual gaps after human rough-cut approval. "
            "This step never authorizes paid generation."
        ),
    },
    "visual_generation_handoff_prepare": {
        "label": "Prepare Premium Visual Generation Briefs",
        "stage": "09",
        "command": [
            sys.executable,
            "production_engine/visual_generation_handoff.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Converts only human-authorized unresolved hero shots into "
            "provider-neutral generation briefs with cinematic direction and "
            "hard per-shot cost ceilings. No provider is called and no money is spent."
        ),
    },
    "visual_assembly_prepare": {
        "label": "Build Visual Edit Assembly Plan",
        "stage": "09",
        "command": [
            sys.executable,
            "production_engine/visual_assembly_plan.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Builds a deterministic edit timeline from approved existing assets, "
            "editorial excerpts, placeholders and premium-generation slots. "
            "It renders no media and makes no provider calls."
        ),
    },
    "edit_manifest_prepare": {
        "label": "Build Edit Preview Manifest",
        "stage": "10",
        "command": [
            sys.executable,
            "production_engine/edit_manifest.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Combines current narration timing, visual assembly and approved "
            "sound-design intent into a deterministic structural edit manifest. "
            "Missing visuals remain explicit placeholders."
        ),
    },
    "edit_preview_render": {
        "label": "Render Free Structural Edit Preview",
        "stage": "10",
        "command": [
            sys.executable,
            "production_engine/edit_preview_render.py",
            "--mode",
            "batch",
        ],
        "description": (
            "Uses local FFmpeg to render a non-publishable preview with current "
            "visual assets/placeholders and QC-passed narration. No paid provider "
            "or generated music/SFX is used."
        ),
    },
    "final_production_handoff_prepare": {
        "label": "Prepare Final Production Handoff",
        "stage": "11",
        "command": [
            sys.executable,
            "production_engine/final_production_handoff.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Builds a provenance-bound provider-neutral final production package "
            "from the approved structural edit, current visual assets, narration "
            "and sound-design intent. It makes no provider call and spends nothing."
        ),
    },
    "production_visual_prepare": {
        "label": "Prepare Visual Acquisition Manifest",
        "stage": "09",
        "command": [
            sys.executable,
            "production_engine/visual_acquisition.py",
            "--mode",
            "prepare",
        ],
        "description": (
            "Converts accepted format beats into cheap-first visual requirements "
            "without searching, downloading media, or spending credits."
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
    "format_output": FORMAT_OUTPUT,
    "production_output": PRODUCTION_OUTPUT,
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
            minimum_channels = int(config.get("minimum_unique_channels", 3))
        except (TypeError, ValueError):
            minimum_channels = 3
        try:
            minimum_velocity = int(config.get("minimum_velocity_samples", 3))
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
    return {item.stem for item in path.glob("*.json") if item.is_file()}


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
        if not isinstance(transcript, dict) or transcript.get("status") != "PROVIDED":
            continue
        evidence = payload.get("evidence", [])
        if not isinstance(evidence, list):
            continue
        if any(
            isinstance(item, dict) and item.get("type") == "transcript"
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
            if not enriched_path.exists() or not isinstance(request, dict):
                continue
            provenance = request.get("request_provenance", {})
            if isinstance(provenance, dict) and provenance.get(
                "profile_sha256"
            ) == sha256_file(enriched_path):
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
        for request_path in EXP2_REVIEW_REQUESTS_DIR.glob("*.review_request.json"):
            video_id = request_path.name[: -len(".review_request.json")]
            analyzed_path = EXP2_ANALYZED_DIR / f"{video_id}.json"
            request = safe_load_json(request_path)
            if not analyzed_path.exists() or not isinstance(request, dict):
                continue
            provenance = request.get("request_provenance", {})
            if isinstance(provenance, dict) and provenance.get(
                "profile_sha256"
            ) == sha256_file(analyzed_path):
                review_request_ids.add(video_id)

    reviewed_ids: set[str] = set()
    for video_id in analyzed_ids:
        analyzed_path = EXP2_ANALYZED_DIR / f"{video_id}.json"
        request_path = EXP2_REVIEW_REQUESTS_DIR / f"{video_id}.review_request.json"
        reviewed_path = EXP2_REVIEWED_DIR / f"{video_id}.json"
        report_path = (
            EXP2_OUTPUT / "human_review_reports" / f"{video_id}.human_review.json"
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
        "visual_attempted_count": len(prepared_ids.intersection(visual_report_ids)),
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
    validation_contract = transformation_validation_contract_sha256()
    handoff_hash = (
        sha256_file(EXP2_SYNTHESIS_FILE) if EXP2_SYNTHESIS_FILE.exists() else None
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

    current_response_hashes: dict[str, str] = {}
    if TRANSFORM_RESPONSES_DIR.exists():
        for path in TRANSFORM_RESPONSES_DIR.glob("*.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            mechanism_id = str(payload.get("mechanism_id") or "").strip()
            provenance = payload.get("response_provenance", {})
            report = safe_load_json(
                TRANSFORM_MODEL_RUNS_DIR
                / f"{transformation_safe_slug(mechanism_id)}.model_run.json"
            )
            if (
                mechanism_id in request_hashes
                and isinstance(provenance, dict)
                and provenance.get("request_sha256") == request_hashes[mechanism_id]
                and provenance.get("validation_contract_sha256")
                == validation_contract
                and isinstance(report, dict)
                and report.get("status") == "VALIDATED"
                and report.get("request_sha256") == request_hashes[mechanism_id]
                and report.get("validation_contract_sha256")
                == validation_contract
            ):
                current_response_hashes[mechanism_id] = sha256_file(path)

    candidates = safe_load_json(TRANSFORM_CANDIDATES_FILE)
    candidate_count = (
        int(candidates.get("count") or 0) if isinstance(candidates, dict) else 0
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
        int(triaged.get("concept_count") or 0) if isinstance(triaged, dict) else 0
    )
    requests_ready = bool(request_hashes)
    responses_complete = requests_ready and set(request_hashes).issubset(
        current_response_hashes
    )
    candidate_provenance = (
        candidates.get("source_response_sha256", {})
        if isinstance(candidates, dict)
        else {}
    )
    candidate_pool_ready = (
        candidates.get("ready_for_triage") is True
        if isinstance(candidates, dict)
        else False
    )
    minimum_candidates = (
        int(candidates.get("minimum_candidates_for_triage") or 0)
        if isinstance(candidates, dict)
        else 0
    )
    candidates_current = (
        isinstance(candidate_provenance, dict)
        and bool(candidate_provenance)
        and candidate_provenance == current_response_hashes
    )
    candidates_ready = (
        candidate_pool_ready
        and candidate_count >= minimum_candidates
        and candidates_current
    )
    gate = (
        concept_gate_snapshot()
        if candidates_ready and triage_ready
        else {
            "status": (
                "WAITING_FOR_TRIAGED_CONCEPTS"
                if candidates_ready and not triage_ready
                else "WAITING_FOR_CONCEPT_CANDIDATES"
            ),
            "complete": False,
            "concepts": [],
        }
    )
    research_handoff = safe_load_json(TRANSFORM_RESEARCH_HANDOFF)
    research_ready = (
        isinstance(research_handoff, dict)
        and research_handoff.get("status") == "READY_FOR_RESEARCH"
        and bool(gate.get("complete"))
    )
    return {
        "handoff_sha256": handoff_hash,
        "validation_contract_sha256": validation_contract,
        "request_mechanism_ids": sorted(request_hashes),
        "current_response_mechanism_ids": sorted(current_response_hashes),
        "candidate_provenance_current": candidates_current,
        "candidate_pool_ready": candidate_pool_ready,
        "minimum_candidates_for_triage": minimum_candidates,
        "mechanism_coverage_complete": (
            bool(candidates.get("mechanism_coverage_complete"))
            if isinstance(candidates, dict)
            else False
        ),
        "missing_mechanism_ids": (
            list(candidates.get("missing_mechanism_ids", []))
            if isinstance(candidates, dict)
            else []
        ),
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
    packaging_config_hash = (
        sha256_file(PACKAGING_CONFIG_FILE)
        if PACKAGING_CONFIG_FILE.exists()
        else None
    )
    request_hashes: dict[str, str] = {}
    if handoff_hash and packaging_config_hash and PACKAGING_REQUESTS_DIR.exists():
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
                and provenance.get("packaging_config_sha256")
                == packaging_config_hash
            ):
                request_hashes[concept_id] = sha256_file(path)

    current_response_hashes: dict[str, str] = {}
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
                current_response_hashes[concept_id] = sha256_file(path)

    candidates = safe_load_json(PACKAGING_CANDIDATES_FILE)
    candidate_count = (
        int(candidates.get("count") or 0) if isinstance(candidates, dict) else 0
    )
    requests_ready = bool(request_hashes)
    responses_complete = requests_ready and set(request_hashes).issubset(
        current_response_hashes
    )
    candidate_provenance = (
        candidates.get("source_response_sha256", {})
        if isinstance(candidates, dict)
        else {}
    )
    candidates_current = (
        isinstance(candidate_provenance, dict)
        and candidate_provenance == current_response_hashes
    )
    candidates_ready = responses_complete and candidate_count > 0 and candidates_current
    gate = (
        packaging_gate_snapshot()
        if candidates_ready
        else {
            "status": "WAITING_FOR_PACKAGE_CANDIDATES",
            "complete": False,
            "packages": [],
        }
    )
    research_handoff = safe_load_json(PACKAGING_RESEARCH_HANDOFF)
    research_ready = (
        isinstance(research_handoff, dict)
        and research_handoff.get("status") == "READY_FOR_RESEARCH"
        and bool(gate.get("complete"))
    )
    return {
        "handoff_sha256": handoff_hash,
        "packaging_config_sha256": packaging_config_hash,
        "request_concept_ids": sorted(request_hashes),
        "current_response_concept_ids": sorted(current_response_hashes),
        "candidate_provenance_current": candidates_current,
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
                and provenance.get("packaging_handoff_sha256") == packaging_handoff_hash
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
                and payload.get("status") == "COMPLETE"
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
    gate = (
        research_gate_snapshot()
        if drafts_ready
        else {
            "status": "WAITING_FOR_DRAFT_RESEARCH_PACKAGES",
            "complete": False,
            "claims": [],
        }
    )
    verified_value = gate.get("verified_packages", []) if isinstance(gate, dict) else []
    verified = verified_value if isinstance(verified_value, list) else []
    story_ready = (
        bool(gate.get("complete"))
        and bool(verified)
        and all(
            isinstance(item, dict) and item.get("status") == "READY_FOR_STORY_SCRIPT"
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
    story_plan_contract = story_plan_validation_contract_sha256()
    script_contract = script_validation_contract_sha256()
    script_profile_config = load_script_psychology_config()

    verified_hashes: dict[str, str] = {}
    if upstream.get("story_ready") and RESEARCH_VERIFIED_DIR.exists():
        for path in RESEARCH_VERIFIED_DIR.glob("*.verified_research_package.json"):
            payload = safe_load_json(path)
            if (
                not isinstance(payload, dict)
                or payload.get("status") != "READY_FOR_STORY_SCRIPT"
            ):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            if concept_id:
                verified_hashes[concept_id] = sha256_file(path)

    story_request_hashes: dict[str, str] = {}
    if STORY_PLAN_REQUESTS_DIR.exists():
        for path in STORY_PLAN_REQUESTS_DIR.glob("*.story_plan_request.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            provenance = payload.get("request_provenance", {})
            if (
                concept_id in verified_hashes
                and isinstance(provenance, dict)
                and provenance.get("verified_research_sha256")
                == verified_hashes[concept_id]
            ):
                story_request_hashes[concept_id] = sha256_file(path)

    story_plan_hashes: dict[str, str] = {}
    expected_branch_ids: set[str] = set()
    if STORY_PLANS_DIR.exists():
        for path in STORY_PLANS_DIR.glob("*.story_plan.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            provenance = payload.get("plan_provenance", {})
            if (
                concept_id in story_request_hashes
                and payload.get("status") == "STORY_PLAN_READY"
                and isinstance(provenance, dict)
                and provenance.get("request_sha256")
                == story_request_hashes[concept_id]
                and provenance.get("validation_contract_sha256")
                == story_plan_contract
            ):
                story_plan_hashes[concept_id] = sha256_file(path)
                package = payload.get("package", {})
                if isinstance(package, dict):
                    try:
                        branches = resolve_script_branches(
                            str(package.get("format_intent") or ""),
                            script_profile_config,
                        )
                    except ValueError:
                        branches = []
                    for fmt in branches:
                        expected_branch_ids.add(f"{concept_id}:{fmt}")

    request_hashes: dict[str, str] = {}
    if SCRIPT_REQUESTS_DIR.exists():
        for path in SCRIPT_REQUESTS_DIR.glob("*.script_request.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            fmt = str(payload.get("format") or "").strip()
            branch_id = f"{concept_id}:{fmt}" if concept_id and fmt else ""
            provenance = payload.get("request_provenance", {})
            if (
                branch_id in expected_branch_ids
                and concept_id in story_plan_hashes
                and isinstance(provenance, dict)
                and provenance.get("story_plan_sha256")
                == story_plan_hashes[concept_id]
            ):
                request_hashes[branch_id] = sha256_file(path)

    draft_ids: set[str] = set()
    if SCRIPT_DRAFTS_DIR.exists():
        for path in SCRIPT_DRAFTS_DIR.glob("*.script_draft.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            fmt = str(payload.get("format") or "").strip()
            branch_id = f"{concept_id}:{fmt}" if concept_id and fmt else ""
            provenance = payload.get("draft_provenance", {})
            if (
                branch_id in request_hashes
                and isinstance(provenance, dict)
                and provenance.get("request_sha256") == request_hashes[branch_id]
                and provenance.get("validation_contract_sha256")
                == script_contract
            ):
                draft_ids.add(branch_id)

    gate = (
        script_gate_snapshot()
        if draft_ids
        else {
            "status": "WAITING_FOR_SCRIPT_DRAFTS",
            "complete": False,
            "scripts": [],
            "production_ready_concept_ids": [],
        }
    )
    ready_value = gate.get("production_ready_concept_ids", [])
    ready_items = ready_value if isinstance(ready_value, list) else []
    ready_ids = {
        str(item)
        for item in ready_items
        if str(item).strip()
    }

    story_requests_ready = bool(verified_hashes) and set(verified_hashes).issubset(
        story_request_hashes
    )
    story_plans_ready = story_requests_ready and set(verified_hashes).issubset(
        story_plan_hashes
    )
    requests_ready = (
        story_plans_ready
        and bool(expected_branch_ids)
        and expected_branch_ids.issubset(request_hashes)
    )
    drafts_ready = requests_ready and expected_branch_ids.issubset(draft_ids)
    production_ready = (
        drafts_ready
        and set(verified_hashes).issubset(ready_ids)
    )
    return {
        "story_plan_validation_contract_sha256": story_plan_contract,
        "script_validation_contract_sha256": script_contract,
        "verified_concept_ids": sorted(verified_hashes),
        "story_request_concept_ids": sorted(story_request_hashes),
        "story_plan_concept_ids": sorted(story_plan_hashes),
        "expected_branch_ids": sorted(expected_branch_ids),
        "request_branch_ids": sorted(request_hashes),
        "draft_branch_ids": sorted(draft_ids),
        "request_concept_ids": sorted(
            {item.split(":", 1)[0] for item in request_hashes}
        ),
        "draft_concept_ids": sorted(
            {item.split(":", 1)[0] for item in draft_ids}
        ),
        "story_requests_ready": story_requests_ready,
        "story_plans_ready": story_plans_ready,
        "requests_ready": requests_ready,
        "drafts_ready": drafts_ready,
        "script_gate": gate,
        "script_gate_complete": bool(gate.get("complete")),
        "production_ready": production_ready,
    }


def format_artifact_state() -> dict[str, Any]:
    upstream = story_script_artifact_state()
    approved_hashes: dict[str, str] = {}
    if upstream.get("production_ready") and SCRIPT_APPROVED_DIR.exists():
        for path in SCRIPT_APPROVED_DIR.glob("*.approved_script.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            gate_info = payload.get("script_gate", {})
            if (
                not isinstance(gate_info, dict)
                or gate_info.get("status") != "READY_FOR_PRODUCTION"
            ):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            if concept_id:
                approved_hashes[concept_id] = sha256_file(path)

    request_hashes: dict[str, str] = {}
    if FORMAT_REQUESTS_DIR.exists():
        for path in FORMAT_REQUESTS_DIR.glob("*.format_request.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            provenance = payload.get("request_provenance", {})
            if (
                concept_id in approved_hashes
                and isinstance(provenance, dict)
                and provenance.get("approved_script_sha256")
                == approved_hashes[concept_id]
            ):
                request_hashes[concept_id] = sha256_file(path)

    plan_ids: set[str] = set()
    if FORMAT_PLANS_DIR.exists():
        for path in FORMAT_PLANS_DIR.glob("*.format_plan.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            provenance = payload.get("plan_provenance", {})
            if (
                concept_id in request_hashes
                and isinstance(provenance, dict)
                and provenance.get("request_sha256") == request_hashes[concept_id]
            ):
                plan_ids.add(concept_id)

    gate = (
        format_gate_snapshot()
        if plan_ids
        else {
            "status": "WAITING_FOR_FORMAT_PLANS",
            "complete": False,
            "plans": [],
        }
    )
    plans_value = gate.get("plans", [])
    plans = plans_value if isinstance(plans_value, list) else []
    approved_ids = {
        str(item.get("concept_id"))
        for item in plans
        if isinstance(item, dict) and item.get("decision") == "ACCEPT"
    }

    requests_ready = bool(approved_hashes) and set(approved_hashes).issubset(
        request_hashes
    )
    plans_ready = requests_ready and set(approved_hashes).issubset(plan_ids)
    production_engine_ready = (
        plans_ready
        and bool(gate.get("complete"))
        and set(approved_hashes).issubset(approved_ids)
    )
    return {
        "approved_script_concept_ids": sorted(approved_hashes),
        "request_concept_ids": sorted(request_hashes),
        "plan_concept_ids": sorted(plan_ids),
        "requests_ready": requests_ready,
        "plans_ready": plans_ready,
        "format_gate": gate,
        "format_gate_complete": bool(gate.get("complete")),
        "production_engine_ready": production_engine_ready,
    }


def voice_performance_artifact_state() -> dict[str, Any]:
    """Return provenance-aware Voice Performance coverage and gate state."""
    fmt = format_artifact_state()
    if not fmt.get("production_engine_ready"):
        return {
            "expected_branches": [],
            "request_branches": [],
            "spec_branches": [],
            "requests_ready": False,
            "specs_ready": False,
            "performance_gate": {
                "status": "WAITING_FOR_VOICE_PERFORMANCE_SPECS",
                "complete": False,
                "specs": [],
            },
            "performance_gate_complete": False,
            "visual_ready": False,
        }

    gate = fmt.get("format_gate", {})
    plans_value = gate.get("plans", []) if isinstance(gate, dict) else []
    accepted_ids = {
        str(item.get("concept_id") or "").strip()
        for item in plans_value
        if isinstance(item, dict) and item.get("decision") == "ACCEPT"
    }
    accepted_ids.discard("")

    plan_hashes: dict[str, str] = {}
    expected: set[tuple[str, str]] = set()
    if FORMAT_APPROVED_DIR.exists():
        for path in FORMAT_APPROVED_DIR.glob("*.approved_format_plan.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            if concept_id not in accepted_ids:
                continue
            plan_hashes[concept_id] = sha256_file(path)
            branches = payload.get("branches", [])
            if not isinstance(branches, list):
                continue
            for branch in branches:
                if not isinstance(branch, dict):
                    continue
                branch_format = str(branch.get("format") or "").strip()
                if branch_format:
                    expected.add((concept_id, branch_format))

    request_hashes: dict[tuple[str, str], str] = {}
    if PRODUCTION_VOICE_REQUESTS_DIR.exists():
        for path in PRODUCTION_VOICE_REQUESTS_DIR.glob("*.voice_request.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            key = (
                str(payload.get("concept_id") or "").strip(),
                str(payload.get("format") or "").strip(),
            )
            provenance = payload.get("request_provenance", {})
            if (
                key in expected
                and isinstance(provenance, dict)
                and provenance.get("approved_format_plan_sha256")
                == plan_hashes.get(key[0])
            ):
                request_hashes[key] = sha256_file(path)

    contract_hash = voice_validation_contract_sha256()
    spec_keys: set[tuple[str, str]] = set()
    if PRODUCTION_VOICE_SPECS_DIR.exists():
        for path in PRODUCTION_VOICE_SPECS_DIR.glob(
            "*.voice_performance_spec.json"
        ):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            key = (
                str(payload.get("concept_id") or "").strip(),
                str(payload.get("format") or "").strip(),
            )
            provenance = payload.get("spec_provenance", {})
            if (
                key in request_hashes
                and isinstance(provenance, dict)
                and provenance.get("request_sha256") == request_hashes[key]
                and provenance.get("validation_contract_sha256")
                == contract_hash
            ):
                spec_keys.add(key)

    requests_ready = bool(expected) and expected.issubset(request_hashes)
    specs_ready = requests_ready and expected.issubset(spec_keys)
    performance_gate = (
        performance_gate_snapshot()
        if specs_ready
        else {
            "status": "WAITING_FOR_VOICE_PERFORMANCE_SPECS",
            "complete": False,
            "specs": [],
        }
    )
    gate_specs = (
        performance_gate.get("specs", [])
        if isinstance(performance_gate, dict)
        else []
    )
    accepted = {
        (
            str(item.get("concept_id") or "").strip(),
            str(item.get("format") or "").strip(),
        )
        for item in gate_specs
        if isinstance(item, dict) and item.get("decision") == "ACCEPT"
    }
    gate_complete = bool(
        isinstance(performance_gate, dict)
        and performance_gate.get("complete")
    )
    visual_ready = specs_ready and gate_complete and expected.issubset(accepted)
    return {
        "expected_branches": [
            {"concept_id": concept_id, "format": branch_format}
            for concept_id, branch_format in sorted(expected)
        ],
        "request_branches": [
            {"concept_id": concept_id, "format": branch_format}
            for concept_id, branch_format in sorted(request_hashes)
        ],
        "spec_branches": [
            {"concept_id": concept_id, "format": branch_format}
            for concept_id, branch_format in sorted(spec_keys)
        ],
        "requests_ready": requests_ready,
        "specs_ready": specs_ready,
        "performance_gate": performance_gate,
        "performance_gate_complete": gate_complete,
        "visual_ready": visual_ready,
    }


def narration_artifact_state() -> dict[str, Any]:
    """Return narration spend, registered provider return and live Audio QC state."""
    voice = voice_performance_artifact_state()
    if not voice.get("visual_ready"):
        return {
            "render": {
                "status": "WAITING_FOR_PERFORMANCE_APPROVAL",
                "prepared": 0,
                "ready_for_spend_gate": 0,
                "items": [],
            },
            "spend_gate": {
                "status": "WAITING_FOR_PROVIDER_QUOTE",
                "complete": False,
                "items": [],
            },
            "render_return": {
                "status": "WAITING_FOR_SPEND_APPROVAL",
                "expected": 0,
                "current": 0,
                "items": [],
            },
            "render_results_present": False,
            "audio_qc": {
                "status": "WAITING_FOR_NARRATION_RENDER_RESULTS",
                "processed": 0,
                "passed": 0,
                "failed": 0,
                "items": [],
            },
            "audio_ready": False,
        }

    render = narration_render_snapshot()
    spend_gate = narration_spend_gate_snapshot()
    render_return = narration_render_return_snapshot()
    audio_qc = narration_audio_qc_snapshot()
    expected_returns = int(render_return.get("expected") or 0)
    current_returns = int(render_return.get("current") or 0)
    render_results_present = bool(
        expected_returns > 0 and current_returns == expected_returns
    )
    audio_ready = bool(
        render_results_present
        and audio_qc.get("status") == "PASS"
        and int(audio_qc.get("processed") or 0) == expected_returns
        and int(audio_qc.get("passed") or 0) == expected_returns
    )
    return {
        "render": render,
        "spend_gate": spend_gate,
        "render_return": render_return,
        "render_results_present": render_results_present,
        "audio_qc": audio_qc,
        "audio_ready": audio_ready,
    }


def production_visual_artifact_state() -> dict[str, Any]:
    """Return visual-manifest coverage bound to current final narration timing."""
    fmt = format_artifact_state()
    narration = narration_artifact_state()
    if not fmt.get("production_engine_ready") or not narration.get("audio_ready"):
        return {
            "expected_branches": [],
            "current_branches": [],
            "manifests_ready": False,
            "manifest_count": 0,
            "timing_ready": False,
        }

    gate = fmt.get("format_gate", {})
    plans_value = gate.get("plans", []) if isinstance(gate, dict) else []
    accepted_ids = {
        str(item.get("concept_id") or "").strip()
        for item in plans_value
        if isinstance(item, dict) and item.get("decision") == "ACCEPT"
    }
    accepted_ids.discard("")

    plan_hashes: dict[str, str] = {}
    expected: set[tuple[str, str]] = set()
    if FORMAT_APPROVED_DIR.exists():
        for path in FORMAT_APPROVED_DIR.glob("*.approved_format_plan.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            if concept_id not in accepted_ids:
                continue
            plan_hashes[concept_id] = sha256_file(path)
            branches = payload.get("branches", [])
            if not isinstance(branches, list):
                continue
            for branch in branches:
                if not isinstance(branch, dict):
                    continue
                branch_format = str(branch.get("format") or "").strip()
                if branch_format:
                    expected.add((concept_id, branch_format))

    timing_hashes: dict[tuple[str, str], tuple[str, str]] = {}
    audio_qc = narration.get("audio_qc", {})
    for item in audio_qc.get("items", []) if isinstance(audio_qc, dict) else []:
        if not isinstance(item, dict) or item.get("status") != "PASS":
            continue
        concept_id = str(item.get("concept_id") or "").strip()
        branch_format = str(item.get("format") or "").strip()
        timing_path = Path(str(item.get("timing_map") or ""))
        if concept_id and branch_format and timing_path.is_file():
            timing_hashes[(concept_id, branch_format)] = (
                str(timing_path.resolve()),
                sha256_file(timing_path),
            )

    current: set[tuple[str, str]] = set()
    if PRODUCTION_VISUAL_MANIFESTS_DIR.exists():
        for path in PRODUCTION_VISUAL_MANIFESTS_DIR.glob(
            "*.visual_manifest.json"
        ):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                continue
            concept_id = str(payload.get("concept_id") or "").strip()
            branch_format = str(payload.get("format") or "").strip()
            key = (concept_id, branch_format)
            timing = timing_hashes.get(key)
            provenance = payload.get("manifest_provenance", {})
            if (
                concept_id in plan_hashes
                and branch_format
                and timing is not None
                and isinstance(provenance, dict)
                and provenance.get("approved_format_plan_sha256")
                == plan_hashes[concept_id]
                and provenance.get("narration_timing_map")
                == timing[0]
                and provenance.get("narration_timing_map_sha256")
                == timing[1]
            ):
                current.add(key)

    timing_ready = bool(expected) and expected.issubset(set(timing_hashes))
    ready = timing_ready and expected.issubset(current)
    return {
        "expected_branches": [
            {"concept_id": concept_id, "format": branch_format}
            for concept_id, branch_format in sorted(expected)
        ],
        "current_branches": [
            {"concept_id": concept_id, "format": branch_format}
            for concept_id, branch_format in sorted(current)
        ],
        "manifests_ready": ready,
        "manifest_count": len(current),
        "timing_ready": timing_ready,
    }


def visual_post_search_artifact_state() -> dict[str, Any]:
    candidate_gate = visual_candidate_review_snapshot()
    rights_gate = visual_rights_review_snapshot()
    candidate_complete = bool(candidate_gate.get("complete"))
    rights_complete = bool(rights_gate.get("complete"))

    expected: set[tuple[str, str]] = set()
    rough_current: set[tuple[str, str]] = set()
    for packet in candidate_gate.get("packets", []):
        if not isinstance(packet, dict):
            continue
        concept_id = str(packet.get("concept_id") or "")
        branch_format = str(packet.get("format") or "")
        result_file = Path(str(packet.get("result_file") or ""))
        if not concept_id or not branch_format or not result_file.name:
            continue
        expected.add((concept_id, branch_format))
        base = result_file.name.replace(".visual_search_results.json", "")
        board_path = PRODUCTION_STORYBOARD_DIR / f"{base}.storyboard.json"
        review_path = (
            PRODUCTION_VISUAL_CANDIDATE_REVIEW_DIR
            / f"{base}.visual_candidate_review.json"
        )
        rights_path = (
            PRODUCTION_VISUAL_RIGHTS_REVIEW_DIR
            / f"{base}.visual_rights_review.json"
        )
        rough_path = (
            PRODUCTION_VISUAL_ROUGH_CUT_DIR
            / f"{base}.visual_rough_cut.json"
        )
        if not (
            board_path.exists()
            and review_path.exists()
            and rough_path.exists()
        ):
            continue
        rough = safe_load_json(rough_path)
        if not isinstance(rough, dict):
            continue
        provenance = rough.get("provenance", {})
        if not isinstance(provenance, dict):
            continue
        if (
            provenance.get("storyboard_sha256") != sha256_file(board_path)
            or provenance.get("candidate_review_sha256")
            != sha256_file(review_path)
        ):
            continue
        rights_required = any(
            isinstance(decision, dict)
            and decision.get("status")
            == "SELECTED_PENDING_RIGHTS_CONTEXT_GATE"
            for decision in packet.get("decisions", {}).values()
        )
        if rights_required:
            if (
                not rights_path.exists()
                or provenance.get("rights_review_sha256")
                != sha256_file(rights_path)
            ):
                continue
        elif provenance.get("rights_review_sha256") not in {None, ""}:
            continue
        rough_current.add((concept_id, branch_format))

    rough_cuts_ready = (
        candidate_complete
        and rights_complete
        and bool(expected)
        and expected.issubset(rough_current)
    )
    rough_gate = (
        visual_rough_cut_review_snapshot()
        if rough_cuts_ready
        else {
            "status": "WAITING_FOR_ROUGH_CUT",
            "complete": False,
            "items": [],
        }
    )

    gap_current: set[tuple[str, str]] = set()
    if bool(rough_gate.get("complete")):
        for item in rough_gate.get("items", []):
            if not isinstance(item, dict):
                continue
            concept_id = str(item.get("concept_id") or "")
            branch_format = str(item.get("format") or "")
            rough_path = Path(str(item.get("rough_cut_file") or ""))
            if not concept_id or not branch_format or not rough_path.exists():
                continue
            base = rough_path.name.replace(".visual_rough_cut.json", "")
            review_path = (
                PRODUCTION_VISUAL_ROUGH_REVIEW_DIR
                / f"{base}.visual_rough_cut_review.json"
            )
            gap_path = (
                PRODUCTION_VISUAL_GAP_PLAN_DIR
                / f"{base}.visual_gap_plan.json"
            )
            if not review_path.exists() or not gap_path.exists():
                continue
            gap = safe_load_json(gap_path)
            provenance = (
                gap.get("provenance", {})
                if isinstance(gap, dict)
                else {}
            )
            if (
                isinstance(provenance, dict)
                and provenance.get("rough_cut_sha256")
                == sha256_file(rough_path)
                and provenance.get("rough_cut_review_sha256")
                == sha256_file(review_path)
            ):
                gap_current.add((concept_id, branch_format))

    gap_plans_ready = (
        bool(rough_gate.get("complete"))
        and bool(expected)
        and expected.issubset(gap_current)
    )
    return {
        "candidate_gate": candidate_gate,
        "candidate_complete": candidate_complete,
        "rights_gate": rights_gate,
        "rights_complete": rights_complete,
        "expected_branches": sorted(expected),
        "rough_current_branches": sorted(rough_current),
        "rough_cuts_ready": rough_cuts_ready,
        "rough_gate": rough_gate,
        "rough_gate_complete": bool(rough_gate.get("complete")),
        "gap_current_branches": sorted(gap_current),
        "gap_plans_ready": gap_plans_ready,
    }


def visual_asset_acquisition_artifact_state() -> dict[str, Any]:
    candidate_gate = visual_candidate_review_snapshot()
    rights_gate = visual_rights_review_snapshot()

    expected_reviews: dict[str, str] = {}
    expected_rights: dict[str, str] = {}
    for packet in candidate_gate.get("packets", []):
        if not isinstance(packet, dict):
            continue
        result_path = Path(str(packet.get("result_file") or ""))
        if not result_path.name:
            continue
        base = result_path.name.replace(".visual_search_results.json", "")
        review_path = (
            PRODUCTION_VISUAL_CANDIDATE_REVIEW_DIR
            / f"{base}.visual_candidate_review.json"
        )
        if review_path.exists():
            expected_reviews[review_path.name] = sha256_file(review_path)

        rights_required = any(
            isinstance(decision, dict)
            and decision.get("status")
            == "SELECTED_PENDING_RIGHTS_CONTEXT_GATE"
            for decision in packet.get("decisions", {}).values()
        )
        if rights_required:
            rights_path = (
                PRODUCTION_VISUAL_RIGHTS_REVIEW_DIR
                / f"{base}.visual_rights_review.json"
            )
            if rights_path.exists():
                expected_rights[rights_path.name] = sha256_file(rights_path)

    payload = safe_load_json(PRODUCTION_VISUAL_ASSET_ACQUISITION_SUMMARY)
    summary = payload if isinstance(payload, dict) else {}
    current = bool(
        candidate_gate.get("complete")
        and rights_gate.get("complete")
        and expected_reviews
        and summary.get("source_review_sha256") == expected_reviews
        and summary.get("source_rights_sha256") == expected_rights
    )
    return {
        "status": (
            "CURRENT"
            if current
            else "READY_TO_ACQUIRE"
            if candidate_gate.get("complete") and rights_gate.get("complete")
            else "WAITING_FOR_VISUAL_REVIEW"
        ),
        "current": current,
        "acquired": int(summary.get("acquired") or 0) if current else 0,
        "manual_required": int(summary.get("manual_required") or 0)
        if current else 0,
        "failures": int(summary.get("failures") or 0) if current else 0,
        "items": summary.get("items", []) if current else [],
        "manual_items": summary.get("manual_items", []) if current else [],
        "failure_items": summary.get("failure_items", []) if current else [],
    }


def visual_generation_handoff_artifact_state() -> dict[str, Any]:
    spend = visual_spend_review_snapshot()
    expected: dict[tuple[str, str, str], float] = {}
    for item in spend.get("items", []):
        if not isinstance(item, dict):
            continue
        concept_id = str(item.get("concept_id") or "")
        branch_format = str(item.get("format") or "")
        decisions = item.get("decisions", {})
        if not isinstance(decisions, dict):
            continue
        for shot_id, decision in decisions.items():
            if (
                isinstance(decision, dict)
                and decision.get("paid_generation_authorized") is True
                and str(decision.get("decision") or "")
                == "AUTHORIZE_GENERATION"
            ):
                expected[(concept_id, branch_format, str(shot_id))] = round(
                    float(decision.get("max_cost_usd") or 0),
                    2,
                )

    current: dict[tuple[str, str, str], float] = {}
    current_details: dict[tuple[str, str, str], dict[str, Any]] = {}
    stale = 0
    if PRODUCTION_VISUAL_GENERATION_REQUEST_DIR.exists():
        for path in PRODUCTION_VISUAL_GENERATION_REQUEST_DIR.glob(
            "*.visual_generation_request.json"
        ):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                stale += 1
                continue
            key = (
                str(payload.get("concept_id") or ""),
                str(payload.get("format") or ""),
                str(payload.get("shot_id") or ""),
            )
            provenance = payload.get("provenance", {})
            authorization = payload.get("spend_authorization", {})
            if not isinstance(provenance, dict) or not isinstance(
                authorization, dict
            ):
                stale += 1
                continue
            gap_path = Path(str(provenance.get("gap_plan") or ""))
            spend_path = Path(
                str(provenance.get("visual_spend_review") or "")
            )
            if (
                not gap_path.exists()
                or not spend_path.exists()
                or provenance.get("gap_plan_sha256") != sha256_file(gap_path)
                or provenance.get("visual_spend_review_sha256")
                != sha256_file(spend_path)
                or authorization.get("human_authorized") is not True
                or authorization.get("execution_authorized") is not False
            ):
                stale += 1
                continue
            max_cost = round(
                float(authorization.get("max_cost_usd") or 0),
                2,
            )
            if key not in expected or expected[key] != max_cost:
                stale += 1
                continue
            current[key] = max_cost
            current_details[key] = {
                "request_file": str(path),
                "desired_visual": payload.get("desired_visual"),
                "story_purpose": payload.get("story_purpose"),
                "generation_brief": payload.get("generation_brief", {}),
                "provider_handoff": payload.get("provider_handoff", {}),
            }

    ready = bool(expected) and expected == current and stale == 0
    return {
        "status": (
            "READY_FOR_PROVIDER_HANDOFF"
            if ready
            else "STALE_OR_INCOMPLETE"
            if expected
            else "NO_PAID_VISUAL_GENERATION_AUTHORIZED"
        ),
        "ready": ready,
        "expected": len(expected),
        "current": len(current),
        "stale": stale,
        "authorized_max_total_usd": round(sum(expected.values()), 2),
        "requests": [
            {
                "concept_id": key[0],
                "format": key[1],
                "shot_id": key[2],
                "max_cost_usd": value,
                **current_details.get(key, {}),
            }
            for key, value in sorted(current.items())
        ],
    }


def visual_assembly_artifact_state(
    expected_branches: list[list[str]] | list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    expected = {
        (str(item[0]), str(item[1]))
        for item in (expected_branches or [])
        if isinstance(item, (list, tuple)) and len(item) == 2
    }
    current: set[tuple[str, str]] = set()
    stale = 0
    waiting_for_premium = 0
    waiting_for_local = 0
    ready_for_edit = 0

    if PRODUCTION_VISUAL_ASSEMBLY_PLAN_DIR.exists():
        for path in PRODUCTION_VISUAL_ASSEMBLY_PLAN_DIR.glob(
            "*.visual_assembly_plan.json"
        ):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                stale += 1
                continue
            key = (
                str(payload.get("concept_id") or ""),
                str(payload.get("format") or ""),
            )
            provenance = payload.get("provenance", {})
            if not isinstance(provenance, dict):
                stale += 1
                continue

            checks = (
                ("rough_cut", "rough_cut_sha256"),
                ("rough_cut_review", "rough_cut_review_sha256"),
                ("gap_plan", "gap_plan_sha256"),
            )
            valid = True
            for path_key, hash_key in checks:
                source = Path(str(provenance.get(path_key) or ""))
                if (
                    not source.exists()
                    or provenance.get(hash_key) != sha256_file(source)
                ):
                    valid = False
                    break

            spend_source = str(provenance.get("spend_review") or "")
            if valid and spend_source:
                spend_path = Path(spend_source)
                if (
                    not spend_path.exists()
                    or provenance.get("spend_review_sha256")
                    != sha256_file(spend_path)
                ):
                    valid = False

            if not valid or (expected and key not in expected):
                stale += 1
                continue

            current.add(key)
            if payload.get("status") == "WAITING_FOR_PREMIUM_GENERATED_ASSETS":
                waiting_for_premium += 1
            elif payload.get("status") == "WAITING_FOR_LOCAL_VISUAL_ASSETS":
                waiting_for_local += 1
            elif payload.get("status") == "READY_FOR_EDIT_ASSEMBLY":
                ready_for_edit += 1

    ready = bool(expected) and expected.issubset(current) and stale == 0
    return {
        "status": (
            "ASSEMBLY_PLANS_READY"
            if ready
            else "STALE_OR_INCOMPLETE"
            if expected
            else "WAITING_FOR_VISUAL_GAP_PLANS"
        ),
        "ready": ready,
        "expected": len(expected),
        "current": len(current),
        "stale": stale,
        "waiting_for_premium_assets": waiting_for_premium,
        "waiting_for_local_assets": waiting_for_local,
        "ready_for_edit_assembly": ready_for_edit,
    }


def edit_manifest_artifact_state(
    expected_branches: list[list[str]] | list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    expected = {
        (str(item[0]), str(item[1]))
        for item in (expected_branches or [])
        if isinstance(item, (list, tuple)) and len(item) == 2
    }
    current: set[tuple[str, str]] = set()
    stale = 0
    placeholders = 0

    if PRODUCTION_EDIT_MANIFEST_DIR.exists():
        for path in PRODUCTION_EDIT_MANIFEST_DIR.glob("*.edit_manifest.json"):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                stale += 1
                continue
            key = (
                str(payload.get("concept_id") or ""),
                str(payload.get("format") or ""),
            )
            provenance = payload.get("provenance", {})
            if not isinstance(provenance, dict):
                stale += 1
                continue
            valid = True
            for path_key, hash_key in (
                ("visual_assembly_plan", "visual_assembly_plan_sha256"),
                ("narration_audio_qc", "narration_audio_qc_sha256"),
                ("narration_timing_map", "narration_timing_map_sha256"),
            ):
                source = Path(str(provenance.get(path_key) or ""))
                if (
                    not source.exists()
                    or provenance.get(hash_key) != sha256_file(source)
                ):
                    valid = False
                    break
            sound_source = str(provenance.get("sound_design_brief") or "")
            if valid and sound_source:
                sound_path = Path(sound_source)
                if (
                    not sound_path.exists()
                    or provenance.get("sound_design_brief_sha256")
                    != sha256_file(sound_path)
                ):
                    valid = False
            if (
                not valid
                or payload.get("status") != "READY_FOR_LOCAL_PREVIEW_RENDER"
                or (expected and key not in expected)
            ):
                stale += 1
                continue
            current.add(key)
            placeholders += int(
                payload.get("preview_policy", {}).get(
                    "placeholder_count", 0
                )
            )

    ready = bool(expected) and expected.issubset(current) and stale == 0
    return {
        "status": "CURRENT" if ready else "STALE_OR_INCOMPLETE",
        "ready": ready,
        "expected": len(expected),
        "current": len(current),
        "stale": stale,
        "placeholder_count": placeholders,
    }


def edit_preview_artifact_state(
    expected_branches: list[list[str]] | list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    expected = {
        (str(item[0]), str(item[1]))
        for item in (expected_branches or [])
        if isinstance(item, (list, tuple)) and len(item) == 2
    }
    current: set[tuple[str, str]] = set()
    stale = 0
    placeholders = 0

    if PRODUCTION_EDIT_PREVIEW_RESULT_DIR.exists():
        for path in PRODUCTION_EDIT_PREVIEW_RESULT_DIR.glob(
            "*.edit_preview_result.json"
        ):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                stale += 1
                continue
            key = (
                str(payload.get("concept_id") or ""),
                str(payload.get("format") or ""),
            )
            provenance = payload.get("provenance", {})
            manifest_path = Path(
                str(
                    provenance.get("edit_manifest")
                    if isinstance(provenance, dict)
                    else ""
                )
            )
            preview_path = Path(str(payload.get("preview_file") or ""))
            valid = bool(
                isinstance(provenance, dict)
                and manifest_path.exists()
                and preview_path.exists()
                and provenance.get("edit_manifest_sha256")
                == sha256_file(manifest_path)
                and payload.get("preview_sha256")
                == sha256_file(preview_path)
                and payload.get("status")
                == "READY_FOR_HUMAN_EDIT_PREVIEW_GATE"
            )
            if not valid or (expected and key not in expected):
                stale += 1
                continue
            current.add(key)
            placeholders += int(payload.get("placeholder_segments") or 0)

    ready = bool(expected) and expected.issubset(current) and stale == 0
    return {
        "status": "CURRENT" if ready else "STALE_OR_INCOMPLETE",
        "ready": ready,
        "expected": len(expected),
        "current": len(current),
        "stale": stale,
        "placeholder_segments": placeholders,
    }


def final_production_handoff_artifact_state(
    expected_branches: list[list[str]] | list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    expected = {
        (str(item[0]), str(item[1]))
        for item in (expected_branches or [])
        if isinstance(item, (list, tuple)) and len(item) == 2
    }
    current: set[tuple[str, str]] = set()
    stale = 0
    blocked = 0
    ready_for_sound = 0

    if PRODUCTION_FINAL_HANDOFF_DIR.exists():
        for path in PRODUCTION_FINAL_HANDOFF_DIR.glob(
            "*.final_production_handoff.json"
        ):
            payload = safe_load_json(path)
            if not isinstance(payload, dict):
                stale += 1
                continue
            key = (
                str(payload.get("concept_id") or ""),
                str(payload.get("format") or ""),
            )
            provenance = payload.get("provenance", {})
            if not isinstance(provenance, dict):
                stale += 1
                continue

            valid = True
            for path_key, hash_key in (
                ("approved_edit_preview", "approved_edit_preview_sha256"),
                ("edit_preview_result", "edit_preview_result_sha256"),
                ("edit_manifest", "edit_manifest_sha256"),
            ):
                source = Path(str(provenance.get(path_key) or ""))
                if (
                    not source.exists()
                    or provenance.get(hash_key) != sha256_file(source)
                ):
                    valid = False
                    break

            sound_source = str(provenance.get("sound_design_brief") or "")
            if valid and sound_source:
                sound_path = Path(sound_source)
                if (
                    not sound_path.exists()
                    or provenance.get("sound_design_brief_sha256")
                    != sha256_file(sound_path)
                ):
                    valid = False

            if not valid or (expected and key not in expected):
                stale += 1
                continue

            current.add(key)
            if payload.get("status") == "BLOCKED":
                blocked += 1
            elif (
                payload.get("status")
                == "READY_FOR_FINAL_SOUND_PROVIDER_OR_ASSET_REGISTRATION"
            ):
                ready_for_sound += 1

    ready = bool(expected) and expected.issubset(current) and stale == 0
    return {
        "status": (
            "CURRENT"
            if ready
            else "STALE_OR_INCOMPLETE"
            if expected
            else "WAITING_FOR_APPROVED_EDIT_DIRECTION"
        ),
        "ready": ready,
        "expected": len(expected),
        "current": len(current),
        "stale": stale,
        "blocked": blocked,
        "ready_for_final_sound": ready_for_sound,
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
        exp13_manifest.exists() and exp13_summary.exists() and exp13_topic.exists()
    )
    cohort_info = exp13_cohort_readiness()
    cohort_sufficient = cohort_files_ready and bool(cohort_info["sufficient"])
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
        shutil.which("yt-dlp") is not None and shutil.which("ffmpeg") is not None
    )
    visual_satisfied = visual_ready or visual_attempted or not visual_available
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
    story = story_script_artifact_state()
    story_requests_ready = bool(story.get("story_requests_ready", False))
    story_plans_ready = bool(story.get("story_plans_ready", False))
    script_requests_ready = bool(story["requests_ready"])
    script_drafts_ready = bool(story["drafts_ready"])
    script_gate = story["script_gate"]
    script_gate_status = str(script_gate.get("status") or "WAITING_FOR_SCRIPT_DRAFTS")
    script_gate_complete = bool(story["script_gate_complete"])
    production_ready = bool(story["production_ready"])
    fmt = format_artifact_state()
    format_requests_ready = bool(fmt["requests_ready"])
    format_plans_ready = bool(fmt["plans_ready"])
    format_gate = fmt["format_gate"]
    format_gate_status = str(format_gate.get("status") or "WAITING_FOR_FORMAT_PLANS")
    format_gate_complete = bool(fmt["format_gate_complete"])
    production_engine_ready = bool(fmt["production_engine_ready"])
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

    if production_ready:
        script_human = "SCRIPT APPROVED — STAGE COMPLETE"
        script_tone = "complete"
        script_next = "Proceed to Format."
    elif active_action in {
        "story_prepare",
        "story_generate",
        "script_prepare",
        "script_generate",
        "script_gate_prepare",
    }:
        script_human = "SCRIPT WORK RUNNING"
        script_tone = "running"
        script_next = "Wait for the current Script job to finish."
    elif not story_ready:
        script_human = "WAITING FOR VERIFIED RESEARCH"
        script_tone = "blocked"
        script_next = "Complete the Research Gate first."
    elif not story_requests_ready:
        script_human = "READY TO PLAN STORY"
        script_tone = "ready"
        script_next = "Run Prepare Story Plan Requests."
    elif not story_plans_ready:
        script_human = "STORY PLANNING NEEDED"
        script_tone = "action"
        script_next = "Run Generate Story Plans."
    elif not script_requests_ready:
        script_human = "READY TO PREPARE SCRIPTS"
        script_tone = "ready"
        script_next = "Build Script Requests from current Story Plans."
    elif not script_drafts_ready:
        script_human = "SCRIPT DRAFTING NEEDED"
        script_tone = "action"
        script_next = "Run Generate Script Drafts."
    elif script_gate_status == "READY_TO_PREPARE":
        script_human = "PREPARE SCRIPT GATE"
        script_tone = "action"
        script_next = "Run Prepare Script Gate."
    elif script_gate_status == "AWAITING_HUMAN_DECISION":
        script_human = "HUMAN SCRIPT DECISION NEEDED"
        script_tone = "action"
        script_next = "Review script drafts in Analyze & Create."
    elif script_gate_complete:
        script_human = "NO APPROVED SCRIPT"
        script_tone = "action"
        script_next = "Rework or regenerate scripts before Format."
    else:
        script_human = "SCRIPT NEEDS ATTENTION"
        script_tone = "action"
        script_next = "Inspect the Script Gate state."

    if production_engine_ready:
        format_human = "FORMAT APPROVED — STAGE COMPLETE"
        format_tone = "complete"
        format_next = "Ready for the Production Engine."
    elif active_action in {
        "format_prepare",
        "format_generate",
        "format_gate_prepare",
    }:
        format_human = "FORMAT WORK RUNNING"
        format_tone = "running"
        format_next = "Wait for the current Format job to finish."
    elif not production_ready:
        format_human = "WAITING FOR APPROVED SCRIPT"
        format_tone = "blocked"
        format_next = "Approve a script first."
    elif not format_requests_ready:
        format_human = "READY TO PREPARE FORMATS"
        format_tone = "ready"
        format_next = "Run Prepare Format Requests."
    elif not format_plans_ready:
        format_human = "FORMAT PLANNING NEEDED"
        format_tone = "action"
        format_next = "Run Generate Format Plans."
    elif format_gate_status == "READY_TO_PREPARE":
        format_human = "PREPARE FORMAT GATE"
        format_tone = "action"
        format_next = "Run Prepare Format Gate."
    elif format_gate_status == "AWAITING_HUMAN_DECISION":
        format_human = "HUMAN FORMAT DECISION NEEDED"
        format_tone = "action"
        format_next = "Review format plans in Analyze & Create."
    elif format_gate_complete:
        format_human = "NO APPROVED FORMAT PLAN"
        format_tone = "action"
        format_next = "Rework or regenerate format plans before production."
    else:
        format_human = "FORMAT NEEDS ATTENTION"
        format_tone = "action"
        format_next = "Inspect the Format Gate state."

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
                or ("READY_TO_BUILD" if exp14_complete else "WAITING_FOR_01_4")
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
        {
            "id": "07",
            "title": "Story / Script",
            "state": script_gate_status if script_drafts_ready else (
                "READY_TO_PREPARE" if story_ready else "WAITING_FOR_RESEARCH"
            ),
            "human_status": script_human,
            "tone": script_tone,
            "detail": (
                "Drafts an original script constrained to human-accepted claims, "
                "then requires a human Script Gate decision."
            ),
            "next_action": script_next,
            "criteria": [
                {
                    "label": "Verified research handoff ready",
                    "done": story_ready,
                },
                {
                    "label": "Script requests prepared",
                    "done": script_requests_ready,
                },
                {
                    "label": "Validated script drafts generated",
                    "done": script_drafts_ready,
                },
                {
                    "label": "Human Script Gate complete",
                    "done": script_gate_complete,
                },
                {
                    "label": "Every script approved for Format",
                    "done": production_ready,
                },
            ],
            "complete": production_ready,
            "ready": story_ready,
            "current": story_ready and not production_ready,
        },
        {
            "id": "08",
            "title": "Format",
            "state": format_gate_status if format_plans_ready else (
                "READY_TO_PREPARE" if production_ready else "WAITING_FOR_SCRIPT"
            ),
            "human_status": format_human,
            "tone": format_tone,
            "detail": (
                "Plans long-form and Shorts as separate productions from the "
                "approved script, then requires a human Format Gate decision."
            ),
            "next_action": format_next,
            "criteria": [
                {
                    "label": "Approved script handoff ready",
                    "done": production_ready,
                },
                {
                    "label": "Format requests prepared",
                    "done": format_requests_ready,
                },
                {
                    "label": "Validated format plans generated",
                    "done": format_plans_ready,
                },
                {
                    "label": "Human Format Gate complete",
                    "done": format_gate_complete,
                },
                {
                    "label": "Every format plan approved for production",
                    "done": production_engine_ready,
                },
            ],
            "complete": production_engine_ready,
            "ready": production_ready,
            "current": production_ready and not production_engine_ready,
        },
    ]


def opportunity_research_state() -> dict[str, Any]:
    payload = safe_load_json(OPPORTUNITY_RESEARCH_STATE)
    return payload if isinstance(payload, dict) else {}


def action_readiness() -> dict[str, dict[str, Any]]:
    cohort_info = exp13_cohort_readiness()
    exp13_cohort = (EXP13_DIR / "cohort_manifest.json").exists() and bool(
        cohort_info["sufficient"]
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
    review_requests_complete = (
        request_count > 0 and review_request_count == request_count
    )
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
    story_requests_ready = bool(story.get("story_requests_ready", False))
    story_plans_ready = bool(story.get("story_plans_ready", False))
    script_requests_ready = bool(story["requests_ready"])
    script_drafts_ready = bool(story["drafts_ready"])
    script_gate = story["script_gate"]
    script_gate_status = str(script_gate.get("status") or "WAITING_FOR_SCRIPT_DRAFTS")
    script_gate_complete = bool(story["script_gate_complete"])
    production_ready = bool(story["production_ready"])
    fmt = format_artifact_state()
    format_requests_ready = bool(fmt["requests_ready"])
    format_plans_ready = bool(fmt["plans_ready"])
    format_gate = fmt["format_gate"]
    format_gate_status = str(format_gate.get("status") or "WAITING_FOR_FORMAT_PLANS")
    format_gate_complete = bool(fmt["format_gate_complete"])
    production_engine_ready = bool(fmt["production_engine_ready"])
    voice = voice_performance_artifact_state()
    voice_requests_ready = bool(voice["requests_ready"])
    voice_specs_ready = bool(voice["specs_ready"])
    performance_gate = voice["performance_gate"]
    performance_gate_status = str(
        performance_gate.get("status")
        or "WAITING_FOR_VOICE_PERFORMANCE_SPECS"
    )
    voice_visual_ready = bool(voice["visual_ready"])
    engagement = pre_render_engagement_snapshot()
    engagement_passed = bool(
        engagement.get("status") == "PASS"
        and int(engagement.get("processed") or 0) > 0
    )
    preview_prepare = narration_preview_prepare_snapshot()
    preview_render_payload = safe_load_json(PRODUCTION_PREVIEW_RENDER_SUMMARY)
    preview_render = preview_render_payload if isinstance(preview_render_payload, dict) else {
        "status": "WAITING_FOR_PREVIEW_MANIFESTS", "rendered": 0
    }
    preview_gate = narration_preview_gate_snapshot()
    preview_prepared = preview_prepare.get("status") == "READY_FOR_FREE_PREVIEW_RENDER"
    preview_items = (
        preview_gate.get("items", [])
        if isinstance(preview_gate, dict)
        else []
    )
    preview_rendered = bool(preview_items) and all(
        isinstance(item, dict) and item.get("audio_ready") is True
        for item in preview_items
    )
    sound_reference_payload = safe_load_json(PRODUCTION_SOUND_REFERENCE_SUMMARY)
    sound_reference = sound_reference_payload if isinstance(sound_reference_payload, dict) else {}
    sound_reference_prepared = sound_reference.get("status") == "READY_FOR_REFERENCE_SOUND_GENERATION"
    preview_approved = bool(preview_gate.get("complete"))
    sound_brief = sound_design_brief_snapshot()
    sound_brief_ready = (
        sound_brief.get("status") == "READY_FOR_FINAL_PROVIDER_HANDOFF"
    )
    narration = narration_artifact_state()
    narration_render = narration["render"]
    narration_spend_gate = narration["spend_gate"]
    narration_prepared = int(narration_render.get("prepared") or 0) > 0
    narration_refresh_required = bool(
        narration_render.get("refresh_required")
    )
    narration_ready_for_spend_gate = (
        narration_render.get("status") == "READY_FOR_SPEND_GATE"
    )
    narration_spend_gate_status = str(narration_spend_gate.get("status") or "WAITING_FOR_PROVIDER_QUOTE")
    narration_spend_complete = bool(narration_spend_gate.get("complete"))
    narration_spend_accepted = bool(
        narration_spend_complete
        and int(narration_spend_gate.get("accepted") or 0) > 0
        and int(narration_spend_gate.get("pending") or 0) == 0
        and int(narration_spend_gate.get("rework") or 0) == 0
        and int(narration_spend_gate.get("rejected") or 0) == 0
    )
    narration_return = narration.get("render_return", {})
    narration_return_status = str(
        narration_return.get("status") or "WAITING_FOR_SPEND_APPROVAL"
    )
    narration_render_results_present = bool(
        narration.get("render_results_present")
    )
    narration_audio_qc_state = narration.get("audio_qc", {})
    narration_audio_qc_status = str(
        narration_audio_qc_state.get("status")
        or "WAITING_FOR_NARRATION_RENDER_RESULTS"
    )
    narration_audio_ready = bool(narration.get("audio_ready"))
    production_visual = production_visual_artifact_state()
    visual_manifests_ready = bool(production_visual["manifests_ready"])
    storyboard_state = production_storyboard_snapshot()
    storyboards_ready = bool(
        visual_manifests_ready
        and storyboard_state.get("status") == "READY_FOR_VISUAL_SEARCH"
        and int(storyboard_state.get("prepared") or 0)
        == int(production_visual.get("manifest_count") or 0)
    )
    visual_search_state = visual_search_prepare_snapshot()
    visual_search_requests_ready = bool(
        storyboards_ready
        and visual_search_state.get("status") == "READY_FOR_SEARCH_ADAPTERS"
        and int(visual_search_state.get("prepared") or 0)
        == int(storyboard_state.get("prepared") or 0)
    )
    visual_search_acquire_state = visual_search_acquire_snapshot()
    visual_post = visual_post_search_artifact_state()
    visual_candidate_complete = bool(visual_post["candidate_complete"])
    visual_candidate_stale = int(
        visual_post["candidate_gate"].get("stale_shots") or 0
    )
    visual_rights_complete = bool(visual_post["rights_complete"])
    visual_asset_acquisition = visual_asset_acquisition_artifact_state()
    visual_asset_acquisition_current = bool(
        visual_asset_acquisition.get("current")
    )
    visual_rough_cuts_ready = bool(visual_post["rough_cuts_ready"])
    visual_rough_gate_complete = bool(visual_post["rough_gate_complete"])
    visual_gap_plans_ready = bool(visual_post["gap_plans_ready"])
    visual_spend = visual_spend_review_snapshot()
    visual_spend_complete = bool(visual_spend.get("complete"))
    visual_spend_authorized = int(visual_spend.get("authorized") or 0)
    visual_generation_handoff = visual_generation_handoff_artifact_state()
    visual_generation_handoff_ready = bool(
        visual_generation_handoff.get("ready")
    )
    visual_assembly = visual_assembly_artifact_state(
        visual_post.get("expected_branches", [])
    )
    visual_assembly_ready = bool(visual_assembly.get("ready"))
    edit_manifest_state = edit_manifest_artifact_state(
        visual_post.get("expected_branches", [])
    )
    edit_manifest_ready = bool(edit_manifest_state.get("ready"))
    edit_preview_state = edit_preview_artifact_state(
        visual_post.get("expected_branches", [])
    )
    edit_preview_ready = bool(edit_preview_state.get("ready"))
    edit_gate_state = edit_preview_review_snapshot()
    final_handoff_state = final_production_handoff_artifact_state(
        visual_post.get("expected_branches", [])
    )
    final_handoff_ready = bool(final_handoff_state.get("ready"))
    agent_reach_installed = shutil.which("agent-reach") is not None
    yt_dlp_installed = shutil.which("yt-dlp") is not None
    ffmpeg_installed = shutil.which("ffmpeg") is not None
    visual_available = yt_dlp_installed and ffmpeg_installed
    visual_satisfied = visual_complete or visual_attempted or not visual_available
    vision_satisfied = (not visual_complete) or vision_complete

    result: dict[str, dict[str, Any]] = {
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
        "vidiq_doctor": {
            "enabled": True,
            "reason": "Safe configuration check; no paid vidIQ research call is made.",
        },
        "vidiq_enrich": {
            "enabled": study_set,
            "reason": (
                "01.5 study set is ready for supplemental vidIQ validation."
                if study_set
                else "Build the 01.5 study set first."
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
                        if human_gate_ready
                        and profiles_prepared
                        and not yt_dlp_installed
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
            "enabled": (human_gate_ready and requests_complete and not analyzed),
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
                human_gate_ready and analysis_complete and not review_requests_complete
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
            "enabled": (human_gate_ready and review_complete and not synthesis_ready),
            "reason": (
                "Human Review is complete for every current analyzed profile."
                if (human_gate_ready and review_complete and not synthesis_ready)
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
                synthesis_ready and transform_requests and not transform_candidates
            ),
            "reason": (
                (
                    "Concept generation progress: "
                    f"{len(transform['current_response_mechanism_ids'])}/"
                    f"{len(transform['request_mechanism_ids'])} current responses. "
                    "Continue FAIR free-only generation."
                )
                if (synthesis_ready and transform_requests and not transform_candidates)
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
                "Run two-pass triage: score 5 concepts at a time, advance up to 10 finalists, then produce a final 0-6 shortlist."
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
                    or (concept_gate_complete and not bool(transform["research_ready"]))
                )
            ),
            "reason": (
                "LLM-shortlisted concepts are ready for final human review."
                if (transform_triage and concept_gate_status == "READY_TO_PREPARE")
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
                    or (research_gate_complete and not bool(research["story_ready"]))
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
        "story_prepare": {
            "enabled": bool(research["story_ready"]) and not story_requests_ready,
            "reason": (
                "Verified research and the approved package are ready for Story Plan requests."
                if bool(research["story_ready"]) and not story_requests_ready
                else (
                    "Story Plan requests are already current."
                    if story_requests_ready
                    else "Complete the Human Research Gate first."
                )
            ),
        },
        "story_generate": {
            "enabled": story_requests_ready and not story_plans_ready,
            "reason": (
                (
                    "Story Plan generation progress: "
                    f"{len(story['story_plan_concept_ids'])}/"
                    f"{len(story['verified_concept_ids'])} current plans."
                )
                if story_requests_ready and not story_plans_ready
                else (
                    "Current Story Plans already exist."
                    if story_plans_ready
                    else "Prepare current Story Plan requests first."
                )
            ),
        },
        "script_prepare": {
            "enabled": story_plans_ready and not script_requests_ready,
            "reason": (
                "Current Story Plans are ready to become narration requests."
                if story_plans_ready and not script_requests_ready
                else (
                    "Script requests are already current."
                    if script_requests_ready
                    else "Generate current Story Plans first."
                )
            ),
        },
        "script_generate": {
            "enabled": script_requests_ready and not script_drafts_ready,
            "reason": (
                (
                    "Script drafting progress: "
                    f"{len(story['draft_branch_ids'])}/"
                    f"{len(story['request_branch_ids'])} current branches."
                )
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
                    or (script_gate_complete and not production_ready)
                )
            ),
            "reason": (
                "Validated script drafts are ready for human review."
                if script_drafts_ready and script_gate_status == "READY_TO_PREPARE"
                else (
                    "No script was approved; reopen the Script Gate."
                    if script_drafts_ready
                    and script_gate_complete
                    and not production_ready
                    else (
                        "Script Gate is already prepared or complete."
                        if script_drafts_ready
                        else "Generate current script drafts first."
                    )
                )
            ),
        },        "format_prepare": {
            "enabled": production_ready and not format_requests_ready,
            "reason": (
                "All required branch scripts are approved and ready for production-format planning."
                if production_ready and not format_requests_ready
                else (
                    "Format requests are already current."
                    if format_requests_ready
                    else "Complete the Human Script Gate first."
                )
            ),
        },
        "format_generate": {
            "enabled": format_requests_ready and not format_plans_ready,
            "reason": (
                "Current format requests are ready for FAIR planning."
                if format_requests_ready and not format_plans_ready
                else (
                    "Current format plans already exist."
                    if format_plans_ready
                    else "Prepare current format requests first."
                )
            ),
        },
        "format_gate_prepare": {
            "enabled": (
                format_plans_ready
                and (
                    format_gate_status == "READY_TO_PREPARE"
                    or (format_gate_complete and not production_engine_ready)
                )
            ),
            "reason": (
                "Validated format plans are ready for human review."
                if format_plans_ready and format_gate_status == "READY_TO_PREPARE"
                else (
                    "No format plan was approved; reopen the Format Gate."
                    if format_plans_ready
                    and format_gate_complete
                    and not production_engine_ready
                    else (
                        "Format Gate is already prepared or complete."
                        if format_plans_ready
                        else "Generate current format plans first."
                    )
                )
            ),
        },
        "voice_prepare": {
            "enabled": production_engine_ready and not voice_requests_ready,
            "reason": (
                "Accepted format branches are ready for immutable narration binding."
                if production_engine_ready and not voice_requests_ready
                else (
                    "Voice Performance requests are already current."
                    if voice_requests_ready
                    else "Complete and accept the Human Format Gate first."
                )
            ),
        },
        "voice_generate": {
            "enabled": voice_requests_ready and not voice_specs_ready,
            "reason": (
                "Current Voice Performance requests are ready for FAIR planning."
                if voice_requests_ready and not voice_specs_ready
                else (
                    "Voice Performance specs are already current."
                    if voice_specs_ready
                    else "Prepare current Voice Performance requests first."
                )
            ),
        },
        "voice_gate_prepare": {
            "enabled": (
                voice_specs_ready
                and performance_gate_status == "READY_TO_PREPARE"
            ),
            "reason": (
                "Validated Voice Performance specs are ready for human review."
                if voice_specs_ready
                and performance_gate_status == "READY_TO_PREPARE"
                else (
                    "Performance Gate is already prepared or complete."
                    if voice_specs_ready
                    else "Generate current Voice Performance specs first."
                )
            ),
        },
        "pre_render_engagement": {
            "enabled": voice_visual_ready and not engagement_passed and engagement.get("status") != "BLOCKED",
            "reason": (
                "Human-approved performance plans are ready for deterministic engagement validation."
                if voice_visual_ready and not engagement_passed and engagement.get("status") != "BLOCKED"
                else ("Pre-render engagement validation passed." if engagement_passed else ("Pre-render engagement validation blocked narration; revise the script/performance plan." if engagement.get("status") == "BLOCKED" else "Complete and accept the Human Performance Gate first."))
            ),
        },
        "narration_preview_prepare": {
            "enabled": engagement_passed and not preview_prepared,
            "reason": (
                "Engagement validation passed; prepare the zero-cost audio prototype."
                if engagement_passed and not preview_prepared
                else ("Free prototype manifest is ready." if preview_prepared else "Pre-render engagement validation must pass first.")
            ),
        },
        "prototype_sound_prepare": {
            "enabled": preview_prepared and not sound_reference_prepared,
            "reason": (
                "Prepare AudioGen/MusicGen research-reference prompts for the rough audio experience."
                if preview_prepared and not sound_reference_prepared
                else ("Reference sound plan is prepared." if sound_reference_prepared else "Prepare the free narration prototype first.")
            ),
        },
        "narration_preview_render": {
            "enabled": preview_prepared and not preview_rendered,
            "reason": (
                "Render the free local Kokoro prototype for listening."
                if preview_prepared and not preview_rendered
                else ("Free prototype audio is ready for human listening." if preview_rendered else "Prepare the free prototype first.")
            ),
        },
        "sound_design_brief_prepare": {
            "enabled": preview_approved and not sound_brief_ready,
            "reason": (
                "Free prototype approved; convert the accepted sound intent into a descriptive final-provider brief."
                if preview_approved and not sound_brief_ready
                else ("Sound Design Brief is ready." if sound_brief_ready else "Approve the free audio prototype first.")
            ),
        },
        "narration_prepare": {
            "enabled": (
                preview_approved
                and sound_brief_ready
                and (not narration_prepared or narration_refresh_required)
            ),
            "reason": (
                "The free prototype and current Sound Design Brief are approved; prepare or refresh the provider-bound narration request and zero-spend quote boundary."
                if (
                    preview_approved
                    and sound_brief_ready
                    and (not narration_prepared or narration_refresh_required)
                )
                else (
                    "Narration request and cost boundary are current."
                    if narration_prepared and not narration_refresh_required
                    else "Listen to and approve the free narration prototype before any provider quote."
                )
            ),
        },
        "narration_spend_gate_prepare": {
            "enabled": (
                narration_prepared
                and not narration_refresh_required
                and narration_spend_gate_status == "READY_TO_PREPARE"
            ),
            "reason": (
                "Refresh the Human Narration Spend Gate from the current narration cost state."
                if (
                    narration_prepared
                    and not narration_refresh_required
                    and narration_spend_gate_status == "READY_TO_PREPARE"
                )
                else (
                    "Narration Spend Gate is already prepared or complete."
                    if narration_ready_for_spend_gate
                    else "Narration remains blocked until provider prerequisites and a current quote exist."
                )
            ),
        },
        "narration_audio_qc": {
            "enabled": (
                narration_spend_accepted
                and narration_render_results_present
                and narration_audio_qc_status
                == "WAITING_FOR_NARRATION_RENDER_RESULTS"
            ),
            "reason": (
                "Current spend-authorized provider audio is registered; run local Audio QC and build the narration timing map."
                if (
                    narration_spend_accepted
                    and narration_render_results_present
                    and narration_audio_qc_status
                    == "WAITING_FOR_NARRATION_RENDER_RESULTS"
                )
                else (
                    "Narration Audio QC has passed and timing maps are ready."
                    if narration_audio_ready
                    else (
                        "Narration Audio QC failed. Re-import corrected provider audio before retrying."
                        if narration_audio_qc_status == "FAIL"
                        else (
                            "Register the current provider narration return after spend approval."
                            if narration_spend_accepted
                            else "Complete the Human Narration Spend Gate first."
                        )
                    )
                )
            ),
        },
        "storyboard_prepare": {
            "enabled": visual_manifests_ready and not storyboards_ready,
            "reason": (
                "Build or refresh the cinematic storyboard from current narration timing and current visual requirements."
                if visual_manifests_ready and not storyboards_ready
                else (
                    "Current narration-bound storyboards are ready."
                    if storyboards_ready
                    else "Current narration-bound visual requirements are not ready."
                )
            ),
        },
        "visual_search_prepare": {
            "enabled": (
                storyboards_ready
                and (
                    not visual_search_requests_ready
                    or visual_candidate_stale > 0
                )
            ),
            "reason": (
                "Storyboard revisions made visual search stale; rebuild only current search requests."
                if visual_candidate_stale > 0
                else (
                    "Prepare rights-aware, existing/free-first visual search requests from the current storyboard."
                    if storyboards_ready and not visual_search_requests_ready
                    else "Current visual search requests are ready."
                )
            ),
        },
        "visual_search_acquire": {
            "enabled": (
                visual_search_requests_ready
                and visual_search_acquire_state.get("status")
                == "READY_TO_SEARCH"
            ),
            "reason": (
                "Search current zero-cost/existing sources. Results are discovery-only; no media is downloaded and no paid generation is called."
                if (
                    visual_search_requests_ready
                    and visual_search_acquire_state.get("status")
                    == "READY_TO_SEARCH"
                )
                else (
                    "Current zero-cost visual search results are ready for human review."
                    if visual_search_acquire_state.get("status")
                    == "SEARCH_COMPLETE"
                    else "Prepare current narration-bound visual search requests first."
                )
            ),
        },
        "visual_asset_acquire": {
            "enabled": (
                visual_candidate_complete
                and visual_rights_complete
                and not visual_asset_acquisition_current
            ),
            "reason": (
                "Approved current visual selections are ready for safe local "
                "asset acquisition."
                if (
                    visual_candidate_complete
                    and visual_rights_complete
                    and not visual_asset_acquisition_current
                )
                else (
                    "Approved visual asset acquisition is current."
                    if visual_asset_acquisition_current
                    else "Complete Visual Candidate and Rights/Context review first."
                )
            ),
        },
        "visual_rough_cut_prepare": {
            "enabled": (
                visual_candidate_complete
                and visual_rights_complete
                and visual_asset_acquisition_current
                and not visual_rough_cuts_ready
            ),
            "reason": (
                "Current visual selections, rights/context decisions and safe asset acquisition are ready; build the rough cut."
                if (
                    visual_candidate_complete
                    and visual_rights_complete
                    and visual_asset_acquisition_current
                    and not visual_rough_cuts_ready
                )
                else (
                    "Current rough-cut manifests are ready."
                    if visual_rough_cuts_ready
                    else "Complete Visual Candidate Review and any required Rights/Context Review first."
                )
            ),
        },
        "visual_gap_prepare": {
            "enabled": (
                visual_rough_gate_complete
                and not visual_gap_plans_ready
            ),
            "reason": (
                "Human-approved rough cuts are ready for unresolved-gap planning."
                if visual_rough_gate_complete and not visual_gap_plans_ready
                else (
                    "Current visual gap plans are ready."
                    if visual_gap_plans_ready
                    else "Complete the Human Rough-Cut Gate first."
                )
            ),
        },
        "visual_generation_handoff_prepare": {
            "enabled": (
                visual_gap_plans_ready
                and visual_spend_complete
                and visual_spend_authorized > 0
                and not visual_generation_handoff_ready
            ),
            "reason": (
                "Human-authorized premium visual gaps are ready for zero-cost "
                "provider handoff preparation."
                if (
                    visual_gap_plans_ready
                    and visual_spend_complete
                    and visual_spend_authorized > 0
                    and not visual_generation_handoff_ready
                )
                else (
                    "Premium visual generation briefs are already current."
                    if visual_generation_handoff_ready
                    else (
                        "No paid visual generation was authorized."
                        if visual_spend_complete and visual_spend_authorized == 0
                        else "Complete the Human Visual Spend Gate first."
                    )
                )
            ),
        },
        "visual_assembly_prepare": {
            "enabled": (
                visual_gap_plans_ready
                and visual_spend_complete
                and (
                    visual_spend_authorized == 0
                    or visual_generation_handoff_ready
                )
                and not visual_assembly_ready
            ),
            "reason": (
                "Current visual decisions are ready for deterministic edit "
                "assembly planning."
                if (
                    visual_gap_plans_ready
                    and visual_spend_complete
                    and (
                        visual_spend_authorized == 0
                        or visual_generation_handoff_ready
                    )
                    and not visual_assembly_ready
                )
                else (
                    "Visual edit assembly plans are already current."
                    if visual_assembly_ready
                    else (
                        "Prepare current premium-generation briefs first."
                        if visual_spend_authorized > 0
                        and not visual_generation_handoff_ready
                        else "Complete visual gap and spend decisions first."
                    )
                )
            ),
        },
        "edit_manifest_prepare": {
            "enabled": visual_assembly_ready and not edit_manifest_ready,
            "reason": (
                "Current visual assembly and narration timing are ready for the "
                "structural edit manifest."
                if visual_assembly_ready and not edit_manifest_ready
                else (
                    "Edit preview manifests are current."
                    if edit_manifest_ready
                    else "Build the current visual assembly plan first."
                )
            ),
        },
        "edit_preview_render": {
            "enabled": edit_manifest_ready and not edit_preview_ready,
            "reason": (
                "Current edit manifests are ready for free local FFmpeg preview."
                if edit_manifest_ready and not edit_preview_ready
                else (
                    "Structural edit previews are current."
                    if edit_preview_ready
                    else "Build current edit manifests first."
                )
            ),
        },
        "final_production_handoff_prepare": {
            "enabled": (
                edit_preview_ready
                and bool(edit_gate_state.get("complete"))
                and int(edit_gate_state.get("rework") or 0) == 0
                and int(
                    visual_assembly.get("waiting_for_premium_assets") or 0
                ) == 0
                and int(
                    visual_assembly.get("waiting_for_local_assets") or 0
                ) == 0
                and not final_handoff_ready
            ),
            "reason": (
                "Approved edit direction and current final visual/audio assets are "
                "ready for a zero-cost final production handoff."
                if (
                    edit_preview_ready
                    and bool(edit_gate_state.get("complete"))
                    and int(edit_gate_state.get("rework") or 0) == 0
                    and int(
                        visual_assembly.get("waiting_for_premium_assets") or 0
                    ) == 0
                    and int(
                        visual_assembly.get("waiting_for_local_assets") or 0
                    ) == 0
                    and not final_handoff_ready
                )
                else (
                    "Final production handoff is current."
                    if final_handoff_ready
                    else "Approve the structural edit and register all final visual assets first."
                )
            ),
        },
        "production_visual_prepare": {
            "enabled": narration_audio_ready and not visual_manifests_ready,
            "reason": (
                "QC-passed narration timing maps unlock cheap-first visual manifests."
                if narration_audio_ready and not visual_manifests_ready
                else (
                    "Visual acquisition manifests are already current."
                    if visual_manifests_ready
                    else "Narration must render and pass local Audio QC first."
                )
            ),
        },

    }

    ready_machine_steps = [
        action_id
        for action_id in AUTO_MACHINE_ACTION_ORDER
        if result.get(action_id, {}).get("enabled")
    ]
    result["auto_continue"] = {
        "enabled": bool(ready_machine_steps),
        "reason": (
            "Automatic machine work is ready: "
            + ACTION_DEFS[ready_machine_steps[0]]["label"]
            if ready_machine_steps
            else "Waiting at a human gate, prerequisite, or completed workflow."
        ),
    }
    return result


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

        if (
            process is not None
            and process.poll() is not None
            and job.get("status") == "RUNNING"
        ):
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
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            log_path = JOB_LOG_DIR / f"{stamp}_{action_id}.log"
            action = ACTION_DEFS[action_id]

            log_handle = log_path.open("w", encoding="utf-8", buffering=1)
            creationflags = 0
            if os.name == "nt":
                creationflags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))

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
                    else "PARTIAL" if return_code == 2 else "FAILED"
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
                key: value for key, value in self._job.items() if key != "_log_handle"
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
        atomic_write_json(JOB_STATE_FILE, payload)


JOB_MANAGER = JobManager()


def human_gate_mutation_block_reason(route: str) -> str | None:
    if route in HUMAN_GATE_MUTATION_ROUTES and JOB_MANAGER.running():
        return (
            "Human Gate changes are locked while an automatic or diagnostic "
            "pipeline job is running."
        )
    return None


def maybe_start_automatic_workflow() -> dict[str, Any] | None:
    """Start deterministic downstream work after a human gate completes.

    If the gate is still incomplete, rejected without a valid downstream
    handoff, or another job is running, no automatic job is started.
    """
    if JOB_MANAGER.running():
        return None
    readiness = action_readiness().get("auto_continue", {})
    if not readiness.get("enabled"):
        return None
    try:
        return JOB_MANAGER.start("auto_continue")
    except RuntimeError:
        return None


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
            "next_action_id": "auto_continue",
            "next_title": "Automatic Experiment 02 continuation",
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
            "next_action_id": "auto_continue",
            "next_title": "Automatic analysis continuation",
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
            "next_action_id": "auto_continue",
            "next_title": "Automatic synthesis and concept generation",
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
            "next_action_id": "auto_continue",
            "next_title": "Automatic Packaging",
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
            "next_action_id": "auto_continue",
            "next_title": "Automatic Research",
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
            "next_action_id": "auto_continue",
            "next_title": "Automatic Story / Script",
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
            "next_action_id": "auto_continue",
            "next_title": "Automatic Format planning",
        }

    fmt = format_artifact_state()
    format_gate = fmt.get("format_gate", {})
    if (
        fmt.get("plans_ready")
        and format_gate.get("status") == "AWAITING_HUMAN_DECISION"
    ):
        return {
            "state": "HUMAN_FORMAT_GATE",
            "current_action_id": None,
            "current_title": "Review Format Plan",
            "current_detail": (
                "Confirm long-form and Shorts are separate productions that each "
                "deliver the approved promise within accepted claims."
            ),
            "next_action_id": "auto_continue",
            "next_title": "Automatic Voice Performance planning",
        }

    voice = voice_performance_artifact_state()
    performance_gate = voice.get("performance_gate", {})
    if (
        voice.get("specs_ready")
        and performance_gate.get("status") == "AWAITING_HUMAN_DECISION"
    ):
        return {
            "state": "HUMAN_PERFORMANCE_GATE",
            "current_action_id": None,
            "current_title": "Review Voice Performance",
            "current_detail": (
                "Review emotion, pace, pauses and emphasis for each immutable "
                "narration beat. This gate spends no provider credits."
            ),
            "next_action_id": "auto_continue",
            "next_title": "Prepare Visual Acquisition",
        }

    preview_gate = narration_preview_gate_snapshot()
    if (
        preview_gate.get("items")
        and not preview_gate.get("complete")
        and any(item.get("audio_ready") for item in preview_gate.get("items", []))
    ):
        return {
            "state": "HUMAN_NARRATION_PREVIEW_GATE",
            "current_action_id": None,
            "current_title": "Listen to Free Audio Prototype",
            "current_detail": (
                "Hear the story with draft tone, pacing and pauses before spending. "
                "Approve final, or send the script, performance, or music/SFX plan back for rework."
            ),
            "next_action_id": "auto_continue",
            "next_title": "Prepare Final Narration Quote",
        }

    narration_state = narration_artifact_state()
    narration_render_state = narration_state.get("render", {})
    narration_spend_state = narration_state.get("spend_gate", {})
    if (
        narration_spend_state.get("status") == "AWAITING_HUMAN_DECISION"
        and narration_spend_state.get("items")
    ):
        return {
            "state": "HUMAN_NARRATION_SPEND_GATE",
            "current_action_id": None,
            "current_title": "Review Narration Spend",
            "current_detail": (
                "Review the current provider quote and worst-case narration cost. "
                "No paid narration call has been authorized yet."
            ),
            "next_action_id": None,
            "next_title": "Paid narration remains locked until you accept.",
        }

    narration_spend_accepted = bool(
        narration_spend_state.get("complete")
        and int(narration_spend_state.get("accepted") or 0) > 0
        and int(narration_spend_state.get("pending") or 0) == 0
        and int(narration_spend_state.get("rework") or 0) == 0
        and int(narration_spend_state.get("rejected") or 0) == 0
    )
    narration_return_state = narration_state.get("render_return", {})
    narration_qc_state = narration_state.get("audio_qc", {})
    if narration_spend_accepted:
        if narration_return_state.get("status") != "READY_FOR_AUDIO_QC":
            return {
                "state": "WAITING_NARRATION_RENDER_RETURN",
                "current_action_id": None,
                "current_title": "Register Final Narration Audio",
                "current_detail": (
                    "Spend is authorized for the exact current quote. Supply the "
                    "provider job/reference, actual cumulative cost, and one local "
                    "audio file for every narration segment. The repository does "
                    "not call an unverified paid provider."
                ),
                "next_action_id": None,
                "next_title": "Automatic local Audio QC",
            }
        if narration_qc_state.get("status") == "FAIL":
            return {
                "state": "NARRATION_AUDIO_QC_FAILED",
                "current_action_id": None,
                "current_title": "Narration Audio QC Failed",
                "current_detail": (
                    "One or more final narration segments failed duration, silence, "
                    "clipping, file, or attempt-policy checks. Register corrected "
                    "provider audio before retrying."
                ),
                "next_action_id": None,
                "next_title": "Re-import corrected narration audio",
            }
        if not narration_state.get("audio_ready"):
            return {
                "state": "ACTION_REQUIRED",
                "current_action_id": "auto_continue",
                "current_title": "Run Narration Audio QC",
                "current_detail": (
                    "Current provider audio is registered against the exact spend "
                    "authorization. Run deterministic local Audio QC and timing-map generation."
                ),
                "next_action_id": None,
                "next_title": "Prepare narration-bound visual plan",
            }

    narration_items = [
        item
        for item in narration_render_state.get("items", [])
        if isinstance(item, dict)
    ]
    narration_blockers = sorted(
        {
            str(blocker)
            for item in narration_items
            for blocker in item.get("render_blockers", [])
            if str(blocker)
        }
    )
    if (
        preview_gate.get("complete")
        and narration_items
        and narration_blockers
    ):
        return {
            "state": "NARRATION_PROVIDER_SETUP_REQUIRED",
            "current_action_id": None,
            "current_title": "Complete Narration Provider Setup",
            "current_detail": (
                "Paid narration is still locked. Current blockers: "
                + ", ".join(narration_blockers)
            ),
            "next_action_id": None,
            "next_title": "Prepare a verified quote only after setup is complete.",
        }

    if (
        preview_gate.get("complete")
        and narration_items
        and not narration_blockers
        and narration_render_state.get("status")
        == "NARRATION_PREPARED_WITH_BLOCKERS"
    ):
        return {
            "state": "WAITING_NARRATION_PROVIDER_QUOTE",
            "current_action_id": None,
            "current_title": "Current Narration Quote Required",
            "current_detail": (
                "The provider-bound narration request and quote template are ready. "
                "Supply a current zero-spend/dry-run or documented provider quote; "
                "the system will not guess a price."
            ),
            "next_action_id": None,
            "next_title": "Human Narration Spend Gate",
        }

    search_state = visual_search_prepare_snapshot()
    search_acquire_state = visual_search_acquire_snapshot()
    candidate_snapshot = visual_candidate_review_snapshot()
    if (
        narration_state.get("audio_ready")
        and search_state.get("status") == "READY_FOR_SEARCH_ADAPTERS"
        and int(search_state.get("prepared") or 0) > 0
        and not candidate_snapshot.get("ready_for_review")
        and search_acquire_state.get("status") == "READY_TO_SEARCH"
    ):
        return {
            "state": "ACTION_REQUIRED",
            "current_action_id": "auto_continue",
            "current_title": "Search Free / Existing Visuals",
            "current_detail": (
                "Run current zero-cost discovery across configured stock and "
                "creator-discovery sources. Results are normalized and rights-aware; "
                "no media is downloaded and no paid generation is allowed."
            ),
            "next_action_id": None,
            "next_title": "Human Visual Candidate Gate",
        }

    visual_post = visual_post_search_artifact_state()
    candidate_gate = visual_post.get("candidate_gate", {})
    if (
        candidate_gate.get("ready_for_review")
        and candidate_gate.get("packets")
        and not visual_post.get("candidate_complete")
    ):
        return {
            "state": "HUMAN_VISUAL_CANDIDATE_GATE",
            "current_action_id": None,
            "current_title": (
                "Re-search Revised Visual Shots"
                if int(candidate_gate.get("stale_shots") or 0) > 0
                else "Choose Visual Candidates"
            ),
            "current_detail": (
                "One or more storyboard shots changed and their old search "
                "results are stale. Continue Automatically to re-search them."
                if int(candidate_gate.get("stale_shots") or 0) > 0
                else (
                    "Choose a current visual, reject the available options, or "
                    "preserve the shot as a visual gap. "
                    + (
                        f"{int(candidate_gate.get('provider_errors') or 0)} provider "
                        "error(s) were isolated; available current candidates remain reviewable."
                        if int(candidate_gate.get("provider_errors") or 0) > 0
                        else "All displayed candidates come from the current search request."
                    )
                )
            ),
            "next_action_id": "auto_continue",
            "next_title": "Rights review or automatic rough cut",
        }

    rights_gate = visual_post.get("rights_gate", {})
    if (
        visual_post.get("candidate_complete")
        and int(rights_gate.get("required") or 0) > 0
        and not visual_post.get("rights_complete")
    ):
        return {
            "state": "HUMAN_VISUAL_RIGHTS_GATE",
            "current_action_id": None,
            "current_title": "Review Creator Footage Context",
            "current_detail": (
                "Creator/editorial footage is never auto-approved. Document "
                "the intended transformative/editorial purpose or reject its use."
            ),
            "next_action_id": "auto_continue",
            "next_title": "Build Visual Rough Cut",
        }

    rough_gate = visual_post.get("rough_gate", {})
    if (
        visual_post.get("rough_cuts_ready")
        and not visual_post.get("rough_gate_complete")
    ):
        return {
            "state": "HUMAN_ROUGH_CUT_GATE",
            "current_action_id": None,
            "current_title": "Review Visual Rough Cut",
            "current_detail": (
                "Review the full storyboard-to-visual assignment before gap "
                "planning. Approving with gaps does not authorize paid generation."
            ),
            "next_action_id": "auto_continue",
            "next_title": "Plan Remaining Visual Gaps",
        }

    if visual_post.get("gap_plans_ready"):
        spend_gate = visual_spend_review_snapshot()
        hero_count = int(spend_gate.get("hero_candidates") or 0)
        if hero_count > 0 and not spend_gate.get("complete"):
            return {
                "state": "HUMAN_VISUAL_SPEND_GATE",
                "current_action_id": None,
                "current_title": "Decide Whether Any Visual Is Worth Paying For",
                "current_detail": (
                    "Existing/free sourcing has already been tried. For each "
                    "high-value unresolved shot, retry existing sources, keep a "
                    "placeholder, or authorize a specific maximum spend."
                ),
                "next_action_id": None,
                "next_title": "Prepare generation briefs or assembly plan",
            }

        authorized = int(spend_gate.get("authorized") or 0)
        if authorized > 0:
            handoff_state = visual_generation_handoff_artifact_state()
            if not handoff_state.get("ready"):
                return {
                    "state": "ACTION_REQUIRED",
                    "current_action_id": "auto_continue",
                    "current_title": "Prepare Premium Visual Generation Briefs",
                    "current_detail": (
                        "Human spend ceilings are approved. Prepare provider-neutral "
                        "cinematic briefs only; this step calls no paid provider."
                    ),
                    "next_action_id": None,
                    "next_title": "Build Visual Edit Assembly Plan",
                }

        assembly_state = visual_assembly_artifact_state(
            visual_post.get("expected_branches", [])
        )
        if not assembly_state.get("ready"):
            return {
                "state": "ACTION_REQUIRED",
                "current_action_id": "auto_continue",
                "current_title": "Build Visual Edit Assembly Plan",
                "current_detail": (
                    "Build the zero-cost timeline contract from current local "
                    "visuals and explicit placeholders. Missing premium/editorial "
                    "assets do not block a structural preview."
                ),
                "next_action_id": None,
                "next_title": "Build Edit Preview Manifest",
            }

        edit_manifest_state = edit_manifest_artifact_state(
            visual_post.get("expected_branches", [])
        )
        if not edit_manifest_state.get("ready"):
            return {
                "state": "ACTION_REQUIRED",
                "current_action_id": "auto_continue",
                "current_title": "Build Edit Preview Manifest",
                "current_detail": (
                    "Combine current narration timing, visual assembly and approved "
                    "sound-design intent into a deterministic preview timeline."
                ),
                "next_action_id": None,
                "next_title": "Render Free Structural Edit Preview",
            }

        edit_preview_state = edit_preview_artifact_state(
            visual_post.get("expected_branches", [])
        )
        if not edit_preview_state.get("ready"):
            return {
                "state": "ACTION_REQUIRED",
                "current_action_id": "auto_continue",
                "current_title": "Render Free Structural Edit Preview",
                "current_detail": (
                    "Render a local FFmpeg preview with current assets, placeholders "
                    "and QC-passed narration. No paid visual provider or generated "
                    "music/SFX is used."
                ),
                "next_action_id": None,
                "next_title": "Human Edit Preview Gate",
            }

        edit_gate = edit_preview_review_snapshot()
        if not edit_gate.get("complete"):
            return {
                "state": "HUMAN_EDIT_PREVIEW_GATE",
                "current_action_id": None,
                "current_title": "Review Structural Edit Preview",
                "current_detail": (
                    "Judge pacing, narration-to-picture rhythm and story flow before "
                    "spending on unresolved hero shots. Dark placeholders are expected "
                    "where final visual assets are still missing."
                ),
                "next_action_id": None,
                "next_title": "Approve direction or return a layer for rework",
            }

        if int(edit_gate.get("rework") or 0) > 0:
            return {
                "state": "EDIT_PREVIEW_REWORK_REQUIRED",
                "current_action_id": None,
                "current_title": "Edit Preview Rework Requested",
                "current_detail": (
                    "A human return request was recorded for visuals, narration or "
                    "sound. The instruction is preserved and must be applied at that "
                    "upstream creative layer before a new preview is approved."
                ),
                "next_action_id": None,
                "next_title": "Apply the human rework instruction",
            }

        premium_missing = int(
            assembly_state.get("waiting_for_premium_assets") or 0
        )
        local_missing = int(
            assembly_state.get("waiting_for_local_assets") or 0
        )
        if premium_missing or local_missing:
            return {
                "state": "WAITING_FOR_FINAL_VISUAL_ASSETS",
                "current_action_id": None,
                "current_title": "Edit Direction Approved — Final Visuals Still Missing",
                "current_detail": (
                    f"The structural edit is approved. {premium_missing} branch(es) "
                    f"still wait for premium-generated assets and {local_missing} "
                    "branch(es) wait for approved local assets. Register those files; "
                    "the assembly and preview approval will become stale automatically."
                ),
                "next_action_id": None,
                "next_title": "Register final visual assets",
            }

        final_handoff = final_production_handoff_artifact_state(
            visual_post.get("expected_branches", [])
        )
        if not final_handoff.get("ready"):
            return {
                "state": "ACTION_REQUIRED",
                "current_action_id": "auto_continue",
                "current_title": "Prepare Final Production Handoff",
                "current_detail": (
                    "The structural edit and all current visual assets are approved. "
                    "Build the zero-cost provider-neutral package containing the final "
                    "visual timeline, narration and sound-design intent."
                ),
                "next_action_id": None,
                "next_title": "Final sound/provider boundary",
            }

        if int(final_handoff.get("blocked") or 0) > 0:
            return {
                "state": "FINAL_PRODUCTION_HANDOFF_BLOCKED",
                "current_action_id": None,
                "current_title": "Final Production Handoff Has Missing Inputs",
                "current_detail": (
                    "One or more branches lost a current final visual, narration or "
                    "sound-design input. Rebuild the stale upstream artifact before "
                    "attempting final production."
                ),
                "next_action_id": None,
                "next_title": "Repair missing final-production inputs",
            }

        return {
            "state": "FINAL_SOUND_PROVIDER_REQUIRED",
            "current_action_id": None,
            "current_title": "Final Production Handoff Ready",
            "current_detail": (
                "The approved visual edit and narration are packaged and current. "
                "Final music/SFX are still descriptive intent only. No paid provider "
                "has been called. Connect a commercial-safe final sound/provider path "
                "before a publish-ready export."
            ),
            "next_action_id": None,
            "next_title": "Connect final sound/provider assets",
        }

    production_visual = production_visual_artifact_state()
    if (
        voice.get("visual_ready")
        and production_visual.get("manifests_ready")
        and not readiness.get("auto_continue", {}).get("enabled")
    ):
        return {
            "state": "VISUAL_ACQUISITION_REQUIRED",
            "current_action_id": None,
            "current_title": "Visual acquisition manifest ready",
            "current_detail": (
                "The Production Engine has mapped every accepted format beat to "
                "the cheap-first visual policy. Asset acquisition is the next build."
            ),
            "next_action_id": None,
            "next_title": "Acquire Visual Assets",
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
                    ACTION_DEFS[next_id]["label"] if next_id else "Workflow complete"
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
    fmt = format_artifact_state()
    voice = voice_performance_artifact_state()
    engagement_payload = safe_load_json(PRODUCTION_ENGAGEMENT_SUMMARY)
    engagement = engagement_payload if isinstance(engagement_payload, dict) else {}
    preview_gate = narration_preview_gate_snapshot()
    narration = narration_artifact_state()
    production_visual = production_visual_artifact_state()
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
                    "workflow" if action_id in WORKFLOW_ACTION_ORDER else "tools"
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
        "format": fmt,
        "format_gate": fmt["format_gate"],
        "voice_performance": voice,
        "performance_gate": voice["performance_gate"],
        "pre_render_engagement": engagement,
        "narration_preview_gate": preview_gate,
        "narration": narration,
        "narration_spend_gate": narration["spend_gate"],
        "narration_render_return": narration["render_return"],
        "production_visual": production_visual,
        "storyboard": production_storyboard_snapshot(),
        "visual_search_prepare": visual_search_prepare_snapshot(),
        "visual_search_acquire": visual_search_acquire_snapshot(),
        "visual_post_search": visual_post_search_artifact_state(),
        "visual_candidate_gate": visual_candidate_review_snapshot(),
        "visual_rights_gate": visual_rights_review_snapshot(),
        "visual_asset_acquisition": visual_asset_acquisition_artifact_state(),
        "managed_visual_assets": managed_visual_asset_snapshot(),
        "visual_rough_cut_gate": visual_rough_cut_review_snapshot(),
        "visual_spend_gate": visual_spend_review_snapshot(),
        "visual_generation_handoff": visual_generation_handoff_artifact_state(),
        "generated_visual_assets": generated_visual_asset_snapshot(),
        "visual_assembly": visual_assembly_artifact_state(
            visual_post_search_artifact_state().get("expected_branches", [])
        ),
        "edit_manifest": edit_manifest_artifact_state(
            visual_post_search_artifact_state().get("expected_branches", [])
        ),
        "edit_preview": edit_preview_artifact_state(
            visual_post_search_artifact_state().get("expected_branches", [])
        ),
        "edit_preview_gate": edit_preview_review_snapshot(),
        "final_production_handoff": final_production_handoff_artifact_state(
            visual_post_search_artifact_state().get("expected_branches", [])
        ),
        "outputs": {
            "experiment_01": str(EXP1_OUTPUT),
            "experiment_02": str(EXP2_OUTPUT),
            "production": str(PRODUCTION_OUTPUT),
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
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

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
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

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
        if route == "/api/script-section-review":
            query = parse_qs(urlparse(self.path).query)
            concept_id = str((query.get("concept_id") or [""])[0]).strip()
            fmt = str((query.get("format") or [""])[0]).strip()
            if bool(concept_id) != bool(fmt):
                self._send_json(
                    {"error": "concept_id and format must be supplied together."},
                    400,
                )
                return
            self._send_json(
                script_section_review_snapshot(
                    concept_id if concept_id else None,
                    fmt if fmt else None,
                )
            )
            return
        if route == "/api/format-gate":
            self._send_json(format_gate_snapshot())
            return
        if route == "/api/performance-gate":
            self._send_json(performance_gate_snapshot())
            return
        if route == "/api/narration-preview-gate":
            self._send_json(narration_preview_gate_snapshot())
            return
        if route == "/api/narration-preview-audio":
            query = parse_qs(urlparse(self.path).query)
            concept_id = str((query.get("concept_id") or [""])[0])
            fmt = str((query.get("format") or [""])[0])
            match = next(
                (
                    item for item in narration_preview_gate_snapshot().get("items", [])
                    if str(item.get("concept_id") or "") == concept_id
                    and str(item.get("format") or "") == fmt
                    and item.get("audio_ready")
                ),
                None,
            )
            if not match or not match.get("audio"):
                self._send_json({"error": "Free preview audio is not ready."}, 404)
                return
            audio_path = Path(str(match["audio"])).resolve()
            if PRODUCTION_PREVIEW_AUDIO_DIR.resolve() not in audio_path.parents:
                self._send_json({"error": "Invalid preview audio path."}, 403)
                return
            self._send_static(audio_path, "audio/wav")
            return
        if route == "/api/narration-spend-gate":
            self._send_json(narration_spend_gate_snapshot())
            return
        if route == "/api/narration-render-return":
            self._send_json(narration_render_return_snapshot())
            return
        if route == "/api/visual-candidate-review":
            self._send_json(visual_candidate_review_snapshot())
            return
        if route == "/api/visual-rights-review":
            self._send_json(visual_rights_review_snapshot())
            return
        if route == "/api/visual-rough-cut-review":
            self._send_json(visual_rough_cut_review_snapshot())
            return
        if route == "/api/visual-spend-review":
            self._send_json(visual_spend_review_snapshot())
            return
        if route == "/api/generated-visual-asset":
            self._send_json(generated_visual_asset_snapshot())
            return
        if route == "/api/managed-visual-asset":
            self._send_json(managed_visual_asset_snapshot())
            return
        if route == "/api/edit-preview-review":
            self._send_json(edit_preview_review_snapshot())
            return
        if route == "/api/edit-preview-video":
            query = parse_qs(urlparse(self.path).query)
            concept_id = str((query.get("concept_id") or [""])[0])
            fmt = str((query.get("format") or [""])[0])
            match = next(
                (
                    item
                    for item in edit_preview_review_snapshot().get(
                        "items", []
                    )
                    if str(item.get("concept_id") or "") == concept_id
                    and str(item.get("format") or "") == fmt
                ),
                None,
            )
            if not match or not match.get("preview_file"):
                self._send_json(
                    {"error": "Current edit preview is not ready."},
                    404,
                )
                return
            preview_path = Path(str(match["preview_file"])).resolve()
            if (
                preview_path.parent.resolve()
                != PRODUCTION_EDIT_PREVIEW_DIR.resolve()
            ):
                self._send_json({"error": "Invalid edit preview path."}, 403)
                return
            self._send_static(preview_path, "video/mp4")
            return
        if route == "/api/storyboard-review":
            self._send_json(storyboard_review_snapshot())
            return
        if route == "/api/narration-performance-review":
            self._send_json(narration_performance_revision_snapshot())
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
        content_type = (
            str(self.headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
        )
        if content_type != "application/json":
            return "POST requests require Content-Type: application/json."

        port = int(getattr(self.server, "server_port", 0))
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

        gate_lock_error = human_gate_mutation_block_reason(route)
        if gate_lock_error:
            self._send_json({"error": gate_lock_error}, 409)
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
                auto_job = maybe_start_automatic_workflow()
                if auto_job:
                    payload = {**payload, "automation_job": auto_job}
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
                auto_job = maybe_start_automatic_workflow()
                if auto_job:
                    payload = {**payload, "automation_job": auto_job}
                self._send_json(payload)
                return

            if route == "/api/human-analysis-review":
                payload = apply_human_analysis_review_action(
                    video_id=str(body.get("video_id", "")),
                    item_id=str(body.get("item_id", "")),
                    decision=str(body.get("decision", "")),
                    note=(str(body["note"]) if body.get("note") is not None else None),
                )
                auto_job = maybe_start_automatic_workflow()
                if auto_job:
                    payload = {**payload, "automation_job": auto_job}
                self._send_json(payload)
                return

            if route == "/api/concept-gate":
                payload = apply_concept_gate_action(
                    concept_id=str(body.get("concept_id", "")),
                    decision=str(body.get("decision", "")),
                    criteria=body.get("criteria", {}),
                    note=(str(body["note"]) if body.get("note") is not None else None),
                )
                auto_job = maybe_start_automatic_workflow()
                if auto_job:
                    payload = {**payload, "automation_job": auto_job}
                self._send_json(payload)
                return

            if route == "/api/packaging-gate":
                payload = apply_packaging_gate_action(
                    package_id=str(body.get("package_id", "")),
                    decision=str(body.get("decision", "")),
                    criteria=body.get("criteria", {}),
                    note=(str(body["note"]) if body.get("note") is not None else None),
                    selected_titles=body.get("selected_titles"),
                )
                auto_job = maybe_start_automatic_workflow()
                if auto_job:
                    payload = {**payload, "automation_job": auto_job}
                self._send_json(payload)
                return

            if route == "/api/research-gate":
                payload = apply_research_gate_action(
                    concept_id=str(body.get("concept_id", "")),
                    claim_id=str(body.get("claim_id", "")),
                    decision=str(body.get("decision", "")),
                    criteria=body.get("criteria", {}),
                    note=(str(body["note"]) if body.get("note") is not None else None),
                )
                auto_job = maybe_start_automatic_workflow()
                if auto_job:
                    payload = {**payload, "automation_job": auto_job}
                self._send_json(payload)
                return

            if route == "/api/script-gate":
                payload = apply_script_gate_action(
                    concept_id=str(body.get("concept_id", "")),
                    format=str(body.get("format", "")),
                    decision=str(body.get("decision", "")),
                    criteria=body.get("criteria", {}),
                    note=(str(body["note"]) if body.get("note") is not None else None),
                )
                auto_job = maybe_start_automatic_workflow()
                if auto_job:
                    payload = {**payload, "automation_job": auto_job}
                self._send_json(payload)
                return

            if route == "/api/script-section-review":
                payload = apply_script_section_review_action(
                    concept_id=str(body.get("concept_id", "")),
                    fmt=str(body.get("format", "")),
                    action=str(body.get("action", "")),
                    target_id=(
                        str(body["target_id"])
                        if body.get("target_id") is not None
                        else None
                    ),
                    reason=(
                        str(body["reason"])
                        if body.get("reason") is not None
                        else None
                    ),
                    custom_instruction=(
                        str(body["custom_instruction"])
                        if body.get("custom_instruction") is not None
                        else None
                    ),
                    selection_id=(
                        str(body["selection_id"])
                        if body.get("selection_id") is not None
                        else None
                    ),
                    replacement_text=(
                        str(body["replacement_text"])
                        if body.get("replacement_text") is not None
                        else None
                    ),
                )
                self._send_json(payload)
                return

            if route == "/api/format-gate":
                payload = apply_format_gate_action(
                    concept_id=str(body.get("concept_id", "")),
                    decision=str(body.get("decision", "")),
                    criteria=body.get("criteria", {}),
                    note=(str(body["note"]) if body.get("note") is not None else None),
                )
                auto_job = maybe_start_automatic_workflow()
                if auto_job:
                    payload = {**payload, "automation_job": auto_job}
                self._send_json(payload)
                return

            if route == "/api/performance-gate":
                payload = apply_performance_gate_action(
                    concept_id=str(body.get("concept_id", "")),
                    format=str(body.get("format", "")),
                    decision=str(body.get("decision", "")),
                    criteria=body.get("criteria", {}),
                    note=(str(body["note"]) if body.get("note") is not None else None),
                )
                auto_job = maybe_start_automatic_workflow()
                if auto_job:
                    payload = {**payload, "automation_job": auto_job}
                self._send_json(payload)
                return

            if route == "/api/narration-preview-gate":
                payload = apply_narration_preview_gate_action(
                    concept_id=str(body.get("concept_id", "")),
                    format=str(body.get("format", "")),
                    decision=str(body.get("decision", "")),
                    note=str(body.get("note") or ""),
                )
                auto_job = maybe_start_automatic_workflow()
                if auto_job:
                    payload = {**payload, "automation_job": auto_job}
                self._send_json(payload)
                return

            if route == "/api/narration-performance-review":
                payload = revise_narration_performance(
                    manifest_file=str(body.get("manifest_file", "")),
                    segment_id=str(body.get("segment_id", "")),
                    instruction=str(body.get("instruction") or ""),
                    delivery_changes=body.get("delivery_changes") if isinstance(body.get("delivery_changes"), dict) else {},
                )
                self._send_json(payload)
                return

            if route == "/api/visual-spend-review":
                spend_decision = str(
                    body.get("decision", "")
                ).strip().upper()
                spend_note = str(body.get("note") or "").strip()
                shot_id = str(body.get("shot_id") or "").strip()
                payload = apply_visual_spend_review_action(
                    gap_plan_file=str(body.get("gap_plan_file", "")),
                    shot_id=shot_id,
                    decision=spend_decision,
                    max_cost_usd=float(body.get("max_cost_usd") or 0),
                    note=spend_note,
                )
                routed_to = None
                if spend_decision == "RETRY_EXISTING":
                    concept_id = str(payload.get("concept_id") or "")
                    branch_format = str(payload.get("format") or "")
                    board = next(
                        (
                            item
                            for item in storyboard_review_snapshot().get(
                                "items", []
                            )
                            if str(item.get("concept_id") or "") == concept_id
                            and str(item.get("format") or "") == branch_format
                        ),
                        None,
                    )
                    if not isinstance(board, dict):
                        raise ValueError(
                            "Current storyboard for existing-visual retry "
                            "was not found."
                        )
                    revise_storyboard_shot(
                        storyboard_file=str(board.get("storyboard_file") or ""),
                        shot_id=shot_id,
                        instruction=spend_note,
                        changes={},
                    )
                    routed_to = "storyboard_visual_search"

                payload = {**payload, "rework_routed_to": routed_to}
                auto_job = maybe_start_automatic_workflow()
                if auto_job:
                    payload = {**payload, "automation_job": auto_job}
                self._send_json(payload)
                return

            if route == "/api/generated-visual-asset":
                payload = register_generated_visual_asset(
                    request_file=str(body.get("request_file", "")),
                    asset_file=str(body.get("asset_file", "")),
                    actual_cost_usd=float(body.get("actual_cost_usd") or 0),
                    provider=str(body.get("provider") or "higgsfield"),
                    provider_job_id=str(body.get("provider_job_id") or ""),
                    note=str(body.get("note") or ""),
                )
                auto_job = maybe_start_automatic_workflow()
                response = {
                    "registered": payload,
                    "generated_visual_assets": generated_visual_asset_snapshot(),
                }
                if auto_job:
                    response["automation_job"] = auto_job
                self._send_json(response)
                return

            if route == "/api/managed-visual-asset":
                payload = register_existing_visual_asset(
                    candidate_review_file=str(
                        body.get("candidate_review_file", "")
                    ),
                    shot_id=str(body.get("shot_id", "")),
                    asset_file=str(body.get("asset_file", "")),
                    note=str(body.get("note") or ""),
                )
                auto_job = maybe_start_automatic_workflow()
                response = {
                    "registered": payload,
                    "managed_visual_assets": managed_visual_asset_snapshot(),
                }
                if auto_job:
                    response["automation_job"] = auto_job
                self._send_json(response)
                return

            if route == "/api/edit-preview-review":
                payload = apply_edit_preview_action(
                    result_file=str(body.get("result_file", "")),
                    decision=str(body.get("decision", "")),
                    note=str(body.get("note") or ""),
                )
                auto_job = maybe_start_automatic_workflow()
                response = dict(payload)
                if auto_job:
                    response["automation_job"] = auto_job
                self._send_json(response)
                return

            if route == "/api/storyboard-review":
                payload = revise_storyboard_shot(
                    storyboard_file=str(body.get("storyboard_file", "")),
                    shot_id=str(body.get("shot_id", "")),
                    instruction=str(body.get("instruction") or ""),
                    changes=body.get("changes") if isinstance(body.get("changes"), dict) else {},
                )
                self._send_json(payload)
                return

            if route == "/api/visual-candidate-review":
                payload = apply_visual_candidate_review_action(
                    result_file=str(body.get("result_file", "")),
                    shot_id=str(body.get("shot_id", "")),
                    action=str(body.get("action", "")),
                    candidate_id=(str(body["candidate_id"]) if body.get("candidate_id") is not None else None),
                    note=str(body.get("note") or ""),
                )
                auto_job = maybe_start_automatic_workflow()
                if auto_job:
                    payload = {**payload, "automation_job": auto_job}
                self._send_json(payload)
                return

            if route == "/api/visual-rights-review":
                payload = apply_visual_rights_review_action(
                    candidate_review_file=str(
                        body.get("candidate_review_file", "")
                    ),
                    shot_id=str(body.get("shot_id", "")),
                    decision=str(body.get("decision", "")),
                    transformative_purpose=str(
                        body.get("transformative_purpose") or ""
                    ),
                    context_note=str(body.get("context_note") or ""),
                )
                auto_job = maybe_start_automatic_workflow()
                if auto_job:
                    payload = {**payload, "automation_job": auto_job}
                self._send_json(payload)
                return

            if route == "/api/visual-rough-cut-review":
                rough_decision = str(body.get("decision", "")).strip().upper()
                rough_note = str(body.get("note") or "").strip()
                rough_cut_file = str(body.get("rough_cut_file", ""))
                rough_payload = apply_visual_rough_cut_review_action(
                    rough_cut_file=rough_cut_file,
                    decision=rough_decision,
                    note=rough_note,
                )
                routed_to = None

                if rough_decision == "REWORK_VISUAL":
                    shot_id = str(body.get("shot_id") or "").strip()
                    if not shot_id:
                        raise ValueError(
                            "Visual rough-cut rework requires a storyboard shot."
                        )
                    concept_id = str(rough_payload.get("concept_id") or "")
                    branch_format = str(rough_payload.get("format") or "")
                    board = next(
                        (
                            item
                            for item in storyboard_review_snapshot().get(
                                "items", []
                            )
                            if str(item.get("concept_id") or "") == concept_id
                            and str(item.get("format") or "") == branch_format
                        ),
                        None,
                    )
                    if not isinstance(board, dict):
                        raise ValueError(
                            "Current storyboard for rough-cut visual rework "
                            "was not found."
                        )
                    revise_storyboard_shot(
                        storyboard_file=str(board.get("storyboard_file") or ""),
                        shot_id=shot_id,
                        instruction=rough_note,
                        changes={},
                    )
                    routed_to = "storyboard_visual_search"

                elif rough_decision == "REWORK_PACING":
                    concept_id = str(rough_payload.get("concept_id") or "")
                    branch_format = str(rough_payload.get("format") or "")
                    apply_format_gate_action(
                        concept_id=concept_id,
                        decision="REWORK",
                        criteria={},
                        note=(
                            f"Rough-cut pacing rework for {branch_format}: "
                            f"{rough_note}"
                        ),
                    )
                    routed_to = "format_gate"

                elif rough_decision == "REWORK_AUDIO":
                    concept_id = str(rough_payload.get("concept_id") or "")
                    branch_format = str(rough_payload.get("format") or "")
                    apply_performance_gate_action(
                        concept_id=concept_id,
                        format=branch_format,
                        decision="REWORK",
                        criteria={},
                        note=(
                            "Rough-cut audio/delivery rework: "
                            + rough_note
                        ),
                    )
                    routed_to = "performance_gate"

                payload = {
                    **rough_payload,
                    "rework_routed_to": routed_to,
                }
                auto_job = maybe_start_automatic_workflow()
                if auto_job:
                    payload = {**payload, "automation_job": auto_job}
                self._send_json(payload)
                return

            if route == "/api/narration-spend-gate":
                payload = apply_narration_spend_gate_action(
                    concept_id=str(body.get("concept_id", "")),
                    format=str(body.get("format", "")),
                    decision=str(body.get("decision", "")),
                    criteria=body.get("criteria", {}),
                    note=(str(body["note"]) if body.get("note") is not None else None),
                )
                auto_job = maybe_start_automatic_workflow()
                if auto_job:
                    payload = {**payload, "automation_job": auto_job}
                self._send_json(payload)
                return

            if route == "/api/narration-render-return":
                payload = register_narration_render_return(
                    concept_id=str(body.get("concept_id", "")),
                    format=str(body.get("format", "")),
                    provider_job_id=str(body.get("provider_job_id", "")),
                    actual_cost_usd=body.get("actual_cost_usd"),
                    segments=(
                        body.get("segments")
                        if isinstance(body.get("segments"), list)
                        else []
                    ),
                )
                auto_job = maybe_start_automatic_workflow()
                if auto_job:
                    payload = {**payload, "automation_job": auto_job}
                self._send_json(payload)
                return

            if route == "/api/open":
                target_id = str(body.get("target_id", ""))
                target = OPEN_TARGETS.get(target_id)
                if target is None:
                    raise ValueError("Unknown open target.")
                target.mkdir(parents=True, exist_ok=True)
                if os.name == "nt":
                    os.startfile(str(target))  # type: ignore[attr-defined]
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
