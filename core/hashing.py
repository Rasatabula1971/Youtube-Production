"""Content hashes used for provenance (D-175).

Every function here replaced byte-for-byte-equivalent copies across the
engines; core/test_core_helpers.py pins their outputs. Changing an output here
makes every stored provenance hash stale.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path | str) -> str:
    """SHA-256 of a file's bytes, read in 1 MiB chunks."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    """SHA-256 of canonical JSON: sorted keys, no spaces, UTF-8, non-ASCII kept."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_text(value: str) -> str:
    """SHA-256 of a string's UTF-8 bytes."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
