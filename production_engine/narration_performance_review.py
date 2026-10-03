"""Human Creative Director edits for narration performance segments.

Approved narration words remain immutable. Performance edits are segment-local,
versioned, and invalidate only the affected free-preview segment/downstream mix.
"""
from __future__ import annotations
import copy
from pathlib import Path
from typing import Any
from pipeline_integrity import atomic_write_json
from voice_performance import load_json,sha256_file

HERE=Path(__file__).resolve().parent;OUTPUT=HERE/"output"
MANIFESTS=OUTPUT/"narration_preview_manifests";REVISIONS=OUTPUT/"narration_performance_revisions"
AUDIO=OUTPUT/"narration_preview_audio";RESPONSES=OUTPUT/"narration_preview_review_responses";APPROVED=OUTPUT/"approved_narration_previews"
ALLOWED={"emotion","intensity","speed","pause_before_ms","pause_after_ms","emphasis_terms"}

def _path(p:Path)->Path:
 REVISIONS.mkdir(parents=True,exist_ok=True);return REVISIONS/p.name.replace(".narration_preview.json",".performance_revisions.json")
def snapshot()->dict[str,Any]:
 items=[]
 for p in sorted(MANIFESTS.glob("*.narration_preview.json")) if MANIFESTS.exists() else []:
  m=load_json(p);rp=_path(p);hist=load_json(rp) if rp.exists() else {"segments":{}}
  items.append({"concept_id":m.get("concept_id"),"format":m.get("format"),"manifest_file":str(p),"manifest_sha256":sha256_file(p),
   "segments":m.get("segments",[]),"revision_history":hist.get("segments",{})})
 return {"status":"READY_FOR_NARRATION_CREATIVE_DIRECTION" if items else "WAITING_FOR_PREVIEW_MANIFEST","items":items}

def revise(*,manifest_file:str,segment_id:str,instruction:str,delivery_changes:dict[str,Any])->dict[str,Any]:
 p=Path(manifest_file)
 if not p.exists() or p.parent.resolve()!=MANIFESTS.resolve():raise ValueError("Invalid narration preview manifest")
 if not instruction.strip():raise ValueError("Performance revision requires an instruction")
 if "immutable_narration" in delivery_changes or "narration" in delivery_changes or "text" in delivery_changes:
  raise ValueError("Narration wording is locked here; use Rework Script")
 m=load_json(p);segments=m.get("segments",[]);idx=next((i for i,x in enumerate(segments) if str(x.get("segment_id"))==segment_id),None)
 if idx is None:raise ValueError("Unknown narration segment")
 seg=copy.deepcopy(segments[idx]);before=copy.deepcopy(seg);delivery=copy.deepcopy(seg.get("delivery",{}))
 for k,v in delivery_changes.items():
  if k not in ALLOWED:raise ValueError(f"Unsupported performance field: {k}")
  if k=="emphasis_terms":
   if not isinstance(v,list):raise ValueError("emphasis_terms must be a list")
   delivery[k]=[str(x).strip() for x in v if str(x).strip()]
  elif k in {"intensity","pause_before_ms","pause_after_ms"}:delivery[k]=int(v)
  elif k=="speed":
   speed=float(v)
   if not 0.5<=speed<=2.0:raise ValueError("Preview speed must be between 0.5 and 2.0")
   delivery[k]=speed
  else:delivery[k]=str(v).strip()
 seg["delivery"]=delivery
 if seg==before:raise ValueError("Revision made no performance changes")
 rp=_path(p);hist=load_json(rp) if rp.exists() else {"artifact":"narration_performance_revision_history","concept_id":m.get("concept_id"),"format":m.get("format"),"segments":{}}
 versions=hist["segments"].setdefault(segment_id,[]);version=len(versions)+2
 versions.append({"from_version":version-1,"to_version":version,"instruction":instruction.strip(),"before_delivery":before.get("delivery",{}),"after_delivery":delivery})
 seg["performance_version"]=version;seg["creative_instruction"]=instruction.strip();segments[idx]=seg;m["segments"]=segments
 m.setdefault("policy",{})["segment_local_performance_revision"]=True;m["paid_calls_allowed"]=False
 atomic_write_json(p,m);hist["current_manifest_sha256"]=sha256_file(p);atomic_write_json(rp,hist)
 key=p.name.replace(".narration_preview.json","")
 audio=AUDIO/f"{key}.preview.wav";meta=audio.with_suffix(".meta.json")
 response=RESPONSES/f"{key}.preview_review.json";approved=APPROVED/f"{key}.approved_preview.json"
 for stale in (audio,meta,response,approved):
  if stale.exists():stale.unlink()
 return {"status":"NARRATION_SEGMENT_REVISED","segment_id":segment_id,"performance_version":version,"segment":seg,
  "invalidation":{"free_preview_segment":True,"draft_audio_mix":True,"listen_gate_approval":True,"paid_quote":True,"other_segments":False},
  "narration_words_changed":False,"manifest_sha256":sha256_file(p)}
