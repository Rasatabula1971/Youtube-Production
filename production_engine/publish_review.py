"""Publish package and Human Publish Gate (D-142).

The Final Export Gate approves the exact rendered bytes and records that
upload and publishing are not authorized. This module assembles everything
YouTube needs for one approved video and holds it for a human decision:

  * the approved final render (file and hash);
  * the exact title, approved thumbnail image and viewer promise from the
    final package bundle (D-099);
  * a description: the viewer promise, the verified research sources the
    script relied on, and a disclosure line;
  * category, language, made-for-kids, privacy, an optional schedule, tags,
    and the altered/synthetic content flag (on by default: the narration is
    an AI voice).

The human may edit the description, tags, privacy, schedule and the
synthetic-content flag; the title stays the one approved at the Final
Packaging Gate. APPROVE_PUBLISH binds the approval to the render, bundle and
research hashes and to the exact metadata. HOLD records a note and keeps the
video unpublished. After an upload the YouTube video id is recorded, either by
the uploader (D-143) or by hand after a manual upload.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import append_jsonl, atomic_write_json, read_jsonl
from final_export_review import APPROVED_DIR as APPROVED_EXPORT_DIR
from final_export_review import approval_is_current
from visual_acquisition import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
CONFIG_FILE = HERE / "publish_config.json"
FINAL_PACKAGES_DIR = _ROOT / "packaging_engine" / "output" / "mature_packaging" / "final_packages"
VERIFIED_DIR = _ROOT / "research_engine" / "output" / "verified_packages"
APPROVED_DIR = OUTPUT / "approved_publish"
PUBLISHED_DIR = OUTPUT / "published_videos"
PENDING_UPLOADS_DIR = OUTPUT / "pending_uploads"
HISTORY_FILE = OUTPUT / "publish_history.jsonl"
DECISIONS = {"APPROVE_PUBLISH", "HOLD"}
PRIVACY = {"private", "unlisted", "public"}
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
REVIEWER_ENV = "YOUTUBE_REVIEWER_ID"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def reviewer() -> str:
    return os.getenv(REVIEWER_ENV, "local-operator").strip() or "local-operator"


def load_config() -> dict[str, Any]:
    return load_json(CONFIG_FILE)


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _clean(text: Any) -> str:
    # YouTube rejects angle brackets in titles and descriptions.
    return str(text or "").replace("<", "").replace(">", "").strip()


def _sources(concept_id: str, limit: int) -> tuple[list[dict[str, str]], str | None]:
    path = VERIFIED_DIR / f"{safe_slug(concept_id)}.verified_research_package.json"
    if not path.exists():
        return [], None
    package = load_json(path)
    seen, rows = set(), []
    for source in package.get("sources", []) or []:
        url = str((source or {}).get("url") or "").strip()
        if not url.startswith(("https://", "http://")) or url in seen:
            continue
        seen.add(url)
        rows.append({"title": _clean(source.get("title") or source.get("publisher") or url), "url": url})
    return rows[:limit], sha256_file(path)


def default_description(promise: str, sources: list[dict[str, str]], synthetic: bool) -> str:
    parts = [_clean(promise)]
    if sources:
        parts.append("Sources:\n" + "\n".join(f"- {s['title']}: {s['url']}" for s in sources))
    if synthetic:
        parts.append("Narration uses an AI-generated voice; some visuals may be AI-generated.")
    return "\n\n".join(p for p in parts if p)


def build_drafts() -> list[dict[str, Any]]:
    """One publish draft per currently approved final export."""
    config = load_config()
    drafts = []
    paths = sorted(APPROVED_EXPORT_DIR.glob("*.approved_final_export.json")) if APPROVED_EXPORT_DIR.exists() else []
    for path in paths:
        approval = approval_is_current(path)
        if approval is None:
            continue
        concept_id, fmt = str(approval.get("concept_id") or ""), str(approval.get("format") or "")
        bundle_path = FINAL_PACKAGES_DIR / f"{safe_slug(concept_id)}.final_package.json"
        problems = []
        package: dict[str, Any] = {}
        if not bundle_path.exists():
            problems.append("No approved final package bundle for this concept.")
        else:
            package = (load_json(bundle_path).get("packages") or {}).get(fmt) or {}
            if not package:
                problems.append(f"The final package bundle has no {fmt} package.")
        image = package.get("thumbnail_image") or {}
        thumbnail = str(image.get("image") or "")
        if package and not (thumbnail and Path(thumbnail).is_file()):
            problems.append("The approved thumbnail image file is missing.")
        sources, research_sha = _sources(concept_id, int(config.get("max_description_sources") or 12))
        synthetic = bool(config.get("contains_synthetic_media_default", True))
        metadata = {
            "title": _clean(package.get("title_text")),
            "description": default_description(str(package.get("viewer_promise") or ""), sources, synthetic),
            "tags": [],
            "category_id": str(config.get("category_id") or "28"),
            "default_language": str(config.get("default_language") or "en"),
            "made_for_kids": bool(config.get("made_for_kids", False)),
            "privacy_status": str(config.get("default_privacy") or "private"),
            "publish_at": None,
            "contains_synthetic_media": synthetic,
        }
        base = {
            "concept_id": concept_id,
            "format": fmt,
            "key": _key(concept_id, fmt),
            "video_file": approval.get("render_file"),
            "video_sha256": approval.get("render_sha256"),
            "thumbnail_file": thumbnail or None,
            "thumbnail_sha256": image.get("image_sha256"),
            "sources": sources,
            "problems": problems,
            "provenance": {
                "approved_final_export": str(path),
                "approved_final_export_sha256": sha256_file(path),
                "final_package_bundle_sha256": sha256_file(bundle_path) if bundle_path.exists() else None,
                "verified_research_sha256": research_sha,
            },
        }
        drafts.append({**base, "draft_metadata": metadata, "base_sha256": _hash(base)})
    return drafts


def validate_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """YouTube's limits and this project's rules, applied before approval."""
    title = _clean(metadata.get("title"))
    if not title or len(title) > 100:
        raise ValueError("The title must be 1 to 100 characters")
    description = _clean(metadata.get("description"))
    if len(description.encode("utf-8")) > 5000:
        raise ValueError("The description must be at most 5,000 bytes")
    tags = metadata.get("tags") or []
    if isinstance(tags, str):
        tags = [t for t in (part.strip() for part in tags.split(",")) if t]
    if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
        raise ValueError("Tags must be a list of words or phrases")
    tags = [_clean(t) for t in tags if _clean(t)]
    if sum(len(t) + 1 for t in tags) > 500:
        raise ValueError("Tags must total at most 500 characters")
    privacy = str(metadata.get("privacy_status") or "").strip().lower()
    if privacy not in PRIVACY:
        raise ValueError("Privacy must be private, unlisted or public")
    publish_at = metadata.get("publish_at") or None
    if publish_at:
        try:
            when = datetime.fromisoformat(str(publish_at).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("The schedule must be an ISO date and time") from exc
        if when.tzinfo is None:
            raise ValueError("The schedule needs a time zone, e.g. 2026-10-20T15:00:00Z")
        if when <= datetime.now(timezone.utc):
            raise ValueError("The schedule must be in the future")
        if privacy != "private":
            raise ValueError("A scheduled video must be uploaded as private until it publishes")
        publish_at = when.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    synthetic = metadata.get("contains_synthetic_media")
    if not isinstance(synthetic, bool):
        raise ValueError("Say whether the video contains realistic altered or synthetic content")
    return {
        "title": title,
        "description": description,
        "tags": tags,
        "category_id": str(metadata.get("category_id") or "28"),
        "default_language": str(metadata.get("default_language") or "en"),
        "made_for_kids": bool(metadata.get("made_for_kids", False)),
        "privacy_status": privacy,
        "publish_at": publish_at,
        "contains_synthetic_media": synthetic,
    }


def _approved_path(key: str) -> Path:
    return APPROVED_DIR / f"{key}.approved_publish.json"


def _published_path(key: str) -> Path:
    return PUBLISHED_DIR / f"{key}.publish_record.json"


def _pending_path(key: str) -> Path:
    return PENDING_UPLOADS_DIR / f"{key}.pending_upload.json"


def pending_upload(concept_id: str, fmt: str) -> dict[str, Any] | None:
    """A resumable upload session that was started and not finished (D-167)."""
    path = _pending_path(_key(concept_id, fmt))
    if not path.exists():
        return None
    record = load_json(path)
    return record if isinstance(record, dict) else None


def save_pending_upload(record: dict[str, Any]) -> None:
    atomic_write_json(_pending_path(_key(str(record["concept_id"]), str(record["format"]))), record)


def clear_pending_upload(concept_id: str, fmt: str) -> None:
    path = _pending_path(_key(concept_id, fmt))
    if path.exists():
        path.unlink()


def discard_pending_upload(concept_id: str, fmt: str) -> dict[str, Any]:
    """The operator gives up an interrupted upload after checking YouTube Studio (audit 2).

    Refused when the video id is already known: that video is on YouTube and
    must be recorded, not forgotten.
    """
    pending = pending_upload(concept_id, fmt)
    if pending is None:
        raise ValueError("There is no interrupted upload for this video")
    if pending.get("video_id"):
        raise ValueError(
            f"YouTube already has this video as {pending['video_id']}: choose Upload to YouTube "
            "to record it (nothing is uploaded again), or record it as a manual upload."
        )
    clear_pending_upload(concept_id, fmt)
    append_jsonl(HISTORY_FILE, {"recorded_at": now(), "gate": "publish", "key": _key(concept_id, fmt),
                                "decision": "UPLOAD_DISCARDED", "session_started_at": pending.get("started_at"),
                                "reviewer": reviewer()})
    return snapshot()


def current_approval(concept_id: str, fmt: str) -> dict[str, Any] | None:
    key = _key(concept_id, fmt)
    draft = next((d for d in build_drafts() if d["key"] == key), None)
    path = _approved_path(key)
    if draft is None or not path.exists():
        return None
    record = load_json(path)
    if record.get("base_sha256") != draft["base_sha256"]:
        return None
    return record


def publish_record(concept_id: str, fmt: str) -> dict[str, Any] | None:
    path = _published_path(_key(concept_id, fmt))
    return load_json(path) if path.exists() else None


def snapshot() -> dict[str, Any]:
    items = []
    for draft in build_drafts():
        approval = current_approval(draft["concept_id"], draft["format"])
        published = publish_record(draft["concept_id"], draft["format"])
        history = [e for e in read_jsonl(HISTORY_FILE) if e.get("key") == draft["key"]]
        held = bool(history) and history[-1].get("decision") == "HOLD" and history[-1].get("base_sha256") == draft["base_sha256"]
        status = (
            "PUBLISHED" if published else "APPROVED_FOR_UPLOAD" if approval else "HELD" if held else "PENDING"
        )
        items.append(
            {
                **draft,
                "metadata": (approval or {}).get("metadata") or draft["draft_metadata"],
                "status": status,
                "decision": "APPROVE_PUBLISH" if approval else "HOLD" if held else "PENDING",
                "published": published,
                "pending_upload": None if published else pending_upload(draft["concept_id"], draft["format"]),
                "history": history,
            }
        )
    return {
        "status": (
            "WAITING_FOR_APPROVED_EXPORT"
            if not items
            else "ALL_PUBLISHED"
            if all(i["status"] == "PUBLISHED" for i in items)
            else "AWAITING_HUMAN_PUBLISH"
        ),
        "pending": sum(i["status"] == "PENDING" for i in items),
        "approved": sum(i["status"] == "APPROVED_FOR_UPLOAD" for i in items),
        "published": sum(i["status"] == "PUBLISHED" for i in items),
        "items": items,
    }


def apply_action(
    *, concept_id: str, format: str, decision: str, metadata: Any = None, note: str | None = None
) -> dict[str, Any]:
    value = str(decision or "").strip().upper()
    if value not in DECISIONS:
        raise ValueError("Decision must be APPROVE_PUBLISH or HOLD")
    key = _key(str(concept_id or ""), str(format or ""))
    draft = next((d for d in build_drafts() if d["key"] == key), None)
    if draft is None:
        raise ValueError("No approved final export for this video")
    if publish_record(draft["concept_id"], draft["format"]):
        raise ValueError("This video is already published; its record is final")
    pending = pending_upload(draft["concept_id"], draft["format"])
    if pending and not pending.get("video_id"):
        # An upload in progress pins the approval it started with (audit 2):
        # changing it now would resume the old session under new metadata.
        raise ValueError(
            "An upload of this video was started"
            + (f" at {pending.get('started_at')}" if pending.get("started_at") else "")
            + " and not finished. Resume it with Upload to YouTube, or discard it (after checking "
            "YouTube Studio for a half-uploaded private video) before changing this decision."
        )
    clean_note = str(note or "").strip()
    record: dict[str, Any] = {
        "artifact": "publish_decision",
        "key": key,
        "concept_id": draft["concept_id"],
        "format": draft["format"],
        "decision": value,
        "note": clean_note,
        "reviewer": reviewer(),
        "reviewed_at": now(),
        "base_sha256": draft["base_sha256"],
    }
    approved = _approved_path(key)
    if value == "APPROVE_PUBLISH":
        if draft["problems"]:
            raise ValueError("Cannot approve: " + " ".join(draft["problems"]))
        edits = metadata if isinstance(metadata, dict) else {}
        merged = {**draft["draft_metadata"], **{k: v for k, v in edits.items() if k != "title"}}
        record["metadata"] = validate_metadata(merged)
        record["video_file"] = draft["video_file"]
        record["video_sha256"] = draft["video_sha256"]
        record["thumbnail_file"] = draft["thumbnail_file"]
        record["thumbnail_sha256"] = draft["thumbnail_sha256"]
        record["provenance"] = draft["provenance"]
        atomic_write_json(approved, record)
    else:
        if not clean_note:
            raise ValueError("Hold needs a note saying why")
        if approved.exists():
            approved.unlink()
    append_jsonl(HISTORY_FILE, {"recorded_at": record["reviewed_at"], "gate": "publish", **{k: v for k, v in record.items() if k != "provenance"}})
    return snapshot()


def record_upload(
    *, concept_id: str, format: str, youtube_video_id: str, method: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Record the YouTube video id once the approved package was uploaded."""
    approval = current_approval(str(concept_id), str(format))
    if approval is None:
        raise ValueError("Approve the publish package before recording an upload")
    if publish_record(str(concept_id), str(format)):
        raise ValueError("This video already has a publish record")
    video_id = str(youtube_video_id or "").strip()
    if not VIDEO_ID.match(video_id):
        raise ValueError("A YouTube video id is 11 letters, digits, - or _")
    pending = pending_upload(str(concept_id), str(format))
    if pending and pending.get("video_id") and str(pending["video_id"]) != video_id:
        raise ValueError(
            f"YouTube already has this video as {pending['video_id']}; record that id, not {video_id}"
        )
    record = {
        "artifact": "publish_record",
        "key": approval["key"],
        "concept_id": approval["concept_id"],
        "format": approval["format"],
        "youtube_video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "method": method,
        "recorded_at": now(),
        "recorded_by": reviewer(),
        "metadata": approval["metadata"],
        "video_sha256": approval["video_sha256"],
        "thumbnail_sha256": approval["thumbnail_sha256"],
        "approval_reviewed_at": approval["reviewed_at"],
        **(details or {}),
    }
    atomic_write_json(_published_path(approval["key"]), record)
    # The publish record now holds the id: the pending upload has done its job.
    clear_pending_upload(str(concept_id), str(format))
    append_jsonl(HISTORY_FILE, {"recorded_at": record["recorded_at"], "gate": "publish", "key": approval["key"],
                                "decision": "UPLOADED", "method": method, "youtube_video_id": video_id})
    return snapshot()
