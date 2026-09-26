# DECISIONS — YouTube Production

This file records project decisions separately from hypotheses. Items marked **Hypothesis** remain open to evidence.

## D-001 — Proven content is evidence, not a template to copy

**Status:** Accepted

Use successful videos to identify demonstrated demand and transferable mechanisms. Do not treat the source video itself as the production blueprint.

> **Copy the demonstrated demand, not the video.**

## D-002 — Use the Source Dependency Test

**Status:** Accepted

A transformed concept should retain its main value even if borrowed clips are removed. If its script, argument, story, research, or insight collapses without the source footage, it is too dependent on the source.

Selective source footage may still be useful as evidence or illustration, subject to rights/licensing/copyright review.

## D-003 — Separate Opportunity, Packaging, and Retention

**Status:** Accepted

The system treats these as distinct questions:

- **Opportunity:** What is worth making?
- **Packaging:** Will the intended viewer choose it?
- **Retention:** Will the viewer keep watching and receive the promised payoff?

Do not use retention mechanics as a substitute for demand research, or demand metrics as a substitute for packaging and creative construction.

## D-004 — Long-form and Shorts require separate format logic

**Status:** Accepted

They may share research and a master story package, but Shorts should not simply be chopped long-form videos and long-form should not inherit Shorts assumptions.

## D-005 — No final opportunity score in Experiment 01.1

**Status:** Accepted

Measure Demand, Breakout, Momentum proxy, baseline quality, and format independently first. Inspect the full dataset before defining a composite score or ranking model.

## D-006 — Rename velocity measurement honestly

**Status:** Accepted

`views / age_days` is **average views per day over the video's lifetime**, not current velocity.

True velocity requires repeated snapshots separated in time.

## D-007 — Duration is only a format heuristic

**Status:** Accepted

A video of 180 seconds or less may be labelled `short_candidate` for research, but the system must not claim that duration alone proves YouTube classified it as a Short.

## D-008 — Retention-engineering rules are hypotheses until tested

**Status:** Accepted

Claims such as:

- hook at 0–3 seconds;
- secondary hook at 15–20 seconds;
- visual reset every 3–5 seconds;
- fixed retention targets;
- the first 30 seconds determining virality;
- a single universally dominant ranking signal;

must not become hard production rules solely because creator/vendor literature recommends them.

Experiment 02 will test which mechanisms appear consistently in successful source content.

## D-009 — Current demand thresholds remain hypotheses

**Status:** Hypothesis

Reference values currently under test:

- analysis floor: 500K views;
- long-form reference: 1M views;
- short-candidate reference: 5M views.

These values are not yet frozen.

## D-010 — Channel-relative breakout is useful but insufficient alone

**Status:** Hypothesis supported by initial test

Large outlier ratios can identify unusual performance, but small channel baselines can produce misleading ratios. Baseline sample size and warnings must accompany the ratio.

Full 30-query evidence is still required.

## D-011 — OpenMontage is production infrastructure, not the creative brain

**Status:** Accepted

Discovery, why-it-worked analysis, transformation, research, story, packaging, and format decisions should occur upstream. OpenMontage or equivalent tooling belongs in the Production Engine.

## D-012 — Build incrementally

**Status:** Accepted

Current milestone is **M1 — Prove the Opportunity Engine**.

Do not build all planned engines simultaneously. Each new layer should address a demonstrated requirement or failure.

## D-013 — Generated experiment output remains untracked for now

**Status:** Accepted

Keep API secrets and generated experiment output out of Git:

- `.env`
- `experiment_01_discovery/output/`

Source code, configuration, project documentation, and validated decisions belong in the repository. Evidence-storage policy can be revisited when repeated experiments need versioned datasets.

## D-014 — Packaging is a first-class engine

**Status:** Accepted

Packaging is not merely a retention subtask. It governs the viewer's decision before retention can occur.

Its responsibility includes concept framing, title, thumbnail where relevant, opening-frame presentation where relevant, curiosity/promise, and alignment between the promise and the delivered video.

## D-015 — Production should optimize for progress, not arbitrary motion

**Status:** Accepted

Frequent visual change can be useful, but "change the screen every 3–5 seconds" is not a universal project rule.

Visuals should advance understanding, emotion, evidence, story, or attention. Generic motion or unrelated stock footage is not considered progress merely because it changes the screen.

## D-016 — Actual channel evidence should replace generic benchmarks over time

**Status:** Accepted

Published best-practice numbers are starting hypotheses. Once the project publishes enough content, its own packaging, retention, satisfaction, and outcome data should increasingly determine production decisions.

## Next decision gate

Run the full 30-query Experiment 01.1 dataset and review its distributions.

Questions for that gate:

1. Does the 500K collection floor retain enough useful candidates?
2. Are the 1M/5M reference thresholds informative?
3. How stable is channel-relative breakout across niches?
4. How often are baseline warnings triggered?
5. How should recency and lifetime average view rate be represented?
6. Is a composite score justified at all?
7. Which candidates should enter Experiment 02?


## D-017 — Relevance is a separate evidence dimension

**Status:** Accepted

High views or a high channel-relative breakout do not prove that a result is relevant to the intended content market.

Experiment 01.2 records relevance separately as `ON_INTENT`, `ADJACENT`, `OFF_INTENT`, or `UNREVIEWED`. OFF_INTENT rows remain in raw outputs so search contamination stays measurable.

## D-018 — Outlier reliability does not alter the raw ratio

**Status:** Accepted

The raw channel-relative `outlier_ratio` remains unchanged. A separate reliability annotation records whether the ratio is `TRUSTED`, requires `CAUTION`, or is `UNAVAILABLE`.

Weak baseline samples, baseline warnings and extreme ratios are reasons for caution, not reasons to rewrite the measurement.

