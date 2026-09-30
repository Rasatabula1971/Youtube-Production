"""Human-first framing contract for Transformation Engine concepts.

This module keeps engagement framing structured and deterministic enough to
validate without pretending to predict views or retention.
"""

from __future__ import annotations

from typing import Any

DRAMA_FLOOR = 4
DRAMA_CENTER = 5
DRAMA_MAX = 10
MAX_UNUSED_DRAMA_CAPACITY = 3

HOOK_ARCHETYPES = (
    "FAILURE_CONSEQUENCE",
    "EXPECTATION_VIOLATION",
    "CONTRADICTION",
    "TRANSFORMATION",
    "BEFORE_AFTER",
    "HIDDEN_CAUSE",
    "PREDICTION",
    "DECISION_PRESSURE",
    "MISTAKE_MYTH",
    "SCALE",
    "DEMONSTRATION",
    "MYSTERY",
    "LOSS_COST",
    "PERSONAL_STAKES",
)

PULL_TYPES = (
    "CURIOSITY",
    "EXPECTATION_VIOLATION",
    "DANGER",
    "LOSS",
    "PERSONAL_STAKES",
    "CONTRADICTION",
    "TRANSFORMATION",
    "UNCERTAINTY",
    "PREDICTION",
    "MYSTERY",
    "SCALE",
    "COMPETITION",
    "CONSEQUENCE",
    "URGENCY",
    "HIDDEN_MECHANISM",
    "DECISION_TENSION",
)


def generation_contract() -> dict[str, Any]:
    return {
        "drama_floor": DRAMA_FLOOR,
        "drama_center": DRAMA_CENTER,
        "drama_max": DRAMA_MAX,
        "normal_working_range": [DRAMA_FLOOR, 8],
        "extreme_range": [9, 10],
        "max_unused_drama_capacity": MAX_UNUSED_DRAMA_CAPACITY,
        "rules": [
            "Never deliberately frame a normal concept at drama level 1, 2, or 3.",
            "Start around drama 5, then raise intensity where the real opportunity supports stronger stakes, consequence, contrast, surprise, failure, transformation, or scale.",
            "Drama must come from a truthful property of the opportunity; do not manufacture catastrophe, certainty, or danger.",
            "Do not flatten a naturally dramatic opportunity into a textbook topic.",
            "Use a drama pulse with rises and releases rather than one constant level.",
            "A lower drama beat is breathing room, not permission to become boring.",
            "Tempo is separate from drama: a slow-motion moment can be high drama.",
            "Use 9-10 only when the real subject genuinely supports extreme stakes or spectacle.",
        ],
    }


def response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "hook_experience",
            "viewer_question",
            "psychological_pull",
            "explanation_payoff",
            "visual_opening_plan",
            "drama",
        ],
        "properties": {
            "hook_experience": {
                "type": "object",
                "additionalProperties": False,
                "required": ["archetype", "description"],
                "properties": {
                    "archetype": {
                        "type": "string",
                        "enum": list(HOOK_ARCHETYPES),
                    },
                    "description": {"type": "string", "minLength": 1},
                },
            },
            "viewer_question": {"type": "string", "minLength": 1},
            "psychological_pull": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "primary_pull",
                    "viewer_expectation",
                    "violation_or_tension",
                    "stakes",
                    "information_gap",
                    "desired_resolution",
                ],
                "properties": {
                    "primary_pull": {
                        "type": "string",
                        "enum": list(PULL_TYPES),
                    },
                    "viewer_expectation": {"type": "string", "minLength": 1},
                    "violation_or_tension": {"type": "string", "minLength": 1},
                    "stakes": {"type": "string", "minLength": 1},
                    "information_gap": {"type": "string", "minLength": 1},
                    "desired_resolution": {"type": "string", "minLength": 1},
                },
            },
            "explanation_payoff": {"type": "string", "minLength": 1},
            "visual_opening_plan": {
                "type": "object",
                "additionalProperties": False,
                "required": ["moments", "opening_narration_intent"],
                "properties": {
                    "moments": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 5,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["visual", "purpose"],
                            "properties": {
                                "visual": {"type": "string", "minLength": 1},
                                "purpose": {"type": "string", "minLength": 1},
                            },
                        },
                    },
                    "opening_narration_intent": {
                        "type": "string",
                        "minLength": 1,
                    },
                },
            },
            "drama": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "capacity",
                    "target",
                    "source",
                    "constraint",
                    "hook_level",
                    "story_curve",
                    "tempo_curve",
                ],
                "properties": {
                    "capacity": {
                        "type": "integer",
                        "minimum": DRAMA_FLOOR,
                        "maximum": DRAMA_MAX,
                    },
                    "target": {
                        "type": "integer",
                        "minimum": DRAMA_FLOOR,
                        "maximum": DRAMA_MAX,
                    },
                    "source": {"type": "string", "minLength": 1},
                    "constraint": {"type": "string", "minLength": 1},
                    "hook_level": {
                        "type": "integer",
                        "minimum": DRAMA_FLOOR,
                        "maximum": DRAMA_MAX,
                    },
                    "story_curve": {
                        "type": "array",
                        "minItems": 4,
                        "maxItems": 8,
                        "items": {
                            "type": "integer",
                            "minimum": DRAMA_FLOOR,
                            "maximum": DRAMA_MAX,
                        },
                    },
                    "tempo_curve": {
                        "type": "array",
                        "minItems": 4,
                        "maxItems": 8,
                        "items": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                        },
                    },
                },
            },
        },
    }


