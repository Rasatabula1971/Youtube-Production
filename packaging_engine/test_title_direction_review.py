from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import title_direction_review as module


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TitleDirectionReviewTests(unittest.TestCase):
    def candidates(self, request_path: Path):
        def item(fmt: str, angle: str):
            return {
                "title_id": f"{fmt}-{angle}",
                "candidate_id": f"{fmt}-{angle}",
                "format": fmt,
                "title_text": f"{angle.title()} Brake Mystery",
                "title": f"{angle.title()} Brake Mystery",
                "psychological_angle": angle,
                "angle": angle,
                "primary_driver": angle,
                "secondary_driver": "specificity",
                "core_claim": "Temperature changes braking behavior.",
                "evidence_refs": ["clm001"],
                "character_count": len(f"{angle.title()} Brake Mystery"),
                "search_intent": "HYBRID",
            }

        angles = ["curiosity", "stakes", "unexpected", "mystery", "payoff"]
        return {
            "artifact": "title_direction_candidates",
            "schema_version": "1.0",
            "count": 1,
            "concepts": [
                {
                    "artifact": "title_direction_candidate_set",
                    "concept_id": "c1",
                    "titles": {
                        "short": [item("short", a) for a in angles],
                        "long_form": [item("long_form", a) for a in angles],
                    },
                    "request_file": str(request_path.resolve()),
                    "request_sha256": module.sha256_file(request_path),
                    "response_provenance": {
                        "request_sha256": module.sha256_file(request_path),
                    },
                }
            ],
            "rejected": [],
        }

    def patched(self, root: Path):
        request_dir = root / "requests"
        response_dir = root / "responses"
        candidates_file = root / "title_direction_candidates.json"
        state_file = root / "title_direction_gate_state.json"
        approved_file = root / "selected_title_directions.json"
        history_dir = root / "history"
        summary_file = root / "summary.json"
        request_path = write_json(
            request_dir / "c1.title_direction_request.json",
            {
                "artifact": "title_direction_request",
                "concept_id": "c1",
                "human_rework_iteration": 0,
            },
        )
        response_path = write_json(
            response_dir / "c1.title_direction_response.json",
            {
                "concept_id": "c1",
                "response_provenance": {
                    "request_sha256": module.sha256_file(request_path)
                },
            },
        )
        write_json(candidates_file, self.candidates(request_path))
        patches = (
            patch.object(module, "REQUESTS_DIR", request_dir),
            patch.object(module, "RESPONSES_DIR", response_dir),
            patch.object(module, "CANDIDATES_FILE", candidates_file),
            patch.object(module, "STATE_FILE", state_file),
            patch.object(module, "APPROVED_FILE", approved_file),
            patch.object(module, "HISTORY_DIR", history_dir),
            patch.object(module, "SUMMARY_FILE", summary_file),
        )
        return patches, {
            "request_path": request_path,
            "response_path": response_path,
            "candidates_file": candidates_file,
            "state_file": state_file,
            "approved_file": approved_file,
            "history_dir": history_dir,
        }

    def selections(self):
        return {
            "short": {
                "title_id": "short-stakes",
                "title_text": "Cold Brakes Can Betray You",
            },
            "long_form": {
                "title_id": "long_form-curiosity",
                "title_text": "Why Better Racing Brakes Can Feel Worse When Cold",
            },
        }

    def test_accept_records_direction_metadata_and_editable_wording(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches, paths = self.patched(root)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
                module.prepare_state()
                snapshot = module.apply_action(
                    concept_id="c1",
                    decision="ACCEPT",
                    selected_titles=self.selections(),
                    note="",
                )
                approved = json.loads(
                    paths["approved_file"].read_text(encoding="utf-8")
                )

        self.assertTrue(snapshot["ready"])
        selected = approved["selected"][0]
        self.assertTrue(selected["final_wording_editable_later"])
        self.assertEqual(
            selected["direction_contract"],
            "PREFERRED_TITLE_AND_PSYCHOLOGICAL_DIRECTION_NOT_FINAL_WORDING",
        )
        short = selected["selected_titles"]["short"]
        self.assertEqual(short["selected_title_id"], "short-stakes")
        self.assertEqual(short["selected_psychological_angle"], "stakes")
        self.assertEqual(short["selected_primary_driver"], "stakes")
        self.assertTrue(short["wording_edited"])

    def test_accept_requires_both_short_and_long_form_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches, _paths = self.patched(root)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
                module.prepare_state()
                with self.assertRaisesRegex(ValueError, "long_form"):
                    module.apply_action(
                        concept_id="c1",
                        decision="ACCEPT",
                        selected_titles={
                            "short": self.selections()["short"],
                        },
                    )

    def test_rework_preserves_upstream_and_invalidates_only_title_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches, paths = self.patched(root)
            upstream = root / "approved_script.json"
            upstream.write_bytes(b"immutable-approved-script")
            before = upstream.read_bytes()
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
                module.prepare_state()
                result = module.apply_action(
                    concept_id="c1",
                    decision="REWORK",
                    note="Use stronger consequence without inventing danger.",
                )
                request = json.loads(
                    paths["request_path"].read_text(encoding="utf-8")
                )
                upstream_after = upstream.read_bytes()

        self.assertEqual(result["status"], "TITLE_DIRECTION_REWORK_REQUESTED")
        self.assertEqual(upstream_after, before)
        self.assertEqual(request["human_rework_iteration"], 1)
        self.assertEqual(
            request["human_rework_scope"],
            "TITLE_DIRECTIONS_ONLY",
        )
        self.assertFalse(paths["response_path"].exists())
        self.assertFalse(paths["candidates_file"].exists())

    def test_duplicate_accept_is_idempotent_and_conflict_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches, paths = self.patched(root)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
                module.prepare_state()
                first = module.apply_action(
                    concept_id="c1",
                    decision="ACCEPT",
                    selected_titles=self.selections(),
                )
                history_before = list(
                    paths["history_dir"].glob(
                        "*.title_direction_selection.json"
                    )
                )
                duplicate = module.apply_action(
                    concept_id="c1",
                    decision="ACCEPT",
                    selected_titles=self.selections(),
                )
                history_after = list(
                    paths["history_dir"].glob(
                        "*.title_direction_selection.json"
                    )
                )
                changed = self.selections()
                changed["short"] = {
                    "title_id": "short-curiosity",
                    "title_text": "A Different Direction",
                }
                with self.assertRaisesRegex(
                    ValueError,
                    "Conflicting duplicate",
                ):
                    module.apply_action(
                        concept_id="c1",
                        decision="ACCEPT",
                        selected_titles=changed,
                    )

        self.assertTrue(first["ready"])
        self.assertTrue(duplicate["ready"])
        self.assertEqual(len(history_before), 1)
        self.assertEqual(len(history_after), 1)

    def test_changed_candidates_invalidate_saved_gate_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches, paths = self.patched(root)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
                module.prepare_state()
                state_before = module.snapshot()
                self.assertEqual(
                    state_before["status"],
                    "AWAITING_HUMAN_TITLE_DIRECTION",
                )
                payload = json.loads(
                    paths["candidates_file"].read_text(encoding="utf-8")
                )
                payload["concepts"][0]["titles"]["short"][0]["title_text"] = (
                    "Changed candidate"
                )
                write_json(paths["candidates_file"], payload)
                stale = module.snapshot()

        self.assertEqual(stale["status"], "READY_TO_PREPARE")
        self.assertFalse(stale["complete"])

    def test_accepted_selection_is_archived_append_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches, paths = self.patched(root)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
                module.prepare_state()
                module.apply_action(
                    concept_id="c1",
                    decision="ACCEPT",
                    selected_titles=self.selections(),
                )
                history = list(
                    paths["history_dir"].glob(
                        "*.title_direction_selection.json"
                    )
                )

        self.assertEqual(len(history), 1)


if __name__ == "__main__":
    unittest.main()
