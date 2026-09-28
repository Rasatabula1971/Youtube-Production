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

def main()->None:
    p=argparse.ArgumentParser(description="Human Script Gate"); p.add_argument("--mode",choices=("prepare","apply"),required=True); p.add_argument("--request",type=Path); p.add_argument("--response",type=Path); a=p.parse_args()
    if a.mode=="prepare": result=prepare()
    else:
        if not a.request or not a.response: raise SystemExit("--request and --response required")
        result=apply(a.request.resolve(),a.response.resolve())
    print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=="__main__": main()
