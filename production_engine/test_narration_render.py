from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import narration_preview_review
import narration_render
from voice_performance import sha256_text


def approved_spec(*, configured: bool = True) -> dict:
    narration = "These exact words must not change."
    return {
        "artifact": "voice_performance_spec",
        "concept_id": "concept-1",
        "format": "long_form",
        "title": "Locked title",
        "validation": {"valid": True, "errors": []},
        "performance_gate": {"status": "PERFORMANCE_SPEC_APPROVED"},
        "beats": [
            {
                "beat_id": "b1",
                "beat_index": 0,
                "purpose": "setup",
                "claim_ids": ["c1"],
                "source_section_ids": ["s1"],
                "immutable_narration": narration,
                "immutable_narration_sha256": sha256_text(narration),
            }
        ],
        "directions": [
            {
                "beat_id": "b1",
                "emotion": "curious",
                "intensity": 0.3,
                "speed": 1.0,
                "pause_before_ms": 100,
                "pause_after_ms": 250,
                "emphasis_terms": ["exact words"],
            }
        ],
        "voice_identity": {
            "provider": "higgsfield",
            "voice_id": "voice-1" if configured else None,
            "license_reference": "licence-1" if configured else None,
            "calibration_artifact": "calibration.json" if configured else None,
        },
        "approved_provenance": {"voice_review_request_sha256": "review-sha"},
    }


def config(*, verified: bool) -> dict:
    return {
        "provider": "higgsfield",
        "provider_contract": {
            "schema_verified": verified,
            "endpoint": "https://api.example.test/narration" if verified else None,
            "documentation_url": "https://docs.example.test/narration" if verified else None,
            "verified_at": "2026-09-29" if verified else None,
        },
        "max_regenerations_per_segment": 2,
        "quote_currency": "USD",
        "require_provider_quote": True,
        "audio_qc": {
            "ffmpeg_binary": "ffmpeg",
            "ffprobe_binary": "ffprobe",
            "duration_tolerance_ratio": 0.3,
            "unexpected_silence_seconds": 0.8,
            "silence_noise_db": -50.0,
            "clipping_peak_dbfs": -0.1,
        },
    }


