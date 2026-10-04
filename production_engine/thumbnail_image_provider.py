"""Candidate subject images for a thumbnail concept (D-135).

Vision: an image router produces three candidate visuals per thumbnail; the
human picks one, and the locked template composes the finished thumbnail.
Until now the renderer only accepted an image the human supplied by path.

This module adds the candidate step in front of the existing renderer:

  * a prompt built from the Slice 25 concept (no text, logos or watermarks);
  * GENERATE: one human-authorized call to the configured provider for three
    candidates, with an explicit maximum cost checked against per-thumbnail
    and per-video caps and recorded in an append-only spend ledger;
  * IMPORT: an image made in any external tool, recorded with its provider,
    licence and cost;
  * CHOOSE: the picked candidate becomes the render spec's subject image
    through ``thumbnail_review.update_spec``, so rights validation, rendering,
    staleness and the Human Thumbnail Gate are unchanged.

No provider is chosen yet. The one built-in adapter speaks the common
"OpenAI-compatible images" request shape and stays inactive until the human
configures it: endpoint, model, API key variable, price per image, licence
and a verified contract. The price is never guessed.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from production_engine import thumbnail_render as render
except ImportError:  # executed as a script from production_engine/
    import thumbnail_render as render  # type: ignore[no-redef]

from pipeline_integrity import append_jsonl, atomic_write_json, read_jsonl

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "thumbnail_image_config.json"
PROJECT_ENV_FILE = HERE.parent / ".env"
MANIFEST_NAME = "image_candidates.json"
CANDIDATE_DIR = "candidates"
IMAGE_SUFFIXES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
CANDIDATE_FILE = re.compile(r"^candidates/[a-z0-9-]{1,64}\.(png|jpg|jpeg|webp)$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config() -> dict[str, Any]:
    config = render.load_json(CONFIG_FILE)
    for key in ("candidates_per_thumbnail", "per_thumbnail_cap_usd", "per_video_cap_usd", "providers"):
        if key not in config:
            raise ValueError(f"Thumbnail image config is missing {key}")
    return config


def _env_value(name: str) -> str:
    value = os.getenv(name, "")
    if value or not PROJECT_ENV_FILE.exists():
        return value.strip()
    for line in PROJECT_ENV_FILE.read_text(encoding="utf-8").splitlines():
        key, _, raw = line.partition("=")
        if key.strip() == name:
            return raw.strip().strip('"').strip("'")
    return ""


# ------------------------------------------------------------------ prompt


def build_prompt(unit: dict[str, Any]) -> str:
    """A text-free subject image prompt from the thumbnail concept fields."""
    parts = [
        ("Hero subject", unit.get("hero_subject")),
        ("Secondary element", unit.get("secondary_element")),
        ("Visual anomaly", unit.get("visual_anomaly")),
        ("Action", unit.get("visual_action")),
        ("Emotion", unit.get("emotion")),
        ("Composition", unit.get("composition")),
        ("Background", unit.get("background")),
        ("Subject separation", unit.get("subject_separation_method")),
    ]
    lines = [f"{label}: {str(value).strip()}." for label, value in parts if str(value or "").strip()]
    people = (
        "A generic, non-identifiable person may appear; never a real or famous person."
        if unit.get("face_present") is True
        else "No people."
    )
    return " ".join(
        [
            "Photorealistic YouTube thumbnail subject image, one clear focal point,",
            "framed to survive a near-square crop, strong contrast, uncluttered.",
            *lines,
            people,
            "No text, letters, numbers, logos, brand marks or watermarks.",
        ]
    )


def prompt_sha256(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


# --------------------------------------------------------------- providers


def provider_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Whether the configured provider may be called, and what is missing."""
    config = config or load_config()
    name = str(config.get("active_provider") or "").strip()
    if not name:
        return {
            "active_provider": "",
            "ready": False,
            "problems": ["No image provider has been chosen yet; import images or configure one."],
        }
    settings = (config.get("providers") or {}).get(name)
    if not isinstance(settings, dict):
        return {"active_provider": name, "ready": False, "problems": [f"Provider {name} is not configured."]}
    problems = []
    if str(settings.get("kind") or "") not in ADAPTERS:
        problems.append(f"Provider kind {settings.get('kind')!r} has no adapter.")
    for key, label in (("endpoint", "endpoint"), ("model", "model"), ("license", "licence terms")):
        if not str(settings.get(key) or "").strip():
            problems.append(f"The provider {label} is not set.")
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
        "ready": not problems,
        "problems": problems,
    }


