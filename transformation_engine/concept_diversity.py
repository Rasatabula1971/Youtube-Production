"""Deterministic concept similarity, pool sizing and diverse selection (D-130).

Vision §§26–28: transformation produces 15–25 concept candidates; automatic
triage presents five finalists that are genuinely different ideas; it must not
return five versions of the same idea merely because they scored highest. When
fewer than five distinct strong concepts exist, the shortfall is stated rather
than filled with weaker or duplicate ideas.

Similarity is lexical and explainable (no model call): the Jaccard overlap of
the stemmed content words pooled from the fields the vision names — premise,
framing (viewer problem, promise, question), hook, title and payoff. Pooling
matters: a paraphrase moves words between fields and reorders them. Calibrated
on real-shaped concepts: a paraphrased restatement of one idea scored 0.52, a
related but different idea from the same domain 0.16, unrelated ideas
0.03–0.06; the threshold is 0.35. It catches restatements of one idea; it is
not a semantic oracle, which is why the Concept Gate keeps every candidate
reachable.
"""

from __future__ import annotations

import re
from typing import Any, Iterable


STOPWORDS = frozenset(
    """
    a an and are as at be but by can do does for from has have how i if in into
    is it its it's just more most not of on or our so than that the their them
    then there these they this to up us was we what when where which who why
    will with you your yours about after before over under very vs versus
    actually really video videos viewer viewers
    """.split()
)

DEFAULT_NEAR_DUPLICATE_THRESHOLD = 0.35


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_text(item) for item in value)
    return ""


def concept_fields(concept: dict[str, Any]) -> dict[str, str]:
    framing = concept.get("human_framing") if isinstance(concept.get("human_framing"), dict) else {}
    hook = framing.get("hook_experience") if isinstance(framing.get("hook_experience"), dict) else {}
    return {
        "premise": _text(concept.get("premise")),
        "viewer_problem": _text(concept.get("viewer_problem")),
        "audience_promise": _text(concept.get("audience_promise")),
        "viewer_question": _text(framing.get("viewer_question")),
        "hook": _text(hook.get("description")),
        "working_title": _text(concept.get("working_title")),
        "payoff": _text(framing.get("explanation_payoff")),
    }