class NarrationRenderTests(unittest.TestCase):
    def build(self, *, verified: bool = True, configured: bool = True) -> tuple[dict, Path, tempfile.TemporaryDirectory]:
        temp = tempfile.TemporaryDirectory()
        path = Path(temp.name) / "approved.json"
        payload = approved_spec(configured=configured)
        path.write_text(json.dumps(payload), encoding="utf-8")
        sound_brief = Path(temp.name) / "sound_design_brief.json"
        sound_brief.write_text("{}", encoding="utf-8")
        with (
            patch.object(
                narration_render,
                "_preview_approved",
                return_value=True,
            ),
            patch.object(
                narration_render,
                "current_brief_for_branch",
                return_value=(sound_brief, {}),
            ),
        ):
            request = narration_render.build_render_request(
                payload,
                path,
                config(verified=verified),
            )
        return request, path, temp


    def test_free_preview_approval_is_mandatory_before_final_quote(self) -> None:
        temp = tempfile.TemporaryDirectory()
        try:
            path = Path(temp.name) / "approved.json"
            payload = approved_spec()
            path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(narration_render, "_preview_approved", return_value=False):
                request = narration_render.build_render_request(
                    payload,
                    path,
                    config(verified=True),
                )
            self.assertEqual(request["status"], "BLOCKED")
            self.assertIn("FREE_PREVIEW_NOT_APPROVED", request["render_blockers"])
            self.assertFalse(request["paid_render_authorized"])
        finally:
            temp.cleanup()

    def test_preview_approval_is_bound_to_current_voice_spec_and_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            voice_dir = root / "voice"
            preview_approved = root / "preview_approved"
            preview_manifests = root / "preview_manifests"
            preview_audio = root / "preview_audio"
            for directory in (
                voice_dir,
                preview_approved,
                preview_manifests,
                preview_audio,
            ):
                directory.mkdir()

            spec_path = voice_dir / "concept-1.long_form.approved_voice_spec.json"
            spec_path.write_text(json.dumps(approved_spec()), encoding="utf-8")
            spec_hash = narration_render.sha256_file(spec_path)
            manifest_path = (
                preview_manifests
                / "concept-1.long_form.narration_preview.json"
            )
            manifest_path.write_text(
                json.dumps(
                    {
                        "concept_id": "concept-1",
                        "format": "long_form",
                        "provenance": {
                            "approved_voice_spec": str(spec_path.resolve()),
                            "approved_voice_spec_sha256": spec_hash,
                        },
                    }
                ),
                encoding="utf-8",
            )
            audio_path = preview_audio / "concept-1.long_form.preview.wav"
            audio_path.write_bytes(b"preview audio")
            audio_hash = narration_render.sha256_file(audio_path)
            audio_path.with_suffix(".meta.json").write_text(
                json.dumps(
                    {
                        "manifest_sha256": narration_render.sha256_file(
                            manifest_path
                        ),
                        "audio_sha256": audio_hash,
                    }
                ),
                encoding="utf-8",
            )
            approval_path = (
                preview_approved
                / "concept-1.long_form.approved_preview.json"
            )
            approval_path.write_text(
                json.dumps(
                    {
                        "decision": "APPROVE_FINAL",
                        "concept_id": "concept-1",
                        "format": "long_form",
                        "preview_manifest_sha256": narration_render.sha256_file(
                            manifest_path
                        ),
                        "preview_audio_sha256": audio_hash,
                        "approved_voice_spec_sha256": spec_hash,
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(
                    narration_render,
                    "APPROVED_PREVIEW_DIR",
                    preview_approved,
                ),
                patch.object(
                    narration_render,
                    "PREVIEW_MANIFEST_DIR",
                    preview_manifests,
                ),
                patch.object(
                    narration_render,
                    "PREVIEW_RENDER_DIR",
                    preview_audio,
                ),
                patch.object(
                    narration_preview_review,
                    "APPROVED_VOICE_DIR",
                    voice_dir,
                ),
            ):
                self.assertTrue(
                    narration_render._preview_approved(
                        "concept-1",
                        "long_form",
                        spec_path,
                    )
                )
                changed = approved_spec()
                changed["title"] = "Changed after preview approval"
                spec_path.write_text(json.dumps(changed), encoding="utf-8")
                self.assertFalse(
                    narration_render._preview_approved(
                        "concept-1",
                        "long_form",
                        spec_path,
                    )
                )

    def test_current_sound_design_brief_is_required_before_quote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "approved.json"
            payload = approved_spec()
            path.write_text(json.dumps(payload), encoding="utf-8")
            with (
                patch.object(
                    narration_render,
                    "_preview_approved",
                    return_value=True,
                ),
                patch.object(
                    narration_render,
                    "current_brief_for_branch",
                    return_value=None,
                ),
            ):
                request = narration_render.build_render_request(
                    payload,
                    path,
                    config(verified=True),
                )

        self.assertEqual(request["status"], "BLOCKED")
        self.assertIn(
            "SOUND_DESIGN_BRIEF_NOT_CURRENT",
            request["render_blockers"],
        )

    def test_invalid_existing_quote_returns_to_waiting_instead_of_crashing(self) -> None:
        request, request_path, temp = self.build()
        try:
            request_path.write_text(json.dumps(request), encoding="utf-8")
            quote_path = Path(temp.name) / "quote.json"
            quote_path.write_text(
                json.dumps(
                    {
                        "artifact": "narration_provider_quote",
                        "concept_id": "concept-1",
                        "format": "long_form",
                        "provider": "higgsfield",
                        "render_request_sha256": "old-request",
                        "currency": "USD",
                        "initial_estimate_usd": 1.0,
                        "worst_case_estimate_usd": 2.0,
                        "attempts_per_segment": 3,
                        "quote_reference": "old",
                        "quoted_at": "2026-09-29T12:00:00Z",
                        "quote_source": "provider_dry_run",
                    }
                ),
                encoding="utf-8",
            )
            estimate = narration_render.build_cost_estimate(
                request,
                request_path,
                config(verified=True),
                quote_path,
            )
            self.assertEqual(
                estimate["status"],
                "WAITING_FOR_PROVIDER_QUOTE",
            )
            self.assertIn("stale", estimate["quote_error"].lower())
        finally:
            temp.cleanup()

    def test_unverified_provider_contract_fails_closed(self) -> None:
        request, _, temp = self.build(verified=False)
        try:
            self.assertEqual(request["status"], "BLOCKED")
            self.assertIn(
                "PROVIDER_NARRATION_CONTRACT_UNVERIFIED",
                request["render_blockers"],
            )
            self.assertFalse(request["paid_render_authorized"])
        finally:
            temp.cleanup()

    def test_missing_voice_prerequisites_block_render(self) -> None:
        request, _, temp = self.build(configured=False)
        try:
            self.assertIn("VOICE_ID_MISSING", request["render_blockers"])
            self.assertIn(
                "VOICE_LICENSE_REFERENCE_MISSING",
                request["render_blockers"],
            )
            self.assertIn(
                "VOICE_CALIBRATION_ARTIFACT_MISSING",
                request["render_blockers"],
            )
        finally:
            temp.cleanup()

    def test_render_request_derives_duration_from_locked_text_and_speed(self) -> None:
        request, _, temp = self.build()
        try:
            segment = request["segments"][0]
            self.assertIn("expected_duration_seconds", segment)
            self.assertGreater(segment["expected_duration_seconds"], 0)
            self.assertEqual(
                segment["expected_duration_seconds"],
                narration_render.expected_speech_duration_seconds(
                    segment["immutable_narration"],
                    segment["delivery"]["speed"],
                ),
            )
        finally:
            temp.cleanup()

    def test_render_request_preserves_exact_narration(self) -> None:
        request, _, temp = self.build()
        try:
            segment = request["segments"][0]
            self.assertEqual(
                segment["immutable_narration"],
                "These exact words must not change.",
            )
            self.assertEqual(
                segment["immutable_narration_sha256"],
                sha256_text(segment["immutable_narration"]),
            )
            self.assertEqual(request["max_attempts_per_segment"], 3)
        finally:
            temp.cleanup()

    def test_no_quote_means_no_spend_gate(self) -> None:
        request, request_path, temp = self.build()
        try:
            request_path.write_text(json.dumps(request), encoding="utf-8")
            estimate = narration_render.build_cost_estimate(
                request,
                request_path,
                config(verified=True),
                None,
            )
            self.assertEqual(estimate["status"], "WAITING_FOR_PROVIDER_QUOTE")
            self.assertIsNone(estimate["worst_case_estimate_usd"])
        finally:
            temp.cleanup()

    def test_current_provider_quote_unlocks_spend_gate(self) -> None:
        request, request_path, temp = self.build()
        try:
            request_path.write_text(json.dumps(request), encoding="utf-8")
            quote_path = Path(temp.name) / "quote.json"
            quote = {
                "artifact": "narration_provider_quote",
                "concept_id": "concept-1",
                "format": "long_form",
                "provider": "higgsfield",
                "render_request_sha256": narration_render.sha256_file(request_path),
                "currency": "USD",
                "initial_estimate_usd": 1.25,
                "worst_case_estimate_usd": 3.75,
                "attempts_per_segment": 3,
                "quote_reference": "provider-quote-123",
                "quoted_at": "2026-09-29T12:00:00Z",
                "quote_source": "provider_dry_run",
            }
            quote_path.write_text(json.dumps(quote), encoding="utf-8")
            estimate = narration_render.build_cost_estimate(
                request,
                request_path,
                config(verified=True),
                quote_path,
            )
            self.assertEqual(estimate["status"], "READY_FOR_SPEND_GATE")
            self.assertEqual(estimate["worst_case_estimate_usd"], 3.75)
        finally:
            temp.cleanup()

    def test_stale_quote_is_rejected(self) -> None:
        request, request_path, temp = self.build()
        try:
            request_path.write_text(json.dumps(request), encoding="utf-8")
            quote = {
                "artifact": "narration_provider_quote",
                "concept_id": "concept-1",
                "format": "long_form",
                "provider": "higgsfield",
                "render_request_sha256": "stale",
                "currency": "USD",
                "initial_estimate_usd": 1.0,
                "worst_case_estimate_usd": 3.0,
                "attempts_per_segment": 3,
                "quote_reference": "q",
                "quoted_at": "2026-09-29T12:00:00Z",
                "quote_source": "provider_dry_run",
            }
            with self.assertRaisesRegex(ValueError, "stale"):
                narration_render.validate_quote(
                    quote,
                    request,
                    request_path,
                    config(verified=True),
                )
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()


def local_config() -> dict:
    payload = config(verified=True)
    payload["provider"] = "kokoro_local"
    payload["provider_contract"] = {
        "schema_verified": True,
        "endpoint": None,
        "documentation_url": "https://huggingface.co/hexgrad/Kokoro-82M",
        "verified_at": "2026-10-04",
    }
    payload["provider_adapter"] = {
        "kind": "LOCAL_KOKORO", "model": "hexgrad/Kokoro-82M", "voice_id": "af_heart",
        "api_key_env": None, "price_per_1000_characters_usd": 0.0,
    }
    return payload


class LocalProviderTests(NarrationRenderTests):
    """A local renderer verifies its contract without an endpoint and quotes itself $0 (D-168)."""

    def test_local_contract_needs_no_endpoint_but_a_paid_one_does(self) -> None:
        self.assertTrue(narration_render.provider_is_local(local_config()))
        self.assertTrue(narration_render.provider_contract_verified(local_config()))
        paid = config(verified=True)
        paid["provider_contract"]["endpoint"] = None
        self.assertFalse(narration_render.provider_contract_verified(paid))

    def test_local_quote_is_valid_and_unlocks_the_spend_gate_at_zero(self) -> None:
        payload = approved_spec(configured=True)
        payload["voice_identity"]["provider"] = "kokoro_local"
        temp = tempfile.TemporaryDirectory()
        try:
            path = Path(temp.name) / "approved.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            brief = Path(temp.name) / "brief.json"
            brief.write_text("{}", encoding="utf-8")
            with (
                patch.object(narration_render, "_preview_approved", return_value=True),
                patch.object(narration_render, "current_brief_for_branch", return_value=(brief, {})),
            ):
                request = narration_render.build_render_request(payload, path, local_config())
            self.assertEqual(request["render_blockers"], [])
            request_path = Path(temp.name) / "request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            quote = narration_render.local_quote(request, request_path, local_config())
            quote_path = Path(temp.name) / "quote.json"
            quote_path.write_text(json.dumps(quote), encoding="utf-8")
            estimate = narration_render.build_cost_estimate(request, request_path, local_config(), quote_path)
        finally:
            temp.cleanup()
        self.assertEqual(estimate["status"], "READY_FOR_SPEND_GATE")
        self.assertEqual(estimate["worst_case_estimate_usd"], 0.0)
        self.assertEqual(estimate["provider_quote"]["quote_reference"], narration_render.LOCAL_QUOTE_REFERENCE)

    def test_prepare_writes_the_local_quote_and_refreshes_it_when_the_request_changes(self) -> None:
        payload = approved_spec(configured=True)
        payload["voice_identity"]["provider"] = "kokoro_local"
        temp = tempfile.TemporaryDirectory()
        try:
            root = Path(temp.name)
            approved = root / "approved_voice"
            approved.mkdir()
            (approved / "concept-1.long_form.approved_voice_spec.json").write_text(json.dumps(payload), encoding="utf-8")
            brief = root / "brief.json"
            brief.write_text("{}", encoding="utf-8")
            with (
                patch.object(narration_render, "APPROVED_VOICE_DIR", approved),
                patch.object(narration_render, "REQUESTS_DIR", root / "requests"),
                patch.object(narration_render, "QUOTE_TEMPLATES_DIR", root / "templates"),
                patch.object(narration_render, "QUOTES_DIR", root / "quotes"),
                patch.object(narration_render, "ESTIMATES_DIR", root / "estimates"),
                patch.object(narration_render, "SUMMARY_FILE", root / "summary.json"),
                patch.object(narration_render, "_preview_approved", return_value=True),
                patch.object(narration_render, "current_brief_for_branch", return_value=(brief, {})),
            ):
                first = narration_render.prepare(local_config())
                quotes = sorted((root / "quotes").glob("*.json"))
                self.assertEqual(len(quotes), 1)
                written = json.loads(quotes[0].read_text(encoding="utf-8"))
                self.assertEqual(written["worst_case_estimate_usd"], 0.0)
                # A changed request gets a fresh quote bound to the new hash.
                payload["beats"][0]["immutable_narration"] = "Different words now."
                payload["beats"][0]["immutable_narration_sha256"] = sha256_text("Different words now.")
                (approved / "concept-1.long_form.approved_voice_spec.json").write_text(json.dumps(payload), encoding="utf-8")
                second = narration_render.prepare(local_config())
                refreshed = json.loads(quotes[0].read_text(encoding="utf-8"))
        finally:
            temp.cleanup()
        self.assertEqual(first["status"], "READY_FOR_SPEND_GATE")
        self.assertEqual(second["status"], "READY_FOR_SPEND_GATE")
        self.assertNotEqual(written["render_request_sha256"], refreshed["render_request_sha256"])
