"""Build storyboard-aware rough-cut manifests from reviewed visual candidates.

Only owned/licence-verified candidates or creator/editorial excerpts explicitly
approved at the human rights/context gate may enter the rough cut. Paid visual
generation remains locked.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json,safe_slug,sha256_file

HERE=Path(__file__).resolve().parent; OUTPUT=HERE/"output"
STORYBOARD_DIR=OUTPUT/"storyboards"; RESULT_DIR=OUTPUT/"visual_search_results"
REVIEW_DIR=OUTPUT/"visual_candidate_reviews"; RIGHTS_DIR=OUTPUT/"visual_rights_reviews"
ROUGH_DIR=OUTPUT/"visual_rough_cuts"; SUMMARY=OUTPUT/"visual_rough_cut_summary.json"

def _key(cid:str,fmt:str)->str:return f"{safe_slug(cid)}.{safe_slug(fmt)}"

def build(board:dict[str,Any],review:dict[str,Any],rights:dict[str,Any]|None,board_path:Path,review_path:Path)->dict[str,Any]:
    if board.get("status")!="READY_FOR_VISUAL_SEARCH": raise ValueError("Storyboard is not current for rough cut")
    if review.get("status")!="READY_FOR_ROUGH_CUT": raise ValueError("Candidate review is incomplete")
    if (board.get("concept_id"),board.get("format"))!=(review.get("concept_id"),review.get("format")): raise ValueError("Storyboard/review identity mismatch")
    decisions=review.get("decisions",{}); rights_decisions=(rights or {}).get("decisions",{})
    scenes=[]
    for i,card in enumerate(board.get("cards",[])):
        sid=str(card.get("shot_id") or ""); d=decisions.get(sid,{})
        assignment={"status":"PLACEHOLDER","candidate_id":None,"source_url":None,"reason":"UNRESOLVED_VISUAL_GAP"}
        if d.get("status")=="SELECTED":
            assignment={"status":"APPROVED_EXISTING_ASSET","candidate_id":d.get("candidate_id"),"source_url":d.get("candidate_source_url"),"reason":"VERIFIED_REUSE_RIGHTS"}
        elif d.get("status")=="SELECTED_PENDING_RIGHTS_CONTEXT_GATE":
            rd=rights_decisions.get(sid,{})
            if rd.get("approved_for_rough_cut") is True:
                assignment={"status":"APPROVED_EDITORIAL_EXCERPT","candidate_id":d.get("candidate_id"),"source_url":d.get("candidate_source_url"),"reason":"HUMAN_RIGHTS_CONTEXT_APPROVED"}
            else:
                assignment["reason"]="RIGHTS_CONTEXT_APPROVAL_REQUIRED_OR_REJECTED"
        scenes.append({"scene_index":i,"shot_id":sid,"beat_id":card.get("beat_id"),"time_range":card.get("time_range"),
            "story_purpose":card.get("story_purpose"),"desired_visual":card.get("desired_visual"),
            "cinematic_direction":card.get("cinematic_direction",{}),"visual_value_score":card.get("visual_value_score",{}),
            "premium_generation_candidate":card.get("premium_generation_candidate",False),"visual_assignment":assignment})
    gaps=[x for x in scenes if x["visual_assignment"]["status"]=="PLACEHOLDER"]
    return {"artifact":"visual_rough_cut_manifest","concept_id":board.get("concept_id"),"format":board.get("format"),
        "status":"READY_FOR_HUMAN_ROUGH_CUT_GATE","premium_generation_allowed":False,"scenes":scenes,
        "summary":{"scenes":len(scenes),"placeholders":len(gaps),"existing_assets":len(scenes)-len(gaps)},
        "gate_policy":{"human_review_required_before_premium_visual_generation":True,"paid_visual_calls_allowed":False},
        "provenance":{"storyboard":str(board_path.resolve()),"storyboard_sha256":sha256_file(board_path),
            "candidate_review":str(review_path.resolve()),"candidate_review_sha256":sha256_file(review_path)}}

def prepare()->dict[str,Any]:
    ROUGH_DIR.mkdir(parents=True,exist_ok=True); items=[]
    for board_path in sorted(STORYBOARD_DIR.glob("*.storyboard.json")) if STORYBOARD_DIR.exists() else []:
        board=load_json(board_path); key=_key(str(board.get("concept_id") or ""),str(board.get("format") or ""))
        review_path=REVIEW_DIR/f"{key}.visual_candidate_review.json"
        if not review_path.exists(): continue
        review=load_json(review_path); rights_path=RIGHTS_DIR/f"{key}.visual_rights_review.json"
        rights=load_json(rights_path) if rights_path.exists() else None
        rough=build(board,review,rights,board_path,review_path); dest=ROUGH_DIR/f"{key}.visual_rough_cut.json"
        atomic_write_json(dest,rough); items.append({"concept_id":rough["concept_id"],"format":rough["format"],"rough_cut":str(dest),**rough["summary"]})
    out={"status":"READY_FOR_HUMAN_ROUGH_CUT_GATE" if items else "WAITING_FOR_REVIEWED_VISUALS","prepared":len(items),"items":items,"paid_visual_calls_allowed":False}
    atomic_write_json(SUMMARY,out); return out
def main()->None:
    argparse.ArgumentParser().parse_args(); print(json.dumps(prepare(),indent=2,ensure_ascii=False))
if __name__=="__main__":main()
