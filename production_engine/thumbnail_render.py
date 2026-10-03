"""Thumbnail rendering from a locked channel template.

Turns each validated Slice 25 thumbnail concept into a 1280x720 image:

    prepare  write/refresh one render spec per thumbnail concept that has at
             least one title pair passing Slice 26 validation
    render   compose the thumbnail with ffmpeg, write phone-size previews,
             deterministic checks, and a mock feed beside the niche's
             breakout thumbnails
    review   apply the Human Thumbnail Gate (ACCEPT / REWORK / REJECT)

About 80% of the design is locked in ``thumbnail_template.json`` (canvas,
layout, fonts, outline, background treatment, logo position). Each video
varies the subject image, the accent colour, and the approved text overlay.
The text overlay comes from the thumbnail concept and cannot be edited here.
Approving an image does not choose a title-thumbnail package; that remains the
job of the final Packaging Human Gate.

The subject image must carry provenance from a source tier that permits
thumbnail use. Editorial excerpts and unknown sources are refused.
"""

from __future__ import annotations

import argparse
import colorsys
import hashlib
import html
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
PACKAGING_DIR = PROJECT_ROOT / "packaging_engine"
for _path in (PROJECT_ROOT, PACKAGING_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from pipeline_integrity import atomic_write_json

import niche_thumbnail_study as niche

TEMPLATE_FILE = HERE / "thumbnail_template.json"
PACKAGING_CONFIG_FILE = PACKAGING_DIR / "packaging_config.json"
OUTPUT_DIR = HERE / "output"
THUMBNAILS_DIR = OUTPUT_DIR / "thumbnails"
APPROVED_THUMBNAILS_DIR = OUTPUT_DIR / "approved_thumbnails"
FONT_ENV = "THUMBNAIL_FONT_FILE"

MEASURE_SIZE = 100
MEASURE_ROW = 220
MEASURE_WIDTH = 4096
DECISIONS = {"ACCEPT", "REWORK", "REJECT"}
INK = bytes(1 if value > 96 else 0 for value in range(256))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", value).strip("._")
    return cleaned or "unknown"


def unit_dir(render_id: str) -> Path:
    return THUMBNAILS_DIR / safe_slug(render_id)


# ---------------------------------------------------------------- template


def rect(box: dict[str, Any]) -> tuple[int, int, int, int]:
    return int(box["x"]), int(box["y"]), int(box["w"]), int(box["h"])


def overlaps(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def validate_template(template: dict[str, Any]) -> list[str]:
    """The locked layout must fit the canvas and keep clear of the timestamp."""
    errors = []
    canvas = (0, 0, int(template["canvas"]["width"]), int(template["canvas"]["height"]))
    zone = rect(template["timestamp_safe_zone"])
    boxes = {
        "text.box": rect(template["text"]["box"]),
        "subject_box": rect(template["subject_box"]),
    }
    logo = template.get("logo") or {}
    if logo.get("path"):
        boxes["logo"] = (int(logo["x"]), int(logo["y"]), int(logo["w"]), int(logo["w"]))
    for name, box in boxes.items():
        x, y, w, h = box
        if x < 0 or y < 0 or x + w > canvas[2] or y + h > canvas[3]:
            errors.append(f"{name} extends beyond the canvas")
    for name in ("text.box", "logo"):
        if name in boxes and overlaps(boxes[name], zone):
            errors.append(f"{name} overlaps the YouTube timestamp safe zone")
    if int(template["text"]["min_font_size"]) > int(template["text"]["max_font_size"]):
        errors.append("text.min_font_size exceeds text.max_font_size")
    return errors


def load_template(path: Path = TEMPLATE_FILE) -> dict[str, Any]:
    template = load_json(path)
    errors = validate_template(template)
    if errors:
        raise ValueError("Thumbnail template is invalid: " + "; ".join(errors))
    return template


def find_font(template: dict[str, Any]) -> Path | None:
    override = os.environ.get(FONT_ENV, "").strip()
    candidates = ([override] if override else []) + list(template["font_candidates"])
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return path
    return None


def accent_from_palette(accent_text: str, template: dict[str, Any]) -> str:
    """Map a free-text colour description (e.g. 'cold blue') to a template hex."""
    lowered = accent_text.lower()
    hex_match = re.search(r"#([0-9a-f]{6})\b", lowered)
    if hex_match:
        return hex_match.group(1).upper()
    names = template["accent_names"]
    found = [
        (match.start(), name)
        for name in names
        for match in [re.search(rf"\b{re.escape(name)}\b", lowered)]
        if match
    ]
    if found:
        return str(names[min(found)[1]])
    return str(template["default_accent_hex"])


def hex_hue_family(hex_value: str) -> str:
    red, green, blue = (int(hex_value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    hue, saturation, _ = colorsys.rgb_to_hsv(red, green, blue)
    return niche.hue_family(hue * 360.0) if saturation >= 0.2 else "neutral"


# ----------------------------------------------------------------- prepare


CONCEPT_FIELDS = (
    "hero_subject",
    "secondary_element",
    "visual_anomaly",
    "visual_action",
    "emotion",
    "composition",
    "background",
    "subject_separation_method",
    "viewer_visual_question",
    "mobile_legibility_intent",
    "face_present",
)


def pairing_sources() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Current Slice 26 pair validations and Slice 25 concept sets, or nothing yet."""
    import package_pairing

    try:
        validations, _ = package_pairing._collect_current()
        concepts = package_pairing._current_thumbnail_items()
    except (OSError, ValueError, KeyError, TypeError):
        return [], {}
    return validations, concepts


def load_render_units(template: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """One render unit per thumbnail concept with at least one renderable pair."""
    template = template or load_template()
    statuses = set(template["render_validation_statuses"])
    validations, concept_sets = pairing_sources()
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for pair in validations:
        key = (str(pair.get("video_id") or ""), str(pair.get("thumbnail_id") or ""))
        grouped.setdefault(key, []).append(pair)

    units = []
    for (video_id, thumbnail_id), pairs in sorted(grouped.items()):
        titles = sorted(
            (
                {
                    "package_id": pair.get("package_id"),
                    "title_id": pair.get("title_id"),
                    "title_text": pair.get("title_text"),
                    "validation_status": pair.get("validation_status"),
                    "selected_title_direction_match": bool(
                        pair.get("selected_title_direction_match")
                    ),
                }
                for pair in pairs
                if pair.get("validation_status") in statuses
            ),
            key=lambda item: (not item["selected_title_direction_match"], str(item["title_id"])),
        )
        if not titles:
            continue
        concept_set = concept_sets.get(video_id) or {}
        concept = next(
            (
                item
                for item in concept_set.get("thumbnail_concepts", [])
                if isinstance(item, dict) and item.get("thumbnail_id") == thumbnail_id
            ),
            None,
        )
        if concept is None:
            continue
        first = pairs[0]
        unit = {
            "render_id": f"{video_id}--{thumbnail_id}",
            "video_id": video_id,
            "concept_id": first.get("concept_id"),
            "format": first.get("format"),
            "thumbnail_id": thumbnail_id,
            "angle_id": concept.get("angle_id"),
            "text_overlay": str(concept.get("text") or "").strip(),
            **{field: concept.get(field) for field in CONCEPT_FIELDS},
            "titles": titles,
            "title": titles[0]["title_text"],
        }
        unit["source_sha256"] = content_sha256({"concept": concept, "titles": titles})
        units.append(unit)
    return units


def suggested_accent(unit: dict[str, Any], template: dict[str, Any]) -> str:
    text = " ".join(
        str(unit.get(field) or "") for field in ("background", "composition", "emotion")
    )
    return accent_from_palette(text, template)


def blank_subject() -> dict[str, Any]:
    return {
        "path": "",
        "source_tier": "",
        "license": "",
        "source_url": "",
        "attribution": "",
    }


def run_prepare() -> dict[str, Any]:
    template = load_template()
    units = load_render_units(template)
    if not units:
        return {"status": "WAITING_FOR_VALIDATED_PACKAGES", "specs": 0}
    written = []
    for binding in units:
        directory = unit_dir(binding["render_id"])
        directory.mkdir(parents=True, exist_ok=True)
        spec_path = directory / "render_spec.json"
        spec = load_json(spec_path) if spec_path.exists() else {}
        accent = spec.get("accent_hex") or suggested_accent(binding, template)
        spec.update(
            {
                "artifact": "thumbnail_render_spec",
                "unit": binding,
                "accent_hex": accent,
                "subject_image": spec.get("subject_image") or blank_subject(),
                "instructions": [
                    "Fill subject_image with the focal subject image and its provenance.",
                    "subject_image.path is relative to this file or absolute.",
                    "source_tier must be one of: "
                    + ", ".join(template["subject_allowed_source_tiers"]),
                    "accent_hex may be changed; unit fields are bound to the current thumbnail concept and its validated titles and are refreshed on prepare.",
                ],
            }
        )
        atomic_write_json(spec_path, spec)
        written.append(str(spec_path))
    return {"status": "RENDER_SPECS_READY", "specs": len(written), "paths": written}


def validate_subject(
    subject: dict[str, Any], *, spec_dir: Path, template: dict[str, Any]
) -> tuple[Path | None, list[str]]:
    raw_path = str(subject.get("path") or "").strip()
    if not raw_path:
        return None, []
    errors = []
    path = Path(raw_path)
    if not path.is_absolute():
        path = (spec_dir / path).resolve()
    if not path.is_file():
        errors.append(f"subject image not found: {path}")
    tier = str(subject.get("source_tier") or "").strip()
    if tier not in template["subject_allowed_source_tiers"]:
        errors.append(
            f"subject source_tier {tier or '(empty)'} is not permitted for thumbnails"
        )
    if tier != "OWN_LIBRARY" and not str(subject.get("license") or "").strip():
        errors.append("subject licence is required unless source_tier is OWN_LIBRARY")
    if tier in template["subject_source_url_required_tiers"] and not str(
        subject.get("source_url") or ""
    ).strip():
        errors.append(f"subject source_url is required for {tier}")
    return path, errors


# ------------------------------------------------------------------ layout


def run_ffmpeg(args: list[str], *, cwd: Path) -> bytes:
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        timeout=120,
    )
    return result.stdout


def drawtext(textfile: str, *, size: int, x: int, y: int, color: str, extra: str = "") -> str:
    return (
        f"drawtext=fontfile=font.ttf:textfile={textfile}:expansion=none:"
        f"fontsize={size}:fontcolor={color}:x={x}:y={y}{extra}"
    )


def measure_lines(lines: list[str], *, work_dir: Path) -> dict[str, dict[str, int]]:
    """Render each line once at MEASURE_SIZE and read its exact pixel extent."""
    unique = list(dict.fromkeys(lines))
    filters = []
    for index, line in enumerate(unique):
        name = f"measure_{index}.txt"
        (work_dir / name).write_text(line, encoding="utf-8")
        filters.append(
            drawtext(name, size=MEASURE_SIZE, x=10, y=index * MEASURE_ROW + 40, color="white")
        )
    height = MEASURE_ROW * len(unique)
    raw = run_ffmpeg(
        [
            "-f", "lavfi", "-i", f"color=c=black:s={MEASURE_WIDTH}x{height}:d=1",
            "-vf", ",".join(filters), "-frames:v", "1",
            "-f", "rawvideo", "-pix_fmt", "gray", "-",
        ],
        cwd=work_dir,
    )
    extents: dict[str, dict[str, int]] = {}
    for index, line in enumerate(unique):
        min_x, max_x, min_y, max_y = MEASURE_WIDTH, -1, MEASURE_ROW, -1
        for row in range(MEASURE_ROW):
            offset = (index * MEASURE_ROW + row) * MEASURE_WIDTH
            ink = raw[offset : offset + MEASURE_WIDTH].translate(INK)
            first = ink.find(1)
            if first >= 0:
                min_x, max_x = min(min_x, first), max(max_x, ink.rfind(1))
                min_y, max_y = min(min_y, row), max(max_y, row)
        if max_x < 0:
            extents[line] = {"width": 0, "height": 0, "top": 0}
        else:
            extents[line] = {
                "width": max_x - 10 + 1,
                "height": max_y - min_y + 1,
                "top": min_y - 40,
            }
    return extents


def candidate_splits(words: list[str], max_lines: int) -> list[list[str]]:
    splits = []
    for count in range(1, min(max_lines, len(words)) + 1):
        for cuts in itertools.combinations(range(1, len(words)), count - 1):
            bounds = (0, *cuts, len(words))
            splits.append(
                [" ".join(words[bounds[i] : bounds[i + 1]]) for i in range(count)]
            )
    return splits


def layout_text(
    text: str, *, template: dict[str, Any], work_dir: Path
) -> dict[str, Any] | None:
    """Choose the line split that allows the largest font inside the text box."""
    spec = template["text"]
    words = (text.upper() if spec["uppercase"] else text).split()
    if not words:
        return None
    splits = candidate_splits(words, int(spec["max_lines"]))
    extents = measure_lines([line for split in splits for line in split], work_dir=work_dir)
    _, _, box_w, box_h = rect(spec["box"])
    border = int(spec["border_width"])
    bar = template["accent_bar"]
    spacing = float(spec["line_spacing"])

    best: dict[str, Any] | None = None
    for split in splits:
        widest = max(extents[line]["width"] for line in split) or 1
        tallest = max(extents[line]["height"] for line in split) or 1
        by_width = (box_w - 2 * border) * MEASURE_SIZE / widest
        reserved = int(bar["gap"]) + int(bar["height"]) + 2 * border
        by_height = (box_h - reserved) / (
            spacing * (len(split) - 1) + tallest / MEASURE_SIZE
        )
        size = int(min(float(spec["max_font_size"]), by_width, by_height))
        if best is None or size > best["font_size"]:
            best = {"lines": split, "font_size": size}
    if best is None:
        return None
    size = best["font_size"]
    scale = size / MEASURE_SIZE
    lines = best["lines"]
    best.update(
        {
            "fits": size >= int(spec["min_font_size"]),
            "line_widths": [round(extents[line]["width"] * scale) for line in lines],
            "glyph_height": round(max(extents[line]["height"] for line in lines) * scale),
            "top_offset": round(min(extents[line]["top"] for line in lines) * scale),
        }
    )
    return best


# ------------------------------------------------------------------ render


def build_filtergraph(
    *,
    template: dict[str, Any],
    layout: dict[str, Any] | None,
    accent_hex: str,
    has_subject: bool,
    has_logo: bool,
) -> str:
    width, height = int(template["canvas"]["width"]), int(template["canvas"]["height"])
    background = template["background"]
    bx, by, bw, bh = rect(template["subject_box"])
    chains = []
    blurred = has_subject and background["mode"] == "blurred_subject"
    subject_pad = "[0:v]"
    if blurred:
        chains.append("[0:v]split[bgsrc][subjsrc]")
        subject_pad = "[subjsrc]"
        chains.append(
            f"[bgsrc]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur={int(background['blur_radius'])}:2,"
            f"eq=brightness={float(background['brightness'])}:"
            f"saturation={float(background['saturation'])},format=rgb24[bg]"
        )
    else:
        chains.append(
            f"color=c={background['color']}:s={width}x{height}:d=1,format=rgb24[bg]"
        )
    if has_subject:
        chains.append(
            f"{subject_pad}scale=w={bw}:h={bh}:force_original_aspect_ratio=decrease[subj]"
        )
        chains.append(f"[bg][subj]overlay=x={bx}+({bw}-w)/2:y={by}+({bh}-h)/2[s1]")
    else:
        chains.append(
            f"[bg]drawbox=x={bx}:y={by}:w={bw}:h={bh}:color=gray@0.35:t=fill,"
            f"drawbox=x={bx}:y={by}:w={bw}:h={bh}:color=white@0.6:t=6[s1]"
        )
    current = "s1"
    if has_logo:
        logo = template["logo"]
        index = 1 if has_subject else 0
        chains.append(f"[{index}:v]scale={int(logo['w'])}:-1[logo]")
        chains.append(f"[s1][logo]overlay=x={int(logo['x'])}:y={int(logo['y'])}[s2]")
        current = "s2"

    steps = []
    if layout:
        scrim = template.get("text_scrim")
        if scrim:
            sx, sy, sw, sh = rect(scrim)
            steps.append(f"drawbox=x={sx}:y={sy}:w={sw}:h={sh}:color={scrim['color']}:t=fill")
        text = template["text"]
        tx, ty, _, th = rect(text["box"])
        border = int(text["border_width"])
        size = int(layout["font_size"])
        pitch = round(size * float(text["line_spacing"]))
        lines = layout["lines"]
        bar = template["accent_bar"]
        block = pitch * (len(lines) - 1) + int(layout["glyph_height"])
        block_with_bar = block + int(bar["gap"]) + int(bar["height"])
        top = ty + (th - block_with_bar) // 2 - int(layout["top_offset"])
        shadow = int(text["shadow_offset"])
        for index, _line in enumerate(lines):
            is_accent = text["accent_line"] == "last" and index == len(lines) - 1 and len(lines) > 1
            steps.append(
                drawtext(
                    f"line_{index}.txt",
                    size=size,
                    x=tx + border,
                    y=top + index * pitch,
                    color=("0x" + accent_hex) if is_accent else text["color"],
                    extra=(
                        f":borderw={border}:bordercolor={text['border_color']}"
                        f":shadowx={shadow}:shadowy={shadow}:shadowcolor={text['shadow_color']}"
                    ),
                )
            )
        bar_y = top + int(layout["top_offset"]) + block + int(bar["gap"])
        steps.append(
            f"drawbox=x={tx + border}:y={bar_y}:w={max(layout['line_widths'])}:"
            f"h={int(bar['height'])}:color=0x{accent_hex}:t=fill"
        )
    chains.append(f"[{current}]" + (",".join(steps) if steps else "null") + "[out]")
    return ";".join(chains)


def encode_jpeg(work_dir: Path, inputs: list[str], graph: str, target: Path, max_bytes: int) -> int:
    for quality in (2, 3, 4, 6, 8, 10):
        run_ffmpeg(
            [
                *inputs,
                "-filter_complex", graph,
                "-map", "[out]", "-frames:v", "1", "-q:v", str(quality), target.name,
            ],
            cwd=work_dir,
        )
        if (work_dir / target.name).stat().st_size <= max_bytes:
            return quality
    raise ValueError("Thumbnail exceeds the maximum upload size at every quality step")


def niche_context(video_format_value: str | None) -> tuple[str | None, str, dict[str, Any] | None]:
    niche_name = None
    if PACKAGING_CONFIG_FILE.exists():
        niche_name = load_json(PACKAGING_CONFIG_FILE).get("channel_niche")
    video_format = "short" if video_format_value == "short" else "long_form"
    if not niche_name:
        return None, video_format, None
    path = niche.tabulation_path(str(niche_name), video_format)
    return str(niche_name), video_format, (load_json(path) if path.exists() else None)


def zone_luminance(
    pixels: list[tuple[int, int, int]], *, grid_w: int, grid_h: int, template: dict[str, Any]
) -> dict[str, float]:
    """Mean luminance inside the template's subject box versus everywhere else."""
    bx, by, bw, bh = rect(template["subject_box"])
    scale_x = grid_w / int(template["canvas"]["width"])
    scale_y = grid_h / int(template["canvas"]["height"])
    inside: list[float] = []
    outside: list[float] = []
    for index, pixel in enumerate(pixels):
        x, y = (index % grid_w + 0.5) / scale_x, (index // grid_w + 0.5) / scale_y
        zone = inside if bx <= x < bx + bw and by <= y < by + bh else outside
        zone.append(niche.luminance(pixel))
    subject = sum(inside) / len(inside) if inside else 0.0
    background = sum(outside) / len(outside) if outside else 0.0
    return {"subject": round(subject, 3), "background": round(background, 3)}


def render_advisories(
    *,
    layout: dict[str, Any] | None,
    template: dict[str, Any],
    zones: dict[str, float],
    accent_hex: str,
    tabulation: dict[str, Any] | None,
    placeholder: bool,
) -> list[dict[str, Any]]:
    advisories = []

    def add(rule: str, guidance: str, status: str = "HYPOTHESIS") -> None:
        advisories.append({"rule": rule, "guidance": guidance, "evidence_status": status})

    if placeholder:
        add("PLACEHOLDER_SUBJECT", "No subject image yet; this render is a layout preview only.", "FACT")
    smallest = min(preview["width"] for preview in template["phone_previews"])
    if layout:
        phone_px = layout["glyph_height"] * smallest / int(template["canvas"]["width"])
        if phone_px < float(template["min_phone_text_px"]):
            add(
                "PHONE_TEXT_TOO_SMALL",
                f"Text is about {phone_px:.1f}px tall at {smallest}px wide; "
                f"target at least {template['min_phone_text_px']}px. Use fewer words.",
            )
    contrast = template["contrast"]
    if not placeholder:
        if zones["background"] > float(contrast["max_background_luminance"]):
            add(
                "BACKGROUND_NOT_DARK",
                f"Background luminance is {zones['background']:.2f}; target at most "
                f"{contrast['max_background_luminance']} so the subject and text pop.",
            )
        if zones["subject"] - zones["background"] < float(contrast["min_subject_lift"]):
            add(
                "SUBJECT_NOT_BRIGHTER",
                f"Subject zone ({zones['subject']:.2f}) is not clearly brighter than the "
                f"background ({zones['background']:.2f}).",
            )
    if tabulation:
        crowded = tabulation.get("color", {}).get("crowded_hue_families", [])
        accent_family = hex_hue_family(accent_hex)
        if accent_family in crowded:
            add(
                "ACCENT_IN_CROWDED_HUE",
                f"Accent is {accent_family}, one of the niche's most common hue families; "
                "candidates: "
                + ", ".join(tabulation.get("color", {}).get("accent_differentiation_candidates", [])),
            )
    return advisories


def feed_html(
    *,
    unit: dict[str, Any],
    directory: Path,
    niche_name: str | None,
    video_format: str,
    limit: int,
) -> str:
    competitors = []
    if niche_name:
        study_dir = niche.study_dir(niche_name, video_format)
        study_path, acquisition_path = study_dir / "study_set.json", study_dir / "acquisition.json"
        if study_path.exists() and acquisition_path.exists():
            acquired = load_json(acquisition_path).get("items", {})
            for video in load_json(study_path).get("videos", []):
                record = acquired.get(video["video_id"], {})
                if record.get("status") != "ACQUIRED":
                    continue
                image = study_dir / record["path"]
                competitors.append(
                    {
                        "image": os.path.relpath(image, directory).replace(os.sep, "/"),
                        "title": video.get("title", ""),
                        "channel": video.get("channel_title") or "",
                        "views": video.get("views"),
                    }
                )
                if len(competitors) >= limit:
                    break
    ours = {
        "image": "thumbnail.jpg",
        "title": unit["title"],
        "channel": "Your channel",
        "views": None,
        "ours": True,
    }
    items = competitors[:1] + [ours] + competitors[1:]

    def views(value: Any) -> str:
        if not value:
            return "new"
        value = int(value)
        for unit, size in (("B", 10**9), ("M", 10**6), ("K", 10**3)):
            if value >= size:
                return f"{value / size:.1f}".rstrip("0").rstrip(".") + unit + " views"
        return f"{value} views"

    def card(item: dict[str, Any], small: bool) -> str:
        cls = "row" if small else "card"
        mark = " ours" if item.get("ours") else ""
        return (
            f'<div class="{cls}{mark}"><div class="thumb"><img src="{html.escape(item["image"])}" alt="">'
            f'<span class="dur">12:34</span></div><div class="meta">'
            f'<div class="title">{html.escape(item["title"])}</div>'
            f'<div class="sub">{html.escape(item["channel"])} · {views(item["views"])}</div></div></div>'
        )

    def phone(theme: str) -> str:
        return (
            f'<section class="phone {theme}"><h2>{theme.title()} · home feed (360px)</h2>'
            + "".join(card(item, False) for item in items[:4])
            + "<h2>Suggested (168px)</h2>"
            + "".join(card(item, True) for item in items[:6])
            + "</section>"
        )

    note = (
        f"Compared with {len(competitors)} breakout thumbnails from the {html.escape(niche_name or '')} "
        f"{video_format} study."
        if competitors
        else "No niche thumbnail study found: set channel_niche and run niche_thumbnail_study.py "
        "to compare against real niche thumbnails."
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mock feed — {html.escape(unit["render_id"])}</title>
<style>
body{{margin:0;padding:16px;font-family:Roboto,Arial,sans-serif;background:#888}}
p.note{{color:#fff;max-width:760px}}
.wrap{{display:flex;flex-wrap:wrap;gap:24px}}
.phone{{width:360px;border-radius:18px;overflow:hidden;padding-bottom:12px}}
.phone h2{{font-size:13px;font-weight:500;margin:12px;opacity:.7}}
.dark{{background:#0f0f0f;color:#f1f1f1}} .light{{background:#fff;color:#0f0f0f}}
.thumb{{position:relative;line-height:0}}
.card .thumb img{{width:360px;height:202px;object-fit:cover}}
.row{{display:flex;gap:8px;margin:0 12px 10px}}
.row .thumb img{{width:168px;height:94px;object-fit:cover;border-radius:8px}}
.dur{{position:absolute;right:6px;bottom:6px;background:rgba(0,0,0,.8);color:#fff;font-size:11px;line-height:1;padding:3px 4px;border-radius:4px}}
.card .meta{{padding:10px 12px 18px}}
.title{{font-size:14px;line-height:20px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.row .title{{font-size:13px;line-height:18px}}
.sub{{font-size:12px;opacity:.65;margin-top:4px}}
.ours .thumb{{outline:3px solid #ff0}}
</style></head><body>
<p class="note">{note} Your thumbnail is outlined in yellow. The 12:34 badge marks the timestamp area.</p>
<div class="wrap">{phone("dark")}{phone("light")}</div>
</body></html>
"""


def render_unit(
    spec_path: Path, *, template: dict[str, Any], placeholder: bool = False
) -> dict[str, Any]:
    directory = spec_path.parent
    spec = load_json(spec_path)
    unit = spec["unit"]
    report_path = directory / "render_report.json"

    def blocked(status: str, errors: list[str]) -> dict[str, Any]:
        report = {
            "artifact": "thumbnail_render_report",
            "render_id": unit["render_id"],
            "status": status,
            "errors": errors,
            "rendered_at": utc_now(),
        }
        atomic_write_json(report_path, report)
        return report

    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        return blocked("BLOCKED", ["ffmpeg and ffprobe are required"])
    font = find_font(template)
    if font is None:
        return blocked("BLOCKED", [f"No bold font found; set {FONT_ENV} or edit font_candidates"])
    accent_hex = str(spec.get("accent_hex") or "").upper().lstrip("#")
    if not re.fullmatch(r"[0-9A-F]{6}", accent_hex):
        return blocked("BLOCKED", ["accent_hex must be a 6-digit hex colour"])
    subject_path, subject_errors = validate_subject(
        spec.get("subject_image") or {}, spec_dir=directory, template=template
    )
    if subject_errors:
        return blocked("BLOCKED", subject_errors)
    if subject_path is None and not placeholder:
        return blocked("WAITING_FOR_SUBJECT_IMAGE", [])
    logo_path = template.get("logo", {}).get("path")
    if logo_path and not Path(logo_path).is_file():
        return blocked("BLOCKED", [f"template logo not found: {logo_path}"])

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        shutil.copyfile(font, work / "font.ttf")
        layout = layout_text(unit["text_overlay"], template=template, work_dir=work)
        if layout and not layout["fits"]:
            return blocked(
                "BLOCKED",
                [
                    f"Text overlay needs font size {layout['font_size']} to fit; template minimum "
                    f"is {template['text']['min_font_size']}. Rework the thumbnail concept text."
                ],
            )
        if layout:
            for index, line in enumerate(layout["lines"]):
                (work / f"line_{index}.txt").write_text(line, encoding="utf-8")
        inputs: list[str] = []
        if subject_path:
            inputs += ["-i", str(subject_path)]
        if logo_path:
            inputs += ["-i", str(Path(logo_path).resolve())]
        graph = build_filtergraph(
            template=template,
            layout=layout,
            accent_hex=accent_hex,
            has_subject=subject_path is not None,
            has_logo=bool(logo_path),
        )
        target = directory / "thumbnail.jpg"
        quality = encode_jpeg(work, inputs, graph, target, int(template["max_jpeg_bytes"]))
        shutil.move(str(work / target.name), target)

    previews = {}
    for preview in template["phone_previews"]:
        name = f"{preview['name']}.png"
        run_ffmpeg(
            [
                "-i", "thumbnail.jpg",
                "-vf", f"scale={int(preview['width'])}:{int(preview['height'])}:flags=lanczos",
                "-frames:v", "1", name,
            ],
            cwd=directory,
        )
        previews[preview["name"]] = name

    width, height = niche.ffprobe_size(target)
    niche_config = niche.load_config()
    grid_w, grid_h = (int(niche_config["measure_grid"][key]) for key in ("width", "height"))
    pixels = niche.ffmpeg_pixels(target, grid_w, grid_h)
    metrics = niche.measure_pixels(pixels, width=grid_w, height=grid_h, config=niche_config)
    zones = zone_luminance(pixels, grid_w=grid_w, grid_h=grid_h, template=template)
    niche_name, video_format, tabulation = niche_context(unit.get("format"))
    (directory / "feed.html").write_text(
        feed_html(
            unit=unit,
            directory=directory,
            niche_name=niche_name,
            video_format=video_format,
            limit=int(template["feed_competitor_limit"]),
        ),
        encoding="utf-8",
    )
    report = {
        "artifact": "thumbnail_render_report",
        "render_id": unit["render_id"],
        "status": "PREVIEW_ONLY" if subject_path is None else "RENDERED",
        "errors": [],
        "rendered_at": utc_now(),
        "template_id": template["template_id"],
        "template_sha256": content_sha256(template),
        "source_sha256": unit["source_sha256"],
        "titles": unit["titles"],
        "spec_sha256": sha256_file(spec_path),
        "image": "thumbnail.jpg",
        "image_sha256": sha256_file(target),
        "image_bytes": target.stat().st_size,
        "jpeg_quality": quality,
        "width": width,
        "height": height,
        "accent_hex": accent_hex,
        "accent_hue_family": hex_hue_family(accent_hex),
        "subject_image": (
            {**spec["subject_image"], "sha256": sha256_file(subject_path)}
            if subject_path
            else None
        ),
        "text_layout": layout,
        "measurements": metrics,
        "zone_luminance": zones,
        "previews": previews,
        "feed": "feed.html",
        "niche_study": {"niche": niche_name, "format": video_format, "found": tabulation is not None},
        "render_advisories": render_advisories(
            layout=layout,
            template=template,
            zones=zones,
            accent_hex=accent_hex,
            tabulation=tabulation,
            placeholder=subject_path is None,
        ),
    }
    atomic_write_json(report_path, report)
    approved_path = APPROVED_THUMBNAILS_DIR / f"{safe_slug(unit['render_id'])}.json"
    if approved_path.exists() and (
        load_json(approved_path).get("image_sha256") != report["image_sha256"]
    ):
        approved_path.unlink()
    return report


def run_render(render_id: str | None = None, *, placeholder: bool = False) -> dict[str, Any]:
    template = load_template()
    specs = sorted(THUMBNAILS_DIR.glob("*/render_spec.json")) if THUMBNAILS_DIR.exists() else []
    current = {safe_slug(unit["render_id"]) for unit in load_render_units(template)}
    specs = [path for path in specs if path.parent.name in current]
    if render_id:
        specs = [path for path in specs if path.parent.name == safe_slug(render_id)]
    if not specs:
        return {"status": "NO_RENDER_SPECS", "rendered": 0}
    results = {}
    for spec_path in specs:
        report = render_unit(spec_path, template=template, placeholder=placeholder)
        results[report["render_id"]] = report["status"]
    return {"status": "RENDER_COMPLETE", "results": results}


# ------------------------------------------------------------------ review


def current_render(render_id: str, template: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    directory = unit_dir(render_id)
    report_path = directory / "render_report.json"
    if not report_path.exists():
        return {}, ["no render report"]
    report = load_json(report_path)
    problems = []
    units = {unit["render_id"]: unit for unit in load_render_units(template)}
    if render_id not in units:
        problems.append("thumbnail concept no longer has a validated title pair")
    elif units[render_id]["source_sha256"] != report.get("source_sha256"):
        problems.append("thumbnail concept or its validated titles changed after rendering")
    if report.get("template_sha256") != content_sha256(template):
        problems.append("thumbnail template changed after rendering")
    image = directory / str(report.get("image", ""))
    if not image.is_file() or sha256_file(image) != report.get("image_sha256"):
        problems.append("rendered image changed after rendering")
    if sha256_file(directory / "render_spec.json") != report.get("spec_sha256"):
        problems.append("render spec changed after rendering")
    return report, problems


def apply_review(response: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    reviewer = str(response.get("reviewer", "")).strip()
    if not reviewer:
        raise ValueError("Thumbnail review requires reviewer")
    decisions = response.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        raise ValueError("Thumbnail review decisions must be a non-empty list")
    required = list(template["review_criteria"])
    outcomes = {}
    for decision in decisions:
        render_id = str(decision.get("render_id", "")).strip()
        value = str(decision.get("decision", "")).strip().upper()
        if value not in DECISIONS:
            raise ValueError(f"Invalid decision for {render_id}: {value!r}")
        criteria = decision.get("criteria") or {}
        normalized = {name: criteria.get(name) is True for name in required}
        note = str(decision.get("note", "") or "").strip()
        report, problems = current_render(render_id, template)
        if value == "ACCEPT":
            if problems:
                raise ValueError(f"{render_id}: render is stale or missing: " + "; ".join(problems))
            if report.get("status") != "RENDERED":
                raise ValueError(f"{render_id}: only a RENDERED thumbnail can be accepted")
            missing = [name for name, passed in normalized.items() if not passed]
            if missing:
                raise ValueError(f"{render_id}: ACCEPT requires " + ", ".join(missing))
        if value == "REWORK" and not note:
            raise ValueError(f"{render_id}: REWORK requires a note")
        record = {
            "render_id": render_id,
            "decision": value,
            "criteria": normalized,
            "note": note,
            "reviewer": reviewer,
            "reviewed_at": utc_now(),
            "image_sha256": report.get("image_sha256"),
        }
        atomic_write_json(unit_dir(render_id) / "review.json", record)
        approved_path = APPROVED_THUMBNAILS_DIR / f"{safe_slug(render_id)}.json"
        if value == "ACCEPT":
            atomic_write_json(
                approved_path,
                {
                    "artifact": "approved_thumbnail",
                    "render_id": render_id,
                    "image": str(unit_dir(render_id) / report["image"]),
                    "image_sha256": report["image_sha256"],
                    "width": report["width"],
                    "height": report["height"],
                    "template_id": report["template_id"],
                    "template_sha256": report["template_sha256"],
                    "subject_image": report["subject_image"],
                    "thumbnail_gate": record,
                },
            )
        elif approved_path.exists():
            approved_path.unlink()
        outcomes[render_id] = value
    return {"status": "THUMBNAIL_REVIEW_APPLIED", "decisions": outcomes}


def main() -> None:
    parser = argparse.ArgumentParser(description="Thumbnail rendering")
    parser.add_argument("--mode", choices=("prepare", "render", "review"), required=True)
    parser.add_argument("--render-id", default=None)
    parser.add_argument(
        "--placeholder",
        action="store_true",
        help="render a layout preview without a subject image (cannot be accepted)",
    )
    parser.add_argument("--response", type=Path, default=None)
    args = parser.parse_args()
    if args.mode == "prepare":
        result = run_prepare()
    elif args.mode == "render":
        result = run_render(args.render_id, placeholder=args.placeholder)
    else:
        if args.response is None:
            raise SystemExit("--response is required for review")
        result = apply_review(load_json(args.response), load_template())
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
