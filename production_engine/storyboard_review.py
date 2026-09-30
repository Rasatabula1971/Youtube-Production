"""Human Creative Director revisions for individual storyboard shots.

Revisions are shot-local by default. They create immutable version history and
invalidate only downstream artifacts for the edited shot. Narration/timing is
locked unless a separate upstream rework is requested.
"""
from __future__ import annotations
import copy,json
from pathlib import Path
from typing import Any
from pipeline_integrity import atomic_write_json
from visual_acquisition import load_json,sha256_file

HERE=Path(__file__).resolve().parent; OUTPUT=HERE/"output"
STORYBOARDS=OUTPUT/"storyboards"; REVISIONS=OUTPUT/"storyboard_revisions"

EDITABLE={"desired_visual","search_terms","story_purpose"}
CINEMATIC={"camera_angle","framing","camera_movement","lens_feel","lighting","depth_of_field","motion_speed","transition"}

def _revision_path(board_path:Path)->Path:
 REVISIONS.mkdir(parents=True,exist_ok=True)
 return REVISIONS/board_path.name.replace(".storyboard.json",".storyboard_revisions.json")

def snapshot()->dict[str,Any]:
 items=[]
 for p in sorted(STORYBOARDS.glob("*.storyboard.json")) if STORYBOARDS.exists() else []:
  board=load_json(p);rp=_revision_path(p);history=load_json(rp) if rp.exists() else {"shots":{}}
  items.append({"concept_id":board.get("concept_id"),"format":board.get("format"),"storyboard_file":str(p),
   "storyboard_sha256":sha256_file(p),"cards":board.get("cards",[]),"revision_history":history.get("shots",{})})
 return {"status":"READY_FOR_CREATIVE_DIRECTION" if items else "WAITING_FOR_STORYBOARD","items":items}

def revise(*,storyboard_file:str,shot_id:str,instruction:str,changes:dict[str,Any])->dict[str,Any]:
 p=Path(storyboard_file)
 if not p.exists() or p.parent.resolve()!=STORYBOARDS.resolve(): raise ValueError("Invalid storyboard file")
 if not instruction.strip(): raise ValueError("Creative revision requires an instruction")
 board=load_json(p);cards=board.get("cards",[]);idx=next((i for i,x in enumerate(cards) if str(x.get("shot_id"))==shot_id),None)
 if idx is None: raise ValueError("Unknown storyboard shot")
 card=copy.deepcopy(cards[idx]);before=copy.deepcopy(card)
 for key,value in changes.items():
  if key in EDITABLE:
   if key=="search_terms":
    if not isinstance(value,list): raise ValueError("search_terms must be a list")
    card[key]=[str(x).strip() for x in value if str(x).strip()]
   else: card[key]=str(value).strip()
  elif key=="cinematic_direction":
   if not isinstance(value,dict): raise ValueError("cinematic_direction must be an object")
   cine=copy.deepcopy(card.get("cinematic_direction",{}))
   for ck,cv in value.items():
    if ck not in CINEMATIC: raise ValueError(f"Unsupported cinematic field: {ck}")
    cine[ck]=str(cv).strip()
   card["cinematic_direction"]=cine
  elif key in {"time_range","beat_id","premium_generation_authorized","source_strategy"}:
   raise ValueError(f"{key} is locked at the shot-local creative gate")
  else: raise ValueError(f"Unsupported storyboard field: {key}")
 if card==before: raise ValueError("Revision made no storyboard changes")
 rp=_revision_path(p);hist=load_json(rp) if rp.exists() else {"artifact":"storyboard_revision_history","concept_id":board.get("concept_id"),"format":board.get("format"),"shots":{}}
 versions=hist["shots"].setdefault(shot_id,[]);version=len(versions)+2
 versions.append({"from_version":version-1,"to_version":version,"instruction":instruction.strip(),"before":before,"after":card})
 card["creative_version"]=version;card["creative_instruction"]=instruction.strip();cards[idx]=card
 board["cards"]=cards;board["status"]="READY_FOR_VISUAL_SEARCH";board["premium_generation_authorized"]=False
 board.setdefault("policy",{})["shot_local_revision_invalidates_only_edited_shot"]=True
 atomic_write_json(p,board)
 hist["current_storyboard_sha256"]=sha256_file(p);atomic_write_json(rp,hist)
 return {"status":"SHOT_REVISED","shot_id":shot_id,"creative_version":version,"card":card,
  "invalidation":{"visual_search":True,"candidate_selection":True,"rights_review":True,"rough_cut_assignment":True,"render_approval":True,"other_shots":False},
  "narration_timing_changed":False,"storyboard_sha256":sha256_file(p)}
