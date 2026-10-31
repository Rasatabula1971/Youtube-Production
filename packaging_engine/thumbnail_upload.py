"""Thumbnails made by the owner from a generated prompt, then uploaded (D-191).

For every packaged video, Short or long-form, the pipeline writes one detailed
prompt from the accepted package and its Packaging Brief: the canvas, the
title it sits beside, the subject and the surprise to show, the exact text for
the image, the facts it may show, and what to leave out. The owner takes the
prompt to an image tool of their choice (ChatGPT, Gemini, ...), makes the
thumbnail there, and uploads the finished image here. Publishing uses it.

An upload is tied to the title and thumbnail text it was made for: if either
changes, the upload no longer counts and a new one is asked for. The prompt
has no timestamp, so it stays the same while the package does. Production does
not wait for the thumbnail; publishing does.
"""

from __future__ import annotations

import hashlib
import json
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.jsonio import load_json
from core.pipeline_integrity import atomic_write_json
from core.request_memo import memoized
from core.slugs import safe_slug
from packaging_engine.packaging_brief import brief_is_current
from packaging_engine.packaging_brief import snapshot as packaging_brief_snapshot

HERE = Path(__file__).resolve().parent
UPLOAD_DIR = HERE / "output" / "thumbnail_uploads"
MAX_BYTES = 2_000_000  # YouTube's thumbnail limit is 2 MB
CANVAS = {
    "short": ("vertical 9:16", "1080 x 1920"),
    "long_form": ("16:9", "1280 x 720"),
}
KEEP_CLEAR = {
    "short": "the bottom fifth and the right edge, where YouTube puts the caption and buttons",
    "long_form": "the bottom-right corner, where YouTube shows the video length",
}
MOOD = {
    "curiosity": "curious, intriguing",
    "stakes": "tense, high stakes",
    "unexpected": "surprising",
    "surprise": "surprising",
    "mystery": "mysterious",
    "payoff": "satisfying, revealing",
    "comparison": "a clear side-by-side contrast",
    "consequence": "dramatic",
    "transformation": "a clear before and after",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def build_prompt(package: dict[str, Any], brief: dict[str, Any] | None) -> str:
    """One detailed, deterministic thumbnail prompt for an image tool."""
    brief = brief or {}
    fmt = str(package.get("format") or brief.get("format") or "long_form")
    ratio, size = CANVAS.get(fmt, CANVAS["long_form"])
    raw_concept = package.get("thumbnail_concept")
    concept: dict[str, Any] = raw_concept if isinstance(raw_concept, dict) else {}
    angle = _clean(package.get("psychological_angle")).lower()
    subject = _clean(concept.get("hero_subject")) or _clean(brief.get("strongest_visual_event"))
    surprise = _clean(concept.get("visual_anomaly")) or _clean(brief.get("opening_hook"))
    question = _clean(concept.get("viewer_visual_question")) or _clean(brief.get("central_question"))
    text = _clean(package.get("thumbnail_text"))
    claims = [
        _clean(claim.get("statement"))
        for claim in brief.get("approved_claims") or []
        if isinstance(claim, dict) and _clean(claim.get("statement"))
    ]
    lines = [
        f"Create a finished YouTube {'Shorts ' if fmt == 'short' else ''}thumbnail image.",
        "",
        f"Canvas: {ratio}, {size} pixels.",
        f'Video title, shown next to the thumbnail (do not write it out in full): "{_clean(package.get("title_text"))}"',
    ]
    if question:
        lines.append(f"The question it should make the viewer ask: {question}")
    if subject:
        lines.append(f"Main subject: {subject}")
    if surprise:
        lines.append(f"What is surprising about it: {surprise}")
    for label, key in (("Supporting detail", "secondary_element"), ("Action or moment", "visual_action")):
        if _clean(concept.get(key)):
            lines.append(f"{label}: {_clean(concept.get(key))}")
    if angle:
        lines.append(f"Mood: {MOOD.get(angle, angle)}.")
    if text:
        lines.append(f'Text on the image, exactly: "{text}". Large, bold, high contrast, no other words.')
    else:
        lines.append(
            "Text on the image: 2 to 4 large, bold words that add to the title rather than repeat it. "
            "No other words."
        )
    if claims:
        lines.append("Only these facts may appear, in words or in the picture:")
        lines.extend(f"- {claim}" for claim in claims)
        lines.append("Show no other number, statistic or claim.")
    else:
        lines.append("Show no numbers, statistics or factual claims.")
    lines.extend(
        [
            (
                "Style: photorealistic, one clear focal point, strong contrast, the subject well separated "
                "from a simpler or blurred background, readable on a phone at small size."
            ),
            f"Keep clear: {KEEP_CLEAR.get(fmt, KEEP_CLEAR['long_form'])}.",
            (
                "Do not include: real or famous people, logos or brand names, watermarks, YouTube icons or "
                "play buttons, borders."
            ),
        ]
    )
    return "\n".join(lines)


def _prompt_sha256(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def record_path(video_id: str) -> Path:
    return UPLOAD_DIR / f"{safe_slug(video_id)}.thumbnail_upload.json"


def _briefs_by_video() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in packaging_brief_snapshot().get("briefs", []):
        if not isinstance(item, dict):
            continue
        brief = brief_is_current(Path(str(item.get("brief_file") or "")))
        if brief is not None:
            out[str(brief.get("video_id") or "")] = brief
    return out


def _packages() -> list[dict[str, Any]]:
    from packaging_engine import final_packaging_review

    packages = []
    for _concept_id, bundle in sorted(final_packaging_review.current_bundles().items()):
        for _fmt, package in sorted((bundle.get("packages") or {}).items()):
            if isinstance(package, dict) and package.get("video_id"):
                packages.append(package)
    return packages


def _made_for(package: dict[str, Any]) -> dict[str, str]:
    return {"title_text": _clean(package.get("title_text")), "thumbnail_text": _clean(package.get("thumbnail_text"))}


def current_upload(package: dict[str, Any]) -> dict[str, Any] | None:
    """The uploaded thumbnail for this package, while it still matches its title and text."""
    path = record_path(str(package.get("video_id") or ""))
    if not path.is_file():
        return None
    try:
        record = load_json(path)
    except (OSError, ValueError):
        return None
    image = Path(str(record.get("image") or ""))
    if (
        not image.is_file()
        or record.get("made_for") != _made_for(package)
        or hashlib.sha256(image.read_bytes()).hexdigest() != record.get("image_sha256")
    ):
        return None
    return record


@memoized
def items() -> list[dict[str, Any]]:
    """Every packaged video with its prompt and its upload, if any."""
    briefs = _briefs_by_video()
    rows = []
    for package in _packages():
        video_id = str(package["video_id"])
        prompt = build_prompt(package, briefs.get(video_id))
        upload = current_upload(package)
        rows.append(
            {
                "video_id": video_id,
                "concept_id": video_id.split(":")[0],
                "format": package.get("format"),
                "title": package.get("title_text"),
                "prompt": prompt,
                "prompt_sha256": _prompt_sha256(prompt),
                "uploaded": upload is not None,
                "upload": upload,
                "replace_needed": upload is None and record_path(video_id).is_file(),
            }
        )
    return rows


def _sniff(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    return None


def image_size(data: bytes) -> tuple[int, int] | None:
    """Width and height of a PNG or JPEG, read from its header."""
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return int(width), int(height)
    if data.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                height, width = struct.unpack(">HH", data[index + 5:index + 9])
                return int(width), int(height)
            length = struct.unpack(">H", data[index + 2:index + 4])[0]
            index += 2 + length
    return None


def upload(*, video_id: str, data: bytes, made_with: str, reviewer: str) -> dict[str, Any]:
    """Store the thumbnail the owner made from this video's prompt."""
    row = next((item for item in items() if item["video_id"] == video_id), None)
    if row is None:
        raise ValueError("No packaged video has that id; its package must be accepted first")
    suffix = _sniff(data)
    if suffix is None:
        raise ValueError("Upload a PNG or JPEG image")
    if len(data) > MAX_BYTES:
        raise ValueError("YouTube accepts thumbnails up to 2 MB; save it as a smaller JPEG")
    package = next(p for p in _packages() if str(p.get("video_id")) == video_id)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    slug = safe_slug(video_id)
    for old in UPLOAD_DIR.glob(f"{slug}.thumbnail.*"):
        old.unlink()
    image = UPLOAD_DIR / f"{slug}.thumbnail{suffix}"
    temporary = image.with_suffix(image.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(image)
    size = image_size(data)
    record = {
        "artifact": "thumbnail_upload",
        "video_id": video_id,
        "format": row["format"],
        "image": str(image.resolve()),
        "image_sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "width": size[0] if size else None,
        "height": size[1] if size else None,
        "made_with": _clean(made_with) or "an image tool",
        "made_for": _made_for(package),
        "prompt_sha256": row["prompt_sha256"],
        "uploaded_by": reviewer,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_json(record_path(video_id), record)
    return record


def image_file(video_id: str) -> Path | None:
    path = record_path(video_id)
    if not path.is_file():
        return None
    try:
        image = Path(str(json.loads(path.read_text(encoding="utf-8")).get("image") or ""))
    except (OSError, ValueError):
        return None
    return image if image.is_file() and image.parent.resolve() == UPLOAD_DIR.resolve() else None
