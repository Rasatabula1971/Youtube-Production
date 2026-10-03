"""Experiment UI controller for thumbnail rendering and the Human Thumbnail Gate.

Read side: one item per approved package with its render spec, latest render
report, previews, mock-feed competitors and current decision.

Write side: save the subject image / accent for a package, and record
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


def file_url(package_id: str, name: str, version: str | None) -> str:
    query = {"package_id": package_id, "name": name}
    if version:
        query["v"] = version[:12]
    return "/api/thumbnail-file?" + urlencode(query)


def competitors(package: dict[str, Any], template: dict[str, Any]) -> list[dict[str, Any]]:
    niche_name, video_format, _ = render.niche_context(package.get("format_intent"))
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
                + urlencode({"package_id": package["package_id"], "video_id": video["video_id"]}),
            }
        )
        if len(items) >= int(template["feed_competitor_limit"]):
            break
    return items


def snapshot() -> dict[str, Any]:
    template = render.load_template()
    packages = render.load_approved_packages()
    if not packages:
        return {"status": "WAITING_FOR_APPROVED_PACKAGES", "items": [], "complete": False}

    criteria = template["review_criteria"]
    items = []
    for package in packages:
        package_id = str(package["package_id"])
        directory = render.package_dir(package_id)
        spec_path = directory / "render_spec.json"
        spec = render.load_json(spec_path) if spec_path.exists() else {}
        binding = render.package_binding(package)
        report_path = directory / "render_report.json"
        report = render.load_json(report_path) if report_path.exists() else {}
        problems: list[str] = []
        if report.get("image_sha256"):
            _, problems = render.current_render(package_id, template)
        review_path = directory / "review.json"
        review = render.load_json(review_path) if review_path.exists() else {}
        current_review = bool(review) and review.get("image_sha256") == report.get(
            "image_sha256"
        ) and not problems
        version = report.get("image_sha256")
        previews = {
            name: file_url(package_id, file_name, version)
            for name, file_name in (report.get("previews") or {}).items()
        }
        items.append(
            {
                "package_id": package_id,
                "concept_id": package.get("concept_id"),
                "title": binding["title"],
                "text_overlay": binding["text_overlay"],
                "thumbnail_message": binding["thumbnail_message"],
                "focal_subject": binding["focal_subject"],
                "palette": binding["palette"],
                "spec_ready": bool(spec),
                "spec_current": spec.get("package", {}).get("package_sha256")
                == binding["package_sha256"],
                "accent_hex": spec.get("accent_hex")
                or render.accent_from_palette(str(binding["palette"].get("accent", "")), template),
                "subject_image": spec.get("subject_image") or render.blank_subject(),
                "render_status": report.get("status", "NOT_RENDERED"),
                "render_errors": report.get("errors", []),
                "stale_reasons": problems,
                "image_url": file_url(package_id, "thumbnail.jpg", version) if version else None,
                "previews": previews,
                "text_layout": report.get("text_layout"),
                "zone_luminance": report.get("zone_luminance"),
                "render_advisories": report.get("render_advisories", []),
                "packaging_advisories": package.get("packaging_advisories", []),
                "competitors": competitors(package, template) if version else [],
                "decision": review.get("decision", "PENDING") if current_review else "PENDING",
                "criteria_decisions": review.get("criteria", {}) if current_review else {},
                "note": review.get("note", "") if current_review else "",
                "required_accept_criteria": list(criteria),
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
        "package_count": len(items),
        "rendered": sum(item["render_status"] == "RENDERED" for item in items),
        "pending": len(items) - len(decided),
        "accepted": sum(item["decision"] == "ACCEPT" for item in items),
        "items": items,
    }


def update_spec(*, package_id: str, accent_hex: Any, subject_image: Any) -> dict[str, Any]:
    template = render.load_template()
    render.run_prepare()
    spec_path = render.package_dir(package_id) / "render_spec.json"
    approved = {str(package["package_id"]) for package in render.load_approved_packages()}
    if package_id not in approved or not spec_path.exists():
        raise ValueError("Unknown or unapproved package_id")

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
    *, package_id: str, decision: str, criteria: Any, note: str | None
) -> dict[str, Any]:
    template = render.load_template()
    render.apply_review(
        {
            "reviewer": reviewer(),
            "decisions": [
                {
                    "package_id": package_id,
                    "decision": decision,
                    "criteria": criteria if isinstance(criteria, dict) else {},
                    "note": note or "",
                }
            ],
        },
        template,
    )
    return snapshot()


def thumbnail_file_path(package_id: str, name: str) -> Path:
    template = render.load_template()
    allowed = {"thumbnail.jpg"} | {
        f"{preview['name']}.png" for preview in template["phone_previews"]
    }
    if name not in allowed:
        raise ValueError("Unknown thumbnail file")
    approved = {str(package["package_id"]) for package in render.load_approved_packages()}
    if package_id not in approved:
        raise ValueError("Unknown package_id")
    path = render.package_dir(package_id) / name
    if not path.is_file():
        raise ValueError("Thumbnail file not rendered yet")
    return path


def competitor_file_path(package_id: str, video_id: str) -> Path:
    if not VIDEO_ID_PATTERN.match(video_id):
        raise ValueError("Invalid video_id")
    package = next(
        (p for p in render.load_approved_packages() if str(p["package_id"]) == package_id),
        None,
    )
    if package is None:
        raise ValueError("Unknown package_id")
    niche_name, video_format, _ = render.niche_context(package.get("format_intent"))
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
