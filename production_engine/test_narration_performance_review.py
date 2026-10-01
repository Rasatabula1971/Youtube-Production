import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import json
import pytest
import narration_performance_review as npr

def test_segment_revision_is_local_and_words_locked(tmp_path,monkeypatch):
 manifests=tmp_path/"manifests";revs=tmp_path/"revs";audio=tmp_path/"audio";responses=tmp_path/"responses";approved=tmp_path/"approved";manifests.mkdir();audio.mkdir();responses.mkdir();approved.mkdir()
 monkeypatch.setattr(npr,"MANIFESTS",manifests);monkeypatch.setattr(npr,"REVISIONS",revs);monkeypatch.setattr(npr,"AUDIO",audio);monkeypatch.setattr(npr,"RESPONSES",responses);monkeypatch.setattr(npr,"APPROVED",approved)
 p=manifests/"c.long.narration_preview.json"
 wav=audio/"c.long.preview.wav";wav.write_bytes(b"old audio");wav.with_suffix(".meta.json").write_text("{}",encoding="utf-8")
 (responses/"c.long.preview_review.json").write_text("{}",encoding="utf-8");(approved/"c.long.approved_preview.json").write_text("{}",encoding="utf-8")
 p.write_text(json.dumps({"concept_id":"c","format":"long","segments":[
  {"segment_id":"s1","immutable_narration":"Locked words.","delivery":{"emotion":"neutral","intensity":4,"speed":1,"pause_before_ms":0,"pause_after_ms":0,"emphasis_terms":[]}},
  {"segment_id":"s2","immutable_narration":"Other words.","delivery":{"emotion":"neutral","intensity":4,"speed":1,"pause_before_ms":0,"pause_after_ms":0,"emphasis_terms":[]}}]}),encoding="utf-8")
 out=npr.revise(manifest_file=str(p),segment_id="s1",instruction="quieter",delivery_changes={"emotion":"calm","speed":0.9})
 data=json.loads(p.read_text())
 assert out["performance_version"]==2 and out["invalidation"]["other_segments"] is False
 assert data["segments"][0]["immutable_narration"]=="Locked words."
 assert data["segments"][1]["delivery"]["speed"]==1
 assert not wav.exists()
 assert not wav.with_suffix(".meta.json").exists()
 assert not (responses/"c.long.preview_review.json").exists()
 assert not (approved/"c.long.approved_preview.json").exists()

def test_words_cannot_change_at_performance_gate(tmp_path,monkeypatch):
 manifests=tmp_path/"manifests";revs=tmp_path/"revs";manifests.mkdir()
 monkeypatch.setattr(npr,"MANIFESTS",manifests);monkeypatch.setattr(npr,"REVISIONS",revs);monkeypatch.setattr(npr,"AUDIO",tmp_path/"audio");monkeypatch.setattr(npr,"RESPONSES",tmp_path/"responses");monkeypatch.setattr(npr,"APPROVED",tmp_path/"approved")
 p=manifests/"x.json";p.write_text(json.dumps({"segments":[{"segment_id":"s","immutable_narration":"x","delivery":{}}]}),encoding="utf-8")
 with pytest.raises(ValueError,match="Rework Script"):
  npr.revise(manifest_file=str(p),segment_id="s",instruction="new words",delivery_changes={"text":"new"})
