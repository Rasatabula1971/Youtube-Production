"""Conditional research review: which claims need a human (D-131).

Vision §32 (locked decision): research does not need mandatory human approval
on every video. A claim may progress automatically when the evidence is
strong, the sources are sufficiently reliable, there is no meaningful
conflict and the claim is not high-risk. Human review is required when
evidence conflicts or is weak, the wording requires care, important claims
remain uncertain, or risk is elevated.

Every claim reaching this policy has already passed quote verification: each
evidence quote was found verbatim in its acquired page (research_model_runner).
The policy adds deterministic, inspectable checks on top and classifies:

  AUTO_CLEARED     accepted automatically, with the reasons recorded
  REVIEW_REQUIRED  shown at the Research Gate with the reasons it needs you
  BLOCKED          cannot be accepted at all (no traceable support); shown so
                   it can be reworked or rejected

It deliberately errs towards review: a wrong automatic clearance costs more
than one extra human decision.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urlparse

AUTO_CLEARED = "AUTO_CLEARED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
BLOCKED = "BLOCKED"

DEFAULT_POLICY: dict[str, Any] = {
    "enabled": True,
    "minimum_independent_supporting_hosts": 2,
    "auto_clear_source_types": ["primary", "secondary", "dataset", "documentation"],
    "absolute_terms": [
        "always", "never", "all", "none", "every", "only", "first", "last",
        "biggest", "largest", "smallest", "fastest", "slowest", "highest",
        "lowest", "deadliest", "safest", "most", "least", "guaranteed",
        "guarantees", "proven", "proves", "impossible", "certainly", "definitely",
        "entirely", "completely", "exactly",
    ],
    "risk_terms": [
        "health", "medical", "medicine", "disease", "cancer", "drug", "drugs",
        "dose", "dosage", "symptom", "symptoms", "treatment", "cure", "cures",
        "vaccine", "diet", "pregnan*", "toxic", "poison", "poisonous", "fatal",
        "lethal", "death", "deaths", "die", "dies", "killed", "kill", "injury",
        "injuries", "dangerous", "unsafe", "illegal", "lawsuit", "legal",
        "legally", "invest", "investing", "investor", "investors", "investment",
        "profit", "returns",
    ],
}
# Risk terms match whole words; a term ending in "*" matches as a stem
# ("pregnan*" matches "pregnancy"). Plain prefix matching flagged "diesel"
# (die) and "investigations" (invest) as elevated-risk wording.


def policy_settings(config: dict[str, Any] | None) -> dict[str, Any]:
    settings = dict(DEFAULT_POLICY)
    supplied = (config or {}).get("evidence_policy")
    if isinstance(supplied, dict):
        settings.update(supplied)
    return settings


def policy_fingerprint(settings: dict[str, Any]) -> str:
    payload = json.dumps(settings, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _host(url: Any) -> str:
    try:
        host = urlparse(str(url or "")).hostname or ""
    except ValueError:
        return ""
    return host.lower().removeprefix("www.")


def _words(text: Any) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", str(text or "").lower())


def _numbers(text: Any) -> set[str]:
    return {
        value.replace(",", "").rstrip(".")
        for value in re.findall(r"\d[\d,]*(?:\.\d+)?", str(text or ""))
    }


def _normalised(text: Any) -> str:
    return " ".join(_words(text))


def _independent_works(supporting: list[dict[str, Any]]) -> list[str]:
    """Supporting sources grouped into independent works.

    Two links are the same work when they share a website, a title or the
    quoted text: one paper mirrored on two sites (a library copy and its DOI
    page) is still one source.
    """
    groups: list[dict[str, set[str]]] = []
    for link in supporting:
        source = link.get("source") or {}
        keys = {
            "host": {_host(source.get("url"))} - {""},
            # Short titles ("Home", "PDF") say nothing about the work.
            "title": {t for t in {_normalised(source.get("title"))} if len(t.split()) >= 4},
            "quote": {_normalised(link.get("evidence_quote"))} - {""},
        }
        if not keys["host"]:
            continue
        matching = [g for g in groups if any(g[k] & keys[k] for k in keys)]
        merged = {k: set().union(keys[k], *(g[k] for g in matching)) for k in keys}
        groups = [g for g in groups if g not in matching] + [merged]
    return [sorted(g["host"])[0] for g in groups]


def evaluate_claim(item: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    """Classify one Research Gate item (claim with its evidence and sources)."""
    evidence = [link for link in item.get("evidence", []) if isinstance(link, dict)]
    raw_coverage = item.get("coverage")
    coverage: dict[str, Any] = raw_coverage if isinstance(raw_coverage, dict) else {}
    statement = str(item.get("statement") or "")

    traceable = [
        link
        for link in evidence
        if isinstance(link.get("source"), dict)
        and str(link.get("evidence_quote") or "").strip()
        and str(link.get("stance") or "").upper() in {"SUPPORTS", "QUALIFIES"}
    ]
    supporting = [link for link in traceable if str(link.get("stance") or "").upper() == "SUPPORTS"]
    if not supporting:
        return {
            "classification": BLOCKED,
            "reasons": ["No traceable supporting source with a verified quote; it cannot be used as fact."],
        }

    reasons: list[str] = []
    state = str(coverage.get("state") or "")
    if state == "CONFLICTED" or any(str(link.get("stance") or "").upper() == "CONTRADICTS" for link in evidence):
        reasons.append("A cited source contradicts this claim (conflicting evidence).")
    if any(str(link.get("stance") or "").upper() == "QUALIFIES" for link in evidence):
        reasons.append("A cited source qualifies this claim, so its wording needs care.")

    hosts = _independent_works(supporting)
    minimum_hosts = int(settings.get("minimum_independent_supporting_hosts", 2))
    if len(hosts) < minimum_hosts:
        reasons.append(
            f"Weak evidence: supported by {len(hosts)} independent website(s); "
            f"{minimum_hosts} are needed to clear automatically."
        )

    allowed_types = {str(value).lower() for value in settings.get("auto_clear_source_types", [])}
    unreliable = sorted(
        {
            str((link.get("source") or {}).get("source_type") or "unknown").lower()
            for link in supporting
        }
        - allowed_types
    )
    if unreliable:
        reasons.append("Source reliability needs a check: " + ", ".join(unreliable) + " source(s).")

    words = set(_words(statement))
    absolute = sorted(words & {str(term).lower() for term in settings.get("absolute_terms", [])})
    if absolute:
        reasons.append("Absolute wording needs care: " + ", ".join(absolute) + ".")

    quoted_numbers = set().union(*(_numbers(link.get("evidence_quote")) for link in supporting))
    unquoted = sorted(_numbers(statement) - quoted_numbers)
    if unquoted:
        reasons.append(
            "A figure in the wording is not in any quoted evidence: " + ", ".join(unquoted) + "."
        )

    risky = sorted(
        {
            term.rstrip("*")
            for term in (str(value).lower() for value in settings.get("risk_terms", []))
            if any(
                word.startswith(term[:-1]) if term.endswith("*") else word == term
                for word in words
            )
        }
    )
    if risky:
        reasons.append("Elevated risk (" + ", ".join(risky) + "): a human must confirm the wording.")

    if reasons:
        return {"classification": REVIEW_REQUIRED, "reasons": reasons}
    return {
        "classification": AUTO_CLEARED,
        "reasons": [
            f"Supported by {len(hosts)} independent websites with verified quotes.",
            "No contradicting or qualifying source.",
            "Plain wording with no absolute terms, unquoted figures or elevated risk.",
        ],
    }
