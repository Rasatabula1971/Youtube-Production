"""Publish package, Human Publish Gate and YouTube upload (D-142, D-143)."""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import publish_review as gate
import youtube_upload as uploader


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PublishTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = self.root = Path(tmp.name)
        for name in ("exports", "bundles", "verified"):
            (root / name).mkdir()
        self.video = root / "final.mp4"
        self.video.write_bytes(b"\x00\x00\x00\x18ftypmp42video")
        self.thumb = root / "thumb.jpg"
        self.thumb.write_bytes(b"\xff\xd8\xffthumb")
        self.export = root / "exports" / "c1.long_form.approved_final_export.json"
        self.export.write_text(json.dumps({"concept_id": "c1", "format": "long_form"}))
        self.approval = {
            "artifact": "approved_final_export", "status": "FINAL_EXPORT_APPROVED",
            "concept_id": "c1", "format": "long_form",
            "render_file": str(self.video), "render_sha256": sha(self.video),
        }
        (root / "bundles" / "c1.final_package.json").write_text(json.dumps({"packages": {"long_form": {
            "title_text": "Why F1 Brakes <Glow>", "viewer_promise": "See why racing brakes must run hot.",
            "thumbnail_image": {"image": str(self.thumb), "image_sha256": sha(self.thumb)},
        }}}))
        (root / "verified" / "c1.verified_research_package.json").write_text(json.dumps({"sources": [
            {"title": "Brake study", "url": "https://example.org/brakes"},
            {"title": "Dup", "url": "https://example.org/brakes"},
            {"title": "Not a web page", "url": "file:///etc/passwd"},
        ]}))
        self.config = json.loads(gate.CONFIG_FILE.read_text())
        for item in (
            patch.object(gate, "APPROVED_EXPORT_DIR", root / "exports"),
            patch.object(gate, "approval_is_current", side_effect=lambda path: copy.deepcopy(self.approval)),
            patch.object(gate, "FINAL_PACKAGES_DIR", root / "bundles"),
            patch.object(gate, "VERIFIED_DIR", root / "verified"),
            patch.object(gate, "APPROVED_DIR", root / "approved"),
            patch.object(gate, "PUBLISHED_DIR", root / "published"),
            patch.object(gate, "PENDING_UPLOADS_DIR", root / "pending"),
            patch.object(gate, "HISTORY_FILE", root / "history.jsonl"),
            patch.object(gate, "load_config", side_effect=lambda: copy.deepcopy(self.config)),
        ):
            item.start()
            self.addCleanup(item.stop)

    def item(self):
        return gate.snapshot()["items"][0]

    def approve(self, **metadata):
        return gate.apply_action(concept_id="c1", format="long_form", decision="APPROVE_PUBLISH", metadata=metadata)

    def test_draft_uses_the_final_package_sources_and_a_disclosure(self):
        item = self.item()
        meta = item["metadata"]
        self.assertEqual(item["status"], "PENDING")
        self.assertEqual(meta["title"], "Why F1 Brakes Glow")  # angle brackets removed
        self.assertIn("See why racing brakes must run hot.", meta["description"])
        self.assertIn("- Brake study: https://example.org/brakes", meta["description"])
        self.assertNotIn("file://", meta["description"])
        self.assertIn("AI-generated voice", meta["description"])
        self.assertEqual((meta["privacy_status"], meta["contains_synthetic_media"]), ("private", True))

    def test_approval_validates_youtube_limits_and_keeps_the_title(self):
        with self.assertRaisesRegex(ValueError, "5,000 bytes"):
            self.approve(description="x" * 5001)
        with self.assertRaisesRegex(ValueError, "500 characters"):
            self.approve(tags=["t" * 300, "u" * 300])
        with self.assertRaisesRegex(ValueError, "private, unlisted or public"):
            self.approve(privacy_status="secret")
        with self.assertRaisesRegex(ValueError, "future"):
            self.approve(publish_at="2020-01-01T00:00:00Z")
        later = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        with self.assertRaisesRegex(ValueError, "private until it publishes"):
            self.approve(publish_at=later, privacy_status="public")
        snap = self.approve(title="Clickbait", tags="brakes, f1", publish_at=later)
        meta = snap["items"][0]["metadata"]
        self.assertEqual(meta["title"], "Why F1 Brakes Glow")
        self.assertEqual(meta["tags"], ["brakes", "f1"])
        self.assertTrue(meta["publish_at"].endswith("Z"))
        self.assertEqual(snap["items"][0]["status"], "APPROVED_FOR_UPLOAD")

    def test_approval_is_bound_to_the_rendered_bytes(self):
        self.approve()
        self.approval["render_sha256"] = "changed"
        self.assertEqual(self.item()["status"], "PENDING")

    def test_hold_needs_a_note_and_manual_upload_is_recorded_once(self):
        with self.assertRaisesRegex(ValueError, "note"):
            gate.apply_action(concept_id="c1", format="long_form", decision="HOLD")
        with self.assertRaisesRegex(ValueError, "Approve the publish package"):
            gate.record_upload(concept_id="c1", format="long_form", youtube_video_id="abcdefghijk", method="MANUAL")
        self.approve()
        with self.assertRaisesRegex(ValueError, "11 letters"):
            gate.record_upload(concept_id="c1", format="long_form", youtube_video_id="bad id", method="MANUAL")
        snap = gate.record_upload(concept_id="c1", format="long_form", youtube_video_id="abcdefghijk", method="MANUAL")
        self.assertEqual(snap["items"][0]["status"], "PUBLISHED")
        self.assertEqual(snap["items"][0]["published"]["url"], "https://www.youtube.com/watch?v=abcdefghijk")
        with self.assertRaisesRegex(ValueError, "already"):
            gate.record_upload(concept_id="c1", format="long_form", youtube_video_id="abcdefghijk", method="MANUAL")
        with self.assertRaisesRegex(ValueError, "already published"):
            self.approve()


