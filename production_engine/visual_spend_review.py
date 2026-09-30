"""Human visual spend gate for premium-generation gaps."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json,sha256_file
HERE=Path(__file__).resolve().parent;OUTPUT=HERE/"output";GAPS=OUTPUT/"visual_gap_plans";SPEND=OUTPUT/"visual_spend_reviews"
def _path(p:Path)->Path:
 SPEND.mkdir(parents=True,exist_ok=True);return SPEND/p.name.replace(".visual_gap_plan.json",".visual_spend_review.json")
def snapshot()->dict[str,Any]:
 items=[]
 for p in sorted(GAPS.glob("*.visual_gap_plan.json")) if GAPS.exists() else []:
  plan=load_json(p);sp=_path(p);review=load_json(sp) if sp.exists() else {"decisions":{}}
  hero=[x for x in plan.get("gaps",[]) if x.get("premium_generation_recommended")]
  items.append({"concept_id":plan.get("concept_id"),"format":plan.get("format"),"gap_plan_file":str(p),"gap_plan_sha256":sha256_file(p),"hero_candidates":hero,"decisions":review.get("decisions",{})})
 return {"status":"READY_FOR_VISUAL_SPEND_GATE" if any(x["hero_candidates"] for x in items) else "NO_PREMIUM_GENERATION_REQUIRED","items":items}
def apply_action(*,gap_plan_file:str,shot_id:str,decision:str,max_cost_usd:float=0,note:str="")->dict[str,Any]:
 p=Path(gap_plan_file)
 if not p.exists() or p.parent.resolve()!=GAPS.resolve():raise ValueError("Invalid gap plan")
 if decision not in {"AUTHORIZE_GENERATION","KEEP_PLACEHOLDER","RETRY_EXISTING"}:raise ValueError("Unsupported visual spend decision")
 plan=load_json(p);gap=next((x for x in plan.get("gaps",[]) if str(x.get("shot_id"))==shot_id),None)
 if not gap:raise ValueError("Unknown visual gap")
 if decision=="AUTHORIZE_GENERATION":
  if gap.get("premium_generation_recommended") is not True:raise ValueError("Shot is not a premium-generation candidate")
  if max_cost_usd<=0 or max_cost_usd>10:raise ValueError("Per-shot authorization must be > $0 and <= $10 USD")
 sp=_path(p);review=load_json(sp) if sp.exists() else {"artifact":"visual_spend_review","concept_id":plan.get("concept_id"),"format":plan.get("format"),"source_gap_plan":str(p.resolve()),"source_gap_plan_sha256":sha256_file(p),"decisions":{}}
 if review.get("source_gap_plan_sha256")!=sha256_file(p):raise ValueError("STALE_VISUAL_SPEND_REVIEW")
 review["decisions"][shot_id]={"decision":decision,"max_cost_usd":round(max_cost_usd,2) if decision=="AUTHORIZE_GENERATION" else 0,
  "note":note.strip(),"paid_generation_authorized":decision=="AUTHORIZE_GENERATION","cinematic_direction":gap.get("cinematic_direction",{}),"desired_visual":gap.get("desired_visual")}
 review["authorized_max_total_usd"]=round(sum(float(x.get("max_cost_usd") or 0) for x in review["decisions"].values()),2)
 if review["authorized_max_total_usd"]>10:raise ValueError("Automated visual authorization hard cap is $10 USD total")
 review["status"]="REVIEW_IN_PROGRESS";atomic_write_json(sp,review);return review
def main()->None:print(json.dumps(snapshot(),indent=2,ensure_ascii=False))
if __name__=="__main__":main()
