"""Tesseract project exchange: an editable project out, the finished edit back (D-144).

Vision: Tesseract is the final editable production environment. Automation
builds the near-final video; the human then moves clips, changes timing,
replaces scenes, adjusts text and graphics, changes music and polishes the
video in Tesseract. The handoff is therefore a structured, editable project,
not only the rendered MP4.

Export. From the current local final render (Slice 22) this writes one
project folder per video:

  media/visuals, media/narration, media/sound   the exact approved media
  <key>.otio                                    OpenTimelineIO timeline
  <key>.xml                                     Final Cut Pro 7 XML timeline
  reference/automated_render.mp4                the automated render, to compare
  thumbnail/                                    the thumbnail's editable source
  exchange.json, README.txt

Every clip is named with a stable clip id (V-<shot id>, N-<segment id>,
S-<sound requirement id>), so the scenes of a returned timeline map back to
the shots, narration segments and sound cues they came from.

Import. The finished edit comes back as a video file (and, optionally, the
edited OpenTimelineIO timeline). The video is probed: it must have a video
stream at the format's frame size and an audio stream. It is copied into
managed storage, bound to the export and the automated render it came from,
and becomes the candidate at the Human Final Export Gate in place of the
automated render. If the automated render changes upstream, the returned
edit is stale and must be redone. Discarding the edit (with a note) returns
the gate to the automated render.

Contract status. Tesseract's own project format is not known to this build,
so the export uses the two open timeline formats most editors import. The
config records ``round_trip_verified: false`` until one project has been
through Tesseract and back; the UI says so instead of claiming integration.
No paid call, upload or publish happens here.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline_integrity import append_jsonl, atomic_write_json, named_lock, read_jsonl
from final_render import RESULT_DIR, _final_visual_segments, result_is_current
from final_render_manifest import manifest_is_current
from visual_acquisition import load_json, safe_slug, sha256_file

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
CONFIG_FILE = HERE / "tesseract_exchange_config.json"
NARRATION_CONFIG = HERE / "narration_render_config.json"
EXPORT_DIR = OUTPUT / "editor_projects"
RETURN_DIR = OUTPUT / "editor_returns"
HISTORY_FILE = OUTPUT / "editor_exchange_history.jsonl"
FINAL_PACKAGES_DIR = _ROOT / "packaging_engine" / "output" / "mature_packaging" / "final_packages"
EXCHANGE_VERSION = 1
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
THUMBNAIL_SOURCE_FILES = ("render_spec.json", "render_report.json")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config() -> dict[str, Any]:
    return load_json(CONFIG_FILE)


def _key(concept_id: str, fmt: str) -> str:
    return f"{safe_slug(concept_id)}.{safe_slug(fmt)}"


def _clip_id(prefix: str, value: Any, used: set[str]) -> str:
    base = prefix + "-" + (re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "")).strip("-") or "clip")
    clip_id, index = base, 2
    while clip_id in used:
        clip_id, index = f"{base}-{index}", index + 1
    used.add(clip_id)
    return clip_id


def _automated(concept_id: str, fmt: str) -> tuple[Path, dict[str, Any]]:
    path = RESULT_DIR / f"{_key(concept_id, fmt)}.final_render_result.json"
    result = result_is_current(path)
    if result is None:
        raise ValueError("There is no current final render for this video; render it first")
    return path, result


# ---------------------------------------------------------------- timeline

def _lanes(clips: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Clips placed on the fewest tracks so that none overlap on a track."""
    lanes: list[list[dict[str, Any]]] = []
    for clip in sorted(clips, key=lambda c: (c["start_frame"], c["clip_id"])):
        for lane in lanes:
            last = lane[-1]
            if last["start_frame"] + last["duration_frames"] <= clip["start_frame"]:
                lane.append(clip)
                break
        else:
            lanes.append([clip])
    return lanes


def _frames(seconds: float, fps: int) -> int:
    return max(0, int(round(float(seconds) * fps)))


def probe_media_seconds(path: Path) -> float | None:
    """The length of an audio or video file, or None when it cannot be read."""
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argument list, no shell
            [_ffprobe_binary(), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, check=False, timeout=60,
        )
        value = float(json.loads(completed.stdout or "{}").get("format", {}).get("duration") or 0)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return value if value > 0 else None


