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


## D-032 — Model analysis runs through FAIR and the evidence gate

**Status:** Accepted

Automated Experiment 02 first-pass analysis must not call model providers
directly.

The initial runner uses FAIR as the provider router and cost-policy boundary.
FAIR validates response structure and free-only routing. Experiment 02 then
restricts the response to evidence that was actually supplied to the model and
runs the deterministic evidence apply gate.

A model response is not considered applied merely because FAIR accepted its
JSON shape. The resulting Experiment 02 profile must also pass final profile
validation.

The runner fails closed if FAIR reports paid inference, escalation, provider
failure, bridge failure, response parsing failure, or final profile validation
failure.

Recurring free-tier providers that require operator confirmation remain
unconfirmed by default. Runtime-zero-cost providers may use FAIR's own
zero-price enforcement.


## D-033 — Replicated model patterns remain drafts until human review

**Status:** Accepted

Cross-video synthesis may identify mechanisms that recur across independent
videos and channels, but model-generated analysis alone does not create a ready
Transformation Engine handoff.

A replicated mechanism is MODEL_SYNTHESIS_DRAFT until the same replication
threshold is met among profiles with review.completed=true. Only then is it a
HUMAN_CONFIRMED_PATTERN and eligible for READY_FOR_TRANSFORMATION_ENGINE.

Single-source observations remain visible in the mechanism library but do not
enter the transformation handoff.

Replication breadth, topic scope and format scope are descriptive evidence, not
a score or ranking.


## D-034 — Human review requires explicit item decisions

**Status:** Accepted

A model-analyzed Experiment 02 profile becomes human-reviewed only after every
factual analysis item and transfer item receives one explicit ACCEPT or REJECT
decision.

There is no implicit approval and no popularity-based approval. Reviewers judge
whether each claim fairly represents its cited evidence.

Rejected items are removed, accepted items remain unchanged, and the resulting
profile must still pass Experiment 02 validation before review.completed is set
to true.

Cross-video synthesis should automatically prefer human-reviewed profiles when
they are available, while retaining analyzed profiles as the fallback during
earlier pipeline stages.


## D-035 — Experiment controls use a local gated UI

**Status:** Accepted

Routine experiment execution should not require the operator to remember or
retype PowerShell commands.

A dependency-free local browser UI may invoke only predefined experiment action
IDs. It must not expose arbitrary shell execution.

The UI reads actual experiment outputs to determine readiness and preserves the
existing stage gates. In particular, Experiment 01.4 remains blocked until the
corrected Experiment 01.3 cohort has measured velocity evidence, not merely a
frozen manifest.

Only one experiment job may run at a time. The server binds to localhost and
retains job logs outside Git.


## D-036 — Transformation preserves mechanisms, not source expression

**Status:** Accepted

The Transformation Engine may use only Experiment 02 patterns that are ready
for the Transformation Engine under the existing human-review handoff gate.

A generated concept must preserve a transferable mechanism while remaining
independently valuable without the source creator's title, wording, footage,
story sequence, personality, examples, or exact execution.

Concepts must declare a passing Source Dependency Test, require no source
assets, and provide independent research questions before they can become
Concept Gate candidates.

The Transformation Engine does not rank concepts or calculate a concept score.

## D-037 — Concept selection is an explicit human gate

**Status:** Accepted

Structurally valid concept candidates do not move directly into research.

Every candidate receives one explicit ACCEPT / REWORK / REJECT decision at the
Concept Gate.

ACCEPT requires human confirmation of originality, audience-promise clarity,
source independence, feasibility, and researchability. REWORK requires a note
describing what must change. Only ACCEPT concepts enter the Research Engine
handoff.

The Concept Gate is not a performance prediction and does not create a numeric
concept ranking.


## D-038 — Research evidence structure is not automatic truth verification

**Status:** Accepted

The Research Engine records source provenance, claim wording, research-question
coverage and supporting / contradicting / qualifying evidence without
automatically declaring claims true.

