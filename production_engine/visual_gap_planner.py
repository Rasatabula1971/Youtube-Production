"""Plan unresolved visual gaps and cinematic premium-generation candidates.

This module never calls a paid provider and never authorizes spend.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json,safe_slug,sha256_file
HERE=Path(__file__).resolve().parent; OUTPUT=HERE/"output"; ROUGH=OUTPUT/"visual_rough_cuts"; REVIEWS=OUTPUT/"visual_rough_cut_reviews"; GAP=OUTPUT/"visual_gap_plans"; SUMMARY=OUTPUT/"visual_gap_plan_summary.json"
def _key(cid:str,fmt:str)->str:return f"{safe_slug(cid)}.{safe_slug(fmt)}"
def build(rough:dict[str,Any],review:dict[str,Any],rp:Path,reviewp:Path)->dict[str,Any]:
 if review.get("approved_for_gap_planning") is not True: raise ValueError("Rough cut is not approved for gap planning")
 if review.get("source_rough_cut_sha256")!=sha256_file(rp): raise ValueError("STALE_ROUGH_CUT_REVIEW")
 gaps=[]
 for s in rough.get("scenes",[]):
  if s.get("visual_assignment",{}).get("status")!="PLACEHOLDER": continue
  score=s.get("visual_value_score",{}); total=int(score.get("total") or 0); hero=bool(s.get("premium_generation_candidate")) and total>=17
  gaps.append({"shot_id":s.get("shot_id"),"time_range":s.get("time_range"),"story_purpose":s.get("story_purpose"),
   "desired_visual":s.get("desired_visual"),"cinematic_direction":s.get("cinematic_direction",{}),"visual_value_score":score,
   "resolution_class":"D_HERO_GENERATION" if hero else "B_OR_C_EXISTING_TREATMENT_OR_BRIDGE",
   "generation_priority":"HIGH" if hero else "LOW","premium_generation_recommended":hero,
   "premium_generation_authorized":False,"reason":s.get("visual_assignment",{}).get("reason")})
 gaps.sort(key=lambda x:int(x.get("visual_value_score",{}).get("total") or 0),reverse=True)
 return {"artifact":"visual_gap_plan","concept_id":rough.get("concept_id"),"format":rough.get("format"),
  "status":"READY_FOR_VISUAL_GAP_REVIEW","premium_generation_authorized":False,"gaps":gaps,
  "summary":{"unresolved":len(gaps),"hero_generation_candidates":sum(x["premium_generation_recommended"] for x in gaps)},
  "policy":{"retry_existing_or_treatment_before_paid_generation":True,"higgsfield_last_resort":True,"human_visual_spend_gate_required":True},
  "provenance":{"rough_cut":str(rp.resolve()),"rough_cut_sha256":sha256_file(rp),"rough_cut_review":str(reviewp.resolve()),"rough_cut_review_sha256":sha256_file(reviewp)}}
def prepare()->dict[str,Any]:
 GAP.mkdir(parents=True,exist_ok=True);items=[]
 for rp in sorted(ROUGH.glob("*.visual_rough_cut.json")) if ROUGH.exists() else []:
  rough=load_json(rp);key=_key(str(rough.get("concept_id") or ""),str(rough.get("format") or ""));reviewp=REVIEWS/f"{key}.visual_rough_cut_review.json"
  if not reviewp.exists():continue
  plan=build(rough,load_json(reviewp),rp,reviewp);dest=GAP/f"{key}.visual_gap_plan.json";atomic_write_json(dest,plan)
  items.append({"concept_id":plan["concept_id"],"format":plan["format"],**plan["summary"],"gap_plan":str(dest)})
 out={"status":"READY_FOR_VISUAL_GAP_REVIEW" if items else "WAITING_FOR_APPROVED_ROUGH_CUT","prepared":len(items),"items":items,"premium_generation_authorized":False};atomic_write_json(SUMMARY,out);return out
def main()->None:
 argparse.ArgumentParser().parse_args();print(json.dumps(prepare(),indent=2,ensure_ascii=False))
if __name__=="__main__":main()
