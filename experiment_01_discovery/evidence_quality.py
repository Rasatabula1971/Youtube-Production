"""Experiment 01.2 relevance and evidence-quality annotations.

This module never changes raw YouTube measurements. It adds auditable
annotations that help a human decide whether a candidate belongs in the
intended research set and whether its channel-relative breakout signal is
trustworthy enough to use.

No third-party packages required.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any


RELEVANCE_ON_INTENT = "ON_INTENT"
RELEVANCE_ADJACENT = "ADJACENT"
RELEVANCE_OFF_INTENT = "OFF_INTENT"
RELEVANCE_UNREVIEWED = "UNREVIEWED"

RELIABILITY_TRUSTED = "TRUSTED"
RELIABILITY_CAUTION = "CAUTION"
RELIABILITY_UNAVAILABLE = "UNAVAILABLE"


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _contains_term(text: str, term: str) -> bool:
    normalized_term = _normalize(term)
    if not normalized_term:
        return False

    escaped = re.escape(normalized_term)
    if normalized_term[0].isalnum():
        escaped = r"(?<!\w)" + escaped
    if normalized_term[-1].isalnum():
        escaped = escaped + r"(?!\w)"

    return re.search(escaped, text) is not None


def _matching_terms(text: str, terms: Iterable[str]) -> list[str]:
    return [
        term
        for term in terms
        if _contains_term(text, term)
    ]


def classify_relevance(
    title: str,
    profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """Classify title relevance from explicit niche configuration.

    The classifier is intentionally conservative and deterministic:
    exclusion terms win first; strong technical terms qualify as ON_INTENT;
    context-only terms are ADJACENT; otherwise the result is OFF_INTENT.
    """

    if not profile:
        return {
            "relevance": RELEVANCE_UNREVIEWED,
            "relevance_reason": "no_intent_profile",
            "relevance_matches": [],
        }

    text = _normalize(title)

    exclusions = _matching_terms(
        text,
        profile.get("exclude_terms", []),
    )
    if exclusions:
        return {
            "relevance": RELEVANCE_OFF_INTENT,
            "relevance_reason": (
                "excluded_term:" + ",".join(exclusions)
            ),
            "relevance_matches": exclusions,
        }

    strong = _matching_terms(
        text,
        profile.get("strong_terms", []),
    )
    if strong:
        return {
            "relevance": RELEVANCE_ON_INTENT,
            "relevance_reason": (
                "strong_intent_term:" + ",".join(strong)
            ),
            "relevance_matches": strong,
        }

    context = _matching_terms(
        text,
        profile.get("context_terms", []),
    )
    if context:
        return {
            "relevance": RELEVANCE_ADJACENT,
            "relevance_reason": (
                "context_only:" + ",".join(context)
            ),
            "relevance_matches": context,
        }

    return {
        "relevance": RELEVANCE_OFF_INTENT,
        "relevance_reason": "no_configured_niche_signal",
        "relevance_matches": [],
    }


def classify_outlier_reliability(
    *,
    outlier_ratio: float | None,
    baseline_confidence: str,
    baseline_warning: str,
    extreme_ratio_threshold: float = 1000.0,
) -> dict[str, Any]:
    """Annotate reliability without modifying the raw outlier ratio."""

    if outlier_ratio is None:
        return {
            "outlier_reliability": RELIABILITY_UNAVAILABLE,
            "outlier_reliability_reason": "no_baseline_or_ratio",
        }

    reasons: list[str] = []

    if baseline_confidence != "strong_sample":
        reasons.append(
            f"baseline_confidence:{baseline_confidence}"
        )

    if baseline_warning:
        reasons.extend(
            f"baseline_warning:{warning}"
            for warning in baseline_warning.split("|")
            if warning
        )

    if outlier_ratio >= extreme_ratio_threshold:
        reasons.append("extreme_outlier_ratio")

    if reasons:
        return {
            "outlier_reliability": RELIABILITY_CAUTION,
            "outlier_reliability_reason": "|".join(reasons),
        }

    return {
        "outlier_reliability": RELIABILITY_TRUSTED,
        "outlier_reliability_reason": "",
    }


def classify_themes(
    title: str,
    theme_rules: dict[str, list[str]] | None,
) -> list[str]:
    if not theme_rules:
        return []

    text = _normalize(title)
    themes = [
        theme
        for theme, terms in theme_rules.items()
        if _matching_terms(text, terms)
    ]

    return sorted(themes)


def choose_intent_profile(
    niches: list[str],
    niche_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Return the first configured profile for the row's matched niches."""

    for niche_name in niches:
        niche = niche_lookup.get(niche_name, {})
        profile = niche.get("intent_profile")
        if profile:
            return profile
    return None


def annotate_evidence_quality(
    row: dict[str, Any],
    niche_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return an annotation bundle for one Experiment 01 row."""

    profile = choose_intent_profile(
        row.get("niches", []),
        niche_lookup,
    )

    relevance = classify_relevance(
        row.get("title", ""),
        profile,
    )

    reliability = classify_outlier_reliability(
        outlier_ratio=row.get("outlier_ratio"),
        baseline_confidence=row.get(
            "baseline_confidence",
            "no_baseline",
        ),
        baseline_warning=row.get(
            "baseline_warning",
            "",
        ),
    )

    themes: list[str] = []
    if (
        relevance["relevance"]
        not in {
            RELEVANCE_OFF_INTENT,
            RELEVANCE_UNREVIEWED,
        }
    ):
        themes = classify_themes(
            row.get("title", ""),
            (profile or {}).get("theme_rules"),
        )

    return {
        **relevance,
        **reliability,
        "themes": themes,
    }