def _nonempty(value: Any) -> bool:
    return bool(str(value or "").strip())


def _valid_level(value: Any, *, minimum: int) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and minimum <= value <= DRAMA_MAX
    )


def validate(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["human_framing must be an object"]

    hook = payload.get("hook_experience")
    if not isinstance(hook, dict):
        errors.append("human_framing.hook_experience must be an object")
    else:
        if str(hook.get("archetype", "")).strip().upper() not in HOOK_ARCHETYPES:
            errors.append(
                "human_framing.hook_experience.archetype must be a supported archetype"
            )
        if not _nonempty(hook.get("description")):
            errors.append("human_framing.hook_experience.description is required")

    if not _nonempty(payload.get("viewer_question")):
        errors.append("human_framing.viewer_question is required")

    pull = payload.get("psychological_pull")
    if not isinstance(pull, dict):
        errors.append("human_framing.psychological_pull must be an object")
    else:
        if str(pull.get("primary_pull", "")).strip().upper() not in PULL_TYPES:
            errors.append(
                "human_framing.psychological_pull.primary_pull must be supported"
            )
        for key in (
            "viewer_expectation",
            "violation_or_tension",
            "stakes",
            "information_gap",
            "desired_resolution",
        ):
            if not _nonempty(pull.get(key)):
                errors.append(f"human_framing.psychological_pull.{key} is required")

    if not _nonempty(payload.get("explanation_payoff")):
        errors.append("human_framing.explanation_payoff is required")

    visual = payload.get("visual_opening_plan")
    if not isinstance(visual, dict):
        errors.append("human_framing.visual_opening_plan must be an object")
    else:
        moments = visual.get("moments")
        if not isinstance(moments, list) or not 3 <= len(moments) <= 5:
            errors.append(
                "human_framing.visual_opening_plan.moments must contain 3-5 moments"
            )
        else:
            for index, moment in enumerate(moments, start=1):
                if not isinstance(moment, dict):
                    errors.append(
                        f"human_framing.visual_opening_plan.moments[{index}] must be an object"
                    )
                    continue
                if not _nonempty(moment.get("visual")):
                    errors.append(
                        f"human_framing.visual_opening_plan.moments[{index}].visual is required"
                    )
                if not _nonempty(moment.get("purpose")):
                    errors.append(
                        f"human_framing.visual_opening_plan.moments[{index}].purpose is required"
                    )
        if not _nonempty(visual.get("opening_narration_intent")):
            errors.append(
                "human_framing.visual_opening_plan.opening_narration_intent is required"
            )

    drama = payload.get("drama")
    if not isinstance(drama, dict):
        errors.append("human_framing.drama must be an object")
        return errors

    capacity = drama.get("capacity")
    target = drama.get("target")
    hook_level = drama.get("hook_level")
    for key, value in (
        ("capacity", capacity),
        ("target", target),
        ("hook_level", hook_level),
    ):
        if not _valid_level(value, minimum=DRAMA_FLOOR):
            errors.append(
                f"human_framing.drama.{key} must be an integer from {DRAMA_FLOOR}-10"
            )

    if (
        isinstance(capacity, int)
        and not isinstance(capacity, bool)
        and DRAMA_FLOOR <= capacity <= DRAMA_MAX
        and isinstance(target, int)
        and not isinstance(target, bool)
        and DRAMA_FLOOR <= target <= DRAMA_MAX
    ):
        if target > capacity:
            errors.append("human_framing.drama.target cannot exceed capacity")
        if capacity - target > MAX_UNUSED_DRAMA_CAPACITY:
            errors.append(
                "human_framing underuses a high-drama opportunity; target is more than "
                f"{MAX_UNUSED_DRAMA_CAPACITY} points below capacity"
            )

    for key in ("source", "constraint"):
        if not _nonempty(drama.get(key)):
            errors.append(f"human_framing.drama.{key} is required")

    story_curve = drama.get("story_curve")
    if not isinstance(story_curve, list) or not 4 <= len(story_curve) <= 8:
        errors.append("human_framing.drama.story_curve must contain 4-8 levels")
    else:
        if not all(_valid_level(value, minimum=DRAMA_FLOOR) for value in story_curve):
            errors.append(
                f"human_framing.drama.story_curve levels must stay within {DRAMA_FLOOR}-10"
            )
        elif len(set(story_curve)) < 2:
            errors.append(
                "human_framing.drama.story_curve must pulse; constant drama is not allowed"
            )
        if _valid_level(target, minimum=DRAMA_FLOOR) and max(story_curve) < target:
            errors.append(
                "human_framing.drama.story_curve must reach the selected drama target"
            )

    tempo_curve = drama.get("tempo_curve")
    if not isinstance(tempo_curve, list) or not 4 <= len(tempo_curve) <= 8:
        errors.append("human_framing.drama.tempo_curve must contain 4-8 levels")
    else:
        if not all(_valid_level(value, minimum=1) for value in tempo_curve):
            errors.append("human_framing.drama.tempo_curve levels must be within 1-10")
        elif len(set(tempo_curve)) < 2:
            errors.append(
                "human_framing.drama.tempo_curve must change; constant tempo is not allowed"
            )

    if (
        isinstance(story_curve, list)
        and isinstance(tempo_curve, list)
        and len(story_curve) != len(tempo_curve)
    ):
        errors.append(
            "human_framing drama and tempo curves must describe the same number of beats"
        )

    return errors
