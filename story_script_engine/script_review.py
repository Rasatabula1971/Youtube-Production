"""Human Script Gate."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from story_script_engine import DRAFTS_DIR, OUTPUT_DIR, load_json, safe_slug, sha256_file

REVIEW_REQUESTS_DIR=OUTPUT_DIR/"script_review_requests"
RESPONSES_DIR=OUTPUT_DIR/"script_review_responses"
APPROVED_DIR=OUTPUT_DIR/"approved_scripts"
SUMMARY_FILE=OUTPUT_DIR/"script_gate_summary.json"
UI_REVIEWER="local-operator"
CRITERIA=("package_promise_delivered","facts_within_verified_claims","claim_mapping_reasonable","original_source_independent","structure_and_payoff_clear")

def build_review_request(draft:dict[str,Any],draft_path:Path)->dict[str,Any]:
    concept_id=str(draft.get("concept_id","")).strip()
    if not concept_id: raise ValueError("Script draft requires concept_id")
    return {
      "request_type":"human_script_gate","concept_id":concept_id,
      "title":draft.get("title"),"opening_hook":draft.get("opening_hook"),"sections":draft.get("sections",[]),"closing":draft.get("closing"),
      "package":draft.get("package",{}),"accepted_claims":draft.get("accepted_claims",[]),
      "required_accept_criteria":list(CRITERIA),
      "criteria":{
        "package_promise_delivered":"The draft delivers the approved title/thumbnail promise and expected payoff.",
        "facts_within_verified_claims":"Factual statements stay within human-accepted research claims.",
        "claim_mapping_reasonable":"Section claim IDs reasonably support the factual narration they are attached to.",
        "original_source_independent":"The script is original and does not depend on source wording, footage, story or personality.",
        "structure_and_payoff_clear":"The hook, progression and final payoff are clear enough to produce."
      },
      "request_provenance":{"script_draft":str(draft_path.resolve()),"script_draft_sha256":sha256_file(draft_path)}
    }

def prepare()->dict[str,Any]:
    REVIEW_REQUESTS_DIR.mkdir(parents=True,exist_ok=True)
    paths=sorted(DRAFTS_DIR.glob("*.script_draft.json")) if DRAFTS_DIR.exists() else []
    prepared=[]
    for path in paths:
        req=build_review_request(load_json(path),path); dest=REVIEW_REQUESTS_DIR/f"{safe_slug(req['concept_id'])}.script_review_request.json"
        dest.write_text(json.dumps(req,indent=2,ensure_ascii=False),encoding="utf-8"); prepared.append({"concept_id":req["concept_id"],"request":str(dest)})
    return {"status":"SCRIPT_GATE_READY" if prepared else "WAITING_FOR_SCRIPT_DRAFTS","prepared":len(prepared),"requests":prepared}

def apply(request_path:Path,response_path:Path)->dict[str,Any]:
    req=load_json(request_path); response=load_json(response_path)
    if str(response.get("concept_id",""))!=str(req.get("concept_id","")): raise ValueError("concept_id mismatch")
    reviewer=str(response.get("reviewer","")).strip()
    if not reviewer: raise ValueError("reviewer is required")
    decision=str(response.get("decision","")).strip().upper()
    if decision not in {"ACCEPT","REWORK","REJECT"}: raise ValueError("invalid decision")
    criteria=response.get("criteria")
    if not isinstance(criteria,dict): raise ValueError("criteria are required")
    normalized={key:criteria.get(key) is True for key in CRITERIA}
    note=str(response.get("note","") or "").strip()
    if decision=="ACCEPT" and not all(normalized.values()): raise ValueError("ACCEPT requires all criteria true")
    if decision=="REWORK" and not note: raise ValueError("REWORK requires note")
    summary={"status":"READY_FOR_PRODUCTION" if decision=="ACCEPT" else ("SCRIPT_REWORK_REQUIRED" if decision=="REWORK" else "SCRIPT_REJECTED"),"concept_id":req["concept_id"],"decision":decision,"criteria":normalized,"note":note,"reviewer":reviewer,"reviewed_at":datetime.now(timezone.utc).isoformat()}
    if decision=="ACCEPT":
        source=Path(req["request_provenance"]["script_draft"]); draft=load_json(source); draft["script_gate"]=summary
        APPROVED_DIR.mkdir(parents=True,exist_ok=True); dest=APPROVED_DIR/f"{safe_slug(req['concept_id'])}.approved_script.json"
        draft["approved_provenance"]={"script_review_request_sha256":sha256_file(request_path),"script_draft_sha256":sha256_file(source)}
        dest.write_text(json.dumps(draft,indent=2,ensure_ascii=False),encoding="utf-8"); summary["approved_script"]=str(dest)
    SUMMARY_FILE.parent.mkdir(parents=True,exist_ok=True); SUMMARY_FILE.write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8"); return summary


def response_path(concept_id:str)->Path:
    return RESPONSES_DIR/f"{safe_slug(concept_id)}.script_review_response.json"

def snapshot()->dict[str,Any]:
    if not REVIEW_REQUESTS_DIR.exists():
        return {"status":"READY_TO_PREPARE","complete":False,"scripts":[],"pending":0,"accepted":0,"rework":0,"rejected":0}
    scripts=[]; counts={"pending":0,"accepted":0,"rework":0,"rejected":0}
    for path in sorted(REVIEW_REQUESTS_DIR.glob("*.script_review_request.json")):
        req=load_json(path); cid=str(req.get("concept_id",""))
        rpath=response_path(cid)
        saved=load_json(rpath) if rpath.exists() else {}
        decision=str(saved.get("decision") or "PENDING").upper()
        key=decision.lower() if decision in {"ACCEPT","REWORK","REJECT"} else "pending"
        counts[key]+=1
        scripts.append({**req,"decision":decision,"criteria_decisions":saved.get("criteria",{}),"note":saved.get("note","")})
    complete=bool(scripts) and counts["pending"]==0
    return {"status":"COMPLETE" if complete else "AWAITING_HUMAN_DECISION","complete":complete,"scripts":scripts,**counts}

def apply_action(*,concept_id:str,decision:str,criteria:dict[str,Any],note:str|None=None)->dict[str,Any]:
    request_path=REVIEW_REQUESTS_DIR/f"{safe_slug(concept_id)}.script_review_request.json"
    if not request_path.exists(): raise ValueError("Script review request not found")
    RESPONSES_DIR.mkdir(parents=True,exist_ok=True)
    payload={"concept_id":concept_id,"reviewer":UI_REVIEWER,"decision":decision,"criteria":criteria,"note":str(note or "")}
    dest=response_path(concept_id)
    dest.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    apply(request_path,dest)
    return snapshot()

def main()->None:
    p=argparse.ArgumentParser(description="Human Script Gate"); p.add_argument("--mode",choices=("prepare","apply"),required=True); p.add_argument("--request",type=Path); p.add_argument("--response",type=Path); a=p.parse_args()
    if a.mode=="prepare": result=prepare()
    else:
        if not a.request or not a.response: raise SystemExit("--request and --response required")
        result=apply(a.request.resolve(),a.response.resolve())
    print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=="__main__": main()
