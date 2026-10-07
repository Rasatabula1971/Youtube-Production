"""Paid premium-visual dispatch for spend-authorized shots (D-140).

A shot reaches premium generation only when free and existing sources failed
and the human authorized a maximum cost at the Visual Spend Gate. The
generation handoff then wrote a provider-neutral request, and the generated
asset was made outside the app and registered by hand.

This module makes the provider call itself. For one current, authorized
request it generates the configured number of variants from the request's
generation brief, keeps them as candidates, and the human chooses one: the
choice is registered through ``visual_generated_asset_import.register``, so
assembly, the edit preview and everything after are unchanged. The request's
policy "the human must choose the final generated asset" is kept.

A generation is allowed only with a verified provider contract, an adapter,
an API key and a price per image (never guessed), and only while the money
already spent on the shot plus the estimate stays within the shot's
authorized maximum. Spend is recorded in the per-video budget as soon as it
happens (D-136), whether or not a variant is chosen. The one built-in adapter
generates still images through the common OpenAI-compatible images request;
a video model needs its own adapter function.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pipeline_integrity import append_jsonl, named_lock, read_jsonl
import video_budget
from visual_acquisition import load_json, safe_slug
from visual_generated_asset_import import (
    OUTPUT,
    REQUEST_DIR,
    _assert_current_request,
    _registry_path,
    register,
)

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "visual_provider_config.json"
CANDIDATES_DIR = OUTPUT / "generated_visual_candidates"
HISTORY_FILE = OUTPUT / "visual_dispatch_history.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_FILE)
    if not isinstance(config, dict) or "providers" not in config:
        raise ValueError("Visual provider config needs providers")
    return config


def _images_adapter(prompt: str, *, count: int, settings: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        from thumbnail_image_provider import openai_compatible_images
    except ImportError:  # imported as production_engine.visual_dispatch
        from production_engine.thumbnail_image_provider import openai_compatible_images
    return openai_compatible_images(prompt, count=count, settings=settings)


ADAPTERS: dict[str, Callable[..., list[dict[str, Any]]]] = {"OPENAI_COMPATIBLE_IMAGES": _images_adapter}


def provider_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        from thumbnail_image_provider import _env_value
    except ImportError:  # imported as production_engine.visual_dispatch
        from production_engine.thumbnail_image_provider import _env_value
    config = config or load_config()
    name = str(config.get("active_provider") or "").strip()
    if not name:
        return {"active_provider": "", "ready": False, "problems": ["No premium visual provider has been chosen yet."]}
    settings = (config.get("providers") or {}).get(name)
    if not isinstance(settings, dict):
        return {"active_provider": name, "ready": False, "problems": [f"Provider {name} is not configured."]}
    problems = []
    if str(settings.get("kind") or "") not in ADAPTERS:
        problems.append(f"Provider kind {settings.get('kind')!r} has no adapter.")
    for key, label in (("endpoint", "endpoint"), ("model", "model"), ("license", "licence terms")):
        if not str(settings.get(key) or "").strip():
            problems.append(f"The provider {label} is not set.")
    if str(settings.get("endpoint") or "").strip() and not str(settings.get("endpoint")).startswith("https://"):
        problems.append("The provider endpoint must be an https:// URL.")
    price = settings.get("price_per_image_usd")
    if not isinstance(price, (int, float)) or price < 0:
        problems.append("The price per image is not set; it is never guessed.")
    if settings.get("contract_verified") is not True:
        problems.append("The provider contract is not verified (contract_verified).")
    if not _env_value(str(settings.get("api_key_env") or "")):
        problems.append(f"The API key variable {settings.get('api_key_env') or '(unset)'} is empty.")
    return {
        "active_provider": name,
        "label": settings.get("label") or name,
        "model": settings.get("model"),
        "price_per_image_usd": price if isinstance(price, (int, float)) else None,
        "variants_per_shot": int(config.get("variants_per_shot") or 2),
        "ready": not problems,
        "problems": problems,
    }


def build_prompt(request: dict[str, Any]) -> str:
    raw = request.get("generation_brief")
    brief: dict[str, Any] = raw if isinstance(raw, dict) else {}
    parts = [
        ("Subject and action", brief.get("subject_and_action")),
        ("Narrative intent", brief.get("narrative_intent")),
        ("Camera angle", brief.get("camera_angle")),
        ("Framing", brief.get("framing")),
        ("Lens", brief.get("lens_feel")),
        ("Lighting", brief.get("lighting")),
        ("Depth of field", brief.get("depth_of_field")),
    ]
    lines = [f"{label}: {str(value).strip()}." for label, value in parts if str(value or "").strip()]
    negatives = [str(x) for x in brief.get("negative_constraints", []) if str(x).strip()]
    return " ".join(["Photorealistic 16:9 documentary still.", *lines, *negatives])


def _shot_key(request: dict[str, Any]) -> str:
    return ".".join(safe_slug(str(request.get(k) or "")) for k in ("concept_id", "format", "shot_id"))


def _events(key: str) -> list[dict[str, Any]]:
    return [event for event in read_jsonl(HISTORY_FILE) if event.get("shot_key") == key]


def spent_on_shot(key: str) -> float:
    return round(sum(float(e.get("cost_usd") or 0) for e in _events(key) if e.get("event") == "GENERATED"), 4)


def _sniff(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def _request_path(request_file: Any) -> Path:
    path = Path(str(request_file or "")).resolve()
    if path.parent != REQUEST_DIR.resolve():
        raise ValueError("Invalid visual generation request")
    return path


def _request_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(
    *,
    request_file: Any,
    reviewer: str = "",
    adapters: dict[str, Callable[..., list[dict[str, Any]]]] | None = None,
) -> dict[str, Any]:
    path = _request_path(request_file)
    # One generation per shot at a time: two clicks must not both pass the
    # authorized-maximum check before either has paid.
    with named_lock(f"visual_dispatch:{path.name}"):
        return _generate(path, reviewer, adapters)


def _generate(
    path: Path,
    reviewer: str,
    adapters: dict[str, Callable[..., list[dict[str, Any]]]] | None,
) -> dict[str, Any]:
    config = load_config()
    status = provider_status(config)
    if not status["ready"]:
        raise ValueError("Premium visual generation is not available: " + " ".join(status["problems"]))
    request = _assert_current_request(path)
    key = _shot_key(request)
    settings = config["providers"][status["active_provider"]]
    count = status["variants_per_shot"]
    estimate = round(float(settings["price_per_image_usd"]) * count, 4)
    authorized = round(float(request["spend_authorization"]["max_cost_usd"]), 4)
    spent = spent_on_shot(key)
    budget_video = video_budget.video_id(request.get("concept_id"), request.get("format"))
    ledger = video_budget.ledger_in(OUTPUT)
    shot_ref = f"shot:{request.get('shot_id')}"
    # Unconfirmed calls on this shot may have billed: they count against its
    # authorization until you settle them on the Budget tab (audit 2).
    unsettled = video_budget.unconfirmed_total(
        budget_video, category="visual", ref_prefix=shot_ref + ":", ledger=ledger
    )
    if spent + unsettled + estimate > authorized:
        raise ValueError(
            f"{count} variants (about ${estimate:.2f}) on top of ${spent:.2f} already spent"
            + (f" and ${unsettled:.2f} in unconfirmed calls" if unsettled else "")
            + f" would pass this shot's authorized ${authorized:.2f}"
        )
    prompt = build_prompt(request)
    adapter = (adapters or ADAPTERS)[str(settings["kind"])]  # a missing adapter is not a paid call
    # The call itself is reserved against the whole-video ceiling first, so
    # no paid call goes out once the video's budget is committed (audit 2).
    call_ref = f"{shot_ref}:call:{now()}"
    video_budget.reserve(
        video=budget_video, category="visual", ref=call_ref, amount_usd=estimate,
        actor=reviewer, note="Premium visual generation call", ledger=ledger,
    )
    try:
        images = adapter(prompt, count=count, settings=settings)
    except Exception as exc:
        if video_budget.outcome_unknown(exc):
            # The call may have run and billed: keep the estimate committed
            # until you confirm the cost on the Budget tab (D-166).
            video_budget.mark_unconfirmed(
                video=budget_video, category="visual", ref=call_ref, amount_usd=estimate,
                actor=reviewer, note=f"Visual generation call failed with an unknown outcome: {str(exc)[:200]}",
                ledger=ledger,
            )
        else:
            video_budget.release(video=budget_video, category="visual", ref=call_ref,
                                 note="provider refused the call; nothing charged", ledger=ledger)
        raise
    video_budget.release(video=budget_video, category="visual", ref=call_ref, note="spent", ledger=ledger)
    cost = round(float(settings["price_per_image_usd"]) * len(images), 4)
    directory = CANDIDATES_DIR / key
    directory.mkdir(parents=True, exist_ok=True)
    stored = []
    for image in images:
        data = image["bytes"]
        suffix = _sniff(data)
        if suffix is None:
            continue
        digest = hashlib.sha256(data).hexdigest()
        (directory / f"{digest[:16]}{suffix}").write_bytes(data)
        stored.append({"candidate_id": digest[:16], "file": f"{digest[:16]}{suffix}", "provider_job_id": image.get("provider_job_id")})
    append_jsonl(HISTORY_FILE, {
        "recorded_at": now(), "event": "GENERATED", "shot_key": key, "request_file": str(path),
        "request_sha256": _request_sha256(path),
        "provider": status["active_provider"], "model": settings.get("model"),
        "prompt": prompt, "cost_usd": cost, "candidates": stored, "reviewer": reviewer,
    })
    video_budget.record_actual(
        video=budget_video, category="visual", ref=shot_ref, total_usd=spent + cost,
        actor=reviewer, note="Premium visual variants generated", ledger=ledger,
    )
    return shot_view(path)


def choose(*, request_file: Any, candidate_id: str) -> dict[str, Any]:
    path = _request_path(request_file)
    request = _assert_current_request(path)
    key = _shot_key(request)
    current_sha = _request_sha256(path)
    for event in reversed(_events(key)):
        # A variant made for an earlier version of the request (another brief
        # or authorization) cannot become this shot's asset.
        if event.get("request_sha256") != current_sha:
            continue
        for candidate in event.get("candidates", []):
            if candidate.get("candidate_id") == candidate_id:
                return register(
                    request_file=str(path),
                    asset_file=str(CANDIDATES_DIR / key / candidate["file"]),
                    actual_cost_usd=spent_on_shot(key),
                    provider=str(event.get("provider") or ""),
                    provider_job_id=str(candidate.get("provider_job_id") or ""),
                    note=f"Chosen from {sum(len(e.get('candidates', [])) for e in _events(key))} generated variant(s)",
                    app_dispatched=True,
                )
    raise ValueError("Unknown generated variant")


def shot_view(path: Path) -> dict[str, Any]:
    request = load_json(path)
    key = _shot_key(request)
    current_sha = _request_sha256(path)
    candidates = [
        {**candidate, "provider": event.get("provider"), "generated_at": event.get("recorded_at")}
        for event in _events(key)
        if event.get("request_sha256") == current_sha
        for candidate in event.get("candidates", [])
        if (CANDIDATES_DIR / key / str(candidate.get("file"))).is_file()
    ]
    return {
        "request_file": str(path),
        "concept_id": request.get("concept_id"),
        "format": request.get("format"),
        "shot_id": request.get("shot_id"),
        "desired_visual": request.get("desired_visual"),
        "time_range": request.get("time_range"),
        "max_cost_usd": (request.get("spend_authorization") or {}).get("max_cost_usd"),
        "spent_usd": spent_on_shot(key),
        "prompt": build_prompt(request),
        "candidates": candidates,
        "registered": _registry_path(request).exists(),
    }


def snapshot() -> dict[str, Any]:
    status = provider_status()
    shots = []
    for path in sorted(REQUEST_DIR.glob("*.visual_generation_request.json")) if REQUEST_DIR.exists() else []:
        try:
            _assert_current_request(path)
        except (ValueError, OSError, json.JSONDecodeError):
            continue
        shots.append(shot_view(path))
    return {**status, "shots": shots}


def candidate_file_path(request_file: Any, candidate_id: str) -> Path:
    path = _request_path(request_file)
    key = _shot_key(load_json(path))
    for event in _events(key):
        for candidate in event.get("candidates", []):
            if candidate.get("candidate_id") == candidate_id:
                target = (CANDIDATES_DIR / key / str(candidate["file"])).resolve()
                if CANDIDATES_DIR.resolve() in target.parents and target.is_file():
                    return target
    raise ValueError("Unknown generated variant")
