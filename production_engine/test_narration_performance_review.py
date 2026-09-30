import json
import pytest
import narration_performance_review as npr

def test_segment_revision_is_local_and_words_locked(tmp_path,monkeypatch):
 manifests=tmp_path/"manifests";revs=tmp_path/"revs";manifests.mkdir()
 monkeypatch.setattr(npr,"MANIFESTS",manifests);monkeypatch.setattr(npr,"REVISIONS",revs)
 p=manifests/"c.long.narration_preview.json"
 p.write_text(json.dumps({"concept_id":"c","format":"long","segments":[
  {"segment_id":"s1","immutable_narration":"Locked words.","delivery":{"emotion":"neutral","intensity":4,"speed":1,"pause_before_ms":0,"pause_after_ms":0,"emphasis_terms":[]}},
  {"segment_id":"s2","immutable_narration":"Other words.","delivery":{"emotion":"neutral","intensity":4,"speed":1,"pause_before_ms":0,"pause_after_ms":0,"emphasis_terms":[]}}]}),encoding="utf-8")
 out=npr.revise(manifest_file=str(p),segment_id="s1",instruction="quieter",delivery_changes={"emotion":"calm","speed":0.9})
 data=json.loads(p.read_text())
 assert out["performance_version"]==2 and out["invalidation"]["other_segments"] is False
 assert data["segments"][0]["immutable_narration"]=="Locked words."
 assert data["segments"][1]["delivery"]["speed"]==1

def test_words_cannot_change_at_performance_gate(tmp_path,monkeypatch):
 manifests=tmp_path/"manifests";revs=tmp_path/"revs";manifests.mkdir()
 monkeypatch.setattr(npr,"MANIFESTS",manifests);monkeypatch.setattr(npr,"REVISIONS",revs)
 p=manifests/"x.json";p.write_text(json.dumps({"segments":[{"segment_id":"s","immutable_narration":"x","delivery":{}}]}),encoding="utf-8")
 with pytest.raises(ValueError,match="Rework Script"):
  npr.revise(manifest_file=str(p),segment_id="s",instruction="new words",delivery_changes={"text":"new"})
