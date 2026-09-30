"""Revision loop for generated visual previews.

A human can approve, reject, or request a shot-local regeneration. The original
render remains immutable; every regeneration request increments the render
version and preserves the creative instruction history.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json,sha256_file

HERE=Path(__file__).resolve().parent;OUTPUT=HERE/"output"
RENDERS=OUTPUT/"generated_visual_previews";REVIEWS=OUTPUT/"generated_visual_reviews"

def _review_path(p:Path)->Path:
 REVIEWS.mkdir(parents=True,exist_ok=True);return REVIEWS/p.name.replace(".generated_visual_preview.json",".generated_visual_review.json")

def snapshot()->dict[str,Any]:
 items=[]
 for p in sorted(RENDERS.glob("*.generated_visual_preview.json")) if RENDERS.exists() else []:
  render=load_json(p);rp=_review_path(p);review=load_json(rp) if rp.exists() else {"history":[]}
  items.append({"render_file":str(p),"render_sha256":sha256_file(p),"render":render,"review":review})
 return {"status":"READY_FOR_GENERATED_VISUAL_REVIEW" if items else "WAITING_FOR_GENERATED_VISUALS","items":items}

def apply_action(*,render_file:str,decision:str,instruction:str="")->dict[str,Any]:
 p=Path(render_file)
 if not p.exists() or p.parent.resolve()!=RENDERS.resolve():raise ValueError("Invalid generated visual preview")
 if decision not in {"APPROVE","REGENERATE","REJECT"}:raise ValueError("Unsupported generated visual decision")
 if decision in {"REGENERATE","REJECT"} and not instruction.strip():raise ValueError("Tell the system what is wrong or what should change")
 render=load_json(p);rp=_review_path(p);review=load_json(rp) if rp.exists() else {"artifact":"generated_visual_review","shot_id":render.get("shot_id"),"history":[]}
 version=int(render.get("render_version") or 1)
 event={"render_version":version,"render_sha256":sha256_file(p),"decision":decision,"instruction":instruction.strip()}
 review["history"].append(event);review["current_decision"]=decision
 review["approved_for_final_assembly"]=decision=="APPROVE"
 review["next_render_version"]=version+1 if decision=="REGENERATE" else None
 review["regeneration_request"]={"shot_id":render.get("shot_id"),"base_render_version":version,"requested_render_version":version+1,
  "instruction":instruction.strip(),"preserve_storyboard_shot":True,"preserve_narration_timing":True} if decision=="REGENERATE" else None
 atomic_write_json(rp,review);return review
def main()->None:print(json.dumps(snapshot(),indent=2,ensure_ascii=False))
if __name__=="__main__":main()
