# Experiment 02 Analysis Execution Helper

## Purpose

This helper turns an enriched Experiment 02 evidence profile into a controlled
analysis workflow without allowing unsupported interpretation to silently become
fact.

It is deliberately provider-neutral and offline.

The helper does **not** call an LLM itself.

Instead it separates analysis into two phases:

1. **prepare** an evidence-constrained analysis request;
2. **apply** a human/LLM response through evidence validation and automatic
   hypothesis routing.

## Why two phases

A language model or human analyst can reason across transcript and visual
evidence, but the repository still needs deterministic controls around:

- which evidence was available;
- which dimensions each evidence type can support;
- which evidence IDs a finding cites;
- whether a claim uses unsupported causal language;
- whether a transformation passes the Source Dependency Test; and
- what happens when a response overreaches.

The execution helper provides those controls.

## Prepare mode

Input should normally be an enriched profile produced by
`evidence_ingest.py`.

Run:

```powershell
python .\experiment_02_analysis\analysis_execute.py --mode prepare --profile ".\experiment_02_analysis\output\profiles_enriched\VIDEO_ID.json"
```

Output:

`experiment_02_analysis\output\analysis_requests\VIDEO_ID.analysis_request.json`

The request contains:

- source context;
- objective evidence metrics;
- the controlled mechanism taxonomy;
- one compact evidence library with each evidence item stored once;
- per-dimension evidence-reference lists;
- dimension-specific evidence selection strategies;
- allowed evidence types per dimension;
- response schemas;
- analysis instructions.

Evidence selection is deliberately asymmetric:

- opening hook emphasizes early evidence;
- audience promise preserves title/thumbnail/opening-frame evidence before early transcript evidence;
- payoff emphasizes late evidence;
- promise/payoff alignment combines packaging evidence with early and late evidence;
- story, reveals, emotion, pacing and visual-language packets sample across the timeline.

### Objective metrics

The helper calculates only directly measurable items such as:

- evidence counts by type;
- transcript segment count;
- transcript word count;
- timestamped transcript span;
- transcript segments per minute; and
- evidence IDs appearing within the configured opening window.

These are descriptive measurements, not retention or virality conclusions.

## Batch prepare

```powershell
python .\experiment_02_analysis\analysis_execute.py --mode batch-prepare --profiles-dir ".\experiment_02_analysis\output\profiles_enriched"
```

This creates one request per enriched profile.

## Analysis response

A response should follow:

`analysis_response_template.json`

Every factual finding should include:

- `finding`;
- zero or more controlled `mechanism_ids`;
- one or more `evidence_refs`; and
- `confidence`.

Unsupported interpretations belong under `working_hypotheses`.

## Apply mode

```powershell
python .\experiment_02_analysis\analysis_execute.py --mode apply --profile ".\experiment_02_analysis\output\profiles_enriched\VIDEO_ID.json" --response ".\path\to\analysis_response.json"
```

Output:

- analyzed profile under `output\profiles_analyzed\`;
- deterministic apply report under `output\analysis_apply_reports\`.

The original enriched profile is not overwritten.

Apply mode is also non-destructive for omitted sections. A partial response can
update one analysis dimension without clearing previously accepted findings in
other dimensions or transfer sections. Existing working hypotheses are
preserved and deduplicated across repeated applies.

## Automatic hypothesis routing

A proposed finding is **not** inserted into factual analysis when:

- it lacks evidence references;
- an evidence reference does not exist;
- the evidence type cannot support that dimension;
- it uses invalid schema values; or
- it makes causal claims such as "made it viral."

Instead the statement is moved to `working_hypotheses` with an explicit
limitation explaining why it was not accepted as a finding.

The same rule applies to unsupported transferable-mechanism or
source-specific-element claims.

## Transformation opportunities

A transformation opportunity is accepted only when:

- its mechanism ID is valid;
- it cites source evidence;
- opportunity-selection evidence is not its only support;
- it defines a new direction;
- the Source Dependency Test has a boolean result;
- the Source Dependency Test passes; and
- a rationale is supplied.

A failed Source Dependency Test prevents the proposal from entering the
accepted transformation list.

## Important boundary

The helper controls evidence discipline; it does not establish causality.

A repeated or well-supported mechanism can be documented as an observation.
It still cannot be described as the cause of views, recommendation exposure,
virality, or retention unless independent evidence actually supports that
causal conclusion.
