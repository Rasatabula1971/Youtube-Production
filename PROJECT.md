# PROJECT — YouTube Production

## 1. Objective

Build a repeatable system that:

1. discovers demonstrated audience demand;
2. determines why successful content worked;
3. transforms transferable mechanisms into genuinely new concepts;
4. researches and verifies the new concept;
5. creates an original story and script;
6. packages the concept so its promise is clear and compelling;
7. selects the correct format;
8. produces the video;
9. applies human quality gates; and
10. learns from actual publishing performance.

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
02 Packaging Engine
        ↓
03 Retention Engine
        ↓
04 Transformation Engine
        ↓
05 Research / Story / Script Engine
        ↓
06 Format Engine
        ↓
07 Production Engine
        ↓
08 Quality Gates
        ↓
09 Learning Engine
        ↺
```

The diagram is a responsibility map, not a rigid one-way runtime pipeline. In practice, Transformation and research can inform Packaging, and the Learning Engine feeds evidence back into every upstream stage.

### 01 — Opportunity Engine

Purpose: identify what may be worth making.

Candidate signals:

- demonstrated demand;
- channel-relative breakout;
- momentum;
- competition/timing;
- later: transformability.

**Current work is here.**

### 02 — Packaging Engine

Purpose: turn a worthwhile concept into a clear viewer promise that earns the choice to watch.

Research and production dimensions:

- concept framing;
- title;
- thumbnail for surfaces where thumbnails matter;
- opening-frame presentation where format requires it;
- curiosity gap;
- specificity;
- emotional or practical payoff;
- consistency between packaging and the actual video.

Title and thumbnail should complement rather than merely duplicate each other when both are relevant.

Packaging must not make a promise the video does not satisfy.

### 03 — Retention Engine

Purpose: understand and construct the mechanisms that keep viewers watching after they choose the video.

Research dimensions:

- hook;
- open loops;
- narrative progression;
- information reveals;
- escalation;
- visual/audio progression;
- payoffs;
- satisfaction of the original promise.

Published "best practice" numbers remain hypotheses until validated. Fixed hook windows, fixed visual-reset intervals, universal retention percentages, and claims that one signal dominates the recommendation system must not automatically become production rules.

The project should increasingly learn from actual retention curves, including intros, top moments, spikes and dips, once its own videos are published.

### 04 — Transformation Engine

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

Transformation should preserve useful mechanisms without reproducing the source creator's script or story.

### 05 — Research / Story / Script Engine

Produces:

- evidence and primary-source research where practical;
- fact verification;
- hook;
- story architecture;
- evidence-backed script;
- visual directions.

A useful default is narrative progress rather than disconnected facts, but individual formats may justify other structures.

### 06 — Format Engine

Long-form and Shorts are separate production branches.

They may share:

- source understanding;
- research;
- facts;
- master story package.

They should not be treated as identical edits of the same timeline.

### 07 — Production Engine

Potential capabilities:

- narration/voice;
- controlled source-footage use;
- B-roll;
- graphics;
- animation;
- music/SFX;
- editing/composition;
- rendering.

Visuals should support the narration or story rather than exist only to create motion.

OpenMontage and related production tooling belong here. Production tooling is the backend, not the creative decision-maker.

### 08 — Quality Gates

Human review remains part of the system.

Planned gates:

- concept gate;
- packaging/hook gate;
- script/fact gate;
- source/copyright/licensing gate;
- rough-cut gate;
- final human review.

### 09 — Learning Engine

Once content is published, actual channel performance should increasingly replace generic internet benchmarks.

Potential measurements include:

- appeal/click or viewed-vs-swiped signals as appropriate to format;
- retention curve;
- average view duration;
- average percentage viewed;
- intros, dips, spikes and top moments;
- engagement/satisfaction indicators;
- publishing outcome.

Learnings feed back into Opportunity, Packaging, Retention, Transformation, Story, Format, and Production decisions.

## 4. Current milestone

# M1 — Prove the Opportunity Engine

Do not build all nine engines at once.

The immediate goal is to establish whether the discovery system can consistently surface useful source opportunities across multiple niches.

### Experiment 01.2

Experiment 01.1 proved collection and baseline measurement but exposed relevance contamination in the first automotive run. Experiment 01.2 keeps the same collector and adds query provenance, deterministic relevance labels, outlier reliability flags, and theme annotations.

Current collector:

`experiment_01_discovery/youtube_discovery.py`

Current niche configuration:

`experiment_01_discovery/niches.json`

The collector can search 10 niches × 3 queries. Experiment 01.2 is first being rerun on the same 3 automotive queries before expanding.

### Experiment 01.3 — Age-Matched Velocity Validation

Experiment 01.3 controls for publication age before comparing current topic
momentum. It freezes a same-age cohort, separates Shorts and long-form
candidates, measures repeated-snapshot velocity, and keeps experiment output
physically isolated.

### Experiment 01.4 — Depth-First Topic Expansion

Experiment 01.4 consumes validated 01.3 topic/format evidence and expands only
cells with replicated current-velocity evidence across multiple channels.

Its first mode is offline planning, so query families and YouTube search cost
are frozen before any search quota is spent. Execution is checkpointed and
quota-bounded.

01.4 remains part of the Opportunity Engine. It does not replace Experiment 02,
which will study why selected successful videos worked creatively.

### Experiment 01.5 — Opportunity Handoff Gate

Experiment 01.5 combines the validated topic/format evidence from 01.3 with
the deeper sub-angle evidence from 01.4 and creates auditable candidate packets
for Experiment 02.

It is offline and uses explicit PASS / REVIEW / HOLD evidence gates rather than
a composite opportunity score. A small diversity-constrained study set becomes
the formal handoff from M1 into Experiment 02.

### Signals currently collected

**Search provenance**

- matched queries;
- best search rank;
- niche/query/rank records.

**Relevance quality**

- ON_INTENT;
- ADJACENT;
- OFF_INTENT;
- explicit reason/matched terms.

**Outlier reliability**

- TRUSTED;
- CAUTION;
- UNAVAILABLE;
- explicit reason.

**Theme annotations**

- configured multi-label content mechanisms for the niche.

**Query competition profile**

- channel concentration;
- channel-size distribution;
- result recency;
- query-level relevance and outlier evidence;
- no composite competition score.

**Snapshot velocity**

- repeated view-count observations;
- measured view delta over elapsed time;
- current views/hour and views/day when a prior snapshot exists.

**Topic evidence**

- topic-level demand/breakout aggregation;
- separate Shorts and long-form evidence.

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

## 6. Next experiment

### Experiment 02 — Why Did It Work? Framework

The Experiment 02 framework is now implemented offline. It consumes the
Experiment 01.5 study set, prepares evidence profiles, validates supported
creative findings against typed evidence, separates findings from hypotheses,
and aggregates repeated mechanisms across independent videos/channels.

The framework itself does not download videos, fetch transcripts, call an LLM,
or spend YouTube API quota.

Actual source analysis begins only after the Experiment 01.5 study set exists
and transcript/thumbnail/visual evidence has been supplied.

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
PAYOFF
```

