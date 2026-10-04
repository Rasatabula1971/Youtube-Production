# Concept LLM Triage

The Transformation Engine deliberately separates three different meanings of "good":

1. **Structurally valid** — the generated concept satisfies schema, source-independence and minimum research-question rules.
2. **Worth human attention** — the FAIR-backed Concept Triage scores the full candidate pool (15–25 concepts) and shortlists up to **five distinct** finalists (D-130).
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

## Pool size and diversity (D-130)

- **Pool size.** Concept requests are sized so one opportunity's pool lands
  in 15–25: five per mechanism, clamped to that range, and never more than
  eight in one request. A single mechanism therefore yields eight, and the
  merge reports the pool as below target.
- **Near-duplicates.** `concept_diversity.concept_similarity` is the Jaccard
  overlap of the stemmed content words in each concept's premise, viewer
  problem, promise, viewer question, hook, title and payoff. At 0.35 or
  above (`near_duplicate_threshold`), two concepts count as restatements of
  one idea.
- **Finalists for the final comparison.** All first-pass decisions are taken
  in rank order. No near-duplicates are admitted, and while other approaches
  are available, at most three come from one mechanism and three from one
  hook type.
- **Shortlist.** Only concepts scoring 70 or more are eligible. In rank
  order, near-duplicates are skipped, and no mechanism or hook type takes
  more than two places while others are available.
- **Shortfall.** If fewer than five distinct concepts qualify, the empty
  places stay empty and the reason is recorded under `selection` and shown
  at the Concept Gate. Every other candidate stays under View all candidates
  with its reason (`NEAR_DUPLICATE` with the concept it restates,
  `APPROACH_ALREADY_REPRESENTED` or `BELOW_SELECTION_CUTOFF`).
