"""Human candidate review gate for storyboard visual search results."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json, sha256_file

HERE=Path(__file__).resolve().parent
OUTPUT=HERE/"output"
RESULT_DIR=OUTPUT/"visual_search_results"
STORYBOARD_DIR=OUTPUT/"storyboards"
REVIEW_DIR=OUTPUT/"visual_candidate_reviews"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _review_path(result_path: Path) -> Path:
    REVIEW_DIR.mkdir(parents=True,exist_ok=True)
    return REVIEW_DIR/result_path.name.replace(".visual_search_results.json",".visual_candidate_review.json")


def snapshot() -> dict[str, Any]:
    packets=[]
    for result_path in sorted(RESULT_DIR.glob("*.visual_search_results.json")) if RESULT_DIR.exists() else []:
        result=load_json(result_path)
        review_path=_review_path(result_path)
        review=load_json(review_path) if review_path.exists() else {"decisions":{}}
        packets.append({
            "concept_id":result.get("concept_id"),"format":result.get("format"),
            "result_file":str(result_path),"result_sha256":sha256_file(result_path),
            "shots":result.get("shots",[]),"decisions":review.get("decisions",{}),
        })
    return {"status":"READY_FOR_VISUAL_CANDIDATE_REVIEW" if packets else "WAITING_FOR_VISUAL_SEARCH_RESULTS","packets":packets}


def apply_action(*, result_file: str, shot_id: str, action: str, candidate_id: str | None=None, note: str="") -> dict[str, Any]:
    result_path=Path(result_file)
    if not result_path.exists() or result_path.parent.resolve()!=RESULT_DIR.resolve():
        raise ValueError("Invalid visual search result file")
    result=load_json(result_path)
    shot=next((x for x in result.get("shots",[]) if str(x.get("shot_id"))==shot_id),None)
    if shot is None:
        raise ValueError("Unknown storyboard shot")
    actions={"SELECT","REJECT_ALL","NEEDS_BETTER_VISUAL"}
    if action not in actions:
        raise ValueError("Unsupported candidate review action")
    candidate=None
    if action=="SELECT":
        candidate=next((x for x in shot.get("candidates",[]) if str(x.get("candidate_id"))==str(candidate_id)),None)
        if candidate is None:
            raise ValueError("Unknown candidate")
        if candidate.get("state")=="BLOCKED":
            raise ValueError("Blocked candidate cannot be selected")
        if candidate.get("state")=="HUMAN_REVIEW_REQUIRED":
            decision_status="SELECTED_PENDING_RIGHTS_CONTEXT_GATE"
        else:
            decision_status="SELECTED"
    else:
        decision_status=action
    review_path=_review_path(result_path)
    review=load_json(review_path) if review_path.exists() else {
        "artifact":"visual_candidate_review","concept_id":result.get("concept_id"),"format":result.get("format"),
        "source_result":str(result_path.resolve()),"source_result_sha256":sha256_file(result_path),"decisions":{}
    }
    if review.get("source_result_sha256")!=sha256_file(result_path):
        raise ValueError("STALE_REVIEW: visual search results changed")
    review["decisions"][shot_id]={
        "action":action,"status":decision_status,"candidate_id":candidate_id if action=="SELECT" else None,
        "note":note.strip(),"candidate_source_url":candidate.get("source_url") if candidate else None,
        "candidate_source_tier":candidate.get("source_tier") if candidate else None,
        "candidate_fingerprint":_hash(json.dumps(candidate,sort_keys=True)) if candidate else None,
    }
    total=len(result.get("shots",[])); decided=len(review["decisions"])
    review["summary"]={"shots_total":total,"shots_decided":decided,"complete":decided==total,
        "remaining_gaps":sum(x.get("action") in {"REJECT_ALL","NEEDS_BETTER_VISUAL"} for x in review["decisions"].values())}
    review["status"]="READY_FOR_ROUGH_CUT" if decided==total else "REVIEW_IN_PROGRESS"
    atomic_write_json(review_path,review)
    return review