def build_clips(
    manifest: dict[str, Any], media_seconds: Callable[[Path], float | None] = probe_media_seconds
) -> list[dict[str, Any]]:
    """The editable clips of a final render manifest, with stable clip ids.

    A moving clip or music bed shorter than its slot loops, as in the
    automated render; a sound effect shorter than its slot plays once.
    """
    fps = int((manifest.get("video_profile") or {}).get("fps") or 0)
    if fps <= 0:
        raise ValueError("The final video profile has no frame rate")
    used: set[str] = set()
    clips: list[dict[str, Any]] = []

    def add(kind: str, clip_id: str, source: Path, start: float, duration: float, extra: dict[str, Any],
            loops: bool) -> None:
        start_frame, duration_frames = _frames(start, fps), _frames(duration, fps)
        still = source.suffix.lower() in IMAGE_EXTENSIONS
        length = None if still else media_seconds(source)
        media_frames = int(length * fps) if length else None
        if media_frames is not None and media_frames > 0 and not loops:
            duration_frames = min(duration_frames, media_frames)
        if duration_frames <= 0:
            return
        clips.append({
            "clip_id": clip_id, "kind": kind,
            "source_file": str(source), "source_sha256": sha256_file(source),
            "start_seconds": round(start_frame / fps, 6), "duration_seconds": round(duration_frames / fps, 6),
            "start_frame": start_frame, "duration_frames": duration_frames,
            "still_image": still, "media_duration_frames": media_frames or None, "loops": bool(loops and media_frames),
            **extra,
        })

    for item in _final_visual_segments(manifest):
        source = Path(str(item["asset_file"]))
        add("VISUAL", _clip_id("V", item.get("shot_id"), used), source,
            float(item.get("start_seconds") or 0), float(item["duration_seconds"]), {
                "shot_id": item.get("shot_id"), "beat_id": item.get("beat_id"),
                "scene_index": item.get("scene_index"), "story_purpose": item.get("story_purpose"),
            }, loops=True)
    for item in manifest.get("narration_track", []):
        source = Path(str(item.get("audio_file") or ""))
        start = float(item.get("audio_start_seconds") or 0)
        end = float(item.get("audio_end_seconds") or 0)
        if not source.is_file() or item.get("audio_sha256") != sha256_file(source):
            raise ValueError("A narration file changed since the final render")
        add("NARRATION", _clip_id("N", item.get("segment_id"), used), source, start, end - start,
            {"segment_id": item.get("segment_id")}, loops=False)
    for item in manifest.get("sound_track", []):
        source = Path(str(item.get("asset_file") or ""))
        if not source.is_file() or item.get("asset_sha256") != sha256_file(source):
            raise ValueError("A sound file changed since the final render")
        start = float(item.get("start_seconds") or 0)
        add(str(item.get("kind") or "SFX"), _clip_id("S", item.get("requirement_id"), used), source, start,
            float(item.get("end_seconds") or start) - start, {
                "requirement_id": item.get("requirement_id"), "segment_id": item.get("segment_id"),
                "volume": item.get("volume"), "loop_to_fill": bool(item.get("loop_to_fill")),
            }, loops=bool(item.get("loop_to_fill")))
    if not any(c["kind"] == "VISUAL" for c in clips) or not any(c["kind"] == "NARRATION" for c in clips):
        raise ValueError("The final render has no visual or narration clips to export")
    return clips


