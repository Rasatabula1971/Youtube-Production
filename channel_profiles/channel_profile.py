"""Load and validate the active Channel Voice Profile."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ACTIVE_SELECTOR = HERE / "active_profile.json"
DEFAULT_UNCONFIGURED = HERE / "profiles" / "default_unconfigured.json"

_REQUIRED_TOP_LEVEL = {
    "schema_version",
    "profile_id",
    "version",
    "status",
    "channel_id",
    "channel_name",
    "niche",
    "audience",
    "narrator_role",
    "tone",
    "technical_language",
    "sentence_style",
    "storytelling",
    "prohibited_style",
    "evidence_style",
    "provenance",
}

_REQUIRED_APPROVED_OBJECTS = {
    "audience",
    "narrator_role",
    "tone",
    "technical_language",
    "sentence_style",
    "storytelling",
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_profile(profile: Any) -> dict[str, Any]:
    """Validate project-level invariants without adding a JSON Schema dependency."""
    errors: list[str] = []
    if not isinstance(profile, dict):
        return {"valid": False, "errors": ["profile must be an object"]}

    missing = sorted(_REQUIRED_TOP_LEVEL - set(profile))
    if missing:
        errors.append("profile is missing: " + ", ".join(missing))

    if profile.get("schema_version") != 1:
        errors.append("schema_version must equal 1")

    status = str(profile.get("status") or "")
    if status not in {"UNCONFIGURED", "APPROVED"}:
        errors.append("status must be UNCONFIGURED or APPROVED")

    version = profile.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        errors.append("version must be a non-negative integer")

    profile_id = str(profile.get("profile_id") or "").strip()
    if not profile_id:
        errors.append("profile_id is required")

    prohibited = profile.get("prohibited_style")
    if not isinstance(prohibited, list) or not all(
        isinstance(item, str) for item in prohibited
    ):
        errors.append("prohibited_style must be a list of strings")

    evidence = profile.get("evidence_style")
    if not isinstance(evidence, dict):
        errors.append("evidence_style must be an object")
    else:
        for field in (
            "state_uncertainty",
            "distinguish_fact_from_hypothesis",
            "numbers_require_support",
        ):
            if not isinstance(evidence.get(field), bool):
                errors.append(f"evidence_style.{field} must be boolean")

    provenance = profile.get("provenance")
    if not isinstance(provenance, dict):
        errors.append("provenance must be an object")

    if status == "UNCONFIGURED":
        if profile_id != "UNCONFIGURED":
            errors.append(
                "UNCONFIGURED profile_id must be exactly UNCONFIGURED"
            )
        if version != 0:
            errors.append("UNCONFIGURED profile version must equal 0")
        for field in (
            "channel_id",
            "channel_name",
            "niche",
            *_REQUIRED_APPROVED_OBJECTS,
        ):
            if profile.get(field) is not None:
                errors.append(f"UNCONFIGURED profile requires {field}=null")
        if prohibited not in ([], None):
            errors.append(
                "UNCONFIGURED profile must not define prohibited_style"
            )

    if status == "APPROVED":
        if version is None or not isinstance(version, int) or version < 1:
            errors.append("APPROVED profile version must be at least 1")
        for field in ("channel_id", "channel_name", "niche"):
            if not str(profile.get(field) or "").strip():
                errors.append(f"APPROVED profile requires {field}")
        for field in sorted(_REQUIRED_APPROVED_OBJECTS):
            value = profile.get(field)
            if not isinstance(value, dict) or not value:
                errors.append(
                    f"APPROVED profile requires non-empty {field}"
                )
        if isinstance(provenance, dict):
            if not str(provenance.get("approved_by") or "").strip():
                errors.append(
                    "APPROVED profile requires provenance.approved_by"
                )
            if not str(provenance.get("approved_at") or "").strip():
                errors.append(
                    "APPROVED profile requires provenance.approved_at"
                )

    return {"valid": not errors, "errors": errors}


def load_profile(path: Path) -> dict[str, Any]:
    """Load one profile and fail closed on invalid configuration."""
    value = _load_json(path)
    validation = validate_profile(value)
    if not validation["valid"]:
        raise ValueError(
            f"Invalid Channel Voice Profile {path}: "
            + "; ".join(validation["errors"])
        )
    return dict(value)


def load_active_profile_binding(
    selector_path: Path = ACTIVE_SELECTOR,
) -> dict[str, Any]:
    """Resolve the active profile without allowing path traversal."""
    selector_path = selector_path.resolve()
    selector = _load_json(selector_path)
    if not isinstance(selector, dict):
        raise ValueError("Channel Voice active selector must be an object")
    if selector.get("schema_version") != 1:
        raise ValueError("Channel Voice selector schema_version must equal 1")

    raw_profile_path = str(selector.get("profile_path") or "").strip()
    if not raw_profile_path:
        raise ValueError("Channel Voice selector requires profile_path")

    profile_root = selector_path.parent.resolve()
    profile_path = (profile_root / raw_profile_path).resolve()
    try:
        profile_path.relative_to(profile_root)
    except ValueError as exc:
        raise ValueError(
            "Channel Voice profile_path must stay inside channel_profiles"
        ) from exc

    if not profile_path.is_file():
        raise FileNotFoundError(profile_path)

    profile = load_profile(profile_path)
    return {
        "profile": profile,
        "binding": {
            "selector_path": str(selector_path),
            "profile_path": str(profile_path),
            "profile_sha256": _sha256(profile_path),
        },
        "apply_to_generation": profile["status"] == "APPROVED",
    }


def unconfigured_binding() -> dict[str, Any]:
    """Return the repository default fail-safe voice binding."""
    profile = load_profile(DEFAULT_UNCONFIGURED)
    return {
        "profile": profile,
        "binding": {
            "selector_path": None,
            "profile_path": str(DEFAULT_UNCONFIGURED.resolve()),
            "profile_sha256": _sha256(DEFAULT_UNCONFIGURED),
        },
        "apply_to_generation": False,
    }
