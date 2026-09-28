"""Story / Script Engine.

Consumes human-verified research packages and prepares bounded script requests.
Only accepted research claims may be referenced as factual support.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any

_OVERLAP_ROOT = Path(__file__).resolve().parent.parent
if str(_OVERLAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_OVERLAP_ROOT))

from source_overlap import check_texts

HERE=Path(__file__).resolve().parent
PROJECT_ROOT=HERE.parent
RESEARCH_VERIFIED_DIR=PROJECT_ROOT/"research_engine"/"output"/"verified_packages"
OUTPUT_DIR=HERE/"output"
REQUESTS_DIR=OUTPUT_DIR/"script_requests"
RESPONSES_DIR=OUTPUT_DIR/"script_responses"
DRAFTS_DIR=OUTPUT_DIR/"script_drafts"
SUMMARY_FILE=OUTPUT_DIR/"summary.json"

def load_json(path: Path)->Any:
    if not path.exists(): raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))

def safe_slug(value:str)->str:
    cleaned="".join(c if c.isalnum() or c in "-_." else "_" for c in value).strip("._")
    return cleaned or "unknown"

def sha256_file(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build_script_request(package:dict[str,Any], package_path:Path)->dict[str,Any]:
    if package.get("status")!="READY_FOR_STORY_SCRIPT":
        raise ValueError("Verified research package is not READY_FOR_STORY_SCRIPT")
    concept_id=str(package.get("concept_id","")).strip()
    if not concept_id: raise ValueError("Verified research package requires concept_id")
    concept=package.get("concept",{})
    if not isinstance(concept,dict): raise ValueError("concept must be an object")
    packaging=concept.get("packaging",{})
    if not isinstance(packaging,dict): packaging={}
    claims=package.get("claims",[])
    if not isinstance(claims,list) or not claims:
        raise ValueError("Story / Script requires at least one accepted research claim")
    accepted=[]
    claim_ids=[]
    for claim in claims:
        claim_id=str(claim.get("claim_id","")).strip()
        statement=str(claim.get("statement","")).strip()
        if not claim_id or not statement:
            raise ValueError("Every accepted claim requires claim_id and statement")
        claim_ids.append(claim_id)
        accepted.append({
            "claim_id":claim_id,
            "statement":statement,
            "role":claim.get("role"),
            "question_ids":list(claim.get("question_ids",[])),
            "coverage":claim.get("coverage",{}),
        })
    return {
        "artifact":"script_request",
        "concept_id":concept_id,
        "package":{
            "title":packaging.get("title") or concept.get("working_title"),
            "thumbnail":packaging.get("thumbnail",{}),
            "opening_frame":packaging.get("opening_frame",{}),
            "one_sentence_promise":packaging.get("one_sentence_promise") or packaging.get("core_promise") or concept.get("audience_promise"),
            "expected_payoff":packaging.get("expected_payoff"),
            "viewer_problem":packaging.get("viewer_problem") or concept.get("viewer_problem"),
            "viewer_moment":packaging.get("viewer_moment") or concept.get("viewer_moment"),
            "desired_outcome":packaging.get("desired_outcome") or concept.get("desired_outcome"),
            "format_intent":packaging.get("format_intent") or concept.get("format_intent"),
        },
        "concept":{
            "premise":concept.get("premise"),
            "audience_promise":concept.get("audience_promise"),
            "viewer_problem":concept.get("viewer_problem"),
            "viewer_moment":concept.get("viewer_moment"),
            "desired_outcome":concept.get("desired_outcome"),
            "mechanism_id":concept.get("mechanism_id"),
            "mechanism_label":concept.get("mechanism_label"),
        },
        "accepted_claim_ids":sorted(claim_ids),
        "accepted_claims":accepted,
        "instructions":[
            "Write an original YouTube script that fulfills the approved package promise.",
            "Do not copy or closely paraphrase source-video wording.",
            "Do not introduce factual claims beyond the accepted research claims supplied here.",
            "Every factual section must cite one or more accepted claim_ids.",
            "Connective narration, transitions, questions and framing may be original but must not add unsupported facts.",
            "Preserve viewer problem, viewer moment, desired outcome and expected payoff.",
            "Use a strong opening hook, progressive reveal and clear payoff.",
            "Do not claim virality, guaranteed performance or facts not present in accepted_claims.",
        ],
        "request_provenance":{
            "verified_research_package":str(package_path.resolve()),
            "verified_research_sha256":sha256_file(package_path),
        },
    }

def validate_script_response(response:dict[str,Any],request:dict[str,Any])->dict[str,Any]:
    errors=[]
    if str(response.get("concept_id",""))!=str(request.get("concept_id","")): errors.append("concept_id mismatch")
    if not str(response.get("title","")).strip(): errors.append("title is required")
    if not str(response.get("opening_hook","")).strip(): errors.append("opening_hook is required")
    if not str(response.get("closing","")).strip(): errors.append("closing is required")
    sections=response.get("sections")
    if not isinstance(sections,list) or not sections:
        errors.append("sections must be a non-empty list"); sections=[]
    allowed=set(request.get("accepted_claim_ids",[]))
    used=set(); seen=set()
    for index,section in enumerate(sections):
        if not isinstance(section,dict): errors.append(f"section {index} must be an object"); continue
        sid=str(section.get("section_id","")).strip()
        if not sid: errors.append(f"section {index} requires section_id")
        elif sid in seen: errors.append(f"duplicate section_id: {sid}")
        seen.add(sid)
        if not str(section.get("purpose","")).strip(): errors.append(f"{sid or index} requires purpose")
        if not str(section.get("narration","")).strip(): errors.append(f"{sid or index} requires narration")
        ids=section.get("claim_ids")
        if not isinstance(ids,list): errors.append(f"{sid or index} claim_ids must be a list"); continue
        if not ids:
            errors.append(f"{sid or index} requires at least one accepted claim_id")
        for cid in ids:
            cid=str(cid)
            if cid not in allowed: errors.append(f"{sid or index} uses unapproved claim_id {cid}")
            else: used.add(cid)
    overlap = check_texts(
        [{"field":"title","text":response.get("title","")},
         {"field":"opening_hook","text":response.get("opening_hook","")},
         *[
            {"field":f"section.{index}","text":section.get("narration","")}
            for index, section in enumerate(sections)
            if isinstance(section, dict)
         ],
         {"field":"closing","text":response.get("closing","")}]
    )
    if overlap.get("blocking"):
        match = overlap.get("matches", [{}])[0]
        errors.append("source overlap block: " + str(match.get("overlap_text") or ""))
    return {"valid":not errors,"errors":errors,"claim_usage":sorted(used),"unused_accepted_claim_ids":sorted(allowed-used),"source_overlap":overlap}

def run_prepare(verified_dir:Path=RESEARCH_VERIFIED_DIR)->dict[str,Any]:
    REQUESTS_DIR.mkdir(parents=True,exist_ok=True)
    paths=sorted(verified_dir.glob("*.verified_research_package.json")) if verified_dir.exists() else []
    prepared=[]; failures=[]
    for path in paths:
        try:
            request=build_script_request(load_json(path),path)
            dest=REQUESTS_DIR/f"{safe_slug(request['concept_id'])}.script_request.json"
            dest.write_text(json.dumps(request,indent=2,ensure_ascii=False),encoding="utf-8")
            prepared.append({"concept_id":request["concept_id"],"request":str(dest)})
        except Exception as exc:
            failures.append({"package":str(path),"error_type":type(exc).__name__})
    summary={"status":"SCRIPT_REQUESTS_READY" if prepared else "WAITING_FOR_VERIFIED_RESEARCH","verified_packages_found":len(paths),"prepared":len(prepared),"failures":failures,"requests_dir":str(REQUESTS_DIR)}
    OUTPUT_DIR.mkdir(parents=True,exist_ok=True)
    SUMMARY_FILE.write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    return summary

def main()->None:
    p=argparse.ArgumentParser(description="Story / Script Engine")
    p.add_argument("--mode",choices=("prepare",),required=True)
    p.add_argument("--verified-dir",type=Path,default=RESEARCH_VERIFIED_DIR)
    a=p.parse_args()
    print(json.dumps(run_prepare(a.verified_dir.resolve()),indent=2,ensure_ascii=False))

if __name__=="__main__": main()