def assign_tracks(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Video V1..; narration A1..; then music and sound-effect tracks."""
    tracks: list[dict[str, Any]] = []
    groups = (("VISUAL", "Video", "V", "Visuals"), ("NARRATION", "Audio", "A", "Narration"),
              ("MUSIC", "Audio", "A", "Music"), ("SFX", "Audio", "A", "Sound effects"))
    counters = {"V": 0, "A": 0}
    for kind, otio_kind, letter, label in groups:
        for lane_number, lane in enumerate(_lanes([c for c in clips if c["kind"] == kind]), start=1):
            counters[letter] += 1
            name = f"{letter}{counters[letter]} {label}" + (f" {lane_number}" if lane_number > 1 else "")
            for clip in lane:
                clip["track"] = name
            tracks.append({"name": name, "kind": otio_kind, "clips": lane})
    return tracks


def pieces(clip: dict[str, Any]) -> list[tuple[int, int]]:
    """(record start, length) of each repeat of a looping clip; one piece otherwise."""
    media = clip.get("media_duration_frames")
    if not clip.get("loops") or not media or media >= clip["duration_frames"]:
        return [(clip["start_frame"], clip["duration_frames"])]
    out, offset = [], 0
    while offset < clip["duration_frames"]:
        length = min(media, clip["duration_frames"] - offset)
        out.append((clip["start_frame"] + offset, length))
        offset += length
    return out


def _available(clip: dict[str, Any]) -> int:
    return int(clip.get("media_duration_frames") or clip["duration_frames"])


def _rt(frames: int, fps: int) -> dict[str, Any]:
    return {"OTIO_SCHEMA": "RationalTime.1", "rate": float(fps), "value": float(frames)}


def _range(start: int, duration: int, fps: int) -> dict[str, Any]:
    return {"OTIO_SCHEMA": "TimeRange.1", "start_time": _rt(start, fps), "duration": _rt(duration, fps)}


def build_otio(tracks: list[dict[str, Any]], *, name: str, fps: int, metadata: dict[str, Any],
               media_url: Callable[[dict[str, Any]], str]) -> dict[str, Any]:
    children = []
    for track in tracks:
        items: list[dict[str, Any]] = []
        cursor = 0
        for clip in track["clips"]:
            for part, (start, length) in enumerate(pieces(clip), start=1):
                if start > cursor:
                    items.append({"OTIO_SCHEMA": "Gap.1", "name": "", "source_range": _range(0, start - cursor, fps),
                                  "effects": [], "markers": [], "enabled": True, "metadata": {}})
                items.append({
                    "OTIO_SCHEMA": "Clip.1", "name": clip["clip_id"],
                    "source_range": _range(0, length, fps),
                    "media_reference": {"OTIO_SCHEMA": "ExternalReference.1", "name": Path(clip["media"]).name,
                                        "target_url": media_url(clip), "available_range": _range(0, _available(clip), fps),
                                        "metadata": {}},
                    "effects": [], "markers": [], "enabled": True,
                    "metadata": {"youtube_production": {**{k: v for k, v in clip.items() if k != "source_file"}, "part": part}},
                })
                cursor = start + length
        children.append({"OTIO_SCHEMA": "Track.1", "name": track["name"], "kind": track["kind"], "children": items,
                         "source_range": None, "effects": [], "markers": [], "enabled": True, "metadata": {}})
    return {
        "OTIO_SCHEMA": "Timeline.1", "name": name, "global_start_time": None,
        "metadata": {"youtube_production": metadata},
        "tracks": {"OTIO_SCHEMA": "Stack.1", "name": "tracks", "children": children, "source_range": None,
                   "effects": [], "markers": [], "enabled": True, "metadata": {}},
    }


def _x(value: Any) -> str:
    return (str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def build_fcp7_xml(tracks: list[dict[str, Any]], *, name: str, fps: int, width: int, height: int,
                   media_url: Callable[[dict[str, Any]], str]) -> str:
    rate = f"<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>"
    duration = max((c["start_frame"] + c["duration_frames"] for t in tracks for c in t["clips"]), default=0)

    def clipitem(clip: dict[str, Any], media: str, track_index: int) -> str:
        return "".join(piece(clip, media, track_index, part, start, length)
                       for part, (start, length) in enumerate(pieces(clip), start=1))

    def piece(clip: dict[str, Any], media: str, track_index: int, part: int, start: int, length: int) -> str:
        end = start + length
        ref = f"{clip['clip_id']}-{part}"
        if media == "video":
            characteristics = f"<video><samplecharacteristics>{rate}<width>{width}</width><height>{height}</height></samplecharacteristics></video>"
            source_track = ""
        else:
            characteristics = "<audio><channelcount>2</channelcount></audio>"
            source_track = f"<sourcetrack><mediatype>audio</mediatype><trackindex>{track_index}</trackindex></sourcetrack>"
        return (
            f'<clipitem id="clipitem-{_x(ref)}"><name>{_x(clip["clip_id"])}</name><enabled>TRUE</enabled>'
            f"<duration>{_available(clip)}</duration>{rate}"
            f"<start>{start}</start><end>{end}</end><in>0</in><out>{length}</out>"
            f'<file id="file-{_x(ref)}"><name>{_x(Path(clip["media"]).name)}</name>'
            f"<pathurl>{_x(media_url(clip))}</pathurl>{rate}<duration>{_available(clip)}</duration>"
            f"<media>{characteristics}</media></file>{source_track}</clipitem>"
        )

    video = "".join("<track>" + "".join(clipitem(c, "video", 1) for c in t["clips"]) + "</track>"
                    for t in tracks if t["kind"] == "Video")
    audio = "".join("<track>" + "".join(clipitem(c, "audio", 1) for c in t["clips"]) + "</track>"
                    for t in tracks if t["kind"] == "Audio")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="5">'
        f'<sequence id="sequence-1"><name>{_x(name)}</name><duration>{duration}</duration>{rate}'
        "<media><video><format><samplecharacteristics>"
        f"{rate}<width>{width}</width><height>{height}</height><pixelaspectratio>square</pixelaspectratio>"
        f"</samplecharacteristics></format>{video}</video><audio>{audio}</audio></media></sequence></xmeml>\n"
    )


# ------------------------------------------------------------------ export

def _export_record_path(concept_id: str, fmt: str) -> Path:
    return EXPORT_DIR / f"{_key(concept_id, fmt)}.editor_export.json"


def _thumbnail_sources(concept_id: str, fmt: str) -> list[Path]:
    """The approved thumbnail and the files it was composed from, when known."""
    bundle = FINAL_PACKAGES_DIR / f"{safe_slug(concept_id)}.final_package.json"
    if not bundle.is_file():
        return []
    try:
        package = (load_json(bundle).get("packages") or {}).get(fmt) or {}
    except (OSError, ValueError):
        return []
    image = Path(str((package.get("thumbnail_image") or {}).get("image") or ""))
    if not image.is_file():
        return []
    files = [image]
    for name in THUMBNAIL_SOURCE_FILES:
        if (image.parent / name).is_file():
            files.append(image.parent / name)
    spec = image.parent / "render_spec.json"
    if spec.is_file():
        try:
            subject = str((load_json(spec).get("subject_image") or {}).get("path") or "")
        except (OSError, ValueError):
            subject = ""
        if subject:
            path = Path(subject) if Path(subject).is_absolute() else image.parent / subject
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                files.append(path)
    return files


def export_is_current(concept_id: str, fmt: str) -> dict[str, Any] | None:
    path = _export_record_path(concept_id, fmt)
    if not path.is_file():
        return None
    try:
        record = load_json(path)
        result_path, _result = _automated(concept_id, fmt)
    except (OSError, ValueError):
        return None
    if (
        record.get("artifact") != "editor_export"
        or record.get("source_final_render_result_sha256") != sha256_file(result_path)
    ):
        return None
    folder = Path(str(record.get("folder") or ""))
    for name, digest in (record.get("timeline_files") or {}).items():
        file = folder / name
        if not file.is_file() or sha256_file(file) != digest:
            return None
    return record


def export(*, concept_id: str, format: str) -> dict[str, Any]:
    """Write the editable project for the current final render (idempotent)."""
    concept_id, fmt = str(concept_id), str(format)
    with named_lock(f"editor_exchange:{_key(concept_id, fmt)}"):
        current = export_is_current(concept_id, fmt)
        if current is not None:
            return current
        return _export(concept_id, fmt)


def _export(concept_id: str, fmt: str) -> dict[str, Any]:
    config = load_config()
    result_path, result = _automated(concept_id, fmt)
    manifest_path = Path(str((result.get("provenance") or {}).get("final_render_manifest") or ""))
    manifest = manifest_is_current(manifest_path)
    if manifest is None:
        raise ValueError("The final render manifest is stale; render again first")
    profile = manifest.get("video_profile") or {}
    fps, width, height = int(profile.get("fps") or 0), int(profile.get("width") or 0), int(profile.get("height") or 0)
    if min(fps, width, height) <= 0:
        raise ValueError("The final video profile is incomplete")

    key = _key(concept_id, fmt)
    result_sha = sha256_file(result_path)
    export_id = result_sha[:12]
    folder = EXPORT_DIR / key / export_id
    staging = EXPORT_DIR / key / f".{export_id}.partial"
    if staging.exists():
        shutil.rmtree(staging)
    clips = build_clips(manifest)
    tracks = assign_tracks(clips)

    sub = {"VISUAL": "visuals", "NARRATION": "narration", "MUSIC": "sound", "SFX": "sound"}
    for clip in clips:
        source = Path(clip.pop("source_file"))
        relative = f"media/{sub.get(clip['kind'], 'sound')}/{clip['clip_id']}{source.suffix.lower()}"
        (staging / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, staging / relative)
        clip["media"] = relative

    def media_url(clip: dict[str, Any]) -> str:
        return (folder / clip["media"]).resolve().as_uri()

    extras: dict[str, str] = {}
    if config.get("copy_reference_render", True):
        (staging / "reference").mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(result["render_file"]), staging / "reference" / "automated_render.mp4")
        extras["reference_render"] = "reference/automated_render.mp4"
    thumbnail_files = []
    for source in _thumbnail_sources(concept_id, fmt):
        (staging / "thumbnail").mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, staging / "thumbnail" / source.name)
        thumbnail_files.append(f"thumbnail/{source.name}")

    metadata = {
        "exchange_version": EXCHANGE_VERSION, "export_id": export_id, "concept_id": concept_id, "format": fmt,
        "video_profile": profile, "source_render_sha256": result.get("render_sha256"),
    }
    otio = build_otio(tracks, name=key, fps=fps, metadata=metadata, media_url=media_url)
    xml = build_fcp7_xml(tracks, name=key, fps=fps, width=width, height=height, media_url=media_url)
    (staging / f"{key}.otio").write_text(json.dumps(otio, indent=2, ensure_ascii=False), encoding="utf-8")
    (staging / f"{key}.xml").write_text(xml, encoding="utf-8")
    (staging / "README.txt").write_text(_readme(config, key, tracks, thumbnail_files), encoding="utf-8")
    exchange = {
        **metadata, "artifact": "editor_exchange", "editor": config.get("editor_name"),
        "duration_seconds": float(manifest.get("duration_seconds") or 0),
        "tracks": [{"name": t["name"], "kind": t["kind"], "clip_ids": [c["clip_id"] for c in t["clips"]]} for t in tracks],
        "clips": clips, "thumbnail_files": thumbnail_files, **extras,
    }
    atomic_write_json(staging / "exchange.json", exchange)

    if folder.exists():
        shutil.rmtree(folder)
    staging.rename(folder)
    record = {
        "artifact": "editor_export", "exchange_version": EXCHANGE_VERSION, "export_id": export_id,
        "concept_id": concept_id, "format": fmt, "exported_at": now(), "folder": str(folder.resolve()),
        "editor": config.get("editor_name"),
        "timeline_files": {name: sha256_file(folder / name) for name in (f"{key}.otio", f"{key}.xml", "exchange.json")},
        "otio_file": str((folder / f"{key}.otio").resolve()), "xml_file": str((folder / f"{key}.xml").resolve()),
        "clips": len(clips), "tracks": len(tracks), "thumbnail_files": thumbnail_files,
        "source_final_render_result": str(result_path.resolve()), "source_final_render_result_sha256": result_sha,
        "source_render_sha256": result.get("render_sha256"),
    }
    atomic_write_json(_export_record_path(concept_id, fmt), record)
    append_jsonl(HISTORY_FILE, {"recorded_at": now(), "event": "EXPORTED", "concept_id": concept_id, "format": fmt,
                                "export_id": export_id, "folder": record["folder"]})
    return record


def _readme(config: dict[str, Any], key: str, tracks: list[dict[str, Any]], thumbnail_files: list[str]) -> str:
    lines = [
        f"Editable project for {key}",
        "",
        f"Open {key}.otio (OpenTimelineIO) or {key}.xml (Final Cut Pro 7 XML) in {config.get('editor_name') or 'your editor'}.",
        "Media is in media/. Every clip is named with a stable id: V-<shot>, N-<narration segment>, S-<sound cue>.",
        "Keep those names when you move, trim or replace clips, so the app can tell which scenes changed.",
        "Sound levels from the automated mix are in exchange.json (volume); set them in the editor.",
        "",
        "Tracks:",
        *[f"  {t['name']}: {len(t['clips'])} clip(s)" for t in tracks],
        "",
        "reference/automated_render.mp4 is the automated render, for comparison.",
    ]
    if thumbnail_files:
        lines.append("thumbnail/ holds the approved thumbnail and the files it was composed from.")
    lines += [
        "",
        "When the edit is finished, export the video at the same frame size, with audio,",
        "and import it in the app (Produce > Tesseract). Optionally import the edited .otio too.",
        "",
        str(config.get("contract_note") or ""),
    ]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ import

def _ffprobe_binary() -> str:
    try:
        return str((load_json(NARRATION_CONFIG).get("audio_qc") or {}).get("ffprobe_binary") or "ffprobe")
    except (OSError, ValueError):
        return "ffprobe"


def probe_video(path: Path) -> dict[str, Any]:
    completed = subprocess.run(  # noqa: S603 - fixed argument list, no shell
        [_ffprobe_binary(), "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise ValueError("The edited video could not be read: " + (completed.stderr or "").strip()[:300])
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("ffprobe returned no usable description of the edited video") from exc
    streams = payload.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    try:
        duration = float((payload.get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    return {
        "has_video": video is not None, "has_audio": audio is not None,
        "width": int((video or {}).get("width") or 0), "height": int((video or {}).get("height") or 0),
        "video_codec": (video or {}).get("codec_name"), "audio_codec": (audio or {}).get("codec_name"),
        "duration_seconds": duration,
    }


def quality_checks(info: dict[str, Any], profile: dict[str, Any], automated_seconds: float) -> list[dict[str, Any]]:
    width, height = int(profile.get("width") or 0), int(profile.get("height") or 0)
    duration = float(info.get("duration_seconds") or 0)

    def check(name: str, ok: bool, detail: str) -> dict[str, Any]:
        return {"check": name, "status": "PASS" if ok else "FAIL", "detail": detail}

    change = duration - automated_seconds
    return [
        check("VIDEO_STREAM", bool(info.get("has_video")), f"codec {info.get('video_codec') or 'none'}"),
        check("FRAME_SIZE", (info.get("width"), info.get("height")) == (width, height),
              f"{info.get('width')}x{info.get('height')}, expected {width}x{height}"),
        check("AUDIO_STREAM", bool(info.get("has_audio")), f"codec {info.get('audio_codec') or 'none'}"),
        check("DURATION", duration > 0,
              f"{duration:.2f} s ({'+' if change >= 0 else ''}{change:.2f} s against the automated render)"),
    ]


def _timeline_clips(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    """Clips of an OpenTimelineIO timeline with their record positions in seconds."""
    def seconds(time_range: Any, field: str) -> float:
        value = (time_range or {}).get(field) or {}
        rate = float(value.get("rate") or 0)
        return float(value.get("value") or 0) / rate if rate > 0 else 0.0

    found: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for child in node:
                walk(child)
            return
        if not isinstance(node, dict):
            return
        schema = str(node.get("OTIO_SCHEMA") or "")
        if schema.startswith("Track."):
            cursor = 0.0
            for child in node.get("children") or []:
                if not isinstance(child, dict):
                    continue
                child_schema = str(child.get("OTIO_SCHEMA") or "")
                if child_schema.startswith("Transition."):
                    continue
                span = child.get("source_range") or ((child.get("media_reference") or {}).get("available_range"))
                duration = seconds(span, "duration")
                if child_schema.startswith("Clip."):
                    meta = ((child.get("metadata") or {}).get("youtube_production") or {})
                    found.append({
                        "clip_id": str(meta.get("clip_id") or child.get("name") or ""),
                        "track": node.get("name"), "start_seconds": round(cursor, 3),
                        "duration_seconds": round(duration, 3),
                    })
                elif child_schema.startswith("Stack."):
                    walk(child)
                cursor += duration
            return
        for value in node.values():
            walk(value)

    walk(timeline.get("tracks"))
    return found


def scene_changes(exchange: dict[str, Any], timeline: dict[str, Any]) -> dict[str, Any]:
    """Which exported clips were kept, moved, retimed or removed, and what was added."""
    fps = float((exchange.get("video_profile") or {}).get("fps") or 30)
    tolerance = 1.0 / fps + 1e-6
    returned: dict[str, list[dict[str, Any]]] = {}
    for clip in _timeline_clips(timeline):
        returned.setdefault(clip["clip_id"], []).append(clip)
    rows = []
    for clip in exchange.get("clips") or []:
        matches = returned.pop(clip["clip_id"], [])
        if not matches:
            change = "REMOVED"
        else:
            # The repeats of a looping clip count as one clip.
            first = {"start_seconds": min(m["start_seconds"] for m in matches),
                     "duration_seconds": round(sum(m["duration_seconds"] for m in matches), 3)}
            moved = abs(first["start_seconds"] - clip["start_seconds"]) > tolerance
            retimed = abs(first["duration_seconds"] - clip["duration_seconds"]) > tolerance * len(matches)
            change = "MOVED_AND_RETIMED" if moved and retimed else "MOVED" if moved else "RETIMED" if retimed else "KEPT"
        rows.append({
            "clip_id": clip["clip_id"], "kind": clip.get("kind"), "change": change, "uses": len(matches),
            "shot_id": clip.get("shot_id"), "segment_id": clip.get("segment_id"),
            "requirement_id": clip.get("requirement_id"),
            "start_seconds": clip.get("start_seconds"),
            "new_start_seconds": first["start_seconds"] if matches else None,
            "new_duration_seconds": first["duration_seconds"] if matches else None,
        })
    added = [c for clips in returned.values() for c in clips]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["change"]] = counts.get(row["change"], 0) + 1
    counts["ADDED"] = len(added)
    return {"clips": rows, "added": added, "counts": counts}


def _return_record_path(concept_id: str, fmt: str) -> Path:
    return RETURN_DIR / f"{_key(concept_id, fmt)}.editor_return.json"


def return_is_current(path: Path) -> dict[str, Any] | None:
    """A returned edit whose bytes and source automated render are unchanged."""
    if not path.is_file() or path.parent.resolve() != RETURN_DIR.resolve():
        return None
    try:
        record = load_json(path)
    except (OSError, ValueError):
        return None
    if record.get("artifact") != "editor_return" or record.get("status") != "READY_FOR_HUMAN_FINAL_EXPORT_GATE":
        return None
    render = Path(str(record.get("render_file") or ""))
    source = Path(str((record.get("provenance") or {}).get("final_render_result") or ""))
    if (
        not render.is_file()
        or render.parent.parent.resolve() != RETURN_DIR.resolve()
        or sha256_file(render) != record.get("render_sha256")
        or render.stat().st_size != int(record.get("render_bytes") or 0)
        or result_is_current(source) is None
        or sha256_file(source) != (record.get("provenance") or {}).get("final_render_result_sha256")
    ):
        return None
    return record


def current_return(concept_id: str, fmt: str) -> tuple[Path, dict[str, Any]] | None:
    path = _return_record_path(concept_id, fmt)
    record = return_is_current(path)
    return (path, record) if record is not None else None


def import_edit(
    *, concept_id: str, format: str, video_path: str, timeline_path: str | None = None, note: str = "",
    probe: Callable[[Path], dict[str, Any]] = probe_video,
) -> dict[str, Any]:
    """Bring the finished edit back as the Final Export Gate candidate."""
    concept_id, fmt = str(concept_id), str(format)
    with named_lock(f"editor_exchange:{_key(concept_id, fmt)}"):
        return _import(concept_id, fmt, video_path, timeline_path, note, probe)


def _import(concept_id: str, fmt: str, video_path: str, timeline_path: str | None, note: str,
            probe: Callable[[Path], dict[str, Any]]) -> dict[str, Any]:
    config = load_config()
    record = export_is_current(concept_id, fmt)
    if record is None:
        raise ValueError("Export the editable project for the current final render first")
    result_path, result = _automated(concept_id, fmt)
    source = Path(str(video_path or "").strip().strip('"')).expanduser()
    allowed = [str(e).lower() for e in config.get("accepted_edit_extensions") or [".mp4", ".mov"]]
    if not source.is_file() or source.stat().st_size <= 0:
        raise ValueError("The edited video file was not found")
    if source.suffix.lower() not in allowed:
        raise ValueError("The edited video must be one of: " + ", ".join(allowed))
    exchange = load_json(Path(record["folder"]) / "exchange.json")

    timeline: dict[str, Any] | None = None
    timeline_source: Path | None = None
    if timeline_path and str(timeline_path).strip():
        timeline_source = Path(str(timeline_path).strip().strip('"')).expanduser()
        if not timeline_source.is_file() or timeline_source.suffix.lower() != ".otio":
            raise ValueError("The edited timeline must be an existing .otio file")
        try:
            timeline = json.loads(timeline_source.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError("The edited timeline is not readable OpenTimelineIO JSON") from exc
        if not isinstance(timeline, dict) or not str(timeline.get("OTIO_SCHEMA") or "").startswith("Timeline."):
            raise ValueError("The edited timeline is not an OpenTimelineIO timeline")

    info = probe(source)
    checks = quality_checks(info, exchange.get("video_profile") or {}, float(result.get("duration_seconds") or 0))
    failed = [c for c in checks if c["status"] == "FAIL"]
    if failed:
        raise ValueError("The edited video failed checks: " + "; ".join(f"{c['check']} ({c['detail']})" for c in failed))

    digest = sha256_file(source)
    folder = RETURN_DIR / _key(concept_id, fmt)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"edited-{digest[:12]}{source.suffix.lower()}"
    partial = destination.with_name(destination.name + ".partial")
    shutil.copy2(source, partial)
    if sha256_file(partial) != digest:
        partial.unlink()
        raise ValueError("The edited video changed while it was being copied; try again")
    partial.replace(destination)
    for old in folder.iterdir():
        if old.is_file() and old != destination and old.name.startswith(("edited-", "returned-")):
            old.unlink()
    changes = None
    if timeline is not None and timeline_source is not None:
        kept = folder / f"returned-{digest[:12]}.otio"
        shutil.copy2(timeline_source, kept)
        changes = scene_changes(exchange, timeline)

    edit = {
        "artifact": "editor_return", "status": "READY_FOR_HUMAN_FINAL_EXPORT_GATE",
        "concept_id": concept_id, "format": fmt, "editor": config.get("editor_name"),
        "imported_at": now(), "note": str(note or "").strip(),
        "render_file": str(destination.resolve()), "render_sha256": digest,
        "render_bytes": destination.stat().st_size, "duration_seconds": float(info.get("duration_seconds") or 0),
        "original_file_name": source.name,
        "quality_checks": checks, "scene_changes": changes,
        "provenance": {
            "editor_export": str(_export_record_path(concept_id, fmt).resolve()),
            "export_id": record.get("export_id"),
            "final_render_result": str(result_path.resolve()),
            "final_render_result_sha256": sha256_file(result_path),
            "automated_render_sha256": result.get("render_sha256"),
        },
    }
    atomic_write_json(_return_record_path(concept_id, fmt), edit)
    append_jsonl(HISTORY_FILE, {"recorded_at": now(), "event": "EDIT_IMPORTED", "concept_id": concept_id,
                                "format": fmt, "render_sha256": digest, "export_id": record.get("export_id"),
                                "scene_counts": (changes or {}).get("counts")})
    return edit


def discard_edit(*, concept_id: str, format: str, note: str) -> None:
    """Withdraw the returned edit; the automated render is the candidate again."""
    concept_id, fmt = str(concept_id), str(format)
    if not str(note or "").strip():
        raise ValueError("Say why the edit is discarded")
    with named_lock(f"editor_exchange:{_key(concept_id, fmt)}"):
        path = _return_record_path(concept_id, fmt)
        if not path.is_file():
            raise ValueError("There is no returned edit to discard")
        record = load_json(path)
        path.unlink()
        folder = RETURN_DIR / _key(concept_id, fmt)
        if folder.is_dir():
            shutil.rmtree(folder)
        append_jsonl(HISTORY_FILE, {"recorded_at": now(), "event": "EDIT_DISCARDED", "concept_id": concept_id,
                                    "format": fmt, "render_sha256": record.get("render_sha256"),
                                    "note": str(note).strip()})


# ---------------------------------------------------------------- snapshot

def snapshot() -> dict[str, Any]:
    config = load_config()
    items = []
    paths = sorted(RESULT_DIR.glob("*.final_render_result.json")) if RESULT_DIR.exists() else []
    for path in paths:
        result = result_is_current(path)
        if result is None:
            continue
        concept_id, fmt = str(result.get("concept_id") or ""), str(result.get("format") or "")
        record = export_is_current(concept_id, fmt)
        returned = current_return(concept_id, fmt)
        edit = returned[1] if returned else None
        items.append({
            "key": _key(concept_id, fmt), "concept_id": concept_id, "format": fmt,
            "status": "EDIT_RETURNED" if edit else "EXPORTED" if record else "READY_TO_EXPORT",
            "duration_seconds": float(result.get("duration_seconds") or 0),
            "automated_render_file": result.get("render_file"),
            "export": record,
            "edit": edit,
        })
    history = [h for h in read_jsonl(HISTORY_FILE)][-20:]
    return {
        "status": ("EDIT_RETURNED" if items and all(i["edit"] for i in items) else
                   "AWAITING_EDIT" if any(i["status"] == "EXPORTED" for i in items) else
                   "READY" if items else "WAITING_FOR_FINAL_RENDER"),
        "editor_name": config.get("editor_name"),
        "round_trip_verified": bool(config.get("round_trip_verified")),
        "native_project_format_known": bool(config.get("native_project_format_known")),
        "contract_note": config.get("contract_note"),
        "formats": config.get("interchange_formats") or [],
        "items": items,
        "history": history,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Tesseract project exchange")
    parser.add_argument("--mode", choices=("status", "export"), default="status")
    parser.add_argument("--concept-id", default="")
    parser.add_argument("--format", default="")
    args = parser.parse_args()
    if args.mode == "export":
        print(json.dumps(export(concept_id=args.concept_id, format=args.format), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(snapshot(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
