# Experiment 02 — Why Did It Work?

## Purpose

Experiment 02 studies successful source videos selected by the Opportunity
Engine and produces structured, evidence-backed observations about the creative
mechanisms they use.

The central question is:

> What mechanisms repeatedly appear in successful source videos, and which of
> those mechanisms can be transferred into genuinely new concepts?

This experiment does **not** assume that a visible mechanism caused the video's
performance. Public source-video observation is not a controlled causal test.

## Inputs

The formal candidate input is:

`experiment_01_discovery/output/experiment_01_5/study_set.json`

Only the evidence-backed study set from Experiment 01.5 should automatically
enter Experiment 02.

## Offline-first boundary

The framework itself:

- does not call YouTube;
- does not fetch transcripts;
- does not download videos;
- does not call an LLM;
- spends zero API quota.

Source evidence can be added later from transcripts, thumbnails, opening
frames, visual notes, timing notes and audio notes.

## Modes

### Prepare

```powershell
python .\experiment_02_analysis\experiment_02.py --mode prepare
```

Prepare mode reads the 01.5 study set and creates:

- `output/work_packets.json`
- one empty evidence profile per source video under
  `output/profiles_to_complete/`

If the 01.5 study set does not yet exist, the experiment writes a
`WAITING_FOR_01_5_STUDY_SET` summary rather than fabricating candidates.

### Validate

After a profile has been completed:

```powershell
python .\experiment_02_analysis\experiment_02.py --mode validate --profile ".\path\to\profile.json"
```

Every supported finding must point to evidence IDs. The validator checks:

- schema version;
- study-set membership when available;
- required analysis dimensions;
- evidence-reference existence;
- evidence type appropriate to the dimension;
- confidence labels;
- mechanism taxonomy;
- transformation Source Dependency Test;
- unsupported causal wording.

### Aggregate

When multiple completed profiles exist:

```powershell
python .\experiment_02_analysis\experiment_02.py --mode aggregate --profiles-dir ".\path\to\completed_profiles"
```

Only valid profiles contribute to cross-video patterns.

A mechanism is labelled `REPLICATED_PATTERN` only when it occurs across at
least two videos from at least two independent channels.

Replication is still observational evidence, not proof that the mechanism
caused performance.

## Required analysis dimensions

Each source profile contains:

1. packaging;
2. opening hook;
3. story progression;
4. information reveals;
5. emotion;
6. pacing;
7. visual language;
8. audience promise;
9. payoff; and
10. promise/payoff alignment.

## Evidence model

Evidence items use stable IDs and typed sources.

Supported evidence types:

- metadata;
- transcript;
- thumbnail;
- opening frame;
- visual note;
- timing note;
- audio note;
- opportunity evidence.

Upstream 01.3/01.4/01.5 evidence establishes why a source was selected. It does
not substitute for transcript or visual evidence when making creative claims
about the video itself.

## Findings vs hypotheses

A **finding** must have direct evidence references.

A **working hypothesis** is kept separately and must state its limitation.

This prevents the system from silently converting an inference into an
observed fact.

## Mechanism taxonomy

The first controlled vocabulary includes:

- curiosity gap;
- hidden mechanism;
- stakes;
- open loop;
- progressive reveal;
- escalation;
- contrast;
- visual proof;
- specificity;
- counterintuitive fact;
- problem/solution;
- failure mode;
- rules/constraint;
- payoff reveal;
- identity/emotion.

The taxonomy is intentionally editable as evidence accumulates.

## Transfer boundary

Profiles explicitly separate:

### Transferable mechanisms

General mechanisms that may be reused without copying the source's expression.

### Source-specific elements

Details tied to the original creator, footage, wording, story, personality or
specific execution.

### Transformation opportunities

Potential new directions that preserve a useful mechanism while changing the
subject, research, argument, story and execution.

Every transformation opportunity must record a **Source Dependency Test**:

> If the source creator's clips and expression were removed, would the new
> concept still retain its main value?

## Outputs

Generated Experiment 02 data is kept under:

`experiment_02_analysis/output/`

and remains untracked by Git.

## Success condition

The framework succeeds when it can:

- prepare evidence packets from the 01.5 study set;
- reject unsupported or weakly sourced creative claims;
- distinguish observations from hypotheses;
- identify mechanisms repeated across independent videos/channels;
- separate transferable mechanisms from source-specific expression; and
- produce transformation opportunities that pass the Source Dependency Test.

The resulting evidence can then feed Packaging, Retention and Transformation
work without treating successful source videos as templates to copy.


## Evidence ingestion layer

The offline evidence-ingestion layer is implemented in:

`evidence_ingest.py`

It accepts a per-video bundle manifest and imports:

- SRT/VTT/plain-text transcripts;
- registered thumbnail files;
- registered opening-frame files; and
- structured visual/timing/audio notes.

Imported files are SHA-256 fingerprinted and converted into stable evidence
IDs. Prepared source profiles are not overwritten by default.

See `EVIDENCE_INGESTION.md` for the workflow and templates.
