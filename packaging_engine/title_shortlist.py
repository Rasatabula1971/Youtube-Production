"""A 2–3 title shortlist per video from the validated pair matrix (D-134).

Vision: five Short and five long-form titles are generated, and the human is
shown a shortlist of two or three. The Slice 26 matrix already validates every
title against every thumbnail concept; this module reads those validations and
ranks each title deterministically and explainably. No model call is made, and
no viral score or click-through prediction is produced:

  1. the title direction the human chose at the Title Direction Gate leads;
  2. then titles with more PASS pairs (they work with more thumbnails);
  3. then the mean of the title-quality diagnostics over their PASS pairs
     (title_strength, clarity, credibility, promise_alignment);
  4. then title_id, so ties are stable.

A title with no PASS pair is not eligible. A title that restates a shortlisted
one (content-word overlap at or above the threshold) never takes a place. When
fewer than the minimum qualify the shortfall is stated, not filled. Every
other title stays reachable at the Final Packaging Gate.
"""

from __future__ import annotations

import re
from typing import Any

TITLE_QUALITY_DIAGNOSTICS = ("title_strength", "clarity", "credibility", "promise_alignment")
DEFAULT_SHORTLIST = {"target": 3, "minimum": 2, "near_duplicate_threshold": 0.5}

STOPWORDS = frozenset(
    """
    a an and are as at be but by can do does for from has have how if in into
    is it its it's of on or so than that the their them then there these they
    this to up was what when where which who why will with you your
    """.split()
)


def shortlist_settings(config: dict[str, Any] | None) -> dict[str, Any]:
    settings = dict(DEFAULT_SHORTLIST)
    supplied = (config or {}).get("title_shortlist")
    if isinstance(supplied, dict):
        settings.update(supplied)
    return settings


def title_words(text: Any) -> set[str]:
    words = re.findall(r"[a-z0-9]+", str(text or "").lower())
    return {word for word in words if word not in STOPWORDS and len(word) > 2}


def title_similarity(first: Any, second: Any) -> float:
    a, b = title_words(first), title_words(second)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def title_rows(packages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per title with the evidence its rank is built from."""
    rows: dict[str, dict[str, Any]] = {}
    for package in packages:
        title_id = str(package.get("title_id") or "")
        if not title_id:
            continue
        row = rows.setdefault(
            title_id,
            {
                "title_id": title_id,
                "title_text": package.get("title_text"),
                "selected_direction": False,
                "pairs": 0,
                "pass_pairs": 0,
                "_scores": [],
            },
        )
        row["pairs"] += 1
        row["selected_direction"] = row["selected_direction"] or bool(
            package.get("selected_title_direction_match")
        )
        if str(package.get("validation_status") or "") == "PASS":
            row["pass_pairs"] += 1
            raw = package.get("diagnostics")
            diagnostics: dict[str, Any] = raw if isinstance(raw, dict) else {}
            values = [
                diagnostics[key]
                for key in TITLE_QUALITY_DIAGNOSTICS
                if isinstance(diagnostics.get(key), (int, float))
            ]
            if values:
                row["_scores"].append(sum(values) / len(values))
    for row in rows.values():
        scores = row.pop("_scores")
        row["title_quality"] = round(sum(scores) / len(scores), 2) if scores else None
    return sorted(rows.values(), key=_rank_key)


def _rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        not row["selected_direction"],
        -row["pass_pairs"],
        -(row["title_quality"] or 0.0),
        row["title_id"],
    )


def _reason(row: dict[str, Any]) -> str:
    parts = []
    if row["selected_direction"]:
        parts.append("your chosen title direction")
    parts.append(f"passes with {row['pass_pairs']} of {row['pairs']} thumbnails")
    if row["title_quality"] is not None:
        parts.append(f"title quality {row['title_quality']}/5")
    return "; ".join(parts) + "."


def build_shortlist(packages: list[dict[str, Any]], settings: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = settings or dict(DEFAULT_SHORTLIST)
    target = int(settings.get("target", 3))
    minimum = int(settings.get("minimum", 2))
    threshold = float(settings.get("near_duplicate_threshold", 0.5))

    entries: list[dict[str, Any]] = []
    excluded: dict[str, dict[str, Any]] = {}
    for row in title_rows(packages):
        if row["pass_pairs"] == 0:
            excluded[row["title_id"]] = {"reason": "NO_PASSING_PAIR", **row}
            continue
        duplicate = next(
            (
                entry["title_id"]
                for entry in entries
                if title_similarity(entry["title_text"], row["title_text"]) >= threshold
            ),
            None,
        )
        if duplicate:
            excluded[row["title_id"]] = {"reason": "NEAR_DUPLICATE", "duplicate_of": duplicate, **row}
            continue
        if len(entries) >= target:
            excluded[row["title_id"]] = {"reason": "BELOW_SHORTLIST_CUTOFF", **row}
            continue
        entries.append({**row, "rank": len(entries) + 1, "reason": _reason(row)})

    shortfall = max(0, minimum - len(entries))
    if shortfall:
        note = (
            f"Only {len(entries)} title(s) have a passing pair; the shortlist needs "
            f"{minimum}. Rework the title directions, or accept from all titles."
        )
    else:
        note = f"{len(entries)} distinct titles shortlisted from {len(entries) + len(excluded)}."
    return {
        "title_ids": [entry["title_id"] for entry in entries],
        "entries": entries,
        "excluded": excluded,
        "target": target,
        "minimum": minimum,
        "shortfall": shortfall,
        "note": note,
    }
