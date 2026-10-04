"""One resolved format per accepted concept (D-132).

Vision: the Short / long-form decision is made early, before research and
scripting, and each production makes one video. A concept may be generated
with ``format_intent: either`` (it would work as both), but the Concept Gate
handoff always resolves it to exactly one format, so downstream stages write
one script branch instead of two.

Resolution, in order:
  1. the format the human chose when accepting the concept;
  2. the concept's own single format (``long_form`` or ``short``);
  3. for ``either``, the configured default (``either_default_format``).
"""

from __future__ import annotations

from typing import Any

FORMATS = ("long_form", "short")
DEFAULT_EITHER_FORMAT = "long_form"
LABELS = {"long_form": "long-form", "short": "Short"}


def normalize_choice(value: Any) -> str | None:
    """A valid chosen format, None when nothing was chosen; raises otherwise."""
    text = str(value or "").strip().lower().replace("-", "_")
    if not text:
        return None
    if text == "longform":
        text = "long_form"
    if text not in FORMATS:
        raise ValueError("Chosen format must be long_form or short")
    return text


def resolve_format(
    format_intent: Any,
    *,
    chosen: Any = None,
    default: Any = None,
) -> dict[str, Any]:
    requested = str(format_intent or "").strip()
    choice = normalize_choice(chosen)
    if choice:
        reason = (
            f"Chosen at the Concept Gate as {LABELS[choice]}"
            + (f" (the concept was generated as {requested})." if requested and requested != choice else ".")
        )
        return {"format_intent": choice, "requested_format_intent": requested, "decided_by": "HUMAN", "reason": reason}
    if requested in FORMATS:
        return {
            "format_intent": requested,
            "requested_format_intent": requested,
            "decided_by": "CONCEPT",
            "reason": f"The concept was generated as {LABELS[requested]}.",
        }
    if requested == "either":
        fallback = normalize_choice(default) or DEFAULT_EITHER_FORMAT
        return {
            "format_intent": fallback,
            "requested_format_intent": requested,
            "decided_by": "DEFAULT",
            "reason": (
                f"The concept fits either format; no format was chosen at the "
                f"Concept Gate, so the default ({LABELS[fallback]}) applies."
            ),
        }
    raise ValueError(f"Unsupported format_intent: {requested!r}")
