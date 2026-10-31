"""Tell current Story / Script work from leftovers (D-182).

Each prepare step keeps only the requests of concepts still in the batch, but
the plans and drafts made from older requests stay on disk. Script requests
used to be built from every story plan on disk, so an old study set's scripts
were drafted again, used the free models' per-minute allowance, and appeared
at the Script Gate; a dropped concept would have done the same.

This lives outside story_script_engine.py and story_plan_engine.py on
purpose: those files are fingerprinted as validation contracts, and changing
them would mark every current plan and draft stale.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core.hashing import sha256_file
from core.jsonio import load_json
from story_script_engine.story_plan_engine import (
    STORY_PLAN_REQUESTS_DIR,
    STORY_PLANS_DIR,
)
from story_script_engine.story_script_engine import REQUESTS_DIR


def made_from_current_request(provenance: Any, requests_dir: Path) -> bool:
    """Whether the request an artifact was made from still exists unchanged.

    The request is looked up by file name in its folder, so moving the
    project folder does not make current work look stale.
    """
    if not isinstance(provenance, dict):
        return False
    source = str(provenance.get("request_source") or "").strip()
    expected = provenance.get("request_sha256")
    if not source or not expected:
        return False
    path = requests_dir / re.split(r"[\\/]", source)[-1]
    return path.is_file() and sha256_file(path) == expected


def current_story_plan_concepts(
    story_plans_dir: Path | None = None,
    story_plan_requests_dir: Path | None = None,
) -> set[str]:
    """Concepts whose story plan was made from their current story plan request."""
    story_plans_dir = story_plans_dir or STORY_PLANS_DIR
    story_plan_requests_dir = story_plan_requests_dir or STORY_PLAN_REQUESTS_DIR
    concepts: set[str] = set()
    if not story_plans_dir.exists():
        return concepts
    for path in story_plans_dir.glob("*.story_plan.json"):
        try:
            plan = load_json(path)
        except (OSError, ValueError):
            continue
        if not isinstance(plan, dict):
            continue
        if made_from_current_request(plan.get("plan_provenance"), story_plan_requests_dir):
            concept_id = str(plan.get("concept_id") or "").strip()
            if concept_id:
                concepts.add(concept_id)
    return concepts


def prune_leftover_script_requests(
    requests_dir: Path | None = None,
    story_plans_dir: Path | None = None,
    story_plan_requests_dir: Path | None = None,
) -> list[str]:
    """Delete script requests whose concept has no current story plan.

    Returns the deleted file names. Drafts are kept: they are no longer
    drafted or reviewed because their request is gone.
    """
    requests_dir = requests_dir or REQUESTS_DIR
    if not requests_dir.exists():
        return []
    current = current_story_plan_concepts(story_plans_dir, story_plan_requests_dir)
    removed: list[str] = []
    for path in sorted(requests_dir.glob("*.script_request.json")):
        try:
            request = load_json(path)
        except (OSError, ValueError):
            continue
        concept_id = str((request or {}).get("concept_id") or "").strip()
        if concept_id not in current:
            path.unlink()
            removed.append(path.name)
    return removed


def current_script_drafts(
    drafts_dir: Path,
    requests_dir: Path | None = None,
) -> list[Path]:
    """Script drafts made from a script request that is still current."""
    requests_dir = requests_dir or REQUESTS_DIR
    if not drafts_dir.exists():
        return []
    kept: list[Path] = []
    for path in sorted(drafts_dir.glob("*.script_draft.json")):
        try:
            draft = load_json(path)
        except (OSError, ValueError):
            continue
        if isinstance(draft, dict) and made_from_current_request(
            draft.get("draft_provenance"), requests_dir
        ):
            kept.append(path)
    return kept
