"""Niche thumbnail study.

Tabulates what the top-performing thumbnails in one niche + format actually
look like, so Packaging can compare the Slice 25 thumbnail contract and D-096
title guidance with the niche's own conventions.

Stages (each idempotent, each writes under packaging_engine/output/niche_thumbnails/):

    select    offline  pick 20-30 breakout videos from Experiment 01 discovery output
    acquire   network  download each public thumbnail image from i.ytimg.com
    measure   offline  deterministic pixel metrics via ffmpeg/ffprobe (no model)
    annotate  offline  write/refresh the human annotation sheet; optional local
                       Ollama drafts that stay DRAFT until a human confirms them
    tabulate  offline  per-niche distributions + comparison with the Slice 25 contract

Tabulated numbers are descriptive and correlational. Selection is by
channel-relative breakout, and nothing here measures or predicts CTR.
"""

from __future__ import annotations

import argparse
import base64
import colorsys
import csv
import hashlib
import json
import re
import shutil
import statistics
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "experiment_02_analysis"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from pipeline_integrity import atomic_write_json


CONFIG_FILE = HERE / "niche_thumbnail_config.json"
PACKAGING_CONFIG_FILE = HERE / "packaging_config.json"
STUDY_ROOT = HERE / "output" / "niche_thumbnails"

FORMATS = {"long_form": "long_form_candidate", "short": "short_candidate"}
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
THUMBNAIL_URL = "https://i.ytimg.com/vi/{video_id}/{variant}"

HUE_FAMILIES = (
    ("red", 345.0, 15.0),
    ("orange", 15.0, 45.0),
    ("yellow", 45.0, 70.0),
    ("green", 70.0, 165.0),
    ("cyan", 165.0, 195.0),
    ("blue", 195.0, 255.0),
    ("purple", 255.0, 290.0),
    ("pink", 290.0, 345.0),
)
WARM_FAMILIES = {"red", "orange", "yellow", "pink"}
WORD_BUCKETS = ("0", "1-2", "3-5", "6+")
ANNOTATION_STATUSES = {"PENDING", "DRAFT", "CONFIRMED"}

ANNOTATION_PROMPT = """Describe only what is directly visible in this YouTube thumbnail.

Return strict JSON with these keys:
- text_overlay: the exact large text printed on the thumbnail, or "" if none or unreadable.
- focal_subject: the single thing the eye lands on first, in a few words.
- focal_subject_type: one of {types}.
- visual_element_count: number of distinct visual elements (people, objects, graphics, text blocks).
- visual_cue_count: number of arrows, circles or similar pointer graphics.
- face_present: true if a human face is clearly visible.

Do not infer intent, emotion, performance or anything not visible. Do not guess unreadable text.
"""


STOPWORDS = frozenset(
    "a an and are as at be by for from how i in is it my of on or the this "
    "to was what when why with you your".split()
)


def content_tokens(text: str) -> list[str]:
    cleaned = re.sub(r"[^0-9a-z\s]", "", text.lower())
    return [token for token in cleaned.split() if token not in STOPWORDS]


