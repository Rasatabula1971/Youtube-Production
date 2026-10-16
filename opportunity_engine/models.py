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


# Every lane decides a video's format from its length alone: 180 seconds or
# less is "short". The YouTube Data API does not say whether a video is a
# Short, so "short" here is a length heuristic, never a confirmed Shorts
# classification (M1 criterion 5, D-177). Candidate videos carry
# ``format_basis`` and the UI shows FORMAT_LABELS, never a bare "Short".
SHORT_MAX_SECONDS = 180
FORMAT_BASIS = "duration_heuristic"
# No length was measured (some yt-dlp flat results carry none); the format
# field still says long_form for compatibility, but nothing claims a length.
FORMAT_BASIS_UNKNOWN = "duration_unknown"
FORMAT_LABELS = {
    "short": f"Short (≤ {SHORT_MAX_SECONDS} s, by length)",
    "long_form": f"Long-form (over {SHORT_MAX_SECONDS} s)",
}
FORMAT_UNKNOWN_LABEL = "Format unknown (no length measured)"


def format_basis(duration_seconds: object) -> str:
    """How a format was decided: by a measured length, or not at all."""
    try:
        seconds = float(str(duration_seconds or 0))
    except ValueError:
        return FORMAT_BASIS_UNKNOWN
    return FORMAT_BASIS if seconds > 0 else FORMAT_BASIS_UNKNOWN


def format_label(value: object, basis: object = FORMAT_BASIS) -> str:
    """The UI wording for a format, which names how it was decided."""
    if basis == FORMAT_BASIS_UNKNOWN:
        return FORMAT_UNKNOWN_LABEL
    try:
        return FORMAT_LABELS[normalize_format(value)]
    except ValueError:
        return "Format unknown"


def normalize_format(value: object) -> str:
    """Map a pipeline format label to a packet format, or raise ValueError."""
    key = str(value or "").strip()
    if key not in FORMAT_ALIASES:
        raise ValueError(f"Unknown video format: {value!r}")
    return FORMAT_ALIASES[key]


def format_candidate(value: str) -> str:
    """Map a packet format back to the study-set label Experiment 02 expects."""
    return normalize_format(value) + "_candidate"
