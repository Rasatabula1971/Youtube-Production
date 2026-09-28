"""Deterministic source-text overlap checks.

Uses locally acquired Experiment 02 transcripts and source titles only.
No model/network calls.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / "source_acquisition" / "output" / "experiment_02"
TRANSCRIPT_SUFFIXES = {".vtt", ".srt", ".txt", ".md"}

WORD_RE = re.compile(r"[A-Za-z0-9']+")


def words(value: Any) -> list[str]:
    return [item.casefold() for item in WORD_RE.findall(str(value or ""))]


def source_documents() -> list[dict[str, str]]:
    docs: list[dict[str, str]] = []
    if not SOURCE_ROOT.exists():
        return docs
    for directory in sorted(path for path in SOURCE_ROOT.iterdir() if path.is_dir()):
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.casefold() in TRANSCRIPT_SUFFIXES:
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                docs.append({
                    "source_id": directory.name,
                    "kind": "transcript",
                    "source": str(path),
                    "text": text,
                })
            elif path.name.endswith(".info.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                title = str(payload.get("title") or "")
                if title:
                    docs.append({
                        "source_id": directory.name,
                        "kind": "title",
                        "source": str(path),
                        "text": title,
                    })
    return docs


def _longest_match(candidate_words: list[str], source_words: list[str], minimum: int) -> tuple[int, int]:
    if len(candidate_words) < minimum or len(source_words) < minimum:
        return (0, -1)
    source_index: dict[tuple[str, ...], list[int]] = {}
    for size in range(min(len(candidate_words), 40), minimum - 1, -1):
        source_index.clear()
        for j in range(0, len(source_words) - size + 1):
            source_index.setdefault(tuple(source_words[j:j + size]), []).append(j)
        for i in range(0, len(candidate_words) - size + 1):
            key = tuple(candidate_words[i:i + size])
            if key in source_index:
                return (size, i)
    return (0, -1)


def check_texts(
    texts: list[dict[str, str]],
    *,
    warn_words: int = 6,
    block_words: int = 10,
) -> dict[str, Any]:
    docs = source_documents()
    matches: list[dict[str, Any]] = []
    for field in texts:
        value = str(field.get("text") or "")
        candidate_words = words(value)
        if len(candidate_words) < warn_words:
            continue
        for doc in docs:
            count, start = _longest_match(candidate_words, words(doc["text"]), warn_words)
            if count < warn_words:
                continue
            phrase = " ".join(candidate_words[start:start + count])
            matches.append({
                "field": str(field.get("field") or ""),
                "source_id": doc["source_id"],
                "source_kind": doc["kind"],
                "word_count": count,
                "overlap_text": phrase,
                "blocking": count >= block_words,
            })
    matches.sort(key=lambda item: (-int(item["word_count"]), item["field"], item["source_id"]))
    return {
        "checked": bool(docs),
        "warning_threshold_words": warn_words,
        "blocking_threshold_words": block_words,
        "blocking": any(item["blocking"] for item in matches),
        "matches": matches[:20],
    }
