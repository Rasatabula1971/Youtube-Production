"""Run current zero-cost visual discovery requests to the Human Candidate Gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json
from visual_search import (
    OUTPUT_DIR,
    RAW_DIR,
    RESULT_DIR,
    compile_results,
    request_fingerprint,
    search_request_is_current,
    search_result_is_current,
    sha256_file,
)
from visual_search_adapters import discover_with_diagnostics

SUMMARY_FILE = OUTPUT_DIR / "visual_search_acquire_summary.json"


def _load_dict(path: Path) -> dict[str, Any] | None:
    try:
        value = load_json(path)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _result_path_for(request_path: Path) -> Path:
    return RESULT_DIR / request_path.name.replace(
        ".visual_search_request.json",
        ".visual_search_results.json",
    )


def _raw_path_for(request_path: Path) -> Path:
    return RAW_DIR / request_path.name.replace(
        ".visual_search_request.json",
        ".visual_search_raw.json",
    )


def _current_requests() -> list[tuple[Path, dict[str, Any]]]:
    items: list[tuple[Path, dict[str, Any]]] = []
    if not RESULT_DIR.exists():
        return items
    for path in sorted(RESULT_DIR.glob("*.visual_search_request.json")):
        state = search_request_is_current(path)
        if state is None:
            continue
        items.append((path, state[0]))
    return items


def snapshot() -> dict[str, Any]:
    expected = 0
    current = 0
    no_search_required = 0
    items: list[dict[str, Any]] = []
    for request_path, request in _current_requests():
        status = str(request.get("status") or "")
        if status == "NO_SEARCH_REQUIRED":
            no_search_required += 1
            continue
        if status != "SEARCH_REQUIRED":
            continue
        expected += 1
        result_path = _result_path_for(request_path)
        is_current = search_result_is_current(result_path) is not None
        if is_current:
            current += 1
        items.append(
            {
                "concept_id": request.get("concept_id"),
                "format": request.get("format"),
                "request": str(request_path),
                "result": str(result_path),
                "current": is_current,
            }
        )

    return {
        "status": (
            "SEARCH_COMPLETE"
            if expected > 0 and current == expected
            else "READY_TO_SEARCH"
            if expected > 0
            else "NO_SEARCH_REQUIRED"
            if no_search_required > 0
            else "WAITING_FOR_SEARCH_REQUESTS"
        ),
        "expected": expected,
        "current": current,
        "no_search_required": no_search_required,
        "items": items,
        "paid_calls_allowed": False,
    }


def _checkpoint_raw(
    *,
    destination: Path,
    request: dict[str, Any],
    request_path: Path,
    shots: dict[str, list[dict[str, Any]]],
    shot_fingerprints: dict[str, str],
    provider_errors: dict[str, list[dict[str, str]]],
    status: str,
) -> None:
    atomic_write_json(
        destination,
        {
            "artifact": "visual_search_raw",
            "concept_id": request.get("concept_id"),
            "format": request.get("format"),
            "status": status,
            "search_request": str(request_path.resolve()),
            "search_request_sha256": sha256_file(request_path),
            "search_request_fingerprint": request_fingerprint(request),
            "shots": shots,
            "shot_fingerprints": shot_fingerprints,
            "provider_errors": provider_errors,
            "policy": {
                "discovery_only": True,
                "no_media_downloaded": True,
                "paid_calls_allowed": False,
            },
        },
    )


def acquire() -> dict[str, Any]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    provider_error_count = 0
    stale_skipped = 0

    request_paths = (
        sorted(RESULT_DIR.glob("*.visual_search_request.json"))
        if RESULT_DIR.exists()
        else []
    )
    for request_path in request_paths:
        current_state = search_request_is_current(request_path)
        if current_state is None:
            stale_skipped += 1
            result_path = _result_path_for(request_path)
            if result_path.exists():
                result_path.unlink()
            continue

        request = current_state[0]
        if request.get("status") == "NO_SEARCH_REQUIRED":
            items.append(
                {
                    "concept_id": request.get("concept_id"),
                    "format": request.get("format"),
                    "status": "NO_SEARCH_REQUIRED",
                    "candidates": 0,
                    "shots_searched": 0,
                    "shots_reused": 0,
                    "provider_errors": 0,
                }
            )
            continue
        if request.get("status") != "SEARCH_REQUIRED":
            stale_skipped += 1
            continue

        initial_request_hash = sha256_file(request_path)
        destination = _raw_path_for(request_path)
        previous = _load_dict(destination) or {}
        previous_shots = (
            previous.get("shots", {})
            if isinstance(previous.get("shots"), dict)
            else {}
        )
        previous_fingerprints = (
            previous.get("shot_fingerprints", {})
            if isinstance(previous.get("shot_fingerprints"), dict)
            else {}
        )
        previous_errors = (
            previous.get("provider_errors", {})
            if isinstance(previous.get("provider_errors"), dict)
            else {}
        )

        shots: dict[str, list[dict[str, Any]]] = {}
        shot_fingerprints: dict[str, str] = {}
        provider_errors: dict[str, list[dict[str, str]]] = {}
        searched = 0
        reused = 0
        stale_during_run = False

        for shot in request.get("shots", []):
            if not isinstance(shot, dict):
                continue

            refreshed = search_request_is_current(request_path)
            if (
                refreshed is None
                or sha256_file(request_path) != initial_request_hash
            ):
                stale_during_run = True
                break

            shot_id = str(shot.get("shot_id") or "").strip()
            fingerprint = str(shot.get("shot_fingerprint") or "").strip()
            if not shot_id or not fingerprint:
                provider_errors.setdefault(shot_id or "unknown", []).append(
                    {
                        "provider": "pipeline",
                        "error_type": "InvalidSearchShot",
                        "error": "Search shot requires shot_id and shot_fingerprint.",
                    }
                )
                continue

            shot_fingerprints[shot_id] = fingerprint
            prior_errors = previous_errors.get(shot_id, [])
            if (
                previous_fingerprints.get(shot_id) == fingerprint
                and isinstance(previous_shots.get(shot_id), list)
                and not prior_errors
            ):
                shots[shot_id] = [
                    item
                    for item in previous_shots[shot_id]
                    if isinstance(item, dict)
                ]
                reused += 1
                _checkpoint_raw(
                    destination=destination,
                    request=request,
                    request_path=request_path,
                    shots=shots,
                    shot_fingerprints=shot_fingerprints,
                    provider_errors=provider_errors,
                    status="PARTIAL_SEARCH",
                )
                continue

            terms = [
                str(value).strip()
                for value in shot.get("search_terms", [])
                if str(value).strip()
            ]
            desired = str(shot.get("desired_visual") or "").strip()
            instruction = str(shot.get("creative_instruction") or "").strip()
            query_parts = list(terms)
            if desired and desired not in query_parts:
                query_parts.append(desired)
            if instruction:
                query_parts.append(instruction)
            query = " ".join(query_parts).strip()[:180]

            if not query:
                shots[shot_id] = []
                provider_errors[shot_id] = [
                    {
                        "provider": "pipeline",
                        "error_type": "EmptySearchQuery",
                        "error": "Current storyboard shot produced no visual search query.",
                    }
                ]
                provider_error_count += 1
            else:
                try:
                    discovery = discover_with_diagnostics(
                        query,
                        int(shot.get("max_candidates_per_source") or 5),
                    )
                    providers = discovery.get("providers", {})
                    errors = discovery.get("errors", [])
                    shots[shot_id] = [
                        candidate
                        for group in providers.values()
                        if isinstance(group, list)
                        for candidate in group
                        if isinstance(candidate, dict)
                    ] if isinstance(providers, dict) else []
                    provider_errors[shot_id] = [
                        item
                        for item in errors
                        if isinstance(item, dict)
                    ] if isinstance(errors, list) else []
                    provider_error_count += len(provider_errors[shot_id])
                except Exception as exc:
                    shots[shot_id] = []
                    provider_errors[shot_id] = [
                        {
                            "provider": "pipeline",
                            "error_type": type(exc).__name__,
                            "error": str(exc)[:500],
                        }
                    ]
                    provider_error_count += 1
                searched += 1

            _checkpoint_raw(
                destination=destination,
                request=request,
                request_path=request_path,
                shots=shots,
                shot_fingerprints=shot_fingerprints,
                provider_errors=provider_errors,
                status="PARTIAL_SEARCH",
            )

        result_path = _result_path_for(request_path)
        if stale_during_run:
            if result_path.exists():
                result_path.unlink()
            items.append(
                {
                    "concept_id": request.get("concept_id"),
                    "format": request.get("format"),
                    "status": "STALE_DURING_SEARCH",
                    "candidates": sum(len(value) for value in shots.values()),
                    "shots_searched": searched,
                    "shots_reused": reused,
                    "provider_errors": sum(
                        len(value) for value in provider_errors.values()
                    ),
                }
            )
            continue

        _checkpoint_raw(
            destination=destination,
            request=request,
            request_path=request_path,
            shots=shots,
            shot_fingerprints=shot_fingerprints,
            provider_errors=provider_errors,
            status="SEARCH_COMPLETE",
        )
        raw = _load_dict(destination)
        if raw is None:
            raise RuntimeError("Visual search checkpoint could not be reloaded")
        compiled = compile_results(request, request_path, raw)
        atomic_write_json(result_path, compiled)

        if search_result_is_current(result_path) is None:
            result_path.unlink(missing_ok=True)
            raise RuntimeError(
                "Compiled visual search result failed current-provenance validation"
            )

        items.append(
            {
                "concept_id": request.get("concept_id"),
                "format": request.get("format"),
                "status": "SEARCH_COMPLETE",
                "raw_results": str(destination),
                "result": str(result_path),
                "candidates": sum(len(value) for value in shots.values()),
                "shots_searched": searched,
                "shots_reused": reused,
                "provider_errors": sum(
                    len(value) for value in provider_errors.values()
                ),
            }
        )

    state = snapshot()
    summary = {
        **state,
        "processed": len(items),
        "provider_errors": provider_error_count,
        "stale_requests_skipped": stale_skipped,
        "items": items,
        "paid_calls_allowed": False,
    }
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Acquire zero-cost storyboard visual candidates"
    )
    parser.add_argument("--mode", choices=("acquire",), required=True)
    parser.parse_args()
    print(json.dumps(acquire(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
