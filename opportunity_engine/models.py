"""Shared vocabulary for canonical Opportunity Packets (spec v2.1, slice O1).

Every value here is an evidence label, not a score. Labels that describe
different questions stay in different fields so no single label can act as a
hidden composite score.
"""

from __future__ import annotations

SCHEMA_VERSION = 1

SOURCE_HISTORICAL = "HISTORICAL"
SOURCE_HUMAN_TOPIC = "HUMAN_TOPIC"
SOURCE_HUMAN_VIDEO = "HUMAN_VIDEO"
SOURCE_VIRAL_RADAR = "VIRAL_RADAR"
SOURCE_TYPES = (
    SOURCE_HISTORICAL,
    SOURCE_HUMAN_TOPIC,
    SOURCE_HUMAN_VIDEO,
    SOURCE_VIRAL_RADAR,
)

# Levels each evidence dimension may take. UNASSESSED / HYPOTHESIS are the
# only levels that may be stored without a written rule.
EVIDENCE_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "historical_demand": ("STRONG", "MODERATE", "WEAK", "UNASSESSED"),
    "current_breakout": ("STRONG", "MODERATE", "WEAK", "NONE", "UNASSESSED"),
    "cross_channel_replication": ("STRONG", "MODERATE", "LOW", "NONE", "UNASSESSED"),
    "viewer_need": ("STRONG", "MODERATE", "WEAK", "HYPOTHESIS"),
    "mechanism_evidence": ("STRONG", "MODERATE", "WEAK", "HYPOTHESIS"),
    "content_gap": ("EVIDENCED", "PLAUSIBLE", "HYPOTHESIS"),
}
RULE_FREE_LEVELS = frozenset({"UNASSESSED", "HYPOTHESIS"})

# Viral classification is four independent axes, never one label (v2.1 §R5).
BREAKOUT_AXES: dict[str, tuple[str, ...]] = {
    "strength": (
        "NORMAL",
        "EARLY_SIGNAL",
        "BREAKOUT_CANDIDATE",
        "BREAKOUT",
        "INSUFFICIENT_EVIDENCE",
    ),
    "trajectory": (
        "ACCELERATING",
        "STABLE_HIGH",
        "DECELERATING",
        "FLAT",
        "INSUFFICIENT_SNAPSHOTS",
    ),
    "breadth": ("REPLICATED", "ONE_OFF", "UNASSESSED"),
    "historical_alignment": ("ESTABLISHED_DEMAND", "NO_HISTORY", "UNASSESSED"),
}

# Channel routing for every opportunity (v2.1 §R10).
ROUTE_ACTIVE = "ACTIVE_CHANNEL"
ROUTE_FUTURE = "FUTURE_CHANNEL"
ROUTE_EXCLUDED = "EXCLUDED"
ROUTE_UNSCOPED = "UNSCOPED"
ROUTES = (ROUTE_ACTIVE, ROUTE_FUTURE, ROUTE_EXCLUDED, ROUTE_UNSCOPED)

# Human Opportunity Gate decisions (v2.1 §R11). WATCH is viral-lane only.
DECISIONS = ("PENDING", "APPROVE", "REWORK", "WATCH", "SAVE", "REJECT")
WATCH_SOURCES = frozenset({SOURCE_VIRAL_RADAR})

FORMATS = ("long_form", "short")

# Experiment 01.3 labels formats by a duration heuristic ("*_candidate"); the
# packet contract stores the plain format name.
FORMAT_ALIASES = {
    "long_form": "long_form",
    "long_form_candidate": "long_form",
    "short": "short",
    "short_candidate": "short",
}


def normalize_format(value: object) -> str:
    """Map a pipeline format label to a packet format, or raise ValueError."""
    key = str(value or "").strip()
    if key not in FORMAT_ALIASES:
        raise ValueError(f"Unknown video format: {value!r}")
    return FORMAT_ALIASES[key]


def format_candidate(value: str) -> str:
    """Map a packet format back to the study-set label Experiment 02 expects."""
    return normalize_format(value) + "_candidate"