def openai_compatible_images(
    prompt: str, *, count: int, settings: dict[str, Any]
) -> list[dict[str, Any]]:
    """POST {model, prompt, n, size} and read data[].b64_json (or data[].url)."""
    payload = json.dumps(
        {
            "model": settings["model"],
            "prompt": prompt,
            "n": count,
            "size": settings.get("size") or "1024x1024",
            "response_format": "b64_json",
        }
    ).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - endpoint is human-configured https
        str(settings["endpoint"]),
        data=payload,
        headers={
            "Authorization": "Bearer " + _env_value(str(settings["api_key_env"])),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = float(settings.get("timeout_seconds") or 120)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Image provider refused the request (HTTP {exc.code})") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise ValueError(f"Image provider call failed: {type(exc).__name__}") from exc
    images = []
    for index, item in enumerate(body.get("data") or []):
        if not isinstance(item, dict):
            continue
        if item.get("b64_json"):
            data = base64.b64decode(item["b64_json"])
        elif item.get("url"):
            with urllib.request.urlopen(str(item["url"]), timeout=timeout) as response:  # noqa: S310
                data = response.read()
        else:
            continue
        images.append({"bytes": data, "provider_job_id": str(body.get("created") or "") + f"-{index}"})
    return images


ADAPTERS: dict[str, Callable[..., list[dict[str, Any]]]] = {
    "OPENAI_COMPATIBLE_IMAGES": openai_compatible_images,
}


# ---------------------------------------------------------------- manifest


def manifest_path(render_id: str) -> Path:
    return render.unit_dir(render_id) / MANIFEST_NAME


def ledger_path() -> Path:
    return render.THUMBNAILS_DIR / "thumbnail_image_spend.jsonl"


def load_manifest(render_id: str) -> dict[str, Any]:
    path = manifest_path(render_id)
    if path.exists():
        return render.load_json(path)
    return {"artifact": "thumbnail_image_candidates", "render_id": render_id, "candidates": []}


def video_spend(video_id: str) -> float:
    return round(
        sum(
            float(event.get("actual_cost_usd") or 0)
            for event in read_jsonl(ledger_path())
            if event.get("video_id") == video_id and event.get("event") == "GENERATED"
        ),
        4,
    )


def _sniff(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def _store(render_id: str, data: bytes, record: dict[str, Any]) -> dict[str, Any]:
    suffix = _sniff(data)
    if suffix is None:
        raise ValueError("The image is not a PNG, JPEG or WebP file")
    digest = hashlib.sha256(data).hexdigest()
    candidate_id = digest[:16]
    directory = render.unit_dir(render_id) / CANDIDATE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{candidate_id}{suffix}").write_bytes(data)
    return {
        **record,
        "candidate_id": candidate_id,
        "file": f"{CANDIDATE_DIR}/{candidate_id}{suffix}",
        "sha256": digest,
        "created_at": now(),
    }


def _current_unit(render_id: str) -> dict[str, Any]:
    unit = next((u for u in render.load_render_units() if u["render_id"] == render_id), None)
    if unit is None:
        raise ValueError("Unknown or no longer validated render_id")
    return unit


def _save(render_id: str, manifest: dict[str, Any], added: list[dict[str, Any]]) -> None:
    known = {c.get("candidate_id") for c in manifest.get("candidates", [])}
    manifest["candidates"] = manifest.get("candidates", []) + [
        c for c in added if c["candidate_id"] not in known
    ]
    manifest["updated_at"] = now()
    atomic_write_json(manifest_path(render_id), manifest)


# ----------------------------------------------------------------- actions


def generate(
    *,
    render_id: str,
    max_cost_usd: Any,
    reviewer: str,
    adapters: dict[str, Callable[..., list[dict[str, Any]]]] | None = None,
) -> dict[str, Any]:
    """Human-authorized generation of the configured number of candidates."""
    config = load_config()
    status = provider_status(config)
    if not status["ready"]:
        raise ValueError("Image generation is not available: " + " ".join(status["problems"]))
    unit = _current_unit(render_id)
    settings = config["providers"][status["active_provider"]]
    count = int(config["candidates_per_thumbnail"])
    estimated = round(float(settings["price_per_image_usd"]) * count, 4)
    try:
        authorized = round(float(max_cost_usd), 4)
    except (TypeError, ValueError) as exc:
        raise ValueError("Generating images needs a maximum cost in US dollars") from exc
    if authorized < estimated:
        raise ValueError(f"The maximum cost ${authorized} is below the estimate ${estimated}")
    if authorized > float(config["per_thumbnail_cap_usd"]):
        raise ValueError(f"The maximum cost exceeds the per-thumbnail cap ${config['per_thumbnail_cap_usd']}")
    spent = video_spend(str(unit["video_id"]))
    if spent + estimated > float(config["per_video_cap_usd"]):
        raise ValueError(
            f"This video has spent ${spent} on thumbnail images; ${estimated} more would pass "
            f"the per-video cap ${config['per_video_cap_usd']}"
        )

    prompt = build_prompt(unit)
    adapter = (adapters or ADAPTERS)[str(settings["kind"])]
    images = adapter(prompt, count=count, settings=settings)
    actual = round(float(settings["price_per_image_usd"]) * len(images), 4)
    manifest = load_manifest(render_id)
    record_base = {
        "origin": "GENERATED",
        "provider": status["active_provider"],
        "model": settings.get("model"),
        "source_tier": str(config.get("generated_source_tier") or "CHEAP_AI"),
        "license": str(settings.get("license") or ""),
        "attribution": f"Generated with {settings.get('label') or status['active_provider']} ({settings.get('model')})",
        "prompt": prompt,
        "prompt_sha256": prompt_sha256(prompt),
        "concept_sha256": unit.get("source_sha256"),
        "cost_usd": round(float(settings["price_per_image_usd"]), 4),
    }
    added = [
        _store(render_id, image["bytes"], {**record_base, "provider_job_id": image.get("provider_job_id")})
        for image in images
    ]
    _save(render_id, manifest, added)
    append_jsonl(
        ledger_path(),
        {
            "recorded_at": now(),
            "event": "GENERATED",
            "render_id": render_id,
            "video_id": unit["video_id"],
            "provider": status["active_provider"],
            "model": settings.get("model"),
            "images": len(images),
            "estimated_cost_usd": estimated,
            "authorized_max_usd": authorized,
            "actual_cost_usd": actual,
            "reviewer": reviewer,
            "prompt_sha256": record_base["prompt_sha256"],
        },
    )
    return candidates_view(render_id)


def import_candidate(
    *,
    render_id: str,
    path: Any,
    provider: Any,
    source_tier: Any,
    license: Any,
    cost_usd: Any = 0,
    reviewer: str,
) -> dict[str, Any]:
    """Register an image made outside the app as a candidate."""
    config = load_config()
    template = render.load_template()
    unit = _current_unit(render_id)
    source = Path(str(path or "").strip()).expanduser()
    if not str(path or "").strip() or not source.is_file():
        raise ValueError("Choose an existing image file to import")
    if source.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError("Import a PNG, JPEG or WebP image")
    if source.stat().st_size > int(config.get("import_max_bytes") or 20_000_000):
        raise ValueError("The image file is too large to import")
    tier = str(source_tier or "").strip()
    if tier not in template["subject_allowed_source_tiers"]:
        raise ValueError(f"Source tier {tier or '(empty)'} is not permitted for thumbnails")
    if tier != "OWN_LIBRARY" and not str(license or "").strip():
        raise ValueError("A licence is required unless the image is from your own library")
    try:
        cost = round(float(cost_usd or 0), 4)
    except (TypeError, ValueError) as exc:
        raise ValueError("Cost must be a number of US dollars") from exc
    label = str(provider or "").strip() or "external tool"
    record = _store(
        render_id,
        source.read_bytes(),
        {
            "origin": "IMPORTED",
            "provider": label,
            "model": None,
            "source_tier": tier,
            "license": str(license or "").strip(),
            "attribution": f"Made with {label}",
            "prompt": build_prompt(unit),
            "prompt_sha256": prompt_sha256(build_prompt(unit)),
            "concept_sha256": unit.get("source_sha256"),
            "cost_usd": cost,
            "imported_from": source.name,
        },
    )
    _save(render_id, load_manifest(render_id), [record])
    append_jsonl(
        ledger_path(),
        {
            "recorded_at": now(),
            "event": "IMPORTED",
            "render_id": render_id,
            "video_id": unit["video_id"],
            "provider": label,
            "actual_cost_usd": cost,
            "reviewer": reviewer,
        },
    )
    return candidates_view(render_id)


def choose(*, render_id: str, candidate_id: str, accent_hex: Any = None) -> dict[str, Any]:
    """Make a candidate the render spec's subject image."""
    try:
        from production_engine import thumbnail_review as review
    except ImportError:  # executed as a script from production_engine/
        import thumbnail_review as review  # type: ignore[no-redef]

    unit = _current_unit(render_id)
    candidate = next(
        (c for c in load_manifest(render_id).get("candidates", []) if c.get("candidate_id") == candidate_id),
        None,
    )
    if candidate is None:
        raise ValueError("Unknown image candidate")
    if candidate.get("concept_sha256") != unit.get("source_sha256"):
        raise ValueError("This candidate was made for an earlier version of the thumbnail concept")
    spec_path = render.unit_dir(render_id) / "render_spec.json"
    spec = render.load_json(spec_path) if spec_path.exists() else {}
    accent = accent_hex or spec.get("accent_hex") or render.suggested_accent(unit, render.load_template())
    return review.update_spec(
        render_id=render_id,
        accent_hex=accent,
        subject_image={
            "path": candidate["file"],
            "source_tier": candidate.get("source_tier"),
            "license": candidate.get("license"),
            "source_url": "",
            "attribution": candidate.get("attribution"),
        },
    )


def candidates_view(render_id: str) -> dict[str, Any]:
    """Public candidate list for the UI (no absolute paths)."""
    unit = _current_unit(render_id)
    spec_path = render.unit_dir(render_id) / "render_spec.json"
    chosen = ""
    if spec_path.exists():
        chosen = str((render.load_json(spec_path).get("subject_image") or {}).get("path") or "")
    rows = []
    for candidate in load_manifest(render_id).get("candidates", []):
        rows.append(
            {
                key: candidate.get(key)
                for key in (
                    "candidate_id", "file", "origin", "provider", "model", "source_tier",
                    "license", "attribution", "cost_usd", "created_at",
                )
            }
            | {
                "current": candidate.get("concept_sha256") == unit.get("source_sha256"),
                "chosen": candidate.get("file") == chosen,
            }
        )
    return {
        "render_id": render_id,
        "prompt": build_prompt(unit),
        "candidates": rows,
        "video_spend_usd": video_spend(str(unit["video_id"])),
    }


def candidate_file_path(render_id: str, name: str) -> Path:
    if not CANDIDATE_FILE.match(name):
        raise ValueError("Unknown thumbnail file")
    path = render.unit_dir(render_id) / name
    if not path.is_file():
        raise ValueError("Thumbnail file not found")
    return path