Candidate mechanisms include:

- curiosity gaps;
- primary/secondary hooks;
- open loops;
- narrative escalation;
- information reveals;
- visual/audio changes;
- payoff;
- title/thumbnail promise;
- opening-frame promise.

These are variables to test, not universal laws.

Experiment 02 should produce a structured **why-it-worked profile** that can feed both the Packaging and Transformation/Retention engines.

## 7. Working production theory

Current evidence and source material support a broad model:

```text
Proven demand
    ↓
Original concept
    ↓
Packaging / viewer choice
    ↓
Retention / continued viewing
    ↓
Satisfaction / promised payoff
    ↓
Measured performance
    ↓
Learning
    ↺
```

The following are useful working principles:

- idea/topic selection precedes expensive production;
- packaging should make a clear promise;
- the opening should quickly establish or begin fulfilling that promise;
- story/progression is often more useful than disconnected facts;
- visuals should correspond to the information being communicated;
- weak sections should be identified from real retention data and improved in later productions;
- repeated production is for learning and format discovery, not merely upload consistency.

The following remain **hypotheses**, not hard rules:

- visual change every 3–5 seconds;
- audio being a fixed percentage of the experience;
- one universal hook duration;
- the first 30 seconds determining whether a video "goes viral";
- universal retention targets;
- particular niches automatically having a higher million-view ceiling;
- a single repeatable structure guaranteeing million-view performance.

