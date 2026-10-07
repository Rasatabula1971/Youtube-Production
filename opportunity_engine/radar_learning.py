"""Lane learning for the Viral Radar (D-165).

Every Approve, Save, Watch or Reject the operator makes on a radar
candidate is a label for what the channel wants. This turns those
decisions into a small word model and scores each tracked video by how
much it looks like what the operator picks. It is a ranking aid beside
the word-list lane (D-162), never a gate: nothing is hidden by it, and it
stays quiet until there are enough decisions to mean something.

The model is naive-Bayes style log-odds over title words and the channel:
for each token, log((picked_t + 1) / (picked + 2)) - log((rejected_t + 1)
/ (rejected + 2)), averaged over the tokens of a video and squashed to
-1..1. No model call, no dependency; the operator can read the strongest
words for and against on the page.
"""

from __future__ import annotations

import math
import re
from typing import Any

MIN_DECISIONS = 20
MIN_EACH_SIDE = 5

POSITIVE_STATUSES = {"SAVED", "APPROVED", "WATCHING"}
NEGATIVE_STATUSES = {"REJECTED"}
POSITIVE_ACTIONS = {"APPROVE", "SAVE", "WATCH"}
NEGATIVE_ACTIONS = {"REJECT"}

LIKELY = "LIKELY"
UNSURE = "UNSURE"
UNLIKELY = "UNLIKELY"

# "how", "why" and "what" stay: for an explainer channel they are the signal.
_STOPWORDS = frozenset(
    "a an and are as at be but by for from i if in into is it its of on or so than that the "
    "their then there these they this to was were when where which who will with you your "
    "we our can could does do did has have had not no vs".split()
)
_WORD = re.compile(r"[a-z0-9][a-z0-9'-]{1,}")


def tokens(title: Any, channel_id: Any = None) -> list[str]:
    """Title words (lower-case, no stopwords) plus one token for the channel."""
    words = [w for w in _WORD.findall(str(title or "").lower()) if w not in _STOPWORDS and len(w) >= 3]
    out = sorted(set(words))
    channel = str(channel_id or "").strip()
    if channel:
        out.append("channel:" + channel)
    return out


def label_for(entry: dict[str, Any]) -> int:
    """+1 for a picked candidate, -1 for a rejected one, 0 when undecided."""
    status = str(entry.get("status") or "").upper()
    if status in POSITIVE_STATUSES:
        return 1
    if status in NEGATIVE_STATUSES:
        return -1
    # A decision made through the analyze routes leaves only history.
    for event in reversed(entry.get("history") or []):
        action = str((event or {}).get("action") or "").upper()
        if action in POSITIVE_ACTIONS:
            return 1
        if action in NEGATIVE_ACTIONS:
            return -1
    return 0


def examples(
    inbox_items: dict[str, Any], packets: list[dict[str, Any]]
) -> list[tuple[list[str], int]]:
    """(tokens, label) for every radar packet the operator decided."""
    out: list[tuple[list[str], int]] = []
    for packet in packets:
        opportunity_id = str(packet.get("opportunity_id") or "")
        entry = inbox_items.get(opportunity_id)
        if not isinstance(entry, dict):
            continue
        label = label_for(entry)
        if not label:
            continue
        video = (packet.get("candidate_videos") or [{}])[0] or {}
        toks = tokens(video.get("title") or packet.get("title"), video.get("channel_id"))
        if toks:
            out.append((toks, label))
    return out


class TasteModel:
    """Log-odds word weights learned from the operator's decisions."""

    def __init__(self, data: list[tuple[list[str], int]], *, min_decisions: int = MIN_DECISIONS):
        self.positive = sum(1 for _, label in data if label > 0)
        self.negative = sum(1 for _, label in data if label < 0)
        self.min_decisions = min_decisions
        pos_counts: dict[str, int] = {}
        neg_counts: dict[str, int] = {}
        for toks, label in data:
            target = pos_counts if label > 0 else neg_counts
            for tok in toks:
                target[tok] = target.get(tok, 0) + 1
        self.weights: dict[str, float] = {}
        for tok in set(pos_counts) | set(neg_counts):
            p = math.log((pos_counts.get(tok, 0) + 1) / (self.positive + 2))
            n = math.log((neg_counts.get(tok, 0) + 1) / (self.negative + 2))
            self.weights[tok] = p - n

    @property
    def decisions(self) -> int:
        return self.positive + self.negative

    @property
    def active(self) -> bool:
        return (
            self.decisions >= self.min_decisions
            and self.positive >= MIN_EACH_SIDE
            and self.negative >= MIN_EACH_SIDE
        )

    def score(self, title: Any, channel_id: Any = None) -> float | None:
        """-1..1: above zero looks like what the operator picks."""
        if not self.active:
            return None
        toks = [tok for tok in tokens(title, channel_id) if tok in self.weights]
        if not toks:
            return 0.0
        mean = sum(self.weights[tok] for tok in toks) / len(toks)
        return round(math.tanh(mean), 3)

    def strongest(self, limit: int = 8) -> dict[str, list[str]]:
        """The words that most mark a pick and a reject, for the page."""
        # Ties broken by the word itself, so the page reads the same every time.
        words_for = [
            tok for tok, weight in sorted(self.weights.items(), key=lambda item: (-item[1], item[0]))
            if weight > 0 and not tok.startswith("channel:")
        ]
        words_against = [
            tok for tok, weight in sorted(self.weights.items(), key=lambda item: (item[1], item[0]))
            if weight < 0 and not tok.startswith("channel:")
        ]
        return {"for": words_for[:limit], "against": words_against[:limit]}

    def status(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "decisions": self.decisions,
            "positive": self.positive,
            "negative": self.negative,
            "needed": self.min_decisions,
            "needed_each_side": MIN_EACH_SIDE,
            "strongest": self.strongest() if self.active else {"for": [], "against": []},
        }


def taste_label(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 0.25:
        return LIKELY
    if score <= -0.25:
        return UNLIKELY
    return UNSURE
