"""Paid narration dispatch: call the configured provider after spend approval (D-139).

Until now the paid narration was produced outside the app and its audio
registered by hand. This module makes the provider call itself, segment by
segment, and hands the audio to the existing return registration
(``narration_render_import.register``). Everything after that is unchanged:
deterministic Audio QC, the Human Final Audio Gate (D-137) and the per-video
budget (D-136).

A dispatch is allowed only when all of these hold:

  * the provider contract is verified in narration_render_config.json (the
    narration request is BLOCKED otherwise, so no spend can be approved);
  * the provider adapter is configured: kind, API key variable, price per
    1,000 characters (never guessed) and model/voice;
  * the Human Narration Spend Gate approved the exact current request;
  * the estimate for the segments to render, added to what was already
    spent on this narration, stays within the approved worst case.

The first dispatch renders every segment. Later dispatches re-record only the
segments the human named at the Final Audio Gate, as the next attempt within
the approved regeneration policy; the other segments keep their registered
audio. Every call is appended to a dispatch history, and a provider failure
part-way records what was already spent.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pipeline_integrity import append_jsonl, read_jsonl
import video_budget
from narration_render import (
    CONFIG_FILE,
    OUTPUT_DIR,
    artifact_key,
    load_config,
    provider_contract_verified,
    safe_slug,
)
from narration_render_import import (
    current_authorization,
    current_result,
    register,
)

PROJECT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
STAGING_DIR = OUTPUT_DIR / "narration_dispatch_staging"
HISTORY_FILE = OUTPUT_DIR / "narration_dispatch_history.jsonl"
AUDIO_TYPES = {"audio/wav": ".wav", "audio/x-wav": ".wav", "audio/wave": ".wav", "audio/mpeg": ".mp3", "audio/mp3": ".mp3"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_value(name: str) -> str:
    value = os.getenv(name, "")
    if value or not PROJECT_ENV_FILE.exists():
        return value.strip()
    for line in PROJECT_ENV_FILE.read_text(encoding="utf-8").splitlines():
        key, _, raw = line.partition("=")
        if key.strip() == name:
            return raw.strip().strip('"').strip("'")
    return ""


# ---------------------------------------------------------------- adapters


def http_tts_json(
    segment: dict[str, Any], *, settings: dict[str, Any], endpoint: str, voice: dict[str, Any]
) -> dict[str, Any]:
    """POST one segment as JSON; accept raw audio or JSON with base64 audio.

    Request: {model, voice_id, text, speed, emotion, intensity, format}.
    Response: an audio/* body, or JSON {"audio": base64} / {"audio_base64": ...}
    with an optional "cost_usd" and "job_id".
    """
    delivery = segment.get("delivery") or {}
    payload = json.dumps(
        {
            "model": settings.get("model"),
            "voice_id": voice.get("voice_id") or settings.get("voice_id"),
            "text": segment["immutable_narration"],
            "speed": delivery.get("speed"),
            "emotion": delivery.get("emotion"),
            "intensity": delivery.get("intensity"),
            "format": settings.get("audio_format") or "wav",
        }
    ).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - endpoint comes from the verified contract
        endpoint,
        data=payload,
        headers={
            "Authorization": "Bearer " + _env_value(str(settings.get("api_key_env") or "")),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = float(settings.get("timeout_seconds") or 120)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            content_type = str(response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Narration provider refused the request (HTTP {exc.code})") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError(f"Narration provider call failed: {type(exc).__name__}") from exc
    if content_type in AUDIO_TYPES:
        return {"bytes": body, "suffix": AUDIO_TYPES[content_type]}
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Narration provider returned neither audio nor JSON") from exc
    encoded = data.get("audio") or data.get("audio_base64")
    if not encoded:
        raise ValueError("Narration provider response has no audio")
    return {
        "bytes": base64.b64decode(encoded),
        "suffix": "." + str(data.get("format") or settings.get("audio_format") or "wav").lstrip("."),
        "cost_usd": data.get("cost_usd"),
        "job_id": data.get("job_id"),
    }


ADAPTERS: dict[str, Callable[..., dict[str, Any]]] = {"HTTP_TTS_JSON": http_tts_json}


def provider_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config(CONFIG_FILE)
    raw = config.get("provider_adapter")
    settings: dict[str, Any] = raw if isinstance(raw, dict) else {}
    problems = []
    if not provider_contract_verified(config):
        problems.append(
            "The narration provider contract is not verified (provider_contract in narration_render_config.json)."
        )
    if str(settings.get("kind") or "") not in ADAPTERS:
        problems.append("No narration provider adapter is configured (provider_adapter.kind).")
    price = settings.get("price_per_1000_characters_usd")
    if not isinstance(price, (int, float)) or price < 0:
        problems.append("The price per 1,000 characters is not set; it is never guessed.")
    if not _env_value(str(settings.get("api_key_env") or "")):
        problems.append(f"The API key variable {settings.get('api_key_env') or '(unset)'} is empty.")
    return {
        "provider": config.get("provider"),
        "ready": not problems,
        "problems": problems,
        "price_per_1000_characters_usd": price if isinstance(price, (int, float)) else None,
    }


def estimate_usd(segments: list[dict[str, Any]], price_per_1000: float) -> float:
    characters = sum(len(str(s.get("immutable_narration") or "")) for s in segments)
    return round(characters / 1000.0 * float(price_per_1000), 4)


# ---------------------------------------------------------------- dispatch


def _history(key: str) -> list[dict[str, Any]]:
    return [event for event in read_jsonl(HISTORY_FILE) if event.get("key") == key]


def dispatch(
    *,
    concept_id: str,
    format: str,
    segment_ids: Any = None,
    reviewer: str = "",
    adapters: dict[str, Callable[..., dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    concept_id, fmt = str(concept_id or "").strip(), str(format or "").strip()
    config = load_config(CONFIG_FILE)
    status = provider_status(config)
    if not status["ready"]:
        raise ValueError("Paid narration dispatch is not available: " + " ".join(status["problems"]))
    authorization = current_authorization(concept_id, fmt)
    if authorization is None:
        raise ValueError("The Narration Spend Gate has not approved the current request for this video")
    _request_path, request, _estimate_path, _estimate, _spend_path, spend = authorization
    ceiling = float((spend.get("spend_gate") or {}).get("worst_case_estimate_usd") or 0)
    planned = [s for s in request.get("segments", []) if isinstance(s, dict)]
    previous = current_result(concept_id, fmt)
    previous_result = previous[1] if previous else None
    previous_segments = {
        str(s.get("segment_id")): s for s in (previous_result or {}).get("segments", []) if isinstance(s, dict)
    }
    wanted = [str(x) for x in (segment_ids or []) if str(x)]
    if previous_result is None:
        targets = planned
    else:
        if not wanted:
            raise ValueError("This narration was already returned; name the segments to re-record")
        unknown = sorted(set(wanted) - {str(s["segment_id"]) for s in planned})
        if unknown:
            raise ValueError("Unknown segment(s): " + ", ".join(unknown))
        targets = [s for s in planned if str(s["segment_id"]) in set(wanted)]
    max_attempts = int(request.get("max_attempts_per_segment") or 1)
    attempts = {}
    for segment in targets:
        prior = int((previous_segments.get(str(segment["segment_id"])) or {}).get("attempt") or 0)
        if prior + 1 > max_attempts:
            raise ValueError(f"{segment['segment_id']} has used all {max_attempts} approved attempts")
        attempts[str(segment["segment_id"])] = prior + 1

    settings = config["provider_adapter"]
    spent_before = float((previous_result or {}).get("actual_cost_usd") or 0)
    estimate = estimate_usd(targets, float(settings["price_per_1000_characters_usd"]))
    if spent_before + estimate > ceiling:
        raise ValueError(
            f"Rendering these segments (about ${estimate:.2f}) on top of ${spent_before:.2f} already "
            f"spent would pass the approved worst case ${ceiling:.2f}"
        )

    key = artifact_key(concept_id, fmt)
    stamp = now()
    staging = STAGING_DIR / key / stamp.replace(":", "-")
    staging.mkdir(parents=True, exist_ok=True)
    adapter = (adapters or ADAPTERS)[str(settings["kind"])]
    endpoint = str(config["provider_contract"]["endpoint"])
    voice = request.get("voice_identity") if isinstance(request.get("voice_identity"), dict) else {}
    rendered: dict[str, Path] = {}
    cost = 0.0
    job_ids = []
    budget_ledger = video_budget.ledger_in(OUTPUT_DIR)
    try:
        for segment in targets:
            segment_id = str(segment["segment_id"])
            audio = adapter(segment, settings=settings, endpoint=endpoint, voice=voice)
            suffix = str(audio.get("suffix") or ".wav")
            path = staging / f"{safe_slug(segment_id)}{suffix}"
            path.write_bytes(audio["bytes"])
            rendered[segment_id] = path
            reported = audio.get("cost_usd")
            cost += (
                float(reported)
                if isinstance(reported, (int, float))
                else estimate_usd([segment], float(settings["price_per_1000_characters_usd"]))
            )
            if audio.get("job_id"):
                job_ids.append(str(audio["job_id"]))
    except Exception as exc:
        partial = round(spent_before + cost, 4)
        append_jsonl(HISTORY_FILE, {
            "recorded_at": now(), "key": key, "concept_id": concept_id, "format": fmt,
            "event": "FAILED", "rendered": sorted(rendered), "cost_usd": round(cost, 4),
            "error": str(exc), "reviewer": reviewer,
        })
        if cost:
            video_budget.record_actual(
                video=video_budget.video_id(concept_id, fmt), category="narration", ref="narration",
                total_usd=partial, actor=reviewer, note="Narration dispatch failed part-way", ledger=budget_ledger,
            )
        raise

    total = round(spent_before + cost, 4)
    segments = []
    for segment in planned:
        segment_id = str(segment["segment_id"])
        if segment_id in rendered:
            segments.append({"segment_id": segment_id, "audio_file": str(rendered[segment_id]), "attempt": attempts[segment_id]})
        else:
            kept = previous_segments[segment_id]
            segments.append({"segment_id": segment_id, "audio_file": str(kept["audio_file"]), "attempt": int(kept["attempt"])})
    job_id = ",".join(job_ids) or f"{config.get('provider')}-{stamp}"
    try:
        register(concept_id=concept_id, format=fmt, provider_job_id=job_id, actual_cost_usd=total, segments=segments)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    registered = current_result(concept_id, fmt)
    result = registered[1] if registered else {}
    append_jsonl(HISTORY_FILE, {
        "recorded_at": now(), "key": key, "concept_id": concept_id, "format": fmt,
        "event": "RENDERED", "rendered": sorted(rendered), "attempts": attempts,
        "cost_usd": round(cost, 4), "total_cost_usd": total, "provider_job_id": job_id, "reviewer": reviewer,
    })
    return result


def snapshot() -> dict[str, Any]:
    status = provider_status()
    events = read_jsonl(HISTORY_FILE)
    return {**status, "history": events[-20:]}
