from pathlib import Path
import json
import pytest
from storyboard_review import revise

def test_shot_revision_versions_and_locks_timing(tmp_path,monkeypatch):
 import storyboard_review as sr
 story=tmp_path/"storyboards"; rev=tmp_path/"revisions";story.mkdir()
 monkeypatch.setattr(sr,"STORYBOARDS",story);monkeypatch.setattr(sr,"REVISIONS",rev)
 p=story/"c.long.storyboard.json"
 p.write_text(json.dumps({"concept_id":"c","format":"long","status":"READY_FOR_VISUAL_SEARCH","cards":[{"shot_id":"shot-001","beat_id":"b1","time_range":{"start_seconds":0,"end_seconds":4},"desired_visual":"old","search_terms":["old"],"cinematic_direction":{"camera_angle":"eye"}}]}),encoding="utf-8")
 out=revise(storyboard_file=str(p),shot_id="shot-001",instruction="lower and tighter",changes={"desired_visual":"hammer impact","cinematic_direction":{"camera_angle":"low"}})
 assert out["creative_version"]==2
 assert out["invalidation"]["other_shots"] is False
 assert out["narration_timing_changed"] is False
 assert json.loads(p.read_text())["cards"][0]["time_range"]["end_seconds"]==4

def test_shot_revision_rejects_timing_change(tmp_path,monkeypatch):
 import storyboard_review as sr
 story=tmp_path/"storyboards";rev=tmp_path/"revisions";story.mkdir()
 monkeypatch.setattr(sr,"STORYBOARDS",story);monkeypatch.setattr(sr,"REVISIONS",rev)
 p=story/"c.long.storyboard.json";p.write_text(json.dumps({"concept_id":"c","format":"long","cards":[{"shot_id":"s","time_range":{}}]}),encoding="utf-8")
 with pytest.raises(ValueError,match="locked"):
  revise(storyboard_file=str(p),shot_id="s",instruction="change time",changes={"time_range":{"start_seconds":1}})
