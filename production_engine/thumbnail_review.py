"""Experiment UI controller for thumbnail rendering and the Human Thumbnail Gate.

Read side: one item per renderable thumbnail concept (a Slice 25 concept with
at least one title pair passing Slice 26 validation), with its render spec,
latest render report, previews, mock-feed competitors and current decision.

Write side: save the subject image / accent for a concept, and record
ACCEPT / REWORK / REJECT through ``thumbnail_render.apply_review``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlencode
from typing import Any

try:
    from production_engine import thumbnail_render as render
except ImportError:  # executed as a script from production_engine/
    import thumbnail_render as render  # type: ignore[no-redef]

from pipeline_integrity import atomic_write_json

REVIEWER_ENV = "YOUTUBE_REVIEWER_ID"
DEFAULT_REVIEWER = "local-operator"
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
SUBJECT_FIELDS = ("path", "source_tier", "license", "source_url", "attribution")


def reviewer() -> str:
    return os.getenv(REVIEWER_ENV, DEFAULT_REVIEWER)


def file_url(render_id: str, name: str, version: str | None) -> str:
    query = {"render_id": render_id, "name": name}
    if version:
        query["v"] = version[:12]
    return "/api/thumbnail-file?" + urlencode(query)


def competitors(unit: dict[str, Any], template: dict[str, Any]) -> list[dict[str, Any]]:
    niche_name, video_format, _ = render.niche_context(unit.get("format"))
    if not niche_name:
        return []
    study_dir = render.niche.study_dir(niche_name, video_format)
    study_path, acquisition_path = study_dir / "study_set.json", study_dir / "acquisition.json"
    if not (study_path.exists() and acquisition_path.exists()):
        return []
    acquired = render.load_json(acquisition_path).get("items", {})
    items = []
    for video in render.load_json(study_path).get("videos", []):
        if acquired.get(video.get("video_id"), {}).get("status") != "ACQUIRED":
            continue
        items.append(
            {
                "video_id": video["video_id"],
                "title": video.get("title", ""),
                "channel": video.get("channel_title") or "",
                "views": video.get("views"),
                "image_url": "/api/thumbnail-competitor?"
                + urlencode({"render_id": unit["render_id"], "video_id": video["video_id"]}),
            }
        )
        if len(items) >= int(template["feed_competitor_limit"]):
            break
    return items


def _image_candidates(render_id: str) -> dict[str, Any]:
    """Candidate subject images (D-135) with file URLs for the UI."""
    try:
        from production_engine import thumbnail_image_provider as images
    except ImportError:  # executed as a script from production_engine/
        import thumbnail_image_provider as images  # type: ignore[no-redef]

    view = images.candidates_view(render_id)
    for row in view["candidates"]:
        row["image_url"] = file_url(render_id, str(row["file"]), str(row["candidate_id"]))
    return view


def image_provider_status() -> dict[str, Any]:
    try:
        from production_engine import thumbnail_image_provider as images
    except ImportError:  # executed as a script from production_engine/
        import thumbnail_image_provider as images  # type: ignore[no-redef]

    return images.provider_status()


def snapshot() -> dict[str, Any]:
    template = render.load_template()
    units = render.load_render_units(template)
    if not units:
        return {"status": "WAITING_FOR_VALIDATED_PACKAGES", "items": [], "complete": False}

    criteria = template["review_criteria"]
    items = []
    for unit in units:
        render_id = unit["render_id"]
        directory = render.unit_dir(render_id)
        spec_path = directory / "render_spec.json"
        spec = render.load_json(spec_path) if spec_path.exists() else {}
        report_path = directory / "render_report.json"
        report = render.load_json(report_path) if report_path.exists() else {}
        problems: list[str] = []
        if report.get("image_sha256"):
            _, problems = render.current_render(render_id, template)
        review_path = directory / "review.json"
        review = render.load_json(review_path) if review_path.exists() else {}
        current_review = (
            bool(review)
            and review.get("image_sha256") == report.get("image_sha256")
            and not problems
        )
        version = report.get("image_sha256")
        previews = {
            name: file_url(render_id, file_name, version)
            for name, file_name in (report.get("previews") or {}).items()
        }
        items.append(
            {
                **{key: unit.get(key) for key in (
                    "render_id",
                    "video_id",
                    "concept_id",
                    "format",
                    "thumbnail_id",
                    "angle_id",
                    "text_overlay",
                    "title",
                    "titles",
                    *render.CONCEPT_FIELDS,
                )},
                "spec_ready": bool(spec),
                "spec_current": spec.get("unit", {}).get("source_sha256")
                == unit["source_sha256"],
                "accent_hex": spec.get("accent_hex")
                or render.suggested_accent(unit, template),
                "subject_image": spec.get("subject_image") or render.blank_subject(),
                "render_status": report.get("status", "NOT_RENDERED"),
                "render_errors": report.get("errors", []),
                "stale_reasons": problems,
                "image_url": file_url(render_id, "thumbnail.jpg", version) if version else None,
                "previews": previews,
                "text_layout": report.get("text_layout"),
                "zone_luminance": report.get("zone_luminance"),
                "render_advisories": report.get("render_advisories", []),
                "competitors": competitors(unit, template) if version else [],
                "decision": review.get("decision", "PENDING") if current_review else "PENDING",
                "criteria_decisions": review.get("criteria", {}) if current_review else {},
                "note": review.get("note", "") if current_review else "",
                "required_accept_criteria": list(criteria),
                "image_candidates": _image_candidates(render_id),
            }
        )

    decided = [item for item in items if item["decision"] != "PENDING"]
    return {
        "status": (
            "COMPLETE" if len(decided) == len(items) else "AWAITING_HUMAN_DECISION"
        ),
        "complete": len(decided) == len(items),
        "reviewer": reviewer(),
        "criteria": criteria,
        "allowed_source_tiers": list(template["subject_allowed_source_tiers"]),
        "image_provider": image_provider_status(),
        "unit_count": len(items),
        "rendered": sum(item["render_status"] == "RENDERED" for item in items),
        "pending": len(items) - len(decided),
        "accepted": sum(item["decision"] == "ACCEPT" for item in items),
        "items": items,
    }


def current_unit(render_id: str) -> dict[str, Any]:
    unit = next(
        (u for u in render.load_render_units() if u["render_id"] == render_id), None
    )
    if unit is None:
        raise ValueError("Unknown or no longer validated render_id")
    return unit


def update_spec(*, render_id: str, accent_hex: Any, subject_image: Any) -> dict[str, Any]:
    template = render.load_template()
    current_unit(render_id)
    render.run_prepare()
    spec_path = render.unit_dir(render_id) / "render_spec.json"
    if not spec_path.exists():
        raise ValueError("Unknown or no longer validated render_id")

    accent = str(accent_hex or "").strip().upper().lstrip("#")
    if not re.fullmatch(r"[0-9A-F]{6}", accent):
        raise ValueError("Accent must be a 6-digit hex colour such as FFD400")
    if not isinstance(subject_image, dict):
        raise ValueError("subject_image must be an object")
    subject = {field: str(subject_image.get(field) or "").strip() for field in SUBJECT_FIELDS}
    _, errors = render.validate_subject(subject, spec_dir=spec_path.parent, template=template)
    if errors:
        raise ValueError("; ".join(errors))

    spec = render.load_json(spec_path)
    spec["accent_hex"] = accent
    spec["subject_image"] = subject
    atomic_write_json(spec_path, spec)
    return snapshot()


def apply_action(
    *, render_id: str, decision: str, criteria: Any, note: str | None
) -> dict[str, Any]:
    template = render.load_template()
    render.apply_review(
        {
            "reviewer": reviewer(),
            "decisions": [
                {
                    "render_id": render_id,
                    "decision": decision,
                    "criteria": criteria if isinstance(criteria, dict) else {},
                    "note": note or "",
                }
            ],
        },
        template,
    )
    return snapshot()


def thumbnail_file_path(render_id: str, name: str) -> Path:
    template = render.load_template()
    allowed = {"thumbnail.jpg"} | {
        f"{preview['name']}.png" for preview in template["phone_previews"]
    }
    if name.startswith("candidates/"):
        current_unit(render_id)
        try:
            from production_engine import thumbnail_image_provider as images
        except ImportError:  # executed as a script from production_engine/
            import thumbnail_image_provider as images  # type: ignore[no-redef]
        return images.candidate_file_path(render_id, name)
    if name not in allowed:
        raise ValueError("Unknown thumbnail file")
    current_unit(render_id)
    path = render.unit_dir(render_id) / name
    if not path.is_file():
        raise ValueError("Thumbnail file not rendered yet")
    return path


def competitor_file_path(render_id: str, video_id: str) -> Path:
    if not VIDEO_ID_PATTERN.match(video_id):
        raise ValueError("Invalid video_id")
    unit = current_unit(render_id)
    niche_name, video_format, _ = render.niche_context(unit.get("format"))
    if not niche_name:
        raise ValueError("No channel niche configured")
    study_dir = render.niche.study_dir(niche_name, video_format)
    record = (
        render.load_json(study_dir / "acquisition.json").get("items", {}).get(video_id, {})
    )
    if record.get("status") != "ACQUIRED":
        raise ValueError("Competitor thumbnail not acquired")
    path = (study_dir / record["path"]).resolve()
    if study_dir.resolve() not in path.parents or not path.is_file():
        raise ValueError("Competitor thumbnail not found")
    return path