## D-019 — Relevance rules must be auditable and data-tuned

**Status:** Accepted

Experiment 01.2 uses explicit niche configuration and deterministic term matching rather than an opaque final relevance score.

Rules should be changed in response to observed false positives/false negatives from live datasets. The first automotive sample already showed that the words "engineer" and "mechanic" alone are too weak to qualify a video as technical intent, so they are treated as context signals instead.


## D-020 — Query competition is a profile, not a score

**Status:** Accepted

Experiment 01.2 records channel concentration, channel scale, recency and query-level evidence independently. It does not collapse them into a proprietary-style keyword or competition score.

The current YouTube API query uses `order=viewCount`, so result position must not be described as organic relevance rank.

## D-021 — Current velocity requires repeated observations

**Status:** Accepted

Lifetime `views / age_days` remains a historical accumulation measure. A separate snapshot store records repeated view counts and calculates views/hour and views/day only when observations are separated by at least one hour.

Count decreases are treated as platform/data adjustments, not negative audience velocity.

## D-022 — Topic evidence is separate from presentation theme

**Status:** Accepted

A topic answers what the video is about (for example brakes or aerodynamics). A theme describes a transferable presentation/content mechanism (for example hidden mechanisms, comparisons or rules/loopholes).

Topic evidence is aggregated separately for Shorts and long-form, and OFF_INTENT rows do not contribute.


## D-023 — Age-matched validation precedes depth expansion

**Status:** Accepted

Before expanding deeply into a topic, control the freshness confound with
Experiment 01.3. A topic/format cell should show replicated current-velocity
evidence across multiple independent channels before Experiment 01.4 spends
additional search quota on deeper sub-angle discovery.

Depth expansion is still Opportunity Engine work. It must not be treated as a
substitute for Experiment 02's creative why-it-worked analysis.

## D-024 — Expansion query planning is frozen before execution

**Status:** Accepted

Experiment 01.4 separates zero-quota planning from YouTube search execution.

The plan records evidence-ready cells, deterministic query families, format
branches, search ordering, lookback window and call budget before execution.
Execution is checkpointed so quota interruptions do not silently change the
planned experiment or repeat completed search work.


## D-025 — Opportunity handoff uses explicit gates

**Status:** Accepted

The transition from the Opportunity Engine to Experiment 02 must preserve the
evidence that justified each source candidate.

Experiment 01.5 uses explicit PASS / REVIEW / HOLD conditions based on:

- replicated 01.3 age-matched topic velocity evidence;
- independent-channel coverage;
- replicated 01.4 depth-family evidence; and
- the current project demand-reference hypothesis.

It does not calculate a composite opportunity score.

## D-026 — Experiment 02 receives a diverse evidence set

**Status:** Accepted

The automatic Experiment 02 study set can contain only PASS candidates.

Coverage constraints limit repeated videos from the same channel and repeated
videos from the same topic/format cell. Ordering uses the primary
age-matched-velocity metric, with absolute views only as a tie-breaker.

The resulting study set is a research handoff, not a claim that its first item
is universally the best video.


## D-027 — Experiment 02 findings require typed source evidence

**Status:** Accepted

Creative findings in Experiment 02 must reference identifiable source evidence.

Supported evidence types include metadata, transcript segments, thumbnails,
opening frames, visual notes, timing notes and audio notes.

Opportunity evidence from Experiments 01.3-01.5 explains why a source was
selected. It does not substitute for source-content evidence when making claims
about packaging, hook, story, pacing, emotion, visuals or payoff.

Unsupported interpretation must remain explicitly labelled as a working
hypothesis.

## D-028 — Repeated mechanisms are observational, not causal proof

**Status:** Accepted

Experiment 02 may identify mechanisms that recur across successful videos and
independent channels.

Repeated occurrence does not prove that the mechanism caused the performance.
Claims such as "this made it viral" or "the algorithm pushed it because of X"
require evidence that public source-video observation does not provide.

Cross-video aggregation therefore reports replicated patterns, not causal
effects.

## D-029 — Transformation opportunities must pass the Source Dependency Test

**Status:** Accepted

A transformation opportunity in Experiment 02 must record whether it passes the
Source Dependency Test and why.

Transferable mechanisms must be separated from source-specific wording,
footage, personality, story details and execution. The objective is to preserve
a useful mechanism while creating a new concept whose main value survives
without the source creator's expression.


## D-030 — Source evidence ingestion is local and fingerprinted

**Status:** Accepted

Experiment 02 source acquisition is separated from interpretation.

The initial ingestion layer accepts user-supplied transcript, image and
timestamped-note files rather than automatically scraping or downloading source
media.

Every imported source file is SHA-256 fingerprinted. Stable evidence IDs and
file provenance are recorded so a later creative finding can be traced back to
the exact source material used.

Registering a file is not itself an observation. Thumbnail or opening-frame
files without a written observation remain `REGISTERED_UNOBSERVED` and cannot
automatically support a creative finding.

Local evidence files and generated enriched profiles remain untracked by Git by
default.


## D-031 — Analysis execution separates reasoning from acceptance

**Status:** Accepted

Experiment 02 separates creative reasoning from deterministic evidence
acceptance.

An analyst or model may propose findings, mechanisms, source-specific elements
and transformation opportunities. The repository accepts them only after
checking their evidence references, evidence type, controlled mechanism IDs,
causal wording and Source Dependency Test requirements.

A proposed finding that is not adequately supported is preserved as a
`working_hypothesis` with the reason it was not accepted. It must not silently
enter the factual analysis.

The helper does not infer semantic labels such as hook, curiosity gap, payoff or
story structure from keyword rules alone. Those labels require analysis of the
available source evidence.
