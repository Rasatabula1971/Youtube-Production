# PROJECT — YouTube Production

## 1. Objective

Build a repeatable system that:

1. discovers demonstrated audience demand;
2. determines why successful content worked;
3. transforms transferable mechanisms into genuinely new concepts;
4. researches and verifies the new concept;
5. creates an original story and script;
6. selects the correct format;
7. produces the video;
8. applies human quality gates; and
9. learns from actual publishing performance.

This is not intended to be a generic "viral video generator."

## 2. Governing principle

> **Copy the demonstrated demand, not the video.**

Successful source content is evidence of audience demand and a research object. The finished production must derive its main value from its own research, argument/story, script, narration, visual construction, and editing.

### Source Dependency Test

Ask:

> If borrowed source clips were removed, would the new video's main value — its script, argument, story, research, and insight — still exist?

If **no**, the concept is too dependent on the source.

## 3. System architecture

```text
01 Opportunity Engine
        ↓
02 Retention Engine
        ↓
03 Transformation Engine
        ↓
04 Story & Script Engine
        ↓
05 Format Engine
        ↓
06 Production Engine
        ↓
07 Quality Gates
        ↓
08 Learning Engine
        ↺
```

### 01 — Opportunity Engine

Purpose: identify what may be worth making.

Candidate signals:

- demonstrated demand;
- channel-relative breakout;
- momentum;
- competition/timing;
- later: transformability.

**Current work is here.**

### 02 — Retention Engine

Purpose: understand the mechanisms that kept viewers choosing and continuing to watch.

Research dimensions:

- packaging;
- hook;
- open loops;
- narrative progression;
- information reveals;
- visual/audio resets;
- payoffs;
- satisfaction.

Published "best practice" numbers are hypotheses until validated. Examples such as fixed hook windows, fixed visual-reset intervals, or universal retention percentages must not automatically become system rules.

### 03 — Transformation Engine

Purpose: turn evidence from successful content into genuinely new concepts.

Expected flow:

```text
Source candidate
      ↓
Why-it-worked analysis
      ↓
Transferable mechanisms
      ↓
Multiple new angles
      ↓
Source Dependency Test
      ↓
Research / verification
      ↓
Selected concept
```

### 04 — Story & Script Engine

Produces:

- hook;
- story architecture;
- evidence-backed script;
- fact verification;
- visual directions.

The system should preserve useful mechanisms without reproducing the source creator's script or story.

### 05 — Format Engine

Long-form and Shorts are separate production branches.

They may share:

- source understanding;
- research;
- facts;
- master story package.

They should not be treated as identical edits of the same timeline.

### 06 — Production Engine

Potential capabilities:

- narration/voice;
- controlled source-footage use;
- B-roll;
- graphics;
- animation;
- music/SFX;
- editing/composition;
- rendering.

OpenMontage and related production tooling belong here. Production tooling is the backend, not the creative decision-maker.

### 07 — Quality Gates

Human review remains part of the system.

Planned gates:

- concept/hook gate;
- script gate;
- source/copyright/licensing gate;
- rough-cut gate;
- final human review.

### 08 — Learning Engine

Once content is published, actual channel performance should increasingly replace generic internet benchmarks.

Potential measurements include:

- appeal/click or viewed-vs-swiped signals as appropriate to format;
- retention curve;
- average view duration;
- average percentage viewed;
- dips and spikes;
- engagement/satisfaction indicators;
- publishing outcome.

Learnings feed back into Opportunity, Retention, Transformation, Story, and Format decisions.

## 4. Current milestone

# M1 — Prove the Opportunity Engine

Do not build all eight engines at once.

The immediate goal is to establish whether the discovery system can consistently surface useful source opportunities across multiple niches.

### Experiment 01.1

Current collector:

`experiment_01_discovery/youtube_discovery.py`

Current niche configuration:

`experiment_01_discovery/niches.json`

The experiment searches 10 niches × 3 queries.

### Signals currently collected

**Demand**

- views;
- original reference threshold status.

**Breakout**

- channel baseline median;
- baseline sample size;
- baseline confidence;
- baseline warnings;
- outlier ratio.

**Momentum proxy**

- publication age;
- average views per day.

Important: `average_views_per_day` is lifetime average accumulation, **not current velocity**. True velocity requires repeated observations.

**Format candidate**

- duration;
- `short_candidate` or `long_form_candidate`.

Duration is only a heuristic and does not prove YouTube classified a video as a Short.

## 5. Current research hypotheses

These remain deliberately unfrozen:

- Analysis collection floor: **500,000 views**
- Long-form proven-demand reference: **1,000,000 views**
- Short-candidate proven-demand reference: **5,000,000 views**
- Channel-relative breakout is useful, but a large ratio alone must not automatically qualify a video.
- Baseline sample quality matters because tiny or weak channel baselines can inflate outlier ratios.
- Demand, breakout, and momentum should initially be inspected independently rather than collapsed into a composite score.

The 30-query dataset will be used to determine whether these assumptions survive contact with evidence.

## 6. Planned next experiment

### Experiment 02 — Why Did It Work?

Use a small set of strong candidates from Experiment 01 to study:

```text
TOPIC
PACKAGING
HOOK
STORY
EMOTION
PACING
VISUAL LANGUAGE
AUDIENCE PROMISE
```

Candidate retention mechanisms include:

- pattern interruption;
- curiosity gaps;
- primary/secondary hooks;
- open loops;
- narrative escalation;
- information reveals;
- visual/audio resets;
- payoff.

These are variables to test, not universal laws.

Experiment 02 should produce a structured **why-it-worked profile** that can feed the Transformation Engine.

## 7. Scope control

Before adding an agent, database, vector store, queue, framework, scraper, API, or automation layer, identify the specific validated failure or bottleneck it solves.

Do not add infrastructure merely because it may be useful later.

## 8. Success condition for M1

M1 succeeds when we can demonstrate that the Opportunity Engine:

- discovers candidates across multiple niches;
- distinguishes absolute demand from channel-relative breakout;
- handles weak baselines transparently;
- avoids calling lifetime average views/day "current velocity";
- does not mistake duration heuristics for confirmed Shorts classification;
- provides enough evidence to select candidates for Experiment 02 without relying on an invented composite score.

Only then should discovery logic be frozen and the project advance.
