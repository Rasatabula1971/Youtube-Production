# Stage 2 Experiment 01.4 — Depth-First Topic Expansion

## Purpose

Experiment 01.4 takes validated age-matched evidence from Experiment 01.3 and
asks a narrower question:

> Once a topic/format cell shows replicated current demand, which sub-angles
> inside that topic repeatedly attract large audiences?

This stays inside **M1 — Prove the Opportunity Engine**. It does not begin the
creative "why did it work?" analysis planned for Experiment 02.

## Dependency

01.4 consumes:

- `output/experiment_01_3/topic_velocity.json`
- `output/experiment_01_3/summary.json`

It does not choose a topic in advance.

## Depth-ready gate

A topic/format cell is eligible for expansion only when it has:

- at least 3 unique channels;
- at least 3 valid current-velocity samples; and
- a non-null age-matched velocity index.

These are evidence-coverage requirements, not a composite opportunity score.

## Two modes

### 1. Plan — zero quota

```powershell
python .\experiment_01_discovery\experiment_01_4.py --mode plan
```

Plan mode:

- reads the final 01.3 evidence;
- identifies evidence-ready topic/format cells;
- creates deterministic deeper query families;
- separates short and long-form search branches;
- allocates a fixed search-call budget; and
- writes a frozen plan.

Output:

`output\experiment_01_4\expansion_plan.json`

If 01.3 has not yet produced enough velocity evidence, the plan is written with:

`WAITING_FOR_01_3_EVIDENCE`

and no YouTube search calls are spent.

## Query families

The initial deterministic families are:

- how it works;
- hidden mechanism;
- engineering constraints;
- failure/problem;
- evolution;
- rules/loopholes.

These are discovery probes, not assumptions that every successful video must
fit one of these structures.

## Budget allocation

The default plan budget is 30 `search.list` calls.

Scheduling uses the primary 01.3 age-matched velocity metric to order
evidence-ready cells, then allocates calls round-robin so one long-form cell
cannot consume the entire budget.

This ordering is operational scheduling only. It is **not** a final opportunity
score.

## 2. Execute — quota controlled

When the frozen plan is READY:

```powershell
python .\experiment_01_discovery\experiment_01_4.py --mode execute
```

Execution:

- runs only the frozen search tasks;
- uses `viewCount` ordering;
- searches the previous five years by default;
- keeps short and long-form duration branches separate;
- validates the returned title against both the topic and F1/motorsport
  context;
- preserves query-family provenance; and
- checkpoints completed search tasks.

If quota or the local execution budget is reached, rerun the same command.
Completed tasks are skipped.

## Outputs

`output\experiment_01_4\`

contains:

- `expansion_plan.json`
- `search_checkpoint.json` while an execution is incomplete
- `raw_results.json`
- `candidates.csv`
- `expansion_evidence.json`
- `summary.json`

## Evidence produced

For each topic, format and query family, 01.4 reports:

- video count;
- unique channels;
- median views;
- maximum views; and
- median publication age.

01.4 does **not** calculate a new current-velocity metric. Its role is to expose
repeatable sub-angles after 01.3 has already validated current topic demand.

## Boundary with Experiment 02

01.4 answers:

> What deeper sub-angles are repeatedly successful inside a validated topic?

Experiment 02 later answers:

> Why did the selected successful videos work creatively?

Keeping those questions separate prevents creative pattern analysis from
substituting for market-demand evidence.
