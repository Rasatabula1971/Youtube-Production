"""Is a concept about the topic the owner approved? (Two Lanes, D-188.)

The concept engine transfers a mechanism from the study videos, and some
transfers leave the topic: on Aviation Tires, 3 of the 10 finalists were bike
helmets, EV batteries and carbon frames. An automatic pick, and the concepts
shown first, must be about the approved topic.

The topic is read from the approved study set: its topic slug (``tyres_tires``)
or, for a video or question the owner submitted, the seed topic. Only when
neither names a topic do the study titles stand in. A concept is on topic when
its title or premise uses one of the topic's words. With no topic words at all
nothing is on topic, so nothing is picked automatically and a person decides.
"""

from __future__ import annotations

import re
from typing import Any

# Topic slugs that name where a study set came from, not what it is about.
SOURCE_SLUGS = {"human_video", "human_topic", "viral_radar", "viral_cluster", "other"}
STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "your", "you", "are",
    "why", "how", "what", "when", "who", "does", "dont", "don", "its", "after", "before",
    "look", "like", "explained", "explain", "shorts", "short", "video", "videos", "most",
    "really", "actually", "vs", "about", "than", "they", "them", "their", "has", "have",
    "just", "will", "can", "all", "out", "get", "new", "one", "inside", "secret", "truth",
}
# One spelling per word, so British and American spellings match.
SPELLINGS = {"tyre": "tire", "colour": "color", "aluminium": "aluminum", "aeroplane": "airplane"}
CONCEPT_FIELDS = ("working_title", "premise")


def _stem(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        word = word[:-3] + "y"
    elif word.endswith(("ches", "shes", "xes", "sses")):
        word = word[:-2]
    elif word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        word = word[:-1]
    return SPELLINGS.get(word, word)


def words(text: Any) -> set[str]:
    found = re.findall(r"[a-z0-9]+", str(text or "").lower())
    return {_stem(word) for word in found if len(word) >= 3 and word not in STOPWORDS}


def _context(row: dict[str, Any]) -> dict[str, Any]:
    context = row.get("opportunity_context")
    return context if isinstance(context, dict) else {}


def topic_terms(study_rows: Any) -> dict[str, Any]:
    """The words that say what the approved topic is, and where they came from."""
    rows = [row for row in study_rows if isinstance(row, dict)] if isinstance(study_rows, list) else []
    terms: set[str] = set()
    basis: list[str] = []
    for row in rows:
        slug = str(row.get("topic") or "").strip().lower()
        if slug and slug not in SOURCE_SLUGS:
            terms |= words(slug.replace("_", " "))
            basis.append(f"topic {slug}")
        context = _context(row)
        seed = str(context.get("seed_topic") or "").strip()
        if seed:
            terms |= words(seed)
            basis.append(f"seed topic {seed!r}")
    if not terms:
        for row in rows:
            context = _context(row)
            for text in (context.get("opportunity_title"), context.get("seed_question"), row.get("title")):
                if str(text or "").strip():
                    terms |= words(text)
                    basis.append(f"title {str(text)[:60]!r}")
    return {"terms": sorted(terms), "basis": list(dict.fromkeys(basis))}


def on_topic(concept: dict[str, Any], terms: Any) -> dict[str, Any]:
    """Whether the concept's title or premise uses a topic word, and which ones."""
    wanted = set(terms or [])
    text = " ".join(str(concept.get(field) or "") for field in CONCEPT_FIELDS)
    matched = sorted(words(text) & wanted)
    return {"on_topic": bool(matched), "matched": matched}
