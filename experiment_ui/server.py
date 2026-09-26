"""Local experiment control UI for the YouTube Production project.

Dependency-free HTTP server bound to 127.0.0.1. The browser UI can run only
predefined experiment actions; arbitrary shell commands are never accepted.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
STATIC_DIR = HERE / "static"

UI_OUTPUT_DIR = PROJECT_ROOT / ".experiment_ui"
JOB_LOG_DIR = UI_OUTPUT_DIR / "jobs"
JOB_STATE_FILE = UI_OUTPUT_DIR / "job_state.json"

EXP1_OUTPUT = PROJECT_ROOT / "experiment_01_discovery" / "output"
EXP13_DIR = EXP1_OUTPUT / "experiment_01_3"
EXP13_CHECKPOINT = EXP1_OUTPUT / "experiment_01_3_discovery_checkpoint.json"
EXP14_DIR = EXP1_OUTPUT / "experiment_01_4"
EXP15_DIR = EXP1_OUTPUT / "experiment_01_5"

EXP2_DIR = PROJECT_ROOT / "experiment_02_analysis"
EXP2_OUTPUT = EXP2_DIR / "output"
SOURCE_ACQ_OUTPUT = PROJECT_ROOT / "source_acquisition" / "output"

ACTION_DEFS: dict[str, dict[str, Any]] = {
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
}

OPEN_TARGETS = {
    "experiment_01_output": EXP1_OUTPUT,
    "experiment_02_output": EXP2_OUTPUT,
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


def exp14_plan_status() -> str | None:
    return json_file_status(EXP14_DIR / "expansion_plan.json", "status")


def exp14_execution_status() -> str | None:
    return json_file_status(EXP14_DIR / "summary.json", "execution_status")


def exp15_status() -> str | None:
    return json_file_status(EXP15_DIR / "summary.json", "status")


def exp2_status() -> str | None:
    return json_file_status(EXP2_OUTPUT / "summary.json", "status")


def current_action_id() -> str | None:
    manager = globals().get("JOB_MANAGER")
    if manager is None:
        return None
    job = manager.public_job()
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

    cohort_ready = (
        exp13_manifest.exists()
        and exp13_summary.exists()
        and exp13_topic.exists()
    )
    valid_velocity_samples = exp13_valid_velocity_samples()
    velocity_ready = cohort_ready and valid_velocity_samples > 0
    cp_status = checkpoint_status()
    active_action = current_action_id()

    if velocity_ready:
        exp13_state = "VELOCITY_READY"
        exp13_human = "STAGE COMPLETE"
        exp13_tone = "complete"
        exp13_detail = (
            f"Measured velocity is available from "
            f"{valid_velocity_samples} valid samples."
        )
        exp13_next = "Proceed to Experiment 01.4."
    elif active_action == "exp13_refresh":
        exp13_state = "REFRESH_RUNNING"
        exp13_human = "VELOCITY REFRESH RUNNING"
        exp13_tone = "running"
        exp13_detail = "The frozen cohort is being measured for current velocity."
        exp13_next = "Wait for the refresh to finish."
    elif active_action == "exp13_discover":
        exp13_state = "DISCOVERY_RUNNING"
        exp13_human = "DISCOVERY RUNNING"
        exp13_tone = "running"
        exp13_detail = "Candidate discovery is running. The cohort is not finished yet."
        exp13_next = "Wait for discovery to finish."
    elif cohort_ready:
        exp13_state = "COHORT_FROZEN_AWAITING_REFRESH"
        exp13_human = "DISCOVERY COMPLETE — REFRESH NEEDED"
        exp13_tone = "action"
        exp13_detail = "The corrected cohort is frozen, but measured velocity is still missing."
        exp13_next = (
            "After at least one hour, run Refresh 01.3 Frozen Cohort."
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
    if study_set_ready:
        exp15_human = "STAGE COMPLETE"
        exp15_tone = "complete"
        exp15_next = "Proceed to Experiment 02."
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

    synthesis_ready = (
        EXP2_OUTPUT
        / "synthesis"
        / "transformation_handoff.json"
    ).exists()
    analyzed = has_json_files(EXP2_OUTPUT / "profiles_analyzed")
    reviewed = has_json_files(EXP2_OUTPUT / "profiles_reviewed")

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
        "analysis_batch_prepare",
        "analysis_model_one",
        "human_review_prepare",
    }:
        exp2_human = "ANALYSIS RUNNING"
        exp2_tone = "running"
        exp2_next = "Wait for the current Experiment 02 job to finish."
    elif not study_set_ready:
        exp2_human = "WAITING FOR 01.5"
        exp2_tone = "blocked"
        exp2_next = "Complete Experiment 01.5 first."
    elif reviewed or analyzed:
        exp2_human = "SYNTHESIS NEEDED"
        exp2_tone = "action"
        exp2_next = "Run Build Experiment 02 Synthesis."
    else:
        exp2_human = "READY TO PREPARE"
        exp2_tone = "ready"
        exp2_next = "Run Prepare Experiment 02 Profiles."

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
                    "done": cohort_ready,
                },
                {
                    "label": "Cohort frozen",
                    "done": cohort_ready,
                },
                {
                    "label": "Measured velocity samples collected",
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
            "state": handoff_status
            or (
                "READY_TO_BUILD"
                if exp14_complete
                else "WAITING_FOR_01_4"
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
                    "label": "Experiment 02 study set exists",
                    "done": study_set_ready,
                },
            ],
            "complete": study_set_ready,
            "ready": exp14_complete,
            "current": exp14_complete and not study_set_ready,
        },
        {
            "id": "02",
            "title": "Why Did It Work?",
            "state": analysis_status
            or (
                "READY_TO_PREPARE"
                if study_set_ready
                else "WAITING_FOR_01_5"
            ),
            "human_status": exp2_human,
            "tone": exp2_tone,
            "detail": "Evidence ingestion, FAIR analysis, human review and synthesis.",
            "next_action": exp2_next,
            "criteria": [
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
            "ready": study_set_ready,
            "current": study_set_ready and not synthesis_ready,
        },
    ]

def action_readiness() -> dict[str, dict[str, Any]]:
    exp13_cohort = (EXP13_DIR / "cohort_manifest.json").exists()
    exp13_evidence = (
        (EXP13_DIR / "topic_velocity.json").exists()
        and (EXP13_DIR / "summary.json").exists()
        and exp13_valid_velocity_samples() > 0
    )

    plan_ready = exp14_plan_status() == "READY"
    exp14_complete = exp14_execution_status() == "COMPLETE"
    study_set = (EXP15_DIR / "study_set.json").exists()

    enriched = has_json_files(EXP2_OUTPUT / "profiles_enriched")
    requests = has_json_files(EXP2_OUTPUT / "analysis_requests")
    analyzed = has_json_files(EXP2_OUTPUT / "profiles_analyzed")
    reviewed = has_json_files(EXP2_OUTPUT / "profiles_reviewed")

    agent_reach_installed = shutil.which("agent-reach") is not None
    yt_dlp_installed = shutil.which("yt-dlp") is not None

    return {
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
        "exp13_refresh": {
            "enabled": exp13_cohort,
            "reason": (
                "Frozen cohort available."
                if exp13_cohort
                else "Run 01.3 discovery first."
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
            "enabled": study_set,
            "reason": (
                "01.5 study set available."
                if study_set
                else "Waiting for 01.5 study set."
            ),
        },
        "fair_doctor": {
            "enabled": True,
            "reason": "Safe diagnostic; no inference.",
        },
        "analysis_batch_prepare": {
            "enabled": enriched,
            "reason": (
                "Enriched profiles available."
                if enriched
                else "Evidence ingestion must create enriched profiles first."
            ),
        },
        "analysis_model_one": {
            "enabled": requests,
            "reason": (
                "Analysis requests available."
                if requests
                else "Prepare analysis requests first."
            ),
        },
        "human_review_prepare": {
            "enabled": analyzed,
            "reason": (
                "Analyzed profiles available."
                if analyzed
                else "Run model or human analysis first."
            ),
        },
        "synthesis_build": {
            "enabled": analyzed or reviewed,
            "reason": (
                "Analyzed/reviewed profiles available."
                if analyzed or reviewed
                else "Waiting for Experiment 02 analyzed profiles."
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

            process = subprocess.Popen(
                action["command"],
                cwd=PROJECT_ROOT,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
                creationflags=creationflags,
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
                self._job["status"] = "SUCCEEDED" if return_code == 0 else "FAILED"
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


def status_payload() -> dict[str, Any]:
    readiness = action_readiness()
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
            }
        )

    return {
        "project_root": str(PROJECT_ROOT),
        "stages": stage_statuses(),
        "actions": actions,
        "job": JOB_MANAGER.current(),
        "checkpoint": {
            "exists": EXP13_CHECKPOINT.exists(),
            "status": checkpoint_status(),
        },
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
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        route = urlparse(self.path).path

        if route == "/":
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

        self.send_error(404)

    def do_POST(self) -> None:
        route = urlparse(self.path).path
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
