# Stage 2 Experiment 01.5 — Opportunity Handoff Gate

## Purpose

Experiment 01.5 closes the Opportunity Engine by turning upstream evidence into
an auditable candidate packet for Experiment 02.

It answers:

> Which source candidates have enough demand evidence, age-matched topic
> momentum, and replicated depth evidence to justify creative analysis?

It is an offline stage and spends **zero YouTube API quota**.

## Inputs

01.5 consumes completed outputs from:

### Experiment 01.3

- `output/experiment_01_3/topic_velocity.json`
- `output/experiment_01_3/summary.json`

### Experiment 01.4

- `output/experiment_01_4/raw_results.json`
- `output/experiment_01_4/expansion_evidence.json`
- `output/experiment_01_4/summary.json`

If the required upstream evidence is missing or 01.4 execution is incomplete,
01.5 writes a `WAITING` summary instead of fabricating a handoff.

## Gate states

Each candidate/topic pair receives one of three explicit states.

### PASS

Requires:

- at least 3 independent channels in the 01.3 topic/format cell;
- at least 3 valid current-velocity samples;
- a non-null age-matched velocity index;
- at least one 01.4 query family replicated across at least 2 videos and
  2 channels; and
- at least 500,000 candidate views.

The 500K value remains the existing project reference hypothesis. It is not
claimed to be a validated universal threshold.

### REVIEW

The 01.3 topic evidence is sufficient, but the candidate lacks either replicated
depth-family evidence or the current candidate-view reference.

### HOLD

The topic/format cell itself does not yet have sufficient 01.3 evidence.

These are gates, not scores.

## Build

```powershell
python .\experiment_01_discovery\experiment_01_5.py --mode build
```

No API key is required and no network request is made.

## Outputs

All files are isolated under:

`output\experiment_01_5\`

Generated files:

- `handoff_packets.json`
- `handoff_candidates.csv`
- `study_set.json`
- `summary.json`

## Handoff packet

Each packet preserves:

- video identity and URL;
- channel;
- format candidate;
- absolute views;
- topic;
- 01.3 age-matched velocity evidence;
- unique-channel evidence;
- matched 01.4 query families;
- replicated-family evidence;
- PASS / REVIEW / HOLD state; and
- explicit reasons.

No composite opportunity score is calculated.

## Experiment 02 study set

Only PASS packets can enter the automatic study set.

The default set is capped at 8 videos with:

- maximum 2 videos per topic/format cell;
- maximum 1 video per channel; and
- no duplicate video IDs.

The ordering uses the project's primary 01.3 metric,
`age_matched_velocity_index`.

Absolute views are used only as a tie-breaker.

This is a coverage-constrained handoff, not a claim that the first video is
universally "best."

## M1 boundary

When 01.5 produces a non-empty study set, the Opportunity Engine has a concrete
handoff artifact for Experiment 02.

Experiment 02 should then analyze why those successful examples worked across
packaging, hook, story, emotion, pacing, visual language, audience promise and
payoff.