## 8. Scope control

Before adding an agent, database, vector store, queue, framework, scraper, API, or automation layer, identify the specific validated failure or bottleneck it solves.

Do not add infrastructure merely because it may be useful later.

## 9. Success condition for M1

M1 succeeds when we can demonstrate that the Opportunity Engine:

- discovers candidates across multiple niches;
- distinguishes absolute demand from channel-relative breakout;
- handles weak baselines transparently;
- avoids calling lifetime average views/day "current velocity";
- does not mistake duration heuristics for confirmed Shorts classification;
- provides enough evidence to select candidates for Experiment 02 without relying on an invented composite score.

Only then should discovery logic be frozen and the project advance.


## 7. Transformation Engine framework

The Transformation Engine framework is now implemented offline.

It consumes the future Experiment 02 transformation handoff and prepares
mechanism-bound concept-generation requests only from entries that are
READY_FOR_TRANSFORMATION_ENGINE.

Returned concepts are structurally validated for:

- unique concept identity;
- premise and audience promise;
- format intent;
- mechanism application;
- transformation method;
- independent research questions;
- declared absence of source-specific elements; and
- a passing Source Dependency Test with no required source assets.

The engine does not rank concepts, calculate a composite score, or claim that a
mechanism will cause performance.

### Concept Gate

The human Concept Gate sits between structural concept validation and research.

Every concept receives exactly one decision:

- ACCEPT;
- REWORK; or
- REJECT.

ACCEPT requires explicit human confirmation that the concept is original
enough, has a clear audience promise, is source-independent, feasible, and
researchable.

Only ACCEPT concepts enter the future Research Engine handoff. Working titles
remain provisional and are not treated as final packaging.


## 8. Research Engine framework

The Research Engine framework is implemented offline.

It consumes only concepts accepted by the human Concept Gate and creates one
research plan per concept. Original concept research questions receive stable
question IDs so claims can be traced back to the information need they answer.

Structured research responses separate:

- source provenance;
- factual claims;
- claim role;
- linked research questions; and
- evidence links with SUPPORTS / CONTRADICTS / QUALIFIES stances.

The engine reports structural claim coverage as UNSUPPORTED, SINGLE_SOURCE,
MULTI_SOURCE, or CONFLICTED. These are evidence-shape labels, not truth scores.

### Research Gate

The human Research Gate reviews each claim against its cited source, locator,
and evidence note.

Every claim receives ACCEPT / REWORK / REJECT. ACCEPT requires explicit human
confirmation that the source is traceable, wording is supported, conflicts are
addressed, and the claim is safe for script use.

CONFLICTED claims require a written resolution note before acceptance.

A research package becomes READY_FOR_STORY_SCRIPT only when at least one claim
is accepted and every original research question is covered by an accepted
claim. Otherwise the package remains RESEARCH_INCOMPLETE.

Only sources used by accepted claims are retained in the verified research
package.


## 9. Packaging Engine framework

The Packaging Engine is implemented as the required bridge between human-
accepted concepts and deep research / scripting.

The project uses a package-before-script rule:

- title and thumbnail are treated as one communication unit;
- the package defines one core promise and expected payoff;
- title and thumbnail should complement rather than merely repeat each other;
- expected viewer and awareness level are explicit;
- opening-frame intent is part of the package;
- any factual or evidentiary dependency implied by the package must be listed
  for downstream research.

The engine creates multiple package candidates but does not rank them or predict
CTR.

### Packaging Gate

Every package candidate receives ACCEPT / REWORK / REJECT.

ACCEPT requires explicit human confirmation of promise clarity, concept
alignment, title/thumbnail complementarity, non-misleading framing, viewer-
awareness fit, payoff clarity and explicit research dependencies.

At most one package may be accepted per concept.

Only concepts with one approved package enter the Research Engine. The approved
package's research dependencies are converted into mandatory package research
questions, so the future Story / Script Engine cannot inherit an unverified
title/thumbnail promise.
