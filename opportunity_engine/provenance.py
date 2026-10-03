"""Deterministic identity and provenance helpers for Opportunity Packets."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

# Fields that change on every rebuild and must not change a packet's identity.
VOLATILE_FIELDS = frozenset({"created_at", "packet_sha256"})


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_artifact(path: Path, role: str) -> dict[str, str]:
    """Record one input file by role, path and content hash."""
    return {"role": role, "path": str(path), "sha256": file_sha256(path)}


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "untitled"


def opportunity_id(source_type: str, *parts: str) -> str:
    """Stable id: the same source evidence always yields the same id."""
    cleaned = [_slug(str(part)) for part in parts if str(part or "").strip()]
    if not cleaned:
        raise ValueError("opportunity_id needs at least one identifying part")
    return "opp_" + source_type.lower() + "__" + "__".join(cleaned)


def packet_sha256(packet: dict[str, Any]) -> str:
    """Hash the evidence content of a packet, ignoring rebuild timestamps."""
    return canonical_sha256(
        {key: value for key, value in packet.items() if key not in VOLATILE_FIELDS}
    )