def _stem(word: str) -> str:
    for suffix in ("ing", "ers", "ies", "ed", "es", "er", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def content_words(text: str) -> set[str]:
    words = (_stem(word) for word in re.findall(r"[a-z0-9]+", text.lower()) if word not in STOPWORDS)
    return {word for word in words if len(word) > 2}


def concept_words(concept: dict[str, Any]) -> set[str]:
    return set().union(*(content_words(value) for value in concept_fields(concept).values()))


def concept_similarity(first: dict[str, Any], second: dict[str, Any]) -> float:
    """Jaccard overlap of the pooled content words of two concepts, 0..1."""
    a, b = concept_words(first), concept_words(second)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def hook_archetype(concept: dict[str, Any]) -> str:
    framing = concept.get("human_framing") if isinstance(concept.get("human_framing"), dict) else {}
    hook = framing.get("hook_experience") if isinstance(framing.get("hook_experience"), dict) else {}
    return str(hook.get("archetype") or "").strip().upper() or "UNSPECIFIED"


def near_duplicate_groups(
    concepts: Iterable[dict[str, Any]],
    *,
    threshold: float = DEFAULT_NEAR_DUPLICATE_THRESHOLD,
) -> list[list[str]]:
    """Groups of concept ids that restate one idea (single-link clusters)."""
    items = [item for item in concepts if isinstance(item, dict) and item.get("concept_id")]
    parent = {str(item["concept_id"]): str(item["concept_id"]) for item in items}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for index, first in enumerate(items):
        for second in items[index + 1 :]:
            if concept_similarity(first, second) >= threshold:
                parent[find(str(first["concept_id"]))] = find(str(second["concept_id"]))
    groups: dict[str, list[str]] = {}
    for key in parent:
        groups.setdefault(find(key), []).append(key)
    return sorted((sorted(group) for group in groups.values() if len(group) > 1), key=lambda g: g[0])


def select_diverse(
    ranked_ids: list[str],
    concepts_by_id: dict[str, dict[str, Any]],
    *,
    limit: int,
    threshold: float = DEFAULT_NEAR_DUPLICATE_THRESHOLD,
    max_per_mechanism: int = 2,
    max_per_archetype: int = 2,
) -> dict[str, Any]:
    """Greedy selection in rank order that never admits a near-duplicate.

    Strict pass: also caps each mechanism and hook archetype so one approach
    cannot fill the list. Relaxed pass: if slots remain, the caps lift, but the
    near-duplicate rule never does. Returns the selection and, for every skipped
    concept, why.
    """
    selected: list[str] = []
    excluded: dict[str, dict[str, Any]] = {}
    mechanism_counts: dict[str, int] = {}
    archetype_counts: dict[str, int] = {}

    def duplicate_of(concept_id: str) -> tuple[str, float] | None:
        concept = concepts_by_id.get(concept_id, {})
        best: tuple[str, float] | None = None
        for chosen in selected:
            similarity = concept_similarity(concept, concepts_by_id.get(chosen, {}))
            if similarity >= threshold and (best is None or similarity > best[1]):
                best = (chosen, similarity)
        return best

    for strict in (True, False):
        for concept_id in ranked_ids:
            if len(selected) >= limit:
                break
            if concept_id in selected or concept_id not in concepts_by_id:
                continue
            if concept_id in excluded and excluded[concept_id]["reason"] == "NEAR_DUPLICATE":
                continue
            duplicate = duplicate_of(concept_id)
            if duplicate is not None:
                excluded[concept_id] = {
                    "reason": "NEAR_DUPLICATE",
                    "duplicate_of": duplicate[0],
                    "similarity": round(duplicate[1], 3),
                }
                continue
            concept = concepts_by_id[concept_id]
            mechanism = str(concept.get("mechanism_id") or "")
            archetype = hook_archetype(concept)
            if strict and (
                mechanism_counts.get(mechanism, 0) >= max_per_mechanism
                or archetype_counts.get(archetype, 0) >= max_per_archetype
            ):
                excluded[concept_id] = {"reason": "APPROACH_ALREADY_REPRESENTED"}
                continue
            selected.append(concept_id)
            excluded.pop(concept_id, None)
            mechanism_counts[mechanism] = mechanism_counts.get(mechanism, 0) + 1
            archetype_counts[archetype] = archetype_counts.get(archetype, 0) + 1

    for concept_id in ranked_ids:
        if concept_id not in selected and concept_id not in excluded and len(selected) >= limit:
            excluded[concept_id] = {"reason": "BELOW_SELECTION_CUTOFF"}
    return {"selected": selected, "excluded": excluded}


def allocate_concept_counts(
    mechanism_ids: list[str],
    *,
    pool_minimum: int,
    pool_maximum: int,
    per_request_minimum: int,
    per_request_maximum: int,
    preferred_per_request: int = 5,
) -> dict[str, int]:
    """Concepts to request per mechanism so the pool lands in [minimum, maximum].

    The established ``preferred_per_request`` per mechanism, clamped into the
    15–25 pool and spread evenly (earlier mechanisms take the remainder). One
    request never asks for more than ``per_request_maximum`` (free models fail
    on oversized structured output), so a single mechanism still falls short
    of the minimum; the merge then reports the shortfall.
    """
    count = len(mechanism_ids)
    if count == 0:
        return {}
    target = min(pool_maximum, max(pool_minimum, count * preferred_per_request))
    base, remainder = divmod(target, count)
    allocation = {}
    for index, mechanism_id in enumerate(mechanism_ids):
        wanted = base + (1 if index < remainder else 0)
        allocation[mechanism_id] = max(per_request_minimum, min(per_request_maximum, wanted))
    return allocation


def pool_assessment(count: int, *, pool_minimum: int, pool_maximum: int) -> dict[str, Any]:
    if count < pool_minimum:
        note = (
            f"The pool has {count} valid concepts, below the {pool_minimum}–{pool_maximum} "
            "target. Triage still picks only distinct strong concepts; it never fills slots."
        )
    elif count > pool_maximum:
        note = f"The pool has {count} valid concepts, above the {pool_maximum} target."
    else:
        note = f"The pool has {count} valid concepts, within the {pool_minimum}–{pool_maximum} target."
    return {
        "count": count,
        "target_minimum": pool_minimum,
        "target_maximum": pool_maximum,
        "within_target": pool_minimum <= count <= pool_maximum,
        "note": note,
    }
