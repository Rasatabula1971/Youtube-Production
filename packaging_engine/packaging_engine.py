"""Packaging Engine framework.

Consumes human-accepted concept candidates and prepares structured packaging
requests. Returned packages are validated for promise clarity, title/thumbnail
complementarity, format context, and explicit research dependencies.

No model, network, or YouTube API calls are made here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

_OVERLAP_ROOT = Path(__file__).resolve().parent.parent
if str(_OVERLAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_OVERLAP_ROOT))

from source_overlap import check_texts

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent

CONFIG_FILE = HERE / "packaging_config.json"
DEFAULT_CONCEPT_HANDOFF = (
    PROJECT_ROOT / "transformation_engine" / "output" / "research_handoff.json"
)

OUTPUT_DIR = HERE / "output"
REQUESTS_DIR = OUTPUT_DIR / "package_requests"
RESPONSES_DIR = OUTPUT_DIR / "package_responses"
CANDIDATES_FILE = OUTPUT_DIR / "package_candidates.json"
REJECTED_FILE = OUTPUT_DIR / "rejected_packages.json"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_FILE)
    required = {
        "packages_per_concept",
        "allowed_format_intents",
        "minimum_research_dependencies",
    }
    missing = sorted(required - set(config))
    if missing:
        raise SystemExit("Packaging config is missing: " + ", ".join(missing))
    return config


def safe_slug(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in "-_." else "_" for char in value
    ).strip("._")
    return cleaned or "unknown"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def niche_conventions(niche: Any, format_intent: Any) -> dict[str, Any]:
    """Attach the niche thumbnail tabulation when the channel niche is configured."""
    if not niche:
        return {}
    from niche_thumbnail_study import packaging_conventions

    return packaging_conventions(str(niche), str(format_intent or ""))


def build_package_request(
    concept: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    concept_id = str(concept.get("concept_id", "")).strip()
    if not concept_id:
        raise ValueError("Accepted concept requires concept_id")

    return {
        "request_type": "packaging_generation",
        "concept_id": concept_id,
        "concept": {
            "working_title": concept.get("working_title"),
            "premise": concept.get("premise"),
            "audience_promise": concept.get("audience_promise"),
            "viewer_problem": concept.get("viewer_problem"),
            "viewer_moment": concept.get("viewer_moment"),
            "desired_outcome": concept.get("desired_outcome"),
            "human_framing": concept.get("human_framing", {}),
            "content_gap": concept.get("content_gap", {}),
            "channel_fit": concept.get("channel_fit", {}),
            "title_clarity_test": concept.get("title_clarity_test", {}),
            "format_intent": concept.get("format_intent"),
            "mechanism_id": concept.get("mechanism_id"),
            "mechanism_label": concept.get("mechanism_label"),
            "mechanism_application": concept.get("mechanism_application"),
            "transformation_method": concept.get("transformation_method"),
            "research_questions": concept.get("research_questions", []),
            "source_dependency_test": concept.get("source_dependency_test", {}),
            "concept_gate": concept.get("concept_gate", {}),
        },
        "niche_thumbnail_conventions": niche_conventions(
            config.get("channel_niche"), concept.get("format_intent")
        ),
        "package_count_requested": int(config["packages_per_concept"]),
        "allowed_format_intents": list(config["allowed_format_intents"]),
        "instructions": [
            "Create package options before script drafting.",
            "Treat title and thumbnail as one communication unit.",
            "Title and thumbnail should complement rather than repeat each other.",
            "Each package must communicate one main promise and one expected payoff.",
            "Define the intended viewer and their awareness level explicitly.",
            "Preserve the accepted viewer problem, viewer moment, desired outcome, and Human Framing contract.",
            "Packaging may sharpen wording, but it must preserve the Hook Experience, Viewer Question, Psychological Pull, Explanation Payoff, and truthful drama intent rather than reverting to a technical topic label.",
            "Use the Visual Opening Plan as the starting psychological intention for the thumbnail/opening frame; do not promise unsupported spectacle.",
            "Write a one-sentence promise in the form: this video helps [viewer/problem] so they can [specific outcome].",
            "Explain how this package addresses the accepted content-gap hypothesis without upgrading a hypothesis into a proven fact.",
            "Preserve the accepted channel-fit rationale.",
            "The package must remain faithful to the accepted concept and must not invent unsupported facts.",
            "List factual or evidentiary dependencies that research must verify before the package can be considered fully supported.",
            "Do not rank the package options.",
            "Do not optimize for clickbait that the future video cannot deliver.",
            "Division of labor: the thumbnail carries emotion and curiosity; the title carries context and fact.",
            "Name the main search keyword and place it near the front of the title; aim for roughly 40-60 title characters so it survives mobile truncation.",
            "Design the thumbnail around one focal subject with at most 2-3 distinct visual elements and at most 1-2 arrows or circles.",
            "The channel is faceless: make the subject itself the focal point (the object, the mechanism, or a before/after contrast).",
            "Thumbnail text, when used, should be 3-5 bold words that add to the title rather than repeat it.",
            "Specify a background / subject / accent palette that stays legible at phone size; pick an accent that stands apart from the niche's usual palette.",
            "These design targets are published starting hypotheses, not proven rules; never trade truthfulness for them.",
            "When niche_thumbnail_conventions are present, they describe the niche's breakout thumbnails: where the niche diverges from a generic hypothesis, prefer the niche convention, and choose an accent from the differentiation candidates rather than the crowded hue families.",
        ],
        "response_schema": {
            "concept_id": concept_id,
            "packages": [
                {
                    "package_id": "unique stable id",
                    "title": "candidate title",
                    "title_keyword": "main search keyword, appearing near the front of the title",
                    "thumbnail": {
                        "message": "what the thumbnail communicates",
                        "visual_concept": "visual idea",
                        "text_overlay": "optional 3-5 word overlay or empty string",
                        "focal_subject": "the single thing the eye lands on first",
                        "visual_elements": [
                            "each distinct visual element, focal subject included"
                        ],
                        "visual_cues": ["arrow or circle, if any"],
                        "palette": {
                            "background": "background tone",
                            "subject": "subject tone",
                            "accent": "accent colour and the emotion it signals",
                        },
                    },
                    "division_of_labor": {
                        "thumbnail_carries": "the emotion / curiosity the thumbnail carries",
                        "title_carries": "the context / fact the title carries",
                    },
                    "opening_frame": {
                        "purpose": "what the first frame should establish",
                        "visual_concept": "first-frame idea",
                    },
                    "expected_viewer": "who this package is for",
                    "awareness_level": "what that viewer already understands",
                    "viewer_problem": "specific problem, question, or curiosity this package addresses",
                    "viewer_moment": "situation or decision state in which the viewer needs this",
                    "desired_outcome": "what the viewer will understand, fix, avoid, or decide",
                    "one_sentence_promise": "This video helps [specific viewer/problem] so they can [specific outcome].",
                    "gap_positioning": "how the package addresses the accepted gap hypothesis without overstating evidence",
                    "channel_fit_alignment": "how the package remains aligned with the intended channel/audience",
                    "core_promise": "single main promise",
                    "curiosity_gap": "important missing answer",
                    "expected_payoff": "what must be delivered",
                    "format_intent": "long_form|short|either",
                    "title_thumbnail_relationship": "how title and thumbnail complement each other",
                    "research_dependencies": [
                        "fact or claim that must be verified before script"
                    ],
                }
            ],
        },
    }


def validate_package(
    package: dict[str, Any],
    *,
    concept_id: str,
    config: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    package_id = str(package.get("package_id", "")).strip()
    if not package_id:
        errors.append("package_id is required")

    for field in (
        "title",
        "title_keyword",
        "expected_viewer",
        "awareness_level",
        "viewer_problem",
        "viewer_moment",
        "desired_outcome",
        "one_sentence_promise",
        "gap_positioning",
        "channel_fit_alignment",
        "core_promise",
        "curiosity_gap",
        "expected_payoff",
        "title_thumbnail_relationship",
    ):
        if not str(package.get(field, "")).strip():
            errors.append(f"{field} is required")

    format_intent = str(package.get("format_intent", "")).strip()
    if format_intent not in config["allowed_format_intents"]:
        errors.append(
            "format_intent must be one of "
            + ", ".join(config["allowed_format_intents"])
        )

    thumbnail = package.get("thumbnail")
    if not isinstance(thumbnail, dict):
        errors.append("thumbnail must be an object")
    else:
        if not str(thumbnail.get("message", "")).strip():
            errors.append("thumbnail.message is required")
        if not str(thumbnail.get("visual_concept", "")).strip():
            errors.append("thumbnail.visual_concept is required")
        if not str(thumbnail.get("focal_subject", "")).strip():
            errors.append("thumbnail.focal_subject is required")
        elements = thumbnail.get("visual_elements")
        if not isinstance(elements, list) or not elements:
            errors.append("thumbnail.visual_elements must be a non-empty list")
        elif any(not str(value).strip() for value in elements):
            errors.append("thumbnail.visual_elements items must be non-empty")
        cues = thumbnail.get("visual_cues")
        if not isinstance(cues, list):
            errors.append("thumbnail.visual_cues must be a list")
        elif any(not str(value).strip() for value in cues):
            errors.append(
                "thumbnail.visual_cues may be empty, but listed items must be non-empty"
            )
        palette = thumbnail.get("palette")
        if not isinstance(palette, dict):
            errors.append("thumbnail.palette must be an object")
        else:
            for key in ("background", "subject", "accent"):
                if not str(palette.get(key, "")).strip():
                    errors.append(f"thumbnail.palette.{key} is required")

    division = package.get("division_of_labor")
    if not isinstance(division, dict):
        errors.append("division_of_labor must be an object")
    else:
        for key in ("thumbnail_carries", "title_carries"):
            if not str(division.get(key, "")).strip():
                errors.append(f"division_of_labor.{key} is required")

    opening_frame = package.get("opening_frame")
    if not isinstance(opening_frame, dict):
        errors.append("opening_frame must be an object")
    else:
        if not str(opening_frame.get("purpose", "")).strip():
            errors.append("opening_frame.purpose is required")
        if not str(opening_frame.get("visual_concept", "")).strip():
            errors.append("opening_frame.visual_concept is required")

    dependencies = package.get("research_dependencies")
    if not isinstance(dependencies, list):
        errors.append("research_dependencies must be a list")
    else:
        invalid = [value for value in dependencies if not str(value).strip()]
        if invalid:
            errors.append(
                "research_dependencies may be empty, but listed items must be non-empty"
            )

    declared_concept_id = str(package.get("concept_id", concept_id)).strip()
    if declared_concept_id not in {"", concept_id}:
        errors.append("package concept_id does not match request")

    return errors


_ADVISORY_STOPWORDS = frozenset(
    "a an and are as at be by for from how i in is it my of on or the this "
    "to was what when why with you your".split()
)


def content_tokens(text: str) -> list[str]:
    cleaned = re.sub(r"[^0-9a-z\s]", "", text.lower())
    return [token for token in cleaned.split() if token not in _ADVISORY_STOPWORDS]


def design_advisories(
    package: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Non-blocking checks of generic title/thumbnail guidance.

    The thresholds are published starting hypotheses (see D-070). They are
    surfaced to the human Packaging Gate and never reject a package.
    """
    rules = config.get("design_advisories")
    if not isinstance(rules, dict):
        return []
    status = str(rules.get("evidence_status", "HYPOTHESIS"))
    advisories: list[dict[str, Any]] = []

    def add(rule: str, observed: Any, guidance: str) -> None:
        advisories.append(
            {
                "rule": rule,
                "observed": observed,
                "guidance": guidance,
                "evidence_status": status,
            }
        )

    title = str(package.get("title", "")).strip()
    length = rules.get("title_length_chars")
    if title and isinstance(length, dict):
        low, high = int(length["min"]), int(length["max"])
        if not low <= len(title) <= high:
            add(
                "TITLE_LENGTH",
                len(title),
                f"Title is {len(title)} characters; target {low}-{high} so it "
                "survives mobile truncation.",
            )

    keyword = str(package.get("title_keyword", "")).strip()
    max_start = rules.get("title_keyword_max_start_chars")
    if title and keyword and max_start is not None:
        start = title.lower().find(keyword.lower())
        if start < 0:
            add(
                "TITLE_KEYWORD_MISSING",
                keyword,
                "The declared keyword does not appear in the title.",
            )
        elif start > int(max_start):
            add(
                "TITLE_KEYWORD_LATE",
                start,
                f"Keyword starts at character {start}; place it within the "
                f"first {int(max_start)} characters.",
            )

    thumbnail = package.get("thumbnail")
    if not isinstance(thumbnail, dict):
        return advisories

    overlay = str(thumbnail.get("text_overlay", "") or "").strip()
    words = rules.get("thumbnail_text_words")
    if overlay and isinstance(words, dict):
        count = len(overlay.split())
        low, high = int(words["min"]), int(words["max"])
        if not low <= count <= high:
            add(
                "THUMBNAIL_TEXT_WORDS",
                count,
                f"Thumbnail text is {count} words; target {low}-{high} bold words.",
            )

    overlap_max = rules.get("thumbnail_text_title_overlap_max")
    overlay_tokens = content_tokens(overlay)
    if overlay_tokens and title and overlap_max is not None:
        title_tokens = set(content_tokens(title))
        shared = sum(token in title_tokens for token in overlay_tokens)
        ratio = round(shared / len(overlay_tokens), 2)
        if ratio > float(overlap_max):
            add(
                "THUMBNAIL_TEXT_REPEATS_TITLE",
                ratio,
                "Thumbnail text mostly repeats the title; it should add to it.",
            )

    elements = thumbnail.get("visual_elements")
    max_elements = rules.get("thumbnail_max_visual_elements")
    if isinstance(elements, list) and max_elements is not None:
        if len(elements) > int(max_elements):
            add(
                "THUMBNAIL_ELEMENT_COUNT",
                len(elements),
                f"{len(elements)} distinct visual elements; keep to "
                f"{int(max_elements)} or fewer around one focal subject.",
            )

    cues = thumbnail.get("visual_cues")
    max_cues = rules.get("thumbnail_max_visual_cues")
    if isinstance(cues, list) and max_cues is not None:
        if len(cues) > int(max_cues):
            add(
                "THUMBNAIL_CUE_COUNT",
                len(cues),
                f"{len(cues)} arrows/circles; use at most {int(max_cues)}.",
            )

    return advisories