def comparison_rules(video_format: str, config: dict[str, Any]) -> dict[str, Any]:
    """Thresholds the niche is compared against: the live Slice 25 / D-096 contract."""
    packaging = json.loads(PACKAGING_CONFIG_FILE.read_text(encoding="utf-8"))
    contract = packaging["thumbnail_concepts"]
    comparison = config["comparison"]
    if video_format == "short":
        title_range = {"min": 1, "max": int(packaging["short_title_contract"]["max_chars"])}
    else:
        title_range = dict(comparison["long_form_title_preferred_chars"])
    return {
        "title_length_chars": title_range,
        "thumbnail_text_words": {"min": 1, "max": int(contract["maximum_text_words"])},
        "thumbnail_text_title_overlap_max": float(comparison["text_title_overlap_max"]),
        "thumbnail_max_visual_elements": int(contract["maximum_meaningful_visual_elements"]),
        "thumbnail_max_visual_cues": int(comparison["max_visual_cues"]),
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> dict[str, Any]:
    return load_json(CONFIG_FILE)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def study_dir(niche: str, video_format: str) -> Path:
    if video_format not in FORMATS:
        raise ValueError("format must be one of " + ", ".join(FORMATS))
    slug = re.sub(r"[^A-Za-z0-9_-]", "_", niche).strip("_")
    if not slug:
        raise ValueError("niche is required")
    return STUDY_ROOT / f"{slug}__{video_format}"


def tabulation_path(niche: str, video_format: str) -> Path:
    return study_dir(niche, video_format) / "tabulation.json"


# ------------------------------------------------------------------ select


def row_niches(row: dict[str, Any]) -> set[str]:
    niches = row.get("niches")
    if isinstance(niches, list):
        return {str(value) for value in niches}
    single = row.get("niche")
    return {str(single)} if single else set()


def select_study_set(
    rows: list[dict[str, Any]],
    *,
    niche: str,
    video_format: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Pick breakout videos: reliability tier, then outlier ratio, then views."""
    wanted_format = FORMATS[video_format]
    allowed_relevance = set(config["allowed_relevance"])
    reliability_order = list(config["outlier_reliability_order"])

    eligible: dict[str, dict[str, Any]] = {}
    excluded = Counter[str]()
    for row in rows:
        video_id = str(row.get("video_id", "")).strip()
        if not VIDEO_ID_PATTERN.match(video_id):
            excluded["invalid_video_id"] += 1
            continue
        if niche not in row_niches(row):
            continue
        if row.get("format_candidate") != wanted_format:
            excluded["other_format"] += 1
            continue
        if row.get("relevance") not in allowed_relevance:
            excluded["relevance"] += 1
            continue
        reliability = str(row.get("outlier_reliability") or "UNAVAILABLE")
        if reliability not in reliability_order:
            excluded["outlier_reliability"] += 1
            continue
        previous = eligible.get(video_id)
        if previous is None or (row.get("views") or 0) > (previous.get("views") or 0):
            eligible[video_id] = row

    def rank_key(row: dict[str, Any]) -> tuple[int, float, int]:
        reliability = str(row.get("outlier_reliability") or "UNAVAILABLE")
        ratio = row.get("outlier_ratio")
        return (
            reliability_order.index(reliability),
            -(float(ratio) if ratio is not None else 0.0),
            -int(row.get("views") or 0),
        )

    selected: list[dict[str, Any]] = []
    per_channel = Counter[str]()
    for row in sorted(eligible.values(), key=rank_key):
        channel = str(row.get("channel_id") or row.get("channel_title") or "")
        if per_channel[channel] >= int(config["max_per_channel"]):
            excluded["channel_cap"] += 1
            continue
        per_channel[channel] += 1
        selected.append(
            {
                "rank": len(selected) + 1,
                "video_id": row["video_id"],
                "title": row.get("title", ""),
                "channel_id": row.get("channel_id"),
                "channel_title": row.get("channel_title"),
                "views": row.get("views"),
                "outlier_ratio": row.get("outlier_ratio"),
                "outlier_reliability": row.get("outlier_reliability"),
                "relevance": row.get("relevance"),
            }
        )
        if len(selected) >= int(config["target_sample"]):
            break

    minimum = int(config["minimum_sample"])
    return {
        "artifact": "niche_thumbnail_study_set",
        "niche": niche,
        "format": video_format,
        "status": "READY" if len(selected) >= minimum else "INSUFFICIENT_SAMPLE",
        "selected_count": len(selected),
        "minimum_sample": minimum,
        "target_sample": int(config["target_sample"]),
        "selection_rule": (
            "relevance in allowed set; ranked by outlier reliability tier, then "
            "channel-relative outlier ratio, then views; at most "
            f"{int(config['max_per_channel'])} per channel"
        ),
        "excluded_counts": dict(sorted(excluded.items())),
        "videos": selected,
    }


def run_select(niche: str, video_format: str, sources: list[Path]) -> dict[str, Any]:
    config = load_config()
    rows: list[dict[str, Any]] = []
    used_sources = []
    for source in sources:
        if not source.exists():
            continue
        payload = load_json(source)
        if isinstance(payload, list):
            rows.extend(item for item in payload if isinstance(item, dict))
            used_sources.append(
                {"path": str(source), "sha256": sha256_bytes(source.read_bytes())}
            )
    if not used_sources:
        return {"status": "WAITING_FOR_DISCOVERY_OUTPUT", "sources": [str(s) for s in sources]}

    study = select_study_set(rows, niche=niche, video_format=video_format, config=config)
    study["sources"] = used_sources
    study["selected_at"] = utc_now()
    directory = study_dir(niche, video_format)
    directory.mkdir(parents=True, exist_ok=True)
    atomic_write_json(directory / "study_set.json", study)
    return {key: study[key] for key in ("status", "niche", "format", "selected_count")}


# ----------------------------------------------------------------- acquire


def http_fetch(url: str, timeout: float = 20.0) -> bytes | None:
    """Return the body, or None when YouTube has no image at this variant."""
    if not url.startswith("https://i.ytimg.com/vi/"):
        raise ValueError("Thumbnail fetch is restricted to i.ytimg.com")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        # The URL prefix check above pins this request to https://i.ytimg.com/vi/.
        with urllib.request.urlopen(  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            request, timeout=timeout
        ) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def run_acquire(
    niche: str,
    video_format: str,
    *,
    fetch: Callable[[str], bytes | None] = http_fetch,
) -> dict[str, Any]:
    config = load_config()
    directory = study_dir(niche, video_format)
    study = load_json(directory / "study_set.json")
    images = directory / "thumbnails"
    images.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "acquisition.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else {"items": {}}

    counts = Counter[str]()
    for video in study["videos"]:
        video_id = video["video_id"]
        existing = manifest["items"].get(video_id, {})
        path = images / f"{video_id}.jpg"
        if existing.get("status") == "ACQUIRED" and path.exists():
            if sha256_bytes(path.read_bytes()) == existing.get("sha256"):
                counts["reused"] += 1
                continue
        record: dict[str, Any] = {"status": "NOT_AVAILABLE", "attempted_at": utc_now()}
        for variant in config["thumbnail_variants"]:
            url = THUMBNAIL_URL.format(video_id=video_id, variant=variant)
            try:
                body = fetch(url)
            except (OSError, urllib.error.URLError) as exc:
                record = {
                    "status": "FAILED",
                    "error": type(exc).__name__,
                    "attempted_at": utc_now(),
                }
                break
            if body:
                path.write_bytes(body)
                record = {
                    "status": "ACQUIRED",
                    "url": url,
                    "variant": variant,
                    "path": str(path.relative_to(directory)),
                    "sha256": sha256_bytes(body),
                    "bytes": len(body),
                    "acquired_at": utc_now(),
                }
                break
        manifest["items"][video_id] = record
        counts[record["status"].lower()] += 1

    manifest["artifact"] = "niche_thumbnail_acquisition"
    atomic_write_json(manifest_path, manifest)
    return {"status": "ACQUISITION_COMPLETE", **dict(counts)}


# ----------------------------------------------------------------- measure


def ffprobe_size(path: Path) -> tuple[int, int]:
    output = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "json", str(path),
        ],
        check=True, capture_output=True, timeout=30,
    ).stdout
    stream = json.loads(output)["streams"][0]
    return int(stream["width"]), int(stream["height"])


def ffmpeg_pixels(path: Path, width: int, height: int) -> list[tuple[int, int, int]]:
    raw = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-i", str(path),
            "-vf", f"scale={width}:{height}", "-frames:v", "1",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ],
        check=True, capture_output=True, timeout=30,
    ).stdout
    if len(raw) != width * height * 3:
        raise ValueError("Unexpected decoded pixel buffer size")
    return [tuple(raw[i : i + 3]) for i in range(0, len(raw), 3)]  # type: ignore[misc]


def hue_family(hue_degrees: float) -> str:
    for name, start, end in HUE_FAMILIES:
        if start > end:
            if hue_degrees >= start or hue_degrees < end:
                return name
        elif start <= hue_degrees < end:
            return name
    return "red"


def luminance(rgb: tuple[int, int, int]) -> float:
    red, green, blue = (channel / 255 for channel in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def measure_pixels(
    pixels: list[tuple[int, int, int]],
    *,
    width: int,
    height: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    luma = [luminance(pixel) for pixel in pixels]
    families = Counter[str]()
    saturations = []
    for pixel in pixels:
        hue, saturation, value = colorsys.rgb_to_hsv(*(channel / 255 for channel in pixel))
        saturations.append(saturation)
        if (
            saturation >= float(config["colorful_min_saturation"])
            and value >= float(config["colorful_min_value"])
        ):
            families[hue_family(hue * 360.0)] += 1

    center: list[float] = []
    border: list[float] = []
    for index, value in enumerate(luma):
        x, y = index % width, index // width
        inside = width * 0.25 <= x < width * 0.75 and height * 0.2 <= y < height * 0.8
        (center if inside else border).append(value)

    colorful = sum(families.values())
    shares = {
        name: round(families[name] / colorful, 3) for name, _, _ in HUE_FAMILIES
    } if colorful else {name: 0.0 for name, _, _ in HUE_FAMILIES}
    ranked = [name for name, count in families.most_common() if count]
    border_mean = statistics.fmean(border)
    center_mean = statistics.fmean(center)
    if border_mean <= float(config["dark_background_max_luminance"]):
        background = "dark"
    elif border_mean >= float(config["light_background_min_luminance"]):
        background = "light"
    else:
        background = "mid"
    lift = center_mean - border_mean
    return {
        "mean_luminance": round(statistics.fmean(luma), 3),
        "luminance_spread": round(percentile(luma, 0.95) - percentile(luma, 0.05), 3),
        "mean_saturation": round(statistics.fmean(saturations), 3),
        "colorful_share": round(colorful / len(pixels), 3),
        "hue_family_shares": shares,
        "dominant_hue_family": ranked[0] if ranked else "neutral",
        "secondary_hue_family": ranked[1] if len(ranked) > 1 else None,
        "warm_share": round(
            sum(families[name] for name in WARM_FAMILIES) / colorful, 3
        ) if colorful else 0.0,
        "background_tone": background,
        "center_lift": round(lift, 3),
        "bright_subject_on_dark_background": (
            background == "dark"
            and lift >= float(config["bright_subject_min_center_lift"])
        ),
    }


def run_measure(niche: str, video_format: str) -> dict[str, Any]:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        return {"status": "BLOCKED", "reason": "ffmpeg and ffprobe are required"}
    config = load_config()
    directory = study_dir(niche, video_format)
    manifest = load_json(directory / "acquisition.json")
    grid = config["measure_grid"]
    minimum = config["minimum_resolution"]
    measurements: dict[str, Any] = {}
    failed = 0
    for video_id, record in sorted(manifest["items"].items()):
        if record.get("status") != "ACQUIRED":
            continue
        path = directory / record["path"]
        try:
            width, height = ffprobe_size(path)
            pixels = ffmpeg_pixels(path, int(grid["width"]), int(grid["height"]))
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            failed += 1
            continue
        metrics = measure_pixels(
            pixels, width=int(grid["width"]), height=int(grid["height"]), config=config
        )
        metrics.update(
            {
                "width": width,
                "height": height,
                "meets_minimum_resolution": (
                    width >= int(minimum["width"]) and height >= int(minimum["height"])
                ),
                "image_sha256": record["sha256"],
            }
        )
        measurements[video_id] = metrics
    atomic_write_json(
        directory / "measurements.json",
        {
            "artifact": "niche_thumbnail_measurements",
            "method": "ffmpeg downscale + deterministic RGB/HSV statistics",
            "measured_at": utc_now(),
            "items": measurements,
        },
    )
    return {"status": "MEASURED", "measured": len(measurements), "failed": failed}


# ---------------------------------------------------------------- annotate


def blank_annotation(video: dict[str, Any]) -> dict[str, Any]:
    return {
        "video_id": video["video_id"],
        "title": video.get("title", ""),
        "status": "PENDING",
        "text_overlay": "",
        "focal_subject": "",
        "focal_subject_type": "",
        "visual_element_count": None,
        "visual_cue_count": None,
        "face_present": None,
        "source": None,
        "note": "",
    }


def validate_annotation(item: dict[str, Any], config: dict[str, Any]) -> list[str]:
    errors = []
    if item.get("status") not in ANNOTATION_STATUSES:
        errors.append("status must be PENDING, DRAFT or CONFIRMED")
    if item.get("status") != "CONFIRMED":
        return errors
    if item.get("focal_subject_type") not in config["focal_subject_types"]:
        errors.append("focal_subject_type must be one of the configured types")
    if not str(item.get("focal_subject", "")).strip():
        errors.append("focal_subject is required")
    for field in ("visual_element_count", "visual_cue_count"):
        value = item.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"{field} must be a non-negative integer")
    if not isinstance(item.get("face_present"), bool):
        errors.append("face_present must be true or false")
    if not isinstance(item.get("text_overlay"), str):
        errors.append("text_overlay must be a string")
    return errors


def ollama_thumbnail_draft(
    image_path: Path, *, model: str, host: str, config: dict[str, Any]
) -> dict[str, Any]:
    from vision_review import normalize_ollama_host

    host = normalize_ollama_host(host)
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {
                "role": "user",
                "content": ANNOTATION_PROMPT.format(
                    types=", ".join(config["focal_subject_types"])
                ),
                "images": [base64.b64encode(image_path.read_bytes()).decode("ascii")],
            }
        ],
        "options": {"temperature": 0},
    }
    request = urllib.request.Request(
        host + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    # normalize_ollama_host restricts this request to loopback HTTP(S).
    with urllib.request.urlopen(request, timeout=90) as response:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        outer = json.loads(response.read().decode("utf-8"))
    parsed = json.loads(str(outer.get("message", {}).get("content") or "{}"))
    if not isinstance(parsed, dict):
        raise ValueError("Thumbnail draft must be a JSON object")
    draft_type = str(parsed.get("focal_subject_type", "")).strip()
    return {
        "text_overlay": re.sub(r"\s+", " ", str(parsed.get("text_overlay") or "")).strip(),
        "focal_subject": str(parsed.get("focal_subject") or "").strip()[:200],
        "focal_subject_type": (
            draft_type if draft_type in config["focal_subject_types"] else "other"
        ),
        "visual_element_count": max(0, int(parsed.get("visual_element_count") or 0)),
        "visual_cue_count": max(0, int(parsed.get("visual_cue_count") or 0)),
        "face_present": bool(parsed.get("face_present")),
    }


def run_annotate(
    niche: str,
    video_format: str,
    *,
    draft_model: str | None = None,
    draft_host: str = "http://127.0.0.1:11434",
) -> dict[str, Any]:
    config = load_config()
    directory = study_dir(niche, video_format)
    study = load_json(directory / "study_set.json")
    manifest_path = directory / "acquisition.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else {"items": {}}
    sheet_path = directory / "annotations.json"
    sheet = load_json(sheet_path) if sheet_path.exists() else {"items": []}
    existing = {item["video_id"]: item for item in sheet.get("items", [])}

    items = []
    drafted = 0
    for video in study["videos"]:
        item = existing.get(video["video_id"]) or blank_annotation(video)
        record = manifest["items"].get(video["video_id"], {})
        item["thumbnail_path"] = record.get("path")
        if draft_model and item["status"] == "PENDING" and record.get("status") == "ACQUIRED":
            try:
                draft = ollama_thumbnail_draft(
                    directory / record["path"], model=draft_model, host=draft_host, config=config
                )
            except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError):
                draft = None
            if draft:
                item.update(draft)
                item["status"] = "DRAFT"
                item["source"] = f"ollama:{draft_model}"
                drafted += 1
        items.append(item)

    counts = Counter(item["status"] for item in items)
    atomic_write_json(
        sheet_path,
        {
            "artifact": "niche_thumbnail_annotations",
            "instructions": [
                "Edit each item, then set status to CONFIRMED.",
                "DRAFT values come from a local vision model and are not tabulated until CONFIRMED.",
                "text_overlay is the exact large text on the thumbnail, or empty.",
                "focal_subject_type: " + ", ".join(config["focal_subject_types"]),
            ],
            "items": items,
        },
    )
    return {"status": "ANNOTATION_SHEET_READY", "drafted": drafted, **dict(counts)}


# ---------------------------------------------------------------- tabulate


def word_bucket(count: int) -> str:
    if count == 0:
        return "0"
    if count <= 2:
        return "1-2"
    if count <= 5:
        return "3-5"
    return "6+"


def distribution(values: list[Any]) -> dict[str, float]:
    if not values:
        return {}
    counts = Counter(str(value) for value in values)
    return {key: round(count / len(values), 3) for key, count in counts.most_common()}


def share(flags: list[bool]) -> float | None:
    return round(sum(flags) / len(flags), 3) if flags else None


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 3) if values else None


def conformance(name: str, rate: float | None, threshold: float) -> dict[str, Any]:
    if rate is None:
        verdict = "NO_DATA"
    elif rate >= threshold:
        verdict = "NICHE_FOLLOWS"
    else:
        verdict = "NICHE_DIVERGES"
    return {"hypothesis": name, "niche_share_conforming": rate, "verdict": verdict}


def tabulate(
    study: dict[str, Any],
    measurements: dict[str, Any],
    annotations: list[dict[str, Any]],
    *,
    config: dict[str, Any],
    advisory_rules: dict[str, Any],
) -> dict[str, Any]:
    titles = {video["video_id"]: video.get("title", "") for video in study["videos"]}
    measured = [measurements[vid] for vid in titles if vid in measurements]
    confirmed = [
        item
        for item in annotations
        if item.get("status") == "CONFIRMED"
        and item.get("video_id") in titles
        and not validate_annotation(item, config)
    ]
    minimum = int(config["minimum_sample"])
    threshold = float(config["convention_share"])

    hue_counts = Counter(item["dominant_hue_family"] for item in measured)
    used = [name for name, _, _ in HUE_FAMILIES if hue_counts[name]]
    crowded = [name for name, count in hue_counts.most_common(2) if count and name != "neutral"]
    accent_candidates = [
        name for name, _, _ in HUE_FAMILIES
        if name in WARM_FAMILIES | {"blue"} and hue_counts[name] / max(1, len(measured)) < 0.1
    ]

    bright_on_dark = share(
        [item["bright_subject_on_dark_background"] for item in measured]
    )
    color: dict[str, Any] = {
        "sample": len(measured),
        "background_tone": distribution([item["background_tone"] for item in measured]),
        "dominant_hue_family": distribution([item["dominant_hue_family"] for item in measured]),
        "hue_families_present": used,
        "crowded_hue_families": crowded,
        "accent_differentiation_candidates": accent_candidates,
        "median_warm_share": median([item["warm_share"] for item in measured]),
        "median_luminance_spread": median([item["luminance_spread"] for item in measured]),
        "median_saturation": median([item["mean_saturation"] for item in measured]),
        "bright_subject_on_dark_share": bright_on_dark,
        "meets_minimum_resolution_share": share(
            [item["meets_minimum_resolution"] for item in measured]
        ),
    }

    word_counts = [len(item["text_overlay"].split()) for item in confirmed]
    overlap_limit = float(advisory_rules.get("thumbnail_text_title_overlap_max", 0.6))
    repeats = []
    for item in confirmed:
        tokens = content_tokens(item["text_overlay"])
        if tokens:
            title_tokens = set(content_tokens(titles[item["video_id"]]))
            repeats.append(sum(t in title_tokens for t in tokens) / len(tokens) > overlap_limit)
    title_lengths = [len(title) for title in titles.values() if title]
    text_range = advisory_rules.get("thumbnail_text_words", {"min": 3, "max": 5})
    title_range = advisory_rules.get("title_length_chars", {"min": 40, "max": 60})
    max_elements = int(advisory_rules.get("thumbnail_max_visual_elements", 3))
    max_cues = int(advisory_rules.get("thumbnail_max_visual_cues", 2))

    text = {
        "sample": len(confirmed),
        "word_count_buckets": {
            bucket: share([word_bucket(n) == bucket for n in word_counts]) for bucket in WORD_BUCKETS
        },
        "median_word_count": median([float(n) for n in word_counts]),
        "text_repeats_title_share": share(repeats),
    }
    focal = {
        "sample": len(confirmed),
        "focal_subject_type": distribution([item["focal_subject_type"] for item in confirmed]),
        "face_present_share": share([item["face_present"] for item in confirmed]),
        "median_visual_element_count": median(
            [float(item["visual_element_count"]) for item in confirmed]
        ),
        "median_visual_cue_count": median(
            [float(item["visual_cue_count"]) for item in confirmed]
        ),
    }
    titles_summary = {
        "sample": len(title_lengths),
        "median_title_chars": median([float(n) for n in title_lengths]),
    }

    texted = [n for n in word_counts if n]
    hypotheses = [
        conformance(
            "TITLE_LENGTH",
            share([title_range["min"] <= n <= title_range["max"] for n in title_lengths]),
            threshold,
        ),
        conformance(
            "THUMBNAIL_TEXT_WORDS (when text is used)",
            share([text_range["min"] <= n <= text_range["max"] for n in texted]),
            threshold,
        ),
        conformance(
            "THUMBNAIL_TEXT_ADDS_TO_TITLE",
            share([not flag for flag in repeats]),
            threshold,
        ),
        conformance(
            "THUMBNAIL_ELEMENT_COUNT",
            share([item["visual_element_count"] <= max_elements for item in confirmed]),
            threshold,
        ),
        conformance(
            "THUMBNAIL_CUE_COUNT",
            share([item["visual_cue_count"] <= max_cues for item in confirmed]),
            threshold,
        ),
        conformance(
            "DARK_BACKGROUND_BRIGHT_SUBJECT",
            bright_on_dark,
            threshold,
        ),
    ]

    return {
        "artifact": "niche_thumbnail_tabulation",
        "niche": study["niche"],
        "format": study["format"],
        "tabulated_at": utc_now(),
        "status": (
            "COMPLETE"
            if len(measured) >= minimum and len(confirmed) >= minimum
            else "PARTIAL"
        ),
        "sample": {
            "selected": len(titles),
            "measured": len(measured),
            "annotations_confirmed": len(confirmed),
            "minimum_sample": minimum,
        },
        "color": color,
        "text": text,
        "focal": focal,
        "titles": titles_summary,
        "hypothesis_comparison": hypotheses,
        "caveats": [
            "Descriptive and correlational: these are conventions of breakout videos, not causes of their performance.",
            "Selection uses channel-relative breakout ratio; no CTR is measured or predicted.",
            "Color metrics come from a downscaled image and approximate perceived color families.",
            "Text, focal-subject, element and cue figures use only human-CONFIRMED annotations.",
            "Where the niche diverges from a Slice 25 / D-096 packaging rule, treat the niche convention as the stronger local evidence, still unvalidated for this channel.",
        ],
    }


def write_csv(path: Path, study: dict[str, Any], measurements: dict[str, Any], annotations: dict[str, Any]) -> None:
    fields = [
        "rank", "video_id", "title", "channel_title", "views", "outlier_ratio",
        "background_tone", "dominant_hue_family", "secondary_hue_family", "warm_share",
        "luminance_spread", "bright_subject_on_dark_background", "width", "height",
        "annotation_status", "text_overlay", "word_count", "focal_subject_type",
        "focal_subject", "face_present", "visual_element_count", "visual_cue_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for video in study["videos"]:
            row = dict(video)
            row.update(measurements.get(video["video_id"], {}))
            annotation = annotations.get(video["video_id"], {})
            row["annotation_status"] = annotation.get("status", "PENDING")
            if annotation.get("status") == "CONFIRMED":
                row.update({key: annotation.get(key) for key in fields if key in annotation})
                row["word_count"] = len(str(annotation.get("text_overlay", "")).split())
            writer.writerow(row)


def render_report(result: dict[str, Any]) -> str:
    def pct(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.0%}"

    def num(value: float | None) -> str:
        return "n/a" if value is None else f"{value:g}"

    lines = [
        f"# Niche thumbnail study — {result['niche']} / {result['format']}",
        "",
        f"Status: **{result['status']}** · selected {result['sample']['selected']}"
        f" · measured {result['sample']['measured']}"
        f" · confirmed annotations {result['sample']['annotations_confirmed']}"
        f" (minimum {result['sample']['minimum_sample']})",
        "",
        "## Hypotheses vs this niche",
        "",
        "| Packaging rule | Niche share conforming | Verdict |",
        "|---|---|---|",
    ]
    for item in result["hypothesis_comparison"]:
        lines.append(
            f"| {item['hypothesis']} | {pct(item['niche_share_conforming'])} | {item['verdict']} |"
        )
    color = result["color"]
    lines += [
        "",
        "## Color",
        "",
        f"- Background tone: {color['background_tone']}",
        f"- Dominant hue family: {color['dominant_hue_family']}",
        f"- Crowded hue families: {', '.join(color['crowded_hue_families']) or 'none'}",
        f"- Accent differentiation candidates: {', '.join(color['accent_differentiation_candidates']) or 'none'}",
        f"- Bright subject on dark background: {pct(color['bright_subject_on_dark_share'])}",
        f"- At least 1280x720: {pct(color['meets_minimum_resolution_share'])}",
        "",
        "## Text and focal subject (confirmed annotations only)",
        "",
        f"- Word-count buckets: {result['text']['word_count_buckets']}",
        f"- Text repeats title: {pct(result['text']['text_repeats_title_share'])}",
        f"- Focal subject types: {result['focal']['focal_subject_type']}",
        f"- Face present: {pct(result['focal']['face_present_share'])}",
        f"- Median elements / cues: {num(result['focal']['median_visual_element_count'])}"
        f" / {num(result['focal']['median_visual_cue_count'])}",
        f"- Median title length: {num(result['titles']['median_title_chars'])} characters",
        "",
        "## Caveats",
        "",
    ]
    lines += [f"- {caveat}" for caveat in result["caveats"]]
    return "\n".join(lines) + "\n"


def run_tabulate(niche: str, video_format: str) -> dict[str, Any]:
    config = load_config()
    directory = study_dir(niche, video_format)
    study = load_json(directory / "study_set.json")
    measurements_path = directory / "measurements.json"
    measurements = load_json(measurements_path)["items"] if measurements_path.exists() else {}
    sheet_path = directory / "annotations.json"
    annotations = load_json(sheet_path)["items"] if sheet_path.exists() else []
    invalid = {
        item["video_id"]: errors
        for item in annotations
        if (errors := validate_annotation(item, config))
    }
    advisory_rules = comparison_rules(video_format, config)
    result = tabulate(
        study, measurements, annotations, config=config, advisory_rules=advisory_rules
    )
    result["invalid_annotations"] = invalid
    atomic_write_json(directory / "tabulation.json", result)
    write_csv(
        directory / "tabulation.csv",
        study,
        measurements,
        {item["video_id"]: item for item in annotations},
    )
    (directory / "REPORT.md").write_text(render_report(result), encoding="utf-8")
    return {"status": result["status"], **result["sample"], "invalid_annotations": len(invalid)}


def packaging_conventions(niche: str | None, format_intent: str | None) -> dict[str, Any]:
    """Compact tabulation summaries for a Packaging request; empty when absent."""
    if not niche:
        return {}
    formats = ["long_form", "short"] if format_intent == "either" else [str(format_intent)]
    summaries = {}
    for video_format in formats:
        if video_format not in FORMATS:
            continue
        path = tabulation_path(niche, video_format)
        if not path.exists():
            continue
        result = load_json(path)
        summaries[video_format] = {
            key: result.get(key)
            for key in ("status", "sample", "color", "text", "focal", "titles", "hypothesis_comparison")
        }
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Niche thumbnail study")
    parser.add_argument(
        "--mode",
        choices=("select", "acquire", "measure", "annotate", "tabulate"),
        required=True,
    )
    parser.add_argument("--niche", required=True)
    parser.add_argument("--format", choices=tuple(FORMATS), default="long_form")
    parser.add_argument("--source", type=Path, action="append", default=None)
    parser.add_argument("--draft-model", default=None)
    parser.add_argument("--draft-host", default="http://127.0.0.1:11434")
    args = parser.parse_args()

    if args.mode == "select":
        sources = args.source or [PROJECT_ROOT / path for path in load_config()["sources"]]
        result = run_select(args.niche, args.format, sources)
    elif args.mode == "acquire":
        result = run_acquire(args.niche, args.format)
    elif args.mode == "measure":
        result = run_measure(args.niche, args.format)
    elif args.mode == "annotate":
        result = run_annotate(
            args.niche, args.format, draft_model=args.draft_model, draft_host=args.draft_host
        )
    else:
        result = run_tabulate(args.niche, args.format)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
