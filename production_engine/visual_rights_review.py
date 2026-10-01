"""Human rights/context gate for selected creator/editorial visual excerpts."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any
from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json, sha256_file

HERE=Path(__file__).resolve().parent
OUTPUT=HERE/"output"
CANDIDATE_REVIEW_DIR=OUTPUT/"visual_candidate_reviews"
SEARCH_RESULT_DIR=OUTPUT/"visual_search_results"
RIGHTS_DIR=OUTPUT/"visual_rights_reviews"

def _path(review_path: Path)->Path:
    RIGHTS_DIR.mkdir(parents=True,exist_ok=True)
    return RIGHTS_DIR/review_path.name.replace(".visual_candidate_review.json",".visual_rights_review.json")

def _candidate(review: dict[str,Any], shot_id:str)->dict[str,Any]|None:
    result_path=Path(str(review.get("source_result") or ""))
    if not result_path.exists() or result_path.parent.resolve()!=SEARCH_RESULT_DIR.resolve():
        return None
    result=load_json(result_path)
    decision=review.get("decisions",{}).get(shot_id,{})
    cid=str(decision.get("candidate_id") or "")
    shot=next((x for x in result.get("shots",[]) if str(x.get("shot_id"))==shot_id),{})
    result_fingerprint=hashlib.sha256(
        json.dumps(
            shot,
            sort_keys=True,
            separators=(",",":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    if decision.get("result_fingerprint") != result_fingerprint:
        return None
    candidate=next((x for x in shot.get("candidates",[]) if str(x.get("candidate_id"))==cid),None)
    if candidate is None:
        return None
    candidate_fingerprint=hashlib.sha256(
        json.dumps(
            candidate,
            sort_keys=True,
            separators=(",",":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    if decision.get("candidate_fingerprint") != candidate_fingerprint:
        return None
    return candidate

def snapshot()->dict[str,Any]:
    items=[]
    for review_path in sorted(CANDIDATE_REVIEW_DIR.glob("*.visual_candidate_review.json")) if CANDIDATE_REVIEW_DIR.exists() else []:
        review=load_json(review_path); rights_path=_path(review_path)
        rights=load_json(rights_path) if rights_path.exists() else {"decisions":{}}
        pending=[]
        for shot_id,decision in review.get("decisions",{}).items():
            if decision.get("status")=="SELECTED_PENDING_RIGHTS_CONTEXT_GATE":
                pending.append({"shot_id":shot_id,"candidate":_candidate(review,shot_id),"decision":rights.get("decisions",{}).get(shot_id)})
        if pending:
            items.append({"concept_id":review.get("concept_id"),"format":review.get("format"),"candidate_review_file":str(review_path),
                "candidate_review_sha256":sha256_file(review_path),"pending":pending})
    return {"status":"READY_FOR_RIGHTS_CONTEXT_REVIEW" if items else "NO_RIGHTS_CONTEXT_REVIEW_REQUIRED","items":items}

def apply_action(*,candidate_review_file:str,shot_id:str,decision:str,transformative_purpose:str="",context_note:str="")->dict[str,Any]:
    review_path=Path(candidate_review_file)
    if not review_path.exists() or review_path.parent.resolve()!=CANDIDATE_REVIEW_DIR.resolve():
        raise ValueError("Invalid candidate review file")
    review=load_json(review_path); selected=review.get("decisions",{}).get(shot_id)
    if not selected or selected.get("status")!="SELECTED_PENDING_RIGHTS_CONTEXT_GATE":
        raise ValueError("Shot is not awaiting rights/context review")
    if decision not in {"APPROVE_CONTEXT_USE","REJECT_USE"}:
        raise ValueError("Unsupported rights/context decision")
    if decision=="APPROVE_CONTEXT_USE" and not transformative_purpose.strip():
        raise ValueError("Approval requires a documented transformative/editorial purpose")
    candidate=_candidate(review,shot_id)
    if not candidate:
        raise ValueError("Selected candidate is unavailable or stale")
    rights_path=_path(review_path)
    rights=load_json(rights_path) if rights_path.exists() else {"artifact":"visual_rights_review","concept_id":review.get("concept_id"),
        "format":review.get("format"),"source_candidate_review":str(review_path.resolve()),"source_candidate_review_sha256":sha256_file(review_path),"decisions":{}}
    if rights.get("source_candidate_review_sha256")!=sha256_file(review_path):
        raise ValueError("STALE_RIGHTS_REVIEW: candidate selections changed")
    rights["decisions"][shot_id]={"decision":decision,"candidate_id":candidate.get("candidate_id"),
        "source_url":candidate.get("source_url"),"creator":candidate.get("creator"),"license":candidate.get("license"),
        "transformative_purpose":transformative_purpose.strip(),"context_note":context_note.strip(),
        "approved_for_rough_cut":decision=="APPROVE_CONTEXT_USE",
        "policy_note":"Human approval records editorial intent; it is not a legal determination of fair use."}
    expected=sum(x.get("status")=="SELECTED_PENDING_RIGHTS_CONTEXT_GATE" for x in review.get("decisions",{}).values())
    rights["summary"]={"required":expected,"decided":len(rights["decisions"]),
        "approved":sum(x.get("approved_for_rough_cut") is True for x in rights["decisions"].values())}
    rights["status"]="COMPLETE" if len(rights["decisions"])==expected else "REVIEW_IN_PROGRESS"
    atomic_write_json(rights_path,rights); return rights

def main()->None:
    print(json.dumps(snapshot(),indent=2,ensure_ascii=False))
if __name__=="__main__": main()
