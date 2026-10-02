"""Story / Script Engine.

Consumes human-verified research packages and prepares bounded script requests.
Only accepted research claims may be referenced as factual support.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_OVERLAP_ROOT = Path(__file__).resolve().parent.parent
if str(_OVERLAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_OVERLAP_ROOT))

from channel_profiles.channel_profile import normalize_binding, unconfigured_binding
from source_overlap import check_texts

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
RESEARCH_VERIFIED_DIR = (
    PROJECT_ROOT / "research_engine" / "output" / "verified_packages"
)
OUTPUT_DIR = HERE / "output"
STORY_PLANS_DIR = OUTPUT_DIR / "story_plans"
REQUESTS_DIR = OUTPUT_DIR / "script_requests"
RESPONSES_DIR = OUTPUT_DIR / "script_responses"
DRAFTS_DIR = OUTPUT_DIR / "script_drafts"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"
PSYCHOLOGY_PROFILE_CONFIG = HERE / "script_psychology_profiles.json"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def safe_slug(value: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_." else "_" for c in value).strip(
        "._"
    )
    return cleaned or "unknown"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validation_contract_sha256() -> str:
    """Fingerprint deterministic Script acceptance and overlap rules."""
    digest = hashlib.sha256()
    for path in (
        Path(__file__).resolve(),
        (PROJECT_ROOT / "source_overlap.py").resolve(),
    ):
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def load_script_psychology_config(
    path: Path = PSYCHOLOGY_PROFILE_CONFIG,
) -> dict[str, Any]:
    config = load_json(path)
    required = {"format_intent_branches", "profiles", "reward_types"}
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(
            "Script psychology config is missing: " + ", ".join(missing)
        )
    return config


def resolve_script_branches(
    format_intent: str,
    config: dict[str, Any],
) -> list[str]:
    mapping = config.get("format_intent_branches", {})
    branches = mapping.get(str(format_intent).strip())
    if not isinstance(branches, list) or not branches:
        raise ValueError(f"Unsupported format_intent: {format_intent!r}")
    profiles = config.get("profiles", {})
    missing = [str(item) for item in branches if str(item) not in profiles]
    if missing:
        raise ValueError(
            "Missing script psychology profile(s): " + ", ".join(missing)
        )
    return [str(item) for item in branches]


def assert_unique_slug_ids(values: list[str], *, label: str) -> None:
    owners: dict[str, str] = {}
    for raw in values:
        slug = safe_slug(raw)
        previous = owners.get(slug)
        if previous is not None:
            if previous == raw:
                raise ValueError(f"Duplicate {label} ID: {raw!r}")
            raise ValueError(
                f"{label} IDs collide after filesystem normalization: "
                f"{previous!r} and {raw!r} -> {slug!r}"
            )
        owners[slug] = raw


def build_script_request(
    plan: dict[str, Any],
    plan_path: Path,
    fmt: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or load_script_psychology_config()
    if plan.get("status") != "STORY_PLAN_READY":
        raise ValueError("Story Plan is not STORY_PLAN_READY")

    concept_id = str(plan.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Story Plan requires concept_id")

    package_value = plan.get("package", {})
    if not isinstance(package_value, dict):
        raise ValueError("Story Plan package must be an object")
    package = dict(package_value)
    working_title = str(package.get("title") or "").strip()
    if not working_title:
        raise ValueError("Story Plan requires an internal working title")
    if str(plan.get("title", "")) != working_title:
        raise ValueError("Story Plan title must match the internal working title")

    required_branches = resolve_script_branches(
        str(package.get("format_intent") or ""),
        config,
    )
    fmt = str(fmt).strip()
    if fmt not in required_branches:
        raise ValueError(f"Unrequested script branch: {fmt}")

    profiles = config.get("profiles", {})
    profile = profiles.get(fmt)
    if not isinstance(profile, dict):
        raise ValueError(f"Missing psychology profile for {fmt}")

    concept = plan.get("concept", {})
    if not isinstance(concept, dict):
        concept = {}

    psychology_contract = plan.get("psychology_contract")
    if not isinstance(psychology_contract, dict) or not psychology_contract:
        raise ValueError("Story Plan requires the audience psychology contract")

    channel_voice_value = plan.get("channel_voice")
    channel_voice = (
        normalize_binding(channel_voice_value)
        if channel_voice_value is not None
        else unconfigured_binding()
    )
    voice_is_active = bool(channel_voice["apply_to_generation"])

    viewer_state = plan.get("viewer_state")
    if not isinstance(viewer_state, dict):
        raise ValueError("Story Plan requires viewer_state")

    opening_psychology = plan.get("opening_psychology")
    if not isinstance(opening_psychology, dict):
        raise ValueError("Story Plan requires opening_psychology")

    claims = plan.get("accepted_claims", [])
    if not isinstance(claims, list) or not claims:
        raise ValueError("Script requires accepted research claims")

    claim_ids: list[str] = []
    accepted: list[dict[str, Any]] = []
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("Every accepted claim must be an object")
        claim_id = str(claim.get("claim_id", "")).strip()
        statement = str(claim.get("statement", "")).strip()
        if not claim_id or not statement:
            raise ValueError("Every accepted claim requires claim_id and statement")
        claim_ids.append(claim_id)
        accepted.append(dict(claim))

    beats = plan.get("beats", [])
    if not isinstance(beats, list) or not beats:
        raise ValueError("Story Plan requires story beats before script drafting")
    for index, beat in enumerate(beats):
        if not isinstance(beat, dict) or not isinstance(beat.get("psychology"), dict):
            raise ValueError(f"Story Plan beat {index} requires psychology metadata")

    reward_types = [
        str(item) for item in config.get("reward_types", [])
        if str(item).strip()
    ]
    if not reward_types:
        raise ValueError("Script psychology config requires reward_types")

    instructions = [
        "Write a FORMAT-SPECIFIC narration from the shared approved Story Plan.",
        "Return the INTERNAL WORKING TITLE exactly for artifact identity; it is not the final public YouTube title.",
        "The opening_hook is the first spoken line and must be high-impact, truthful and tied to the accepted concept/viewer promise.",
        "The branch may compress, combine or emphasize Story Plan beats differently, but it may not invent facts or abandon the main payoff.",
        "Every script section must cite one or more source_story_beat_ids.",
        "Section claim_ids may use only claims available from those source Story Plan beats.",
        "Use the supplied format psychology profile rather than generic engagement advice.",
        (
            "Apply the approved Channel Voice Profile to wording, narrator posture, "
            "technical-language treatment and prohibited-style rules. Verified "
            "research, the accepted viewer/story contract and format psychology "
            "remain higher-priority constraints."
            if voice_is_active
            else (
                "No approved Channel Voice Profile exists. Do not invent a persistent "
                "channel personality from the niche, title, source videos or generic "
                "creator advice."
            )
        ),
        "Do not copy or closely paraphrase source-video wording.",
        "Do not claim virality, guaranteed performance or unsupported facts.",
    ]
    if fmt == "short":
        instructions.extend(
            [
                "Treat hook_target_seconds as a production target to be measured after narration rendering; do not fake timing from text length.",
                "Aim for rapid reward density: every section must provide PROOF, NOVELTY, REVEAL, EXPECTATION_SHIFT, MICRO_PAYOFF or PROGRESS.",
                "Keep cognitive branching low and stay on one core idea.",
                "The 4-6 second attention-refresh window is a testable hypothesis, not a universal physiological law.",
                "Close open loops quickly and end with a strong payoff.",
            ]
        )
    else:
        instructions.extend(
            [
                "Prioritize sustained curiosity and comprehension over constant novelty.",
                "Allow setup, explanation, examples and breathing room when they reduce cognitive load.",
                "Use larger delayed payoffs where appropriate rather than forcing a reward into every section.",
            ]
        )

    return {
        "artifact": "script_request",
        "concept_id": concept_id,
        "format": fmt,
        "required_branches": required_branches,
        "package": package,
        "concept": concept,
        "psychology_contract": psychology_contract,
        "psychology_profile": dict(profile),
        "channel_voice": channel_voice,
        "reward_types": reward_types,
        "story_plan": {
            "title": plan.get("title"),
            "story_question": plan.get("story_question"),
            "opening_hook_intent": plan.get("opening_hook_intent"),
            "viewer_state": viewer_state,
            "opening_psychology": opening_psychology,
            "beats": beats,
            "payoff_intent": plan.get("payoff_intent"),
            "closing_intent": plan.get("closing_intent"),
        },
        "accepted_claim_ids": sorted(set(claim_ids)),
        "accepted_claims": accepted,
        "instructions": instructions,
        "request_provenance": {
            "story_plan": str(plan_path.resolve()),
            "story_plan_sha256": sha256_file(plan_path),
        },
    }


def validate_script_response(
    response: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    errors: list[str] = []
    concept_id = str(request.get("concept_id", ""))
    fmt = str(request.get("format", "")).strip()

    if str(response.get("concept_id", "")) != concept_id:
        errors.append("concept_id mismatch")
    if str(response.get("format", "")).strip() != fmt:
        errors.append("format mismatch")

    working_title = str(request.get("package", {}).get("title") or "")
    if str(response.get("title", "")) != working_title:
        errors.append("title must exactly match the internal working title")

    if not str(response.get("opening_hook", "")).strip():
        errors.append("opening_hook is required")
    if not str(response.get("closing", "")).strip():
        errors.append("closing is required")

    allowed_hook_mechanisms = set(
        request.get("psychology_contract", {})
        .get("opening_line", {})
        .get("allowed_mechanisms", [])
    )
    actual_hook_mechanism = str(
        response.get("opening_hook_mechanism", "")
    ).strip().upper()
    if not actual_hook_mechanism:
        errors.append("opening_hook_mechanism is required")
    elif actual_hook_mechanism not in allowed_hook_mechanisms:
        errors.append("opening_hook_mechanism is not allowed")

    allowed = set(request.get("accepted_claim_ids", []))
    hook_claim_ids = response.get("opening_hook_claim_ids")
    if not isinstance(hook_claim_ids, list):
        errors.append("opening_hook_claim_ids must be a list")
        hook_claim_ids = []
    used: set[str] = set()
    for cid in hook_claim_ids:
        normalized = str(cid)
        if normalized not in allowed:
            errors.append(f"opening hook uses unapproved claim_id {normalized}")
        else:
            used.add(normalized)

    story_plan = request.get("story_plan", {})
    if not isinstance(story_plan, dict):
        errors.append("request Story Plan is missing")
        story_plan = {}
    story_beats = story_plan.get("beats", [])
    if not isinstance(story_beats, list) or not story_beats:
        errors.append("request Story Plan beats are missing")
        story_beats = []

    beat_claims: dict[str, set[str]] = {}
    payoff_beats: set[str] = set()
    for beat in story_beats:
        if not isinstance(beat, dict):
            continue
        beat_id = str(beat.get("beat_id", "")).strip()
        if not beat_id:
            continue
        ids = beat.get("claim_ids", [])
        beat_claims[beat_id] = (
            {str(item) for item in ids}
            if isinstance(ids, list)
            else set()
        )
        if str(beat.get("role", "")).strip().upper() == "PAYOFF":
            payoff_beats.add(beat_id)

    sections = response.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("sections must be a non-empty list")
        sections = []

    profile = request.get("psychology_profile", {})
    if not isinstance(profile, dict):
        profile = {}
    minimum = profile.get("min_sections")
    maximum = profile.get("max_sections")
    if isinstance(minimum, int) and len(sections) < minimum:
        errors.append(f"{fmt} requires at least {minimum} sections")
    if isinstance(maximum, int) and len(sections) > maximum:
        errors.append(f"{fmt} allows at most {maximum} sections")

    allowed_psychology = set(
        request.get("psychology_contract", {}).get("beat_mechanisms", [])
    )
    allowed_rewards = set(request.get("reward_types", []))
    seen_sections: set[str] = set()
    covered_beats: set[str] = set()

    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            errors.append(f"section {index} must be an object")
            continue
        sid = str(section.get("section_id", "")).strip()
        label = sid or str(index)
        if not sid:
            errors.append(f"section {index} requires section_id")
        elif sid in seen_sections:
            errors.append(f"duplicate section_id: {sid}")
        seen_sections.add(sid)

        if not str(section.get("purpose", "")).strip():
            errors.append(f"{label} requires purpose")
        if not str(section.get("narration", "")).strip():
            errors.append(f"{label} requires narration")

        source_ids = section.get("source_story_beat_ids")
        if not isinstance(source_ids, list) or not source_ids:
            errors.append(f"{label} requires source_story_beat_ids")
            source_ids = []
        normalized_sources = {str(item) for item in source_ids}
        for beat_id in normalized_sources:
            if beat_id not in beat_claims:
                errors.append(f"{label} references unknown Story Plan beat {beat_id}")
            else:
                covered_beats.add(beat_id)

        psychology = str(section.get("psychology_mechanism", "")).strip().upper()
        if psychology not in allowed_psychology:
            errors.append(f"{label} uses invalid psychology_mechanism {psychology}")

        reward_type = str(section.get("reward_type", "")).strip().upper()
        if reward_type not in allowed_rewards:
            errors.append(f"{label} uses invalid reward_type {reward_type}")
        if fmt == "short" and reward_type == "NONE":
            errors.append(f"{label} short section requires a reward/progress event")

        ids = section.get("claim_ids")
        if not isinstance(ids, list):
            errors.append(f"{label} claim_ids must be a list")
            continue
        normalized_ids = {str(cid) for cid in ids}
        source_claims: set[str] = set()
        for beat_id in normalized_sources:
            source_claims.update(beat_claims.get(beat_id, set()))
        for cid in normalized_ids:
            if cid not in allowed:
                errors.append(f"{label} uses unapproved claim_id {cid}")
            elif cid not in source_claims:
                errors.append(
                    f"{label} claim_id {cid} is not available from its source Story Plan beat(s)"
                )
            else:
                used.add(cid)

    if profile.get("require_all_story_beats") is True:
        missing = set(beat_claims) - covered_beats
        if missing:
            errors.append(
                f"{fmt} script is missing Story Plan beat(s): "
                + ", ".join(sorted(missing))
            )
    if payoff_beats and not (covered_beats & payoff_beats):
        errors.append(f"{fmt} script must include a Story Plan PAYOFF beat")
    if not used:
        errors.append(f"{fmt} script must use at least one accepted claim")

    overlap = check_texts(
        [
            {"field": "title", "text": response.get("title", "")},
            {"field": "opening_hook", "text": response.get("opening_hook", "")},
            *[
                {"field": f"section.{index}", "text": section.get("narration", "")}
                for index, section in enumerate(sections)
                if isinstance(section, dict)
            ],
            {"field": "closing", "text": response.get("closing", "")},
        ]
    )
    if overlap.get("blocking"):
        match = overlap.get("matches", [{}])[0]
        errors.append("source overlap block: " + str(match.get("overlap_text") or ""))

    return {
        "valid": not errors,
        "errors": errors,
        "format": fmt,
        "claim_usage": sorted(used),
        "unused_accepted_claim_ids": sorted(allowed - used),
        "source_overlap": overlap,
        "covered_story_beat_ids": sorted(covered_beats),
        "opening_hook_mechanism": actual_hook_mechanism,
        "hook_target_seconds": profile.get("hook_target_seconds"),
        "attention_refresh_window_seconds": profile.get(
            "attention_refresh_window_seconds"
        ),
    }


def run_prepare(
    story_plans_dir: Path = STORY_PLANS_DIR,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or load_script_psychology_config()
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = (
        sorted(story_plans_dir.glob("*.story_plan.json"))
        if story_plans_dir.exists()
        else []
    )

    prepared: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    pending: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        try:
            plan = load_json(path)
            package = plan.get("package", {})
            if not isinstance(package, dict):
                raise ValueError("Story Plan package must be an object")
            branches = resolve_script_branches(
                str(package.get("format_intent") or ""),
                config,
            )
            for fmt in branches:
                request = build_script_request(plan, path, fmt, config)
                pending.append((path, request))
        except Exception as exc:
            failures.append(
                {
                    "story_plan": str(path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    assert_unique_slug_ids(
        [
            f"{request['concept_id']}.{request['format']}"
            for _, request in pending
        ],
        label="concept-format",
    )

    current_destinations: set[Path] = set()
    for _, request in pending:
        dest = REQUESTS_DIR / (
            f"{safe_slug(str(request['concept_id']))}."
            f"{safe_slug(str(request['format']))}.script_request.json"
        )
        dest.write_text(
            json.dumps(request, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        current_destinations.add(dest.resolve())
        prepared.append(
            {
                "concept_id": request["concept_id"],
                "format": request["format"],
                "request": str(dest),
            }
        )

    for stale_path in REQUESTS_DIR.glob("*.script_request.json"):
        if stale_path.resolve() not in current_destinations:
            stale_path.unlink()

    summary = {
        "status": (
            "SCRIPT_REQUESTS_READY" if prepared else "WAITING_FOR_STORY_PLANS"
        ),
        "story_plans_found": len(paths),
        "prepared": len(prepared),
        "failures": failures,
        "requests_dir": str(REQUESTS_DIR),
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description="Story / Script Engine")
    p.add_argument("--mode", choices=("prepare",), required=True)
    p.add_argument("--story-plans-dir", type=Path, default=STORY_PLANS_DIR)
    a = p.parse_args()
    print(
        json.dumps(
            run_prepare(a.story_plans_dir.resolve()),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