class UploadTests(PublishTests):
    def setUp(self):
        super().setUp()
        self.config["youtube_upload"]["enabled"] = True
        env = {"YOUTUBE_OAUTH_CLIENT_ID": "id", "YOUTUBE_OAUTH_CLIENT_SECRET": "secret", "YOUTUBE_OAUTH_REFRESH_TOKEN": "refresh"}
        item = patch.dict("os.environ", env)
        item.start()
        self.addCleanup(item.stop)
        self.requests = []
        self.bodies = []

    def fake_http(self, thumbnail_fails=False, interrupt_put=False, probe=None):
        """probe: what the session answers to a Content-Range bytes */size probe:
        ("308", "bytes=0-4") to resume after byte 4, "done" for a finished session,
        "gone" for a dead one."""
        state = {"interrupted": False}

        def http(request, timeout):
            url = request.full_url
            self.requests.append((request.get_method(), url, request))
            if url == uploader.TOKEN_URL:
                return {}, json.dumps({"access_token": "tok"}).encode()
            if url.startswith(uploader.UPLOAD_URL.split("?")[0]) and request.get_method() == "POST" and "thumbnails" not in url:
                return {"Location": "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=s1"}, b""
            if request.get_method() == "PUT":
                if request.get_header("Content-range", "").startswith("bytes */"):
                    if probe == "done":
                        return {}, json.dumps({"id": "VIDEOid_001"}).encode()
                    if probe == "gone":
                        raise uploader.UploadHttpError("YouTube refused the request (HTTP 404)", code=404)
                    if isinstance(probe, tuple):
                        raise uploader.UploadHttpError("Resume Incomplete (HTTP 308)", code=308, headers={"Range": probe[1]})
                    raise AssertionError("unexpected probe")
                if interrupt_put and not state["interrupted"]:
                    state["interrupted"] = True
                    raise ValueError("YouTube request failed: TimeoutError")
                self.bodies.append(request.data.read() if hasattr(request.data, "read") else request.data)
                return {}, json.dumps({"id": "VIDEOid_001"}).encode()
            if "thumbnails/set" in url:
                if thumbnail_fails:
                    raise ValueError("YouTube refused the request (HTTP 403)")
                return {}, b"{}"
            raise AssertionError(url)
        return http

    def puts(self):
        return [r for m, u, r in self.requests if m == "PUT"]

    def starts(self):
        return [r for m, u, r in self.requests if m == "POST" and "uploadType=resumable" in u]

    def test_an_interrupted_upload_is_saved_and_resumed_from_the_reported_byte(self):
        self.approve()
        with self.assertRaisesRegex(ValueError, "resumes where it stopped"):
            uploader.upload(concept_id="c1", format="long_form", http=self.fake_http(interrupt_put=True))
        pending = gate.pending_upload("c1", "long_form")
        self.assertEqual(pending["session"], "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=s1")
        self.assertEqual(pending["size"], self.video.stat().st_size)
        self.assertTrue(self.item()["pending_upload"])

        self.requests = []
        snap = uploader.upload(concept_id="c1", format="long_form", http=self.fake_http(probe=("308", "bytes=0-4")))
        self.assertEqual(self.starts(), [])  # no second session: no second video
        probe, continued = self.puts()
        self.assertEqual(probe.get_header("Content-range"), f"bytes */{self.video.stat().st_size}")
        size = self.video.stat().st_size
        self.assertEqual(continued.get_header("Content-range"), f"bytes 5-{size - 1}/{size}")
        self.assertEqual(continued.get_header("Content-length"), str(size - 5))
        self.assertEqual(self.bodies[-1], self.video.read_bytes()[5:])
        published = snap["items"][0]["published"]
        self.assertEqual((published["youtube_video_id"], published["resumed"]), ("VIDEOid_001", True))
        self.assertIsNone(gate.pending_upload("c1", "long_form"))
        self.assertIsNone(self.item()["pending_upload"])

    def test_a_session_that_already_finished_is_recorded_without_sending_bytes(self):
        self.approve()
        with self.assertRaises(ValueError):
            uploader.upload(concept_id="c1", format="long_form", http=self.fake_http(interrupt_put=True))
        self.requests = []
        snap = uploader.upload(concept_id="c1", format="long_form", http=self.fake_http(probe="done"))
        self.assertEqual(len(self.puts()), 1)
        self.assertEqual(self.starts(), [])
        self.assertEqual(snap["items"][0]["published"]["youtube_video_id"], "VIDEOid_001")

    def test_a_dead_session_starts_a_fresh_upload_once(self):
        self.approve()
        with self.assertRaises(ValueError):
            uploader.upload(concept_id="c1", format="long_form", http=self.fake_http(interrupt_put=True))
        self.requests = []
        snap = uploader.upload(concept_id="c1", format="long_form", http=self.fake_http(probe="gone"))
        self.assertEqual(len(self.starts()), 1)
        self.assertEqual(len(self.puts()), 2)  # the probe, then the whole file
        self.assertIsNone(self.puts()[1].get_header("Content-range"))
        self.assertFalse(snap["items"][0]["published"]["resumed"])
        self.assertIsNone(gate.pending_upload("c1", "long_form"))

    def test_a_session_opened_for_other_bytes_is_never_resumed_or_replaced_silently(self):
        """Audit 2: it may hold a finished private video; a person decides after checking Studio."""
        self.approve()
        gate.save_pending_upload({"concept_id": "c1", "format": "long_form", "session": "https://www.googleapis.com/x",
                                  "size": 1, "video_sha256": "other"})
        with self.assertRaisesRegex(ValueError, "Check YouTube Studio"):
            uploader.upload(concept_id="c1", format="long_form", http=self.fake_http())
        self.assertEqual((self.starts(), self.puts()), ([], []))
        gate.discard_pending_upload("c1", "long_form")
        snap = uploader.upload(concept_id="c1", format="long_form", http=self.fake_http())
        self.assertEqual(len(self.starts()), 1)
        self.assertEqual(snap["items"][0]["published"]["youtube_video_id"], "VIDEOid_001")
        history = [json.loads(line) for line in (self.root / "history.jsonl").read_text().splitlines()]
        self.assertIn("UPLOAD_DISCARDED", [e["decision"] for e in history])

    def test_a_failure_after_youtube_has_the_video_is_retried_by_recording_never_by_uploading(self):
        """Audit 2 F1: the id is kept until the publish record holds it."""
        self.approve()
        real_record = gate.record_upload
        with patch.object(gate, "record_upload", side_effect=ValueError("disk full")):
            with self.assertRaisesRegex(ValueError, "disk full"):
                uploader.upload(concept_id="c1", format="long_form", http=self.fake_http())
        pending = gate.pending_upload("c1", "long_form")
        self.assertEqual(pending["video_id"], "VIDEOid_001")
        with self.assertRaisesRegex(ValueError, "record it"):
            gate.discard_pending_upload("c1", "long_form")
        self.requests = []
        with patch.object(gate, "record_upload", side_effect=real_record):
            snap = uploader.upload(concept_id="c1", format="long_form", http=self.fake_http())
        self.assertEqual((self.starts(), self.puts()), ([], []))  # nothing uploaded again
        published = snap["items"][0]["published"]
        self.assertEqual((published["youtube_video_id"], published["resumed"]), ("VIDEOid_001", True))
        self.assertIsNone(gate.pending_upload("c1", "long_form"))

    def test_a_thumbnail_step_crash_still_records_the_video(self):
        self.approve()
        base = self.fake_http()

        def http(request, timeout):
            if "thumbnails/set" in request.full_url:
                raise OSError("connection reset")
            return base(request, timeout)

        snap = uploader.upload(concept_id="c1", format="long_form", http=http)
        published = snap["items"][0]["published"]
        self.assertEqual(published["youtube_video_id"], "VIDEOid_001")
        self.assertFalse(published["thumbnail_set"])
        self.assertIn("connection reset", published["thumbnail_error"])

    def test_an_upload_in_progress_pins_its_approval(self):
        """Audit 2 F2: no decision change while a session may be resumed."""
        self.approve()
        with self.assertRaises(ValueError):
            uploader.upload(concept_id="c1", format="long_form", http=self.fake_http(interrupt_put=True))
        with self.assertRaisesRegex(ValueError, "not finished"):
            self.approve(privacy_status="public")
        with self.assertRaisesRegex(ValueError, "not finished"):
            gate.apply_action(concept_id="c1", format="long_form", decision="HOLD", note="wait")

    def test_a_changed_approval_after_youtube_has_the_video_records_it_and_flags_the_metadata(self):
        self.approve()
        with patch.object(gate, "record_upload", side_effect=ValueError("approval moved")):
            with self.assertRaises(ValueError):
                uploader.upload(concept_id="c1", format="long_form", http=self.fake_http())
        self.approve(tags=["changed"])  # allowed: the video id is known
        self.requests = []
        snap = uploader.upload(concept_id="c1", format="long_form", http=self.fake_http())
        published = snap["items"][0]["published"]
        self.assertEqual(published["youtube_video_id"], "VIDEOid_001")
        self.assertFalse(published["metadata_matches_upload"])
        self.assertEqual(self.starts(), [])

    def test_connection_level_errors_reach_the_caller_as_value_errors(self):
        import http.client

        for exc in (http.client.RemoteDisconnected("gone"), http.client.IncompleteRead(b"x"), ConnectionResetError()):
            with self.subTest(exc=type(exc).__name__):
                with patch.object(uploader.urllib.request, "urlopen", side_effect=exc):
                    with self.assertRaisesRegex(ValueError, "YouTube request failed"):
                        uploader._http(uploader.urllib.request.Request("https://www.googleapis.com/x"), 5)

    def test_upload_is_off_until_enabled_and_authorized(self):
        self.config["youtube_upload"]["enabled"] = False
        self.assertIn("off", " ".join(uploader.status()["problems"]))
        self.approve()
        with self.assertRaisesRegex(ValueError, "not available"):
            uploader.upload(concept_id="c1", format="long_form", http=self.fake_http())
        self.assertEqual(self.requests, [])

    def test_upload_sends_the_approved_package_and_records_the_video(self):
        later = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        self.approve(publish_at=later, tags=["brakes"])
        snap = uploader.upload(concept_id="c1", format="long_form", http=self.fake_http())
        start = next(r for m, u, r in self.requests if m == "POST" and "uploadType=resumable" in u)
        body = json.loads(start.data)
        self.assertEqual(body["snippet"]["title"], "Why F1 Brakes Glow")
        self.assertEqual(body["status"]["privacyStatus"], "private")
        self.assertTrue(body["status"]["containsSyntheticMedia"])
        self.assertIn("publishAt", body["status"])
        self.assertEqual(start.get_header("Authorization"), "Bearer tok")
        published = snap["items"][0]["published"]
        self.assertEqual((published["youtube_video_id"], published["method"], published["thumbnail_set"]), ("VIDEOid_001", "YOUTUBE_DATA_API", True))
        with self.assertRaisesRegex(ValueError, "already published"):
            uploader.upload(concept_id="c1", format="long_form", http=self.fake_http())

    def test_changed_video_bytes_are_refused(self):
        self.approve()
        self.video.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "changed since approval"):
            uploader.upload(concept_id="c1", format="long_form", http=self.fake_http())

    def test_thumbnail_failure_still_records_the_uploaded_video(self):
        self.approve()
        snap = uploader.upload(concept_id="c1", format="long_form", http=self.fake_http(thumbnail_fails=True))
        published = snap["items"][0]["published"]
        self.assertEqual(published["youtube_video_id"], "VIDEOid_001")
        self.assertFalse(published["thumbnail_set"])


if __name__ == "__main__":
    unittest.main()
