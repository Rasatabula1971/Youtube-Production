"""Theme clustering and replication for radar breakouts (spec v2.1 slice O10).

Breakout videos are grouped by the words their titles share, then each group
is checked for independence: different channels, with re-uploads and clip
copies (near-identical title and duration on another channel) not counted.

Each cluster is labelled by what its members share. These are not equivalent
(spec 17):

    SAME_EVENT            one news event: weak evidence of durable demand
    SAME_VIEWER_QUESTION  the same question asked by several channels
    SAME_MECHANISM        the same hidden mechanism explained
    SAME_TOPIC            the same subject, nothing more specific

The clustering is deterministic and labelled as such, so it can later be
replaced by AI theme clustering behind the same output.
"""

from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from typing import Any

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your", "you",
    "its", "they", "them", "their", "than", "then", "there", "about", "over",
    "under", "just", "really", "actually", "video", "shorts", "short", "new",
    "every", "most", "more", "very", "here", "will", "have", "has", "had",
    "was", "were", "not", "but", "all", "out", "one", "two", "get", "got",
    "why", "how", "what", "when", "can", "does", "is", "are", "explained",
}


def keywords(title: str) -> set[str]:
    words = set()
    for word in re.findall(r"[a-z0-9]+", str(title or "").lower()):
        if (len(word) >= 3 or any(ch.isdigit() for ch in word)) and word not in STOPWORDS:
            words.add(word[:-1] if len(word) > 4 and word.endswith("s") else word)
    return words


def _similar_title(a: str, b: str) -> float:
    return SequenceMatcher(None, str(a or "").lower(), str(b or "").lower()).ratio()


def _kind(titles: list[str], settings: dict[str, Any]) -> str:
    terms = settings["kind_terms"]
    padded = [" " + re.sub(r"[^a-z0-9 ]+", " ", title.lower()) + " " for title in titles]
    count = len(titles) or 1

    def share(kind: str) -> float:
        return sum(1 for title in padded if any(f" {term} " in title for term in terms[kind])) / count

    # Event-bound wins whenever most members are about one event: it is the
    # weakest evidence and must never be mistaken for durable demand.
    for kind in ("SAME_EVENT", "SAME_VIEWER_QUESTION", "SAME_MECHANISM"):
        if share(kind) >= 0.5:
            return kind
    return "SAME_TOPIC"


def _independent(members: list[dict[str, Any]], settings: dict[str, Any]) -> list[dict[str, Any]]:
    """One member per channel, and no re-uploads of another member."""
    kept: list[dict[str, Any]] = []
    for member in sorted(members, key=lambda m: str(m.get("published_at") or "")):
        if any(k["channel_id"] == member["channel_id"] for k in kept):
            member["independence"] = "SAME_CHANNEL"
            continue
        duplicate = None
        for other in kept:
            longest = max(int(other.get("duration_seconds") or 0), int(member.get("duration_seconds") or 0), 1)
            close_duration = (
                abs(int(other.get("duration_seconds") or 0) - int(member.get("duration_seconds") or 0)) / longest
                <= float(settings["reupload_duration_tolerance"])
            )
            if close_duration and _similar_title(other["title"], member["title"]) >= float(
                settings["reupload_title_similarity"]
            ):
                duplicate = other
                break
        if duplicate:
            member["independence"] = f"REUPLOAD_OF:{duplicate['video_id']}"
            continue
        member["independence"] = "INDEPENDENT"
        kept.append(member)
    return kept


def cluster(records: dict[str, dict[str, Any]], settings: dict[str, Any]) -> list[dict[str, Any]]:
    """Greedy single-pass clustering of tracked breakout records."""
    members: list[dict[str, Any]] = []
    for video_id, record in records.items():
        if record.get("strength") not in settings["member_strengths"]:
            continue
        video = record.get("video") or {}
        members.append(
            {
                "video_id": video_id,
                "title": str(video.get("title") or ""),
                "channel_id": str(video.get("channel_id") or ""),
                "channel_title": video.get("channel_title"),
                "published_at": video.get("published_at"),
                "duration_seconds": video.get("duration_seconds"),
                "strength": record.get("strength"),
                "lifetime_ratio": (record.get("metrics") or {}).get("lifetime_ratio"),
                "keywords": keywords(str(video.get("title") or "")),
            }
        )
    members.sort(key=lambda m: -float(m.get("lifetime_ratio") or 0))

    groups: list[dict[str, Any]] = []
    for member in members:
        best, best_score = None, 0.0
        for group in groups:
            shared = member["keywords"] & group["keywords"]
            union = member["keywords"] | group["keywords"]
            score = len(shared) / len(union) if union else 0.0
            if len(shared) >= int(settings["min_shared_keywords"]) and score >= float(settings["min_jaccard"]) and score > best_score:
                best, best_score = group, score
        if best is None:
            groups.append({"keywords": set(member["keywords"]), "core": set(member["keywords"]), "members": [member]})
        else:
            best["members"].append(member)
            best["core"] &= member["keywords"]
            best["keywords"] |= member["keywords"]

    clusters: list[dict[str, Any]] = []
    for group in groups:
        independent = _independent(group["members"], settings)
        shared = sorted(group["core"]) or sorted(group["keywords"])[:3]
        signature = "|".join(sorted(m["video_id"] for m in group["members"]))
        cluster_id = "cl_" + hashlib.sha256(signature.encode("utf-8")).hexdigest()[:12]
        kind = _kind([m["title"] for m in independent], settings)
        channels = len(independent)
        if channels >= int(settings["replicated_min_independent_channels"]):
            breadth = "REPLICATED"
            if kind == "SAME_EVENT":
                rule = "CL-EVENT-BOUND"
            elif channels >= int(settings["strong_min_independent_channels"]):
                rule = "CL-REPLICATED-STRONG"
            else:
                rule = "CL-REPLICATED"
        else:
            breadth = "ONE_OFF"
            rule = "CL-PAIR" if channels == 2 else "CL-ONE-OFF"
        clusters.append(
            {
                "cluster_id": cluster_id,
                "label": " ".join(shared[:4]) or group["members"][0]["title"][:40],
                "shared_keywords": shared,
                "kind": kind,
                "breadth": breadth,
                "replication_rule_id": rule,
                "independent_channel_count": channels,
                "member_count": len(group["members"]),
                "members": [
                    {k: v for k, v in m.items() if k != "keywords"} for m in group["members"]
                ],
                "method": "deterministic_title_keywords",
            }
        )
    clusters.sort(key=lambda c: (-int(c["independent_channel_count"]), str(c["cluster_id"])))
    return clusters
