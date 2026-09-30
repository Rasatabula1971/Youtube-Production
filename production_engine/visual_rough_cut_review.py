"""Human rough-cut gate and unresolved visual gap handoff."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json,sha256_file
HERE=Path(__file__).resolve().parent; OUTPUT=HERE/"output"; ROUGH=OUTPUT/"visual_rough_cuts"; REVIEW=OUTPUT/"visual_rough_cut_reviews"

def _path(p:Path)->Path:
 REVIEW.mkdir(parents=True,exist_ok=True); return REVIEW/p.name.replace(".visual_rough_cut.json",".visual_rough_cut_review.json")
def snapshot()->dict[str,Any]:
 items=[]
 for p in sorted(ROUGH.glob("*.visual_rough_cut.json")) if ROUGH.exists() else []:
  rough=load_json(p); rp=_path(p); review=load_json(rp) if rp.exists() else None
  items.append({"concept_id":rough.get("concept_id"),"format":rough.get("format"),"rough_cut_file":str(p),"rough_cut_sha256":sha256_file(p),
   "summary":rough.get("summary",{}),"scenes":rough.get("scenes",[]),"decision":review})
 return {"status":"READY_FOR_HUMAN_ROUGH_CUT_GATE" if items else "WAITING_FOR_ROUGH_CUT","items":items}
def apply_action(*,rough_cut_file:str,decision:str,note:str="")->dict[str,Any]:
 p=Path(rough_cut_file)
 if not p.exists() or p.parent.resolve()!=ROUGH.resolve(): raise ValueError("Invalid rough cut")
 if decision not in {"APPROVE_WITH_GAPS","REWORK_VISUAL","REWORK_PACING","REWORK_AUDIO"}: raise ValueError("Unsupported rough-cut decision")
 if decision!="APPROVE_WITH_GAPS" and not note.strip(): raise ValueError("Rework decision requires a note")
 rough=load_json(p)
 out={"artifact":"visual_rough_cut_review","concept_id":rough.get("concept_id"),"format":rough.get("format"),"decision":decision,"note":note.strip(),
  "source_rough_cut":str(p.resolve()),"source_rough_cut_sha256":sha256_file(p),
  "approved_for_gap_planning":decision=="APPROVE_WITH_GAPS","premium_generation_authorized":False}
 atomic_write_json(_path(p),out); return out
def main()->None: print(json.dumps(snapshot(),indent=2,ensure_ascii=False))
if __name__=="__main__":main()
