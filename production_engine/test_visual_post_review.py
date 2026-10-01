from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from visual_rough_cut import build
from visual_gap_planner import build as build_gaps
from visual_search import shot_fingerprint

def test_editorial_excerpt_stays_placeholder_without_rights_gate(tmp_path):
 board={"status":"READY_FOR_VISUAL_SEARCH","concept_id":"c","format":"long","cards":[{"shot_id":"s1","beat_id":"b1","time_range":{},"story_purpose":"hook","desired_visual":"x","cinematic_direction":{},"visual_value_score":{"total":20},"premium_generation_candidate":True}]}
 review={"status":"READY_FOR_ROUGH_CUT","concept_id":"c","format":"long","decisions":{"s1":{"status":"SELECTED_PENDING_RIGHTS_CONTEXT_GATE","candidate_id":"e1","candidate_source_url":"https://example.test","shot_fingerprint":shot_fingerprint(board["cards"][0])}}}
 bp=tmp_path/"b.json";rp=tmp_path/"r.json";bp.write_text("{}",encoding="utf-8");rp.write_text("{}",encoding="utf-8")
 rough=build(board,review,None,bp,rp)
 assert rough["scenes"][0]["visual_assignment"]["status"]=="PLACEHOLDER"

def test_rights_approved_editorial_excerpt_can_enter_rough_cut(tmp_path):
 board={"status":"READY_FOR_VISUAL_SEARCH","concept_id":"c","format":"long","cards":[{"shot_id":"s1","beat_id":"b1","time_range":{},"story_purpose":"hook","desired_visual":"x","cinematic_direction":{},"visual_value_score":{"total":20},"premium_generation_candidate":True}]}
 review={"status":"READY_FOR_ROUGH_CUT","concept_id":"c","format":"long","decisions":{"s1":{"status":"SELECTED_PENDING_RIGHTS_CONTEXT_GATE","candidate_id":"e1","candidate_source_url":"https://example.test"}}}
 rights={"decisions":{"s1":{"approved_for_rough_cut":True}}};bp=tmp_path/"b.json";rp=tmp_path/"r.json";bp.write_text("{}",encoding="utf-8");rp.write_text("{}",encoding="utf-8")
 rough=build(board,review,rights,bp,rp)
 assert rough["scenes"][0]["visual_assignment"]["status"]=="APPROVED_EDITORIAL_EXCERPT"

def test_gap_planner_keeps_paid_generation_locked(tmp_path):
 rough={"concept_id":"c","format":"long","scenes":[{"shot_id":"s1","time_range":{},"story_purpose":"hook","desired_visual":"hero","cinematic_direction":{"camera_movement":"push_in"},"visual_value_score":{"total":20},"premium_generation_candidate":True,"visual_assignment":{"status":"PLACEHOLDER","reason":"gap"}}]}
 rp=tmp_path/"rough.json";reviewp=tmp_path/"review.json";rp.write_text("rough",encoding="utf-8");reviewp.write_text("review",encoding="utf-8")
 import hashlib
 review={"approved_for_gap_planning":True,"source_rough_cut_sha256":hashlib.sha256(b"rough").hexdigest()}
 plan=build_gaps(rough,review,rp,reviewp)
 assert plan["gaps"][0]["resolution_class"]=="D_HERO_GENERATION"
 assert plan["gaps"][0]["premium_generation_authorized"] is False