def validate_response(
    response: dict[str, Any],
    request: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    concept_id = str(request["concept_id"])
    if str(response.get("concept_id", "")) != concept_id:
        raise ValueError("Packaging response concept_id does not match request")

    packages = response.get("packages")
    if not isinstance(packages, list):
        raise ValueError("Packaging response packages must be a list")

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, package in enumerate(packages):
        if not isinstance(package, dict):
            rejected.append(
                {
                    "index": index,
                    "package": package,
                    "errors": ["package must be an object"],
                }
            )
            continue

        errors = validate_package(
            package,
            concept_id=concept_id,
            config=config,
        )

        package_id = str(package.get("package_id", "")).strip()
        if package_id and package_id in seen_ids:
            errors.append("package_id must be unique within response")
        if package_id:
            seen_ids.add(package_id)

        normalized = dict(package)
        normalized["concept_id"] = concept_id
        normalized["concept_context"] = request["concept"]
        overlap = check_texts(
            [
                {"field": "title", "text": normalized.get("title", "")},
                {
                    "field": "one_sentence_promise",
                    "text": normalized.get("one_sentence_promise", ""),
                },
                {"field": "core_promise", "text": normalized.get("core_promise", "")},
                {"field": "curiosity_gap", "text": normalized.get("curiosity_gap", "")},
                {
                    "field": "thumbnail.message",
                    "text": (normalized.get("thumbnail") or {}).get("message", ""),
                },
                {
                    "field": "opening_frame.purpose",
                    "text": (normalized.get("opening_frame") or {}).get("purpose", ""),
                },
            ]
        )
        normalized["source_overlap"] = overlap
        normalized["packaging_advisories"] = design_advisories(normalized, config)
        if overlap.get("blocking"):
            match = overlap.get("matches", [{}])[0]
            errors.append(
                "source overlap block: " + str(match.get("overlap_text") or "")
            )

        if errors:
            rejected.append(
                {
                    "index": index,
                    "package": normalized,
                    "errors": errors,
                }
            )
        else:
            accepted.append(normalized)

    return {
        "concept_id": concept_id,
        "accepted": accepted,
        "rejected": rejected,
    }


def run_prepare(
    concept_handoff_path: Path,
) -> dict[str, Any]:
    config = load_config()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)

    if not concept_handoff_path.exists():
        summary = {
            "status": "WAITING_FOR_ACCEPTED_CONCEPTS",
            "concept_handoff": str(concept_handoff_path),
            "requests_created": 0,
        }
        SUMMARY_FILE.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return summary

    handoff = load_json(concept_handoff_path)
    handoff_sha256 = sha256_file(concept_handoff_path)
    concepts = handoff.get("concepts", [])
    if not isinstance(concepts, list):
        raise ValueError("Accepted concept handoff concepts must be a list")

    concept_ids = [
        str(concept.get("concept_id", "")).strip()
        for concept in concepts
        if isinstance(concept, dict)
    ]
    assert_unique_slug_ids(concept_ids, label="concept")

    paths = []
    current_destinations: set[Path] = set()
    seen_concept_ids: set[str] = set()

    for concept in concepts:
        request = build_package_request(concept, config)
        request["request_provenance"] = {
            "concept_handoff_source": str(concept_handoff_path),
            "concept_handoff_sha256": handoff_sha256,
        }
        concept_id = str(request["concept_id"])
        if concept_id in seen_concept_ids:
            raise ValueError(
                f"Duplicate concept_id in accepted concept handoff: {concept_id}"
            )
        seen_concept_ids.add(concept_id)

        destination = REQUESTS_DIR / f"{safe_slug(concept_id)}.package_request.json"
        destination.write_text(
            json.dumps(request, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        current_destinations.add(destination.resolve())
        paths.append(str(destination))

    for stale_path in REQUESTS_DIR.glob("*.package_request.json"):
        if stale_path.resolve() not in current_destinations:
            stale_path.unlink()

    summary = {
        "status": ("PACKAGE_REQUESTS_READY" if paths else "NO_ACCEPTED_CONCEPTS"),
        "requests_created": len(paths),
        "requests": paths,
        "network_calls": 0,
        "model_calls": 0,
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def reserve_generated_id(
    *,
    raw_id: str,
    namespace: str,
    used_ids: set[str],
) -> tuple[str, bool]:
    """Reserve a stable globally unique package ID without dropping output."""
    raw_id = str(raw_id).strip()
    if raw_id not in used_ids:
        used_ids.add(raw_id)
        return raw_id, False

    base = f"{safe_slug(namespace)}--{safe_slug(raw_id)}"
    candidate = base
    suffix = 2
    while candidate in used_ids:
        candidate = f"{base}--{suffix}"
        suffix += 1
    used_ids.add(candidate)
    return candidate, True


def run_apply() -> dict[str, Any]:
    config = load_config()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    global_package_ids: set[str] = set()

    if not RESPONSES_DIR.exists():
        summary = {
            "status": "WAITING_FOR_PACKAGE_RESPONSES",
            "accepted_packages": 0,
            "rejected_packages": 0,
        }
        SUMMARY_FILE.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return summary

    for response_path in sorted(RESPONSES_DIR.glob("*.json")):
        response = load_json(response_path)
        concept_id = str(response.get("concept_id", "")).strip()
        request_path = REQUESTS_DIR / f"{safe_slug(concept_id)}.package_request.json"
        if not request_path.exists():
            rejected.append(
                {
                    "response": str(response_path),
                    "errors": ["matching package request not found"],
                }
            )
            continue

        request = load_json(request_path)
        response_provenance = response.get("response_provenance", {})
        if not isinstance(response_provenance, dict) or response_provenance.get(
            "request_sha256"
        ) != sha256_file(request_path):
            rejected.append(
                {
                    "response": str(response_path),
                    "errors": [
                        "response provenance does not match current package request"
                    ],
                }
            )
            continue

        try:
            result = validate_response(
                response,
                request,
                config,
            )
        except ValueError as exc:
            rejected.append(
                {
                    "response": str(response_path),
                    "errors": [str(exc)],
                }
            )
            continue

        for accepted_package in result["accepted"]:
            package = dict(accepted_package)
            model_package_id = str(package["package_id"]).strip()
            package_id, renamed = reserve_generated_id(
                raw_id=model_package_id,
                namespace=concept_id,
                used_ids=global_package_ids,
            )
            if renamed:
                package["model_package_id"] = model_package_id
                package["package_id"] = package_id
            package["response_source"] = str(response_path)
            accepted.append(package)

        for item in result["rejected"]:
            item["response_source"] = str(response_path)
            rejected.append(item)

    current_response_hashes: dict[str, str] = {}
    for response_path in sorted(RESPONSES_DIR.glob("*.json")):
        try:
            response = load_json(response_path)
        except (OSError, json.JSONDecodeError):
            continue
        concept_id = str(response.get("concept_id", "")).strip()
        request_path = REQUESTS_DIR / f"{safe_slug(concept_id)}.package_request.json"
        if not request_path.exists():
            continue
        provenance = response.get("response_provenance", {})
        if (
            isinstance(provenance, dict)
            and provenance.get("request_sha256") == sha256_file(request_path)
        ):
            current_response_hashes[concept_id] = sha256_file(response_path)

    CANDIDATES_FILE.write_text(
        json.dumps(
            {
                "artifact": "package_candidates",
                "count": len(accepted),
                "source_response_sha256": current_response_hashes,
                "packages": accepted,
                "notes": [
                    "Packages are not ranked.",
                    "Structural validity does not equal human approval.",
                    "Package research dependencies must be incorporated into downstream research.",
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    REJECTED_FILE.write_text(
        json.dumps(
            {
                "artifact": "rejected_packages",
                "count": len(rejected),
                "items": rejected,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = {
        "status": (
            "PACKAGE_CANDIDATES_READY" if accepted else "NO_VALID_PACKAGE_CANDIDATES"
        ),
        "accepted_packages": len(accepted),
        "rejected_packages": len(rejected),
        "candidates_file": str(CANDIDATES_FILE),
        "rejected_file": str(REJECTED_FILE),
        "network_calls": 0,
        "model_calls": 0,
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Packaging Engine framework")
    parser.add_argument(
        "--mode",
        choices=("prepare", "apply"),
        required=True,
    )
    parser.add_argument(
        "--concept-handoff",
        type=Path,
        default=DEFAULT_CONCEPT_HANDOFF,
    )
    args = parser.parse_args()

    if args.mode == "prepare":
        result = run_prepare(args.concept_handoff.resolve())
    else:
        result = run_apply()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
