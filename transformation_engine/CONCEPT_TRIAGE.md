# Concept LLM Triage

The Transformation Engine deliberately separates three different meanings of "good":

1. **Structurally valid** — the generated concept satisfies schema, source-independence and minimum research-question rules.
2. **Worth human attention** — the FAIR-backed Concept Triage compares the full candidate pool and shortlists only the strongest 3–6.
3. **Human accepted** — the Human Concept Gate makes the final decision.

## Triage rubric

Every concept is evaluated on seven 0–5 dimensions:

- channel fit
- viewer problem
- promise clarity
- feasibility
- researchability
- originality
- overclaim safety

The LLM must account for every candidate exactly once as:

- `SHORTLIST`
- `REWORK`
- `DROP`

The triage stage is comparative. It penalizes off-channel mechanism transfer, unsupported "optimal/exact/safest" promises, false precision, technical category mistakes, weak viewer moments, unrealistic production requirements and concepts that are difficult to research credibly.

The complete audit is saved to:

`transformation_engine/output/concept_triage.json`

Only the `SHORTLIST` concepts are copied to:

`transformation_engine/output/concept_candidates_triaged.json`

That shortlist becomes the input to the Human Concept Gate. Triage never counts as human approval.
