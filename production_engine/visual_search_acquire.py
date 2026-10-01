"""Run configured zero-cost visual discovery adapters for storyboard requests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json
from visual_search import RESULT_DIR, RAW_DIR, SUMMARY_FILE, compile_results
from visual_search_adapters import discover


def acquire() -> dict:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    requests = sorted(RESULT_DIR.glob("*.visual_search_request.json")) if RESULT_DIR.exists() else []
    items = []
    for request_path in requests:
        request = load_json(request_path)
        destination = RAW_DIR / request_path.name.replace(
            ".visual_search_request.json",
            ".visual_search_raw.json",
        )
        previous = load_json(destination) if destination.exists() else {}
        previous_shots = (
            previous.get("shots", {})
            if isinstance(previous, dict)
            and isinstance(previous.get("shots"), dict)
            else {}
        )
        previous_fingerprints = (
            previous.get("shot_fingerprints", {})
            if isinstance(previous, dict)
            and isinstance(previous.get("shot_fingerprints"), dict)
            else {}
        )
        shots = {}
        shot_fingerprints = {}
        searched = 0
        reused = 0
        for shot in request.get("shots", []):
            shot_id = str(shot.get("shot_id") or "")
            fingerprint = str(shot.get("shot_fingerprint") or "")
            shot_fingerprints[shot_id] = fingerprint
            if (
                shot_id
                and fingerprint
                and previous_fingerprints.get(shot_id) == fingerprint
                and isinstance(previous_shots.get(shot_id), list)
            ):
                shots[shot_id] = previous_shots[shot_id]
                reused += 1
                continue
            terms = [
                str(x).strip()
                for x in shot.get("search_terms", [])
                if str(x).strip()
            ]
            query = (
                " ".join(terms)[:100]
                or str(shot.get("desired_visual") or "").strip()
            )
            found = discover(
                query,
                int(shot.get("max_candidates_per_source") or 5),
            )
            shots[shot_id] = [
                candidate
                for group in found.values()
                for candidate in group
            ]
            searched += 1
        raw = {
            "artifact": "visual_search_raw",
            "concept_id": request.get("concept_id"),
            "format": request.get("format"),
            "shots": shots,
            "shot_fingerprints": shot_fingerprints,
            "policy": {
                "discovery_only": True,
                "no_media_downloaded": True,
                "paid_calls_allowed": False,
            },
        }
        atomic_write_json(destination, raw)
        compiled = compile_results(request, request_path, raw)
        compiled_path = RESULT_DIR / request_path.name.replace(".visual_search_request.json", ".visual_search_results.json")
        atomic_write_json(compiled_path, compiled)
        items.append({
            "concept_id": request.get("concept_id"),
            "format": request.get("format"),
            "raw_results": str(destination),
            "candidates": sum(len(x) for x in shots.values()),
            "shots_searched": searched,
            "shots_reused": reused,
        })
    summary = {"status": "SEARCH_COMPLETE" if items else "WAITING_FOR_SEARCH_REQUESTS", "processed": len(items), "items": items, "paid_calls_allowed": False}
    atomic_write_json(SUMMARY_FILE, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire zero-cost storyboard visual candidates")
    parser.add_argument("--mode", choices=("acquire",), required=True)
    parser.parse_args()
    print(json.dumps(acquire(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