UNSUPPORTED, SINGLE_SOURCE, MULTI_SOURCE and CONFLICTED are structural evidence
states only. MULTI_SOURCE does not mean verified, and CONFLICTED does not mean
false.

Source types are descriptive and no numeric source-authority score is
introduced.

## D-039 — Script claims require explicit human Research Gate approval

**Status:** Accepted

A draft research claim may enter the Story / Script Engine only after an
explicit human ACCEPT decision.

ACCEPT requires source traceability, supported wording, handled conflicts and
script-safety confirmation. An accepted CONFLICTED claim additionally requires
a written resolution note.

Rejected and REWORK claims do not enter the verified research package.

The verified research package is READY_FOR_STORY_SCRIPT only when every
original concept research question has at least one accepted claim. Otherwise
the package remains RESEARCH_INCOMPLETE.

Here, verified means human-approved for this project's script use, not universal
or permanent truth.


## D-040 — Packaging is approved before Story / Script

**Status:** Accepted

The Story / Script Engine must not begin from a topic or research package alone.

A human-approved packaging object must exist first and must define the intended
viewer, awareness level, title, thumbnail communication, opening-frame intent,
core promise, curiosity gap and expected payoff.

Title and thumbnail are treated as one communication unit and should complement
rather than simply repeat each other.

Packaging candidates are not ranked with a clickability score or predicted CTR.

## D-041 — Package dependencies become mandatory research questions

**Status:** Accepted

A packaging candidate may imply factual or evidentiary requirements that are
not yet verified.

Every candidate therefore records explicit research dependencies. Once a
package is human-approved, those dependencies become mandatory research
questions in the Research Engine.

The research package cannot become READY_FOR_STORY_SCRIPT until those package
questions are covered by accepted claims.

At most one package may be ACCEPTED per concept, preventing downstream research
and scripting from inheriting competing promises.


## D-042 — Agent Reach is an acquisition layer, not a reasoning layer

**Status:** Accepted

Agent Reach may be used to discover, read or transcribe external sources and to
report which upstream backend is currently healthy.

It must not replace the project's opportunity calculations, Experiment 02
evidence model, FAIR routing, Transformation / Packaging / Research decisions,
human gates, Story / Script logic, production logic or learning metrics.

The integration follows Agent Reach's own model: run doctor to determine the
active backend, then call that upstream tool directly.

## D-043 — Benchmark quota-free YouTube discovery before replacing search.list

**Status:** Superseded by D-044

Experiment 01.3 currently uses YouTube Data API search.list for controlled
discovery and official API endpoints for measurement.

Agent Reach / yt-dlp may be evaluated as a quota-free discovery backend, but
must not silently replace search.list.

The initial benchmark compares video-ID overlap per configured 01.3 query
against the saved API search audit and records the limitations caused by
different publication-window, duration and ordering controls.

Only after acceptable coverage and contamination are demonstrated may a new
discovery backend be added to Experiment 01.3.

Even then, official YouTube videos.list / channels.list remain the canonical
measurement and snapshot path.


## D-044 — Experiment 01.3 uses one automatic discovery control

**Status:** Accepted

Routine Experiment 01.3 discovery uses one AUTO control instead of requiring
the operator to choose between YouTube Data API v3 and Agent Reach / yt-dlp.

AUTO attempts YouTube search.list first. If that search path is unavailable or
quota-rejected, remaining discovery jobs automatically use the healthy Agent
Reach / yt-dlp backend.

This is a discovery fallback, not a measurement substitution.

All discovered IDs still pass the existing local age, minimum-view,
title-topic, motorsport-context and actual-duration validation. Official
YouTube videos.list / channels.list remain canonical for candidate metadata,
channel baselines, frozen cohort details and repeated velocity measurements.

Every query match and search audit record must retain discovery backend
provenance.

D-043's benchmark remains useful for comparing backend coverage, but successful
benchmarking is no longer a prerequisite for using yt-dlp as a continuity
fallback because the user explicitly chose automatic availability routing and
the project retains strict downstream validation plus official measurement.
