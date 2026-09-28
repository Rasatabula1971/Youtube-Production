"""Acquire public Experiment 02 source evidence without downloading video media.

Network acquisition is intentionally separate from offline evidence ingestion.
This collector uses yt-dlp only for English subtitles/captions, thumbnail, and
source metadata. A transcript is required before the offline ingestion layer is
allowed to create an enriched Experiment 02 profile.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXP2_DIR = PROJECT_ROOT / "experiment_02_analysis"
EXP2_OUTPUT = EXP2_DIR / "output"
PREPARED_DIR = EXP2_OUTPUT / "profiles_to_complete"
ENRICHED_DIR = EXP2_OUTPUT / "profiles_enriched"
INGEST_SCRIPT = EXP2_DIR / "evidence_ingest.py"

ACQUISITION_ROOT = Path(__file__).resolve().parent / "output" / "experiment_02"
SUMMARY_FILE = ACQUISITION_ROOT / "summary.json"

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
TRANSCRIPT_SUFFIXES = {".vtt", ".srt", ".txt", ".md"}

RATE_LIMIT_PATTERNS = ("HTTP Error 429", "Too Many Requests")
AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".opus", ".webm"}
DEFAULT_WHISPER_MODEL = "base"


def whisper_path() -> str | None:
    return shutil.which("whisper")


def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def local_transcription_available() -> bool:
    return whisper_path() is not None and ffmpeg_path() is not None


def classify_ytdlp_failure(stderr: str) -> str | None:
    text = stderr or ""
    if any(pattern.casefold() in text.casefold() for pattern in RATE_LIMIT_PATTERNS):
        return "RATE_LIMITED_429"
    return None


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "unknown"


def youtube_url(profile: dict[str, Any]) -> str:
    value = str(profile.get("youtube_url") or "").strip()
    if not value:
        video_id = str(profile.get("video_id") or "").strip()
        if video_id:
            value = f"https://www.youtube.com/watch?v={video_id}"

    parsed = urlparse(value)
    host = parsed.hostname.casefold() if parsed.hostname else ""
    if parsed.scheme != "https" or host not in {
        "youtube.com",
        "www.youtube.com",
        "youtu.be",
    }:
        raise ValueError("Experiment 02 profile requires a valid HTTPS YouTube URL")
    return value


def transcript_rank(path: Path, video_id: str) -> tuple[int, str]:
    name = path.name.casefold()
    exact_en = f"{video_id.casefold()}.en.vtt"
    if name == exact_en:
        return (0, name)
    if ".en-" in name or ".en_" in name:
        return (1, name)
    if ".en." in name:
        return (2, name)
    return (3, name)


def find_transcript(directory: Path, video_id: str) -> Path | None:
    candidates = (
        [
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix.casefold() in TRANSCRIPT_SUFFIXES
            and path.name.casefold().startswith(video_id.casefold())
        ]
        if directory.exists()
        else []
    )
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: transcript_rank(path, video_id))[0]


def find_thumbnail(directory: Path, video_id: str) -> Path | None:
    candidates = (
        [
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix.casefold() in IMAGE_SUFFIXES
            and path.name.casefold().startswith(video_id.casefold())
        ]
        if directory.exists()
        else []
    )
    if not candidates:
        return None
    preferred = {".jpg": 0, ".jpeg": 1, ".png": 2, ".webp": 3, ".avif": 4}
    return sorted(
        candidates,
        key=lambda path: (preferred.get(path.suffix.casefold(), 9), path.name),
    )[0]


def find_info_json(directory: Path, video_id: str) -> Path | None:
    candidate = directory / f"{safe_name(video_id)}.info.json"
    if candidate.exists():
        return candidate
    matches = sorted(directory.glob(f"{safe_name(video_id)}*.info.json"))
    return matches[0] if matches else None


def clear_generated_files(directory: Path, video_id: str) -> None:
    if not directory.exists():
        return
    prefix = video_id.casefold()
    for path in directory.iterdir():
        if not path.is_file():
            continue
        name = path.name.casefold()
        if name.startswith(prefix) or name in {
            "evidence_bundle.json",
            "acquisition.json",
        }:
            path.unlink()


def yt_dlp_command(
    yt_dlp: str,
    *,
    url: str,
    directory: Path,
) -> list[str]:
    template = str(directory / "%(id)s.%(ext)s")
    return [
        yt_dlp,
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        "en.*,en",
        "--sub-format",
        "vtt",
        "--write-thumbnail",
        "--write-info-json",
        "--no-playlist",
        "--restrict-filenames",
        "--output",
        template,
        url,
    ]


def yt_dlp_audio_command(
    yt_dlp: str,
    *,
    url: str,
    directory: Path,
) -> list[str]:
    template = str(directory / "%(id)s.fallback.%(ext)s")
    return [
        yt_dlp,
        "--no-playlist",
        "--restrict-filenames",
        "-f",
        "bestaudio/best",
        "-x",
        "--audio-format",
        "wav",
        "--output",
        template,
        url,
    ]


def find_fallback_audio(directory: Path, video_id: str) -> Path | None:
    if not directory.exists():
        return None
    candidates = [
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.suffix.casefold() in AUDIO_SUFFIXES
        and path.name.casefold().startswith(f"{video_id.casefold()}.fallback")
    ]
    return sorted(candidates)[0] if candidates else None


def run_local_whisper(
    audio_path: Path,
    *,
    output_dir: Path,
    model: str | None = None,
) -> subprocess.CompletedProcess[str]:
    executable = whisper_path()
    if not executable:
        raise RuntimeError("Local Whisper CLI is not available on PATH.")
    selected_model = (
        model or os.environ.get("YOUTUBE_WHISPER_MODEL") or DEFAULT_WHISPER_MODEL
    )
    return subprocess.run(
        [
            executable,
            str(audio_path),
            "--model",
            selected_model,
            "--language",
            "en",
            "--task",
            "transcribe",
            "--output_format",
            "txt",
            "--output_dir",
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def transcribe_audio_fallback(
    *,
    yt_dlp: str,
    url: str,
    video_id: str,
    output_dir: Path,
) -> dict[str, Any]:
    if not local_transcription_available():
        return {
            "status": "LOCAL_TRANSCRIBER_UNAVAILABLE",
            "message": "Local fallback requires ffmpeg and the Whisper CLI on PATH.",
        }

    audio_result = subprocess.run(
        yt_dlp_audio_command(yt_dlp, url=url, directory=output_dir),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    audio_path = find_fallback_audio(output_dir, video_id)
    if audio_result.returncode != 0 or audio_path is None:
        return {
            "status": "AUDIO_ACQUISITION_FAILED",
            "yt_dlp_return_code": audio_result.returncode,
            "stderr_tail": audio_result.stderr[-4000:],
        }

    try:
        whisper_result = run_local_whisper(audio_path, output_dir=output_dir)
        produced = output_dir / f"{audio_path.stem}.txt"
        transcript_path = output_dir / f"{video_id}.fallback.txt"
        if whisper_result.returncode == 0 and produced.exists():
            produced.replace(transcript_path)
            return {
                "status": "READY",
                "transcript": str(transcript_path),
                "model": (
                    os.environ.get("YOUTUBE_WHISPER_MODEL") or DEFAULT_WHISPER_MODEL
                ),
            }
        return {
            "status": "TRANSCRIPTION_FAILED",
            "return_code": whisper_result.returncode,
            "stderr_tail": whisper_result.stderr[-4000:],
        }
    finally:
        try:
            audio_path.unlink()
        except OSError:
            pass


def enriched_profile_ready(
    enriched_path: Path,
    prepared_profile: Path,
) -> bool:
    if not enriched_path.exists():
        return False
    try:
        profile = load_json(enriched_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    ingestion = profile.get("evidence_ingestion", {})
    if not isinstance(ingestion, dict):
        return False
    if ingestion.get("profile_source_sha256") != sha256_file(prepared_profile):
        return False

    source_inputs = profile.get("source_inputs", {})
    transcript = (
        source_inputs.get("transcript", {}) if isinstance(source_inputs, dict) else {}
    )
    if not isinstance(transcript, dict) or transcript.get("status") != "PROVIDED":
        return False

    return any(
        item.get("type") == "transcript"
        for item in profile.get("evidence", [])
        if isinstance(item, dict)
    )


def write_report(directory: Path, payload: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "acquisition.json"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def build_bundle(
    *,
    profile_path: Path,
    video_id: str,
    transcript: Path,
    thumbnail: Path | None,
    destination: Path,
) -> Path:
    payload: dict[str, Any] = {
        "video_id": video_id,
        "profile": str(profile_path.resolve()),
        "transcript": str(transcript.resolve()),
    }
    if thumbnail is not None:
        payload["thumbnail"] = {
            "path": str(thumbnail.resolve()),
            "observation": None,
        }

    destination.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return destination


def run_ingest(
    bundle_path: Path,
    *,
    python_executable: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            python_executable,
            str(INGEST_SCRIPT),
            "--bundle",
            str(bundle_path),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def acquire_one(
    profile_path: Path,
    *,
    yt_dlp: str,
    python_executable: str,
    force: bool = False,
) -> dict[str, Any]:
    profile = load_json(profile_path)
    video_id = safe_name(str(profile.get("video_id") or profile_path.stem))
    url = youtube_url(profile)
    output_dir = ACQUISITION_ROOT / video_id
    output_dir.mkdir(parents=True, exist_ok=True)

    enriched_path = ENRICHED_DIR / f"{video_id}.json"
    prepared_hash = sha256_file(profile_path)

    if not force and enriched_profile_ready(enriched_path, profile_path):
        result = {
            "video_id": video_id,
            "status": "READY_EXISTING",
            "profile_sha256": prepared_hash,
            "enriched_profile": str(enriched_path),
            "network_called": False,
        }
        result["report"] = str(write_report(output_dir, result))
        return result

    if force:
        clear_generated_files(output_dir, video_id)

    transcript = find_transcript(output_dir, video_id)
    thumbnail = find_thumbnail(output_dir, video_id)
    info_json = find_info_json(output_dir, video_id)
    network_called = False
    yt_result: subprocess.CompletedProcess[str] | None = None

    if transcript is None:
        network_called = True
        yt_result = subprocess.run(
            yt_dlp_command(yt_dlp, url=url, directory=output_dir),
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        transcript = find_transcript(output_dir, video_id)
        thumbnail = find_thumbnail(output_dir, video_id)
        info_json = find_info_json(output_dir, video_id)

    fallback_result: dict[str, Any] | None = None
    if transcript is None:
        fallback_result = transcribe_audio_fallback(
            yt_dlp=yt_dlp,
            url=url,
            video_id=video_id,
            output_dir=output_dir,
        )
        transcript = find_transcript(output_dir, video_id)

    if transcript is None:
        failure_status = (
            classify_ytdlp_failure(yt_result.stderr) if yt_result is not None else None
        )
        result = {
            "video_id": video_id,
            "status": failure_status or "TRANSCRIPT_UNAVAILABLE",
            "profile_sha256": prepared_hash,
            "network_called": network_called,
            "yt_dlp_return_code": (
                yt_result.returncode if yt_result is not None else None
            ),
            "thumbnail": str(thumbnail) if thumbnail else None,
            "info_json": str(info_json) if info_json else None,
            "fallback": fallback_result,
            "message": (
                "YouTube rate-limited subtitle acquisition (HTTP 429). "
                "Do not immediately retry; preserve this job and retry after the "
                "rate limit clears."
                if failure_status == "RATE_LIMITED_429"
                else "No English subtitle/caption file was acquired. "
                "The profile was not enriched."
            ),
        }
        if yt_result is not None:
            result["yt_dlp_stderr_tail"] = yt_result.stderr[-4000:]
        result["report"] = str(write_report(output_dir, result))
        return result

    bundle_path = build_bundle(
        profile_path=profile_path,
        video_id=video_id,
        transcript=transcript,
        thumbnail=thumbnail,
        destination=output_dir / "evidence_bundle.json",
    )
    ingest = run_ingest(
        bundle_path,
        python_executable=python_executable,
    )

    status = (
        "READY"
        if ingest.returncode == 0
        and enriched_profile_ready(enriched_path, profile_path)
        else "INGEST_FAILED"
    )
    result = {
        "video_id": video_id,
        "status": status,
        "profile_sha256": prepared_hash,
        "network_called": network_called,
        "yt_dlp_return_code": (yt_result.returncode if yt_result is not None else None),
        "transcript": str(transcript),
        "thumbnail": str(thumbnail) if thumbnail else None,
        "info_json": str(info_json) if info_json else None,
        "transcript_origin": (
            "local_whisper_fallback"
            if transcript.name.endswith(".fallback.txt")
            else "youtube_captions"
        ),
        "fallback": fallback_result,
        "bundle": str(bundle_path),
        "ingest_return_code": ingest.returncode,
        "enriched_profile": str(enriched_path) if enriched_path.exists() else None,
    }
    if yt_result is not None and yt_result.returncode != 0:
        result["yt_dlp_stderr_tail"] = yt_result.stderr[-4000:]
    if ingest.returncode != 0:
        result["ingest_stderr_tail"] = ingest.stderr[-4000:]
    result["report"] = str(write_report(output_dir, result))
    return result


def current_prepared_profiles() -> list[Path]:
    if not PREPARED_DIR.exists():
        return []
    return sorted(PREPARED_DIR.glob("*.json"))


def remove_stale_enriched(current_ids: set[str]) -> list[str]:
    removed: list[str] = []
    if not ENRICHED_DIR.exists():
        return removed

    for path in ENRICHED_DIR.glob("*.json"):
        if path.stem not in current_ids:
            path.unlink()
            removed.append(path.name)
    return removed


def run_batch(
    *,
    yt_dlp: str,
    python_executable: str,
    force: bool = False,
) -> dict[str, Any]:
    profiles = current_prepared_profiles()
    if not profiles:
        raise SystemExit(
            "No Experiment 02 prepared profiles found. "
            "Run Prepare Experiment 02 Profiles first."
        )

    current_ids = {safe_name(path.stem) for path in profiles}
    stale_removed = remove_stale_enriched(current_ids)

    results = [
        acquire_one(
            profile_path,
            yt_dlp=yt_dlp,
            python_executable=python_executable,
            force=force,
        )
        for profile_path in profiles
    ]

    ready_statuses = {"READY", "READY_EXISTING"}
    ready = sum(result["status"] in ready_statuses for result in results)
    failed = len(results) - ready
    status = "COMPLETE" if failed == 0 else "PARTIAL"

    summary = {
        "status": status,
        "profiles_found": len(profiles),
        "ready": ready,
        "failed": failed,
        "stale_enriched_removed": stale_removed,
        "results": results,
    }
    ACQUISITION_ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Acquire transcript/thumbnail evidence for Experiment 02"
    )
    parser.add_argument("--mode", choices=("doctor", "acquire"), required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    yt_dlp = shutil.which("yt-dlp")
    if args.mode == "doctor":
        result = {
            "status": "READY" if yt_dlp else "MISSING_YT_DLP",
            "yt_dlp": yt_dlp,
            "ffmpeg": ffmpeg_path(),
            "whisper": whisper_path(),
            "local_transcription_fallback": local_transcription_available(),
            "whisper_model": (
                os.environ.get("YOUTUBE_WHISPER_MODEL") or DEFAULT_WHISPER_MODEL
            ),
            "prepared_profiles": len(current_prepared_profiles()),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if not yt_dlp:
        raise SystemExit(
            "yt-dlp is not installed or not on PATH. "
            "Experiment 02 evidence acquisition cannot run."
        )

    summary = run_batch(
        yt_dlp=yt_dlp,
        python_executable=sys.executable,
        force=args.force,
    )
    print("\nEXPERIMENT 02 SOURCE EVIDENCE ACQUISITION")
    print("=" * 60)
    print(f"Status:           {summary['status']}")
    print(f"Prepared profiles:{summary['profiles_found']}")
    print(f"Evidence ready:   {summary['ready']}")
    print(f"Needs attention:  {summary['failed']}")
    for result in summary["results"]:
        print(
            f"  {result['video_id']}: {result['status']}"
            + (" (network)" if result.get("network_called") else " (reused)")
        )
    print(f"Summary:          {SUMMARY_FILE}")

    if summary["status"] != "COMPLETE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
