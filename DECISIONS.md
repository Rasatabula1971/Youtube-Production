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


## D-045 — 01.3 does not refresh structurally insufficient cohorts

**Status:** Accepted

A frozen Experiment 01.3 cohort is not considered refresh-worthy merely because
discovery exited successfully.

At least one topic/format cell must meet the configured independent-channel
floor before velocity refresh is enabled. If no cell meets that floor, the
human-facing state is INSUFFICIENT COHORT and the next action is another
discovery pass.

The yt-dlp fallback uses only currently supported `ytsearch` acquisition.
For each configured query it merges the base query with a year-hinted query
derived from the active age window, then prefilters known age, format and view
metadata before official API enrichment.

The removed/broken `ytsearchdate` scheme must not be used.

Official YouTube video/channel metadata remains canonical for final cohort
acceptance and velocity measurement.

Official candidate view observations are retained across cohort rebuilds in a
persistent snapshot ledger, and archived official observations may be reused
for the same video ID. Replacing a cohort must not needlessly reset the
measurement clock.


## D-046 — A topic is not a finished viewer need

**Status:** Accepted

Opportunity evidence may establish that a topic attracts attention, but a concept
must separately identify the specific problem, question or curiosity the viewer
is trying to resolve, the moment in which that need matters, and the desired
outcome.

Transformation therefore records `viewer_problem`, `viewer_moment` and
`desired_outcome` before Concept Gate review.

Demand does not substitute for this framing.

## D-047 — Content-gap claims preserve evidence status

**Status:** Accepted

A content gap must be labelled `SUPPORTED`, `HYPOTHESIS` or `UNASSESSED`.

Popularity, outlier performance or model intuition alone do not prove that an
existing content gap exists. `SUPPORTED` requires a concrete evidence basis.

Future comment/question mining may provide audience evidence for repeated
unanswered problems, confusion, missing examples or follow-up needs. Until such
evidence exists, gap claims remain hypotheses or unassessed.

No numeric gap score is introduced.

## D-048 — Channel fit is separate from popularity

**Status:** Accepted

A concept can be popular and still be wrong for the audience/channel the project
intends to build.

Concept Gate and Packaging Gate therefore require explicit human confirmation of
channel fit/alignment. Channel fit is not inferred from views and is not reduced
to a numeric score.

## D-049 — Three-title and one-sentence tests are clarity gates

**Status:** Accepted

Before Concept Gate acceptance, a concept must support at least three distinct
working title options. This is an idea-clarity test, not final title selection
or ranking.

Packaging must then express the viewer need and outcome in one clear sentence.

If the idea cannot survive these clarity checks, the correct action is REWORK /
REFRAME rather than cosmetic title optimization.


## D-050 — Downstream framework code does not close M1

**Status:** Accepted

M1 remains **Prove the Opportunity Engine** until its live success criteria are
demonstrated and the operator has reviewed the resulting opportunities.

Experiment 02, Transformation, Packaging and Research components may exist as
offline frameworks ahead of M1 closure. Their implementation is preparatory
work, not evidence that the upstream milestone succeeded.

Repository status documents must distinguish between:

- framework implemented;
- live evidence demonstrated; and
- milestone formally closed.

The human opportunity gate between 01.5 and Experiment 02 is part of that
boundary: machine-generated demand evidence does not automatically authorize
creative analysis or downstream production work.


## D-051 — Age-matched velocity baselines are niche-and-format matched

**Status:** Accepted

Experiment 01.3 topics must declare an explicit niche.

The age-matched velocity index compares a topic median only with the cohort
median for the **same niche and same format**. A format-only denominator is not
allowed once more than one niche can exist in the experiment.

A video that validates multiple topics in one niche contributes once to that
niche/format cohort denominator. This preserves topic comparisons without
double-counting the same video merely because it matched more than one topic.

The former top-level format-only cohort median remains only as a transitional
single-niche compatibility alias. It becomes empty when multiple niches are
present so cross-niche pooling cannot silently return.


## D-052 — Frozen-cohort velocity refresh is schedulable and self-limiting

**Status:** Accepted

Repeated-snapshot velocity must not depend on the operator remembering to click
Refresh at the right time.

On Windows the project may register a recurring Task Scheduler job that invokes
a project-owned scheduled refresh runner. The runner may call only the existing
Experiment 01.3 frozen-cohort refresh path; it must never perform discovery.

The runner skips API work when there is no usable cohort, when a recent
snapshot already exists, when another scheduled refresh is running, or when the
current cohort already has enough velocity evidence for Experiment 01.4.

Manual refresh remains available as an explicit control and for diagnostics.


## D-053 — Confidence labels name the evidence dimension they describe

**Status:** Accepted

`baseline_confidence` and topic replication breadth are different concepts and
must not be presented as one generic confidence scale.

Channel baseline confidence continues to describe the quality of the historical
comparison sample for one source channel.

Experiment 01.3 uses `topic_channel_confidence` to describe the number of
independent channels supporting a topic/format cell. Its LOW / MODERATE /
STRONG thresholds are not reused for channel baseline quality.


## D-054 — Opportunity Engine experiments are automated behind a human-facing workflow

**Status:** Accepted

Experiments 01.3, 01.4 and 01.5 remain independently runnable and testable, but
they are no longer the normal operator workflow.

The creator-facing action is **Run Opportunity Research**. The orchestrator may
perform discovery, timed frozen-cohort measurement, depth expansion and handoff
construction automatically. It must stop at the Human Opportunity Gate.

Velocity refreshes may be scheduled automatically at two-hour intervals on
Windows. The system stops after three actual refresh attempts without sufficient
evidence and requests human attention instead of polling indefinitely.

Doctor commands, manual experiment actions, clean restart, scheduler management
and benchmarks are maintenance tools and belong under **Tools & Diagnostics**.


## D-055 — Creator workflow uses multiple views, not one scrolling control page

**Status:** Accepted

The normal working UI is split into Home, Opportunity, Analyze & Create, and
Tools & Diagnostics views.

Home should fit the current decision, next step, compact progress and recent
activity without exposing full experiment internals. Human opportunity review
gets its own workspace. Experiment 02 and later creative stages share the
Analyze & Create workspace. Doctors, manual experiment controls, raw outputs and
technical stage state belong in Tools & Diagnostics.

The Live Job console is global and opens as a drawer so logs remain available
without occupying permanent vertical space.


## D-056 — Experiment 02 network acquisition is separate from offline ingestion

**Status:** Accepted

Experiment 02 may automatically acquire public source evidence, but network
acquisition must remain outside `evidence_ingest.py`.

The source-acquisition layer may use `yt-dlp` to retrieve English captions,
thumbnail and metadata with `--skip-download`. It must not download video media
as part of this evidence step.

A transcript is required before automatic acquisition can create an enriched
profile. A thumbnail without an observation is provenance only and cannot
support a finding.

Guided Experiment 02 readiness is provenance-aware. Current prepared profiles,
enriched profiles, analysis requests and analyzed outputs must correspond to the
current approved video set; stale same-ID artifacts do not advance the workflow
unless their recorded hashes match the current upstream artifact.


## D-057 — Visual structure evidence is objective and non-semantic

**Status:** Accepted

Experiment 02 may stream a low-resolution source rendition through `ffmpeg`
without saving the full video file.

The automated visual stage may record detector-derived facts such as candidate
scene-transition timestamps, transition frequency and interval statistics.
Those are `timing_note` evidence.

Extracted frames are not automatically treated as semantic evidence. An opening
frame or scene frame becomes claim-supporting visual evidence only after a human
or a validated multimodal vision layer supplies an observation.

Visual structure is preferred when `yt-dlp` and `ffmpeg` are available, but
a failed attempt must not deadlock Experiment 02. The workflow may continue with
transcript-only evidence after an attempted failure, while a force-retry remains
available as a maintenance action.


## D-058 — Vision model output requires explicit human acceptance

**Status:** Accepted

Semantic frame descriptions are allowed into Experiment 02 only after a human
decision.

A local Ollama vision model may generate draft observations for retained source
frames, but model drafts are not evidence and cannot unlock downstream analysis
by themselves.

The human reviewer must accept, edit-and-accept, or reject every selected frame.
Accepted scene observations are stored as `visual_note` evidence with the
source frame SHA-256. Accepted opening-frame observations are stored as
`opening_frame` evidence.

The review set is intentionally bounded to avoid review overload: opening frame
plus at most eight evenly distributed scene frames per video.

The automatic provider is local-first and free/open-source friendly. When no
local model is configured or available, the workflow falls back to human-only
review rather than blocking.


## D-059 — Concept generation is automated; concept selection remains human

**Status:** Accepted

After Experiment 02 produces a human-confirmed transformation handoff, the
Transformation Engine may use FAIR free-only routing to generate multiple
concept candidates.

Generated concepts must still pass the deterministic Transformation schema and
Source Dependency Test before appearing in the Concept Gate.

No concept score, ranking, predicted virality, or automatic winner selection is
introduced.

Every runner-produced response is bound to the SHA-256 of the exact concept
request that produced it. Every concept request is bound to the SHA-256 of the
current Experiment 02 transformation handoff.

The human Concept Gate remains mandatory. ACCEPT requires every configured
human criterion to be affirmed. Only accepted concepts may enter the Research
Engine handoff.


## D-060 — Long-form and Shorts are planned as separate productions

**Status:** Accepted

After the Human Script Gate approves a script, the Format Engine plans one
production branch per required format rather than one timeline that is later
re-cut.

The approved concept `format_intent` determines the required branches:
`long_form` and `short` each require their own branch, and `either` requires
both. An unrecognised `format_intent` fails deterministic validation instead of
defaulting to a branch.

Branches share source understanding, research, accepted facts and the master
story package. They are not identical edits of one timeline. A plan whose
branches carry the same beat sequence, or whose shorter branch is a prefix of
the longer one, fails deterministic validation before human review.

Every beat carrying factual material cites Research Gate accepted `claim_id`
values, and every beat traces to the approved script `section_id` values it is
built from. Each branch must carry at least one accepted claim, so no branch
drifts free of verified research.

Branch duration bounds, beat minimums and aspect ratios are configuration, not
proven production rules. They remain hypotheses open to revision by the Learning
Engine.

No format score, predicted retention, or automatic branch winner is introduced.

The Human Format Gate remains mandatory. ACCEPT requires every configured human
criterion to be affirmed, and each review request is bound to the SHA-256 of the
exact format plan it was prepared from. Only accepted format plans may enter the
Production Engine.


## D-061 — Voice performance is planned by the system and rendered by Higgsfield

**Status:** Accepted

The Voice Performance Layer is the first sub-stage of the Production Engine
(07). It consumes Format Gate approved plans and produces one performance
specification per production branch, because a performance curve belongs to a
branch, not to a script.

### What the layer owns and what it does not

The layer annotates approved beats with performance direction. It never
rewrites what is said. The approved script and its accepted claims are the
input; the layer adds only how each beat is delivered.

Higgsfield is the single production provider for narration and generated
video. Provider independence, as proposed in the original design note, is
consciously deferred in favour of simplicity. The performance specification
remains a JSON artifact so that a later provider change is a data migration
rather than a rebuild, but the control vocabulary is Higgsfield's own exposed
controls (emotion, speed, pauses, emphasis), read from its API at build time.

### Performance vocabulary

Six core emotions: `neutral`, `curious`, `serious`, `concerned`, `tense`,
`reflective`. `surprised` is permitted only on a reveal beat. The range is
deliberately narrow because the channel is faceless: with no visual affect
channel, large vocal swings read as performed rather than felt. Expressive work
sits in pace, pause placement and emphasis rather than emotional amplitude.

An intensity ceiling and a maximum change between adjacent beats are
configuration. They are enforced by deterministic validation before the human
gate. Their starting values are hypotheses, not validated rules.

### Voice identity

The project renders with a licensed voice, not a clone. Cloning is not enabled
at the adapter. The voice identity (`provider`, `voice_id`, licence reference)
is recorded in artifact provenance. Calibration is one human listening pass
across the emotion range with the chosen voice, recorded as a config artifact
bound to the voice identity; a change of voice invalidates it.

### Free and paid channels

Performance annotation runs through FAIR free-only routing under the existing
cost policy. Rendering is paid and runs through a separate metered channel
that is never routed through the FAIR bridge. A dry-run estimate quotes the
worst case (one render plus two regenerations per segment) before any paid
call, and the Human Performance Gate must accept the specification before any
credit is spent.

### Audio QC and regeneration

Audio QC is deterministic only: expected duration, unexpected silence,
clipping, and missing segments, checked locally with `ffmpeg`. A failed
segment may be regenerated at most twice; a third failure escalates to a
human. No acoustic emotion verification is attempted.

### Accepted provider facts

A paid Higgsfield plan is required; free-tier output is watermarked and
carries no commercial licence. Higgsfield trains on inputs and outputs by
default for non-enterprise accounts. Both are accepted knowingly.

No performance score, predicted retention, or automatic take selection is
introduced. The human rough-cut gate (08) remains mandatory before publish.

## D-062 — Visual acquisition is cheap-first before paid generation

**Status:** Accepted

The Production Engine does not default to generating every visual with
Higgsfield. During pre-monetization testing, the system proves audience demand
before increasing production spend.

The default visual source order is:

1. project-owned and previously licensed reusable assets;
2. verified free commercial-use footage;
3. verified public-domain material;
4. compatible Creative Commons material with recorded licence provenance;
5. third-party editorial excerpts, which always require human rights/context
   review;
6. project-created motion graphics or still treatments;
7. low-cost AI generation; and
8. Higgsfield premium generation.

This order is a cost policy, not a legal conclusion. The system never implements
a "three-second rule" or any other clip-duration shortcut. An
`EDITORIAL_EXCERPT` is never auto-selected regardless of duration. Its source,
intended use and context are preserved for the source/copyright/licensing gate.

Every candidate asset records provenance and rights metadata where applicable,
including source URL or local path, licence reference, commercial-use status,
attribution requirement and estimated paid cost.

For the `pre_monetization` production phase, the initial operating target is
US$5 or less of paid visual generation per finished video and the automated
hard cap is US$10. These values are hypotheses for economical channel testing
and remain configuration, not universal production rules.

D-061 remains in force for narration: the Voice Performance Layer plans delivery
and Higgsfield renders the licensed voice. D-061's earlier assumption that
Higgsfield is the single generated-video provider is narrowed by this decision:
for visuals, Higgsfield is the premium fallback after cheaper acceptable routes
have been exhausted.

The first implementation is deliberately offline. It prepares provenance-bound
visual manifests and routes supplied candidates without web search, downloads or
provider calls. External acquisition and paid-generation adapters are added only
after this policy layer is proven by tests.

## D-063 — Story structure is planned before narration and Packaging owns the title

**Status:** Accepted

After the Research Gate verifies the factual material, the Story / Script Engine
runs in two machine stages:

1. **Story Plan** — decides the viewer journey, hook intent, progression,
   explanation/reveal sequence, payoff and closing intent.
2. **Script Draft** — turns that accepted structure into natural spoken
   narration.

The Story Plan is structural, not polished prose. It may use only Research Gate
accepted claim IDs for factual beats and must contain a payoff beat. Every script
section maps to exactly one Story Plan beat, and the factual claim IDs attached
to that section must match the claim IDs assigned to the corresponding beat.

The Human Script Gate remains the single human boundary for this stage. A
separate human Story Plan gate is not added; the final script review explicitly
checks that the narration followed the Story Plan.

The **Packaging title is immutable downstream**. Packaging owns the title because
it defines the click promise. Story Planning, Script Writing, Format Planning,
Voice Performance and Production may fulfill that promise but may not silently
rewrite it. Both Story Plan and Script validators fail closed if their returned
title differs from the approved Packaging title.

This separation exists to prevent one model call from simultaneously inventing
structure and wording, which can produce informative but shapeless scripts or
allow the story to drift away from the approved package promise.

## D-064 — Audience psychology is explicit in Story Planning and Script Writing

**Status:** Accepted

The Story / Script Engine makes audience psychology an explicit, auditable
planning layer instead of leaving "engagement" as an unstructured model
instruction.

The first spoken line is a hard design requirement: it must be high-impact and
directly connected to the approved Packaging promise. Allowed opening
mechanisms are contradiction, surprising fact, stakes, expectation violation,
specific curiosity and bold promise. "High-impact" does not mean unsupported
sensationalism. Factual hook claims remain bounded by Research Gate accepted
claims, and the narration immediately following the hook must justify,
contextualize or begin proving it.

Each Story Plan beat records one primary audience mechanism, the viewer
expectation being acted on, a cognitive-load instruction, tension level and
open-loop action. Explicit open loops are stateful: every OPEN must ultimately
receive a PAYOFF. A plan with an unresolved open loop fails deterministic
validation.

The mechanisms available to beats are curiosity, prediction, tension, stakes,
novelty, expectation violation, clarity and payoff. They describe the intended
viewer experience; they are not claims that a given mechanism guarantees
retention or virality.

The design intentionally avoids universal timing rules such as "hook by three
seconds" or "pattern interrupt every five seconds." YouTube's own retention
guidance emphasizes that the opening should match the title/thumbnail promise,
keep the audience interested, and be tested against actual retention data. The
Learning Engine should therefore refine these hypotheses from channel evidence
rather than hard-code generic timing folklore.

External evidence also supports a narrower distinction: higher-arousal emotion
has been associated with greater online sharing, including in research on viral
video, but sharing evidence does not prove that simply making narration more
dramatic improves YouTube retention. The system therefore optimizes for
high-impact, credible openings rather than maximum emotional intensity.

Evidence references:
- YouTube Help, "Measure key moments for audience retention":
  https://support.google.com/youtube/answer/9314415
- YouTube Help, "Understand your content performance for YouTube's recommendation system":
  https://support.google.com/youtube/answer/16559650
- Berger & Milkman (2012), "What Makes Online Content Viral?":
  https://doi.org/10.1509/jmr.10.0353
- Nelson-Field, Riebe & Newstead (2013), "The emotions that drive viral video":
  https://doi.org/10.1016/j.ausmj.2013.07.003

## D-065 — Final narration splits by format before the Human Script Gate

**Status:** Accepted

D-065 refines D-060, D-063 and D-064. The **Story Plan remains shared**, but
final spoken wording no longer waits until the Format Engine to become
format-specific.

After the shared Story Plan is validated, the Story / Script Engine resolves the
approved `format_intent` and writes one script request per required branch.
`either` therefore produces a `long_form` script and a `short` script before
the Human Script Gate.

### Long-form psychology profile

Long-form keeps the high-impact truthful opening requirement but does not carry
a fixed timing interval. It prioritizes sustained curiosity, progressive
understanding, lower cognitive overload, examples/breathing room where useful,
and larger delayed payoffs.

### Shorts psychology profile

Shorts uses a high reward-density profile. Its starting production hypotheses
are:

- first spoken hook target: **3 seconds**;
- meaningful attention/reward refresh: roughly **every 4–6 seconds**;
- low cognitive branching and one dominant idea;
- repeated progress through proof, novelty, reveal, expectation shift or
  micro-payoff;
- rapid loop closure and a strong final payoff.

These numbers are **hypotheses to be tested against actual Shorts retention**,
not universal neurological or physiological laws. The system does not claim to
measure dopamine. "Reward density" is an operational storytelling label for
frequent meaningful viewer progress.

The 3-second target is not guessed from text length. After narration rendering,
actual audio timing can determine whether the opening meets the target. A miss
should become a rework signal rather than silent speeding or rewriting.

### Gate and downstream contract

The Human Script Gate reviews each required branch independently. A concept is
not production-ready until every required branch is accepted. Only then is one
approved script bundle emitted.

The bundle keeps the branch narrations separate. Identical narration sequences,
or a Short that is merely a prefix/truncation of the long-form script, fail
closed.

The Format Engine now owns **production treatment only**. It may plan scenes,
visuals, duration intent, aspect ratio and production beats around the approved
branch narration, but it may not rewrite, paraphrase, shorten, combine or
substitute that narration.

Voice Performance subsequently binds each production branch only to the
matching approved script sections, preserving branch isolation through audio
planning.

## D-066 — Concept Gate uses four direct human choices

**Status:** Accepted

The Human Concept Gate uses four mutually exclusive choices that map directly
to reviewer intent:

- **ACCEPT** — approve the concept as-is and send it forward.
- **REJECT** — discard it from the forward workflow.
- **REWORK** — keep the concept but revise selected parts.
- **SAVE IDEA** — park it in the Idea / Title Bank for possible future use.

The criteria checkboxes are **not acceptance gates**. They are REWORK controls:
checked criteria mean "keep this part"; unchecked criteria mean "change this
part." ACCEPT, REJECT and SAVE IDEA ignore checkbox state.

SAVE IDEA is terminal for an active gate concept: it counts as reviewed but does
not enter Packaging/Research. From a non-active override card, or after the gate
is already complete, Save Idea remains a bookmark-only action.

This keeps human review explicit without forcing repetitive confirmation clicks
that add no new decision information.

## D-067 — Human Framing uses a drama floor and changing tempo

**Status:** Accepted

Concept generation now includes a Human Framing Layer before a technical topic
is allowed to become the final concept. Every concept must define a Hook
Experience, Viewer Question, Psychological Pull, Explanation Payoff and Visual
Opening Plan.

Drama is an editorial scale, not a biological measurement or a prediction of
retention. Normal production uses a **4/10 floor** and a **5/10 center**. The
system actively raises intensity when the opportunity truthfully contains
stronger danger, consequence, loss, contradiction, transformation, scale or
decision tension. Levels 9-10 are reserved for opportunities that genuinely
support extreme stakes or spectacle.

Each concept records both **drama capacity** and **drama target**. Target may not
exceed capacity and may not underuse capacity by more than three points. This
prevents high-drama opportunities from being reduced to low-energy technical
framings.

Drama is not held constant. Story Planning and Format Planning use changing
beat-level drama values from 4-10. Tempo is a separate 1-10 control and must
also change. A slow beat can therefore remain high drama, and a lower-drama beat
can provide breathing room without becoming boring.

The framing contract is preserved through Packaging and Research. Research must
verify factual assumptions inside the hook, stakes, drama source and payoff.
Story, Format and Voice Performance inherit the accepted framing rather than
reinventing or flattening it downstream.

No stage may manufacture catastrophe, danger or certainty merely to raise the
drama score.

## D-068 — FAIR remains primary; repo Gemini is free-tier exhaustion fallback

**Status:** Accepted

All FAIR-backed YouTube stages must call FAIR first. The repo-local
`DIRECT_GEMINI_API_KEY` is not a peer provider and is not part of normal FAIR
routing.

Direct Gemini is eligible only when FAIR returns `ESCALATION_REQUIRED`,
confirms `paid_inference_executed: false`, and reports a recognized free-route
exhaustion/unavailability state. FAIR quality failures, bridge/internal
failures, validation failures, disagreement, system stops, or unknown cost
states must not bypass FAIR into Gemini.

The default repo-Gemini order is:

1. `gemini-3.5-flash-lite`
2. `gemini-3.5-flash`

Temporary capacity/rate failures may advance to the next configured free-tier
model. If the chain cannot return a valid response, the pipeline preserves its
current artifacts and remains partial for a later retry. No paid-inference
route is permitted.

Gemini quota values are not hard-coded from documentation examples. The app
records provider-returned token usage when available and relies on the actual
Google project/model limits and HTTP quota/capacity responses. The former
1,000,000-token assumption is not treated as a daily ceiling.

## D-069 — Gemini schema rejection falls back to deterministic JSON mode

**Status:** Accepted

The repo-local Gemini free-tier backup first requests structured JSON using the
stage's response schema. Google documents that very large or deeply nested
structured-output schemas may be rejected even when their individual JSON
Schema keywords are supported.

When Direct Gemini returns HTTP 400 while the full response schema is attached,
the adapter retries the same free model once in JSON-only mode using
`application/json` without a response schema. The generated JSON is still
parsed and passed through the exact same stage-specific deterministic validator;
no concept, research, script, format, or voice artifact is accepted merely
because JSON mode returned syntactically valid JSON.

Quota/capacity errors retain the D-068 routing behavior: 429/temporary 5xx may
advance to the next configured free Gemini model, and exhaustion preserves
partial state for a later retry. Paid inference remains prohibited.


## D-070 — Channel Voice is versioned channel configuration, not a global project voice

**Status:** Accepted

The YouTube Production system does not have one universal writing voice.
Different channels may use the same Opportunity, Research, Story/Script, Format
and Production engines while presenting with different audience assumptions,
narrator posture, tone, technical-language treatment, sentence style,
storytelling preferences and prohibited style.

The repository therefore defines a versioned **Channel Voice Profile** layer.
A profile becomes generation-active only when its status is `APPROVED`.
Story Planning binds the exact active profile version and hash into the story
request, and downstream Script Writing inherits that bound profile rather than
re-reading whichever profile happens to be active later.

Until a channel thesis, niche and target viewer are deliberately chosen, the
active profile remains `UNCONFIGURED`. In that state the model must not infer
a persistent channel personality from the niche, title, source videos or
generic creator advice. Existing research, Human Framing, psychology and format
rules continue to operate normally.

Channel Voice is distinct from Voice Performance. Channel Voice controls how a
channel writes and presents ideas; Voice Performance controls how an approved
script is spoken, including emotion, intensity, speed, pauses and emphasis.

Future profiles are versioned rather than silently overwritten. Published
retention, comment and performance evidence may justify Voice v2, v3 and later,
but learning-driven changes remain explicit human-approved channel decisions.


## D-071 — Canonical selective Script Rework state is separate from the Script Draft

**Status:** Accepted

Selective Script Rework uses `script_section_state.py` as its single
per-target state contract. It does not embed mutable review state in the Script
Draft or create a second competing section-state format.

Stable target IDs are `hook:opening`, `section:<section_id>`, and
`closing:closing`. Each target has a deterministic `target_sha256`, decision,
locked flag, ordinal and optional rework metadata. The state records the exact
source Script Draft path/SHA-256, a monotonically advancing `state_version`,
timestamps and action history.

State creation fails closed for missing/duplicate section IDs and for target IDs
that collide after filesystem normalization. Before use, the target set and
hashes are recomputed from the exact Script Draft; changed draft content or
tampered state is stale.

Slice 1 is non-destructive: it creates review state but never changes narration.


## D-072 — Section decisions and branch approval share one canonical consistency boundary

**Status:** Accepted

Section actions are handled by `script_section_service.py` and
`script_section_state.py`. Supported target actions are `ACCEPT`, `LOCK`,
`UNLOCK`, `REWORK`, and `CANCEL_REWORK`.

`ACCEPT` marks a target accepted and locked. `LOCK` may freeze a pending
target without accepting it. Unlocking an accepted target returns it to
`PENDING`. A locked target cannot be reworked until explicitly unlocked.
Rework requires a supported bounded reason or custom instruction; the canonical
custom reason token is `CUSTOM`.

Every state action is written to history and advances `state_version`. These
actions never mutate Script Draft text.

The local UI supplies logical concept/format/target identities only; service
code resolves project-owned artifact paths and validates draft identity.
`REWORK` and `UNLOCK` invalidate stale branch-level response/bundle artifacts.

Section mutations and whole-branch Human Script Gate decisions use the same
in-process lock. Whole-branch `ACCEPT` checks the canonical state and fails if
any target is `REWORK_REQUESTED`. This prevents a threaded branch-accept versus
section-rework race from leaving contradictory approval state.


## D-073 — Slice 3 prepares one bounded, provenance-locked rework request before inference

**Status:** Accepted

A separate `PREPARE_REWORK_REQUEST` action exists before alternative
generation. It may run only for a canonical target already marked
`REWORK_REQUESTED`.

Slice 3 request preparation performs no FAIR/model call and cannot change the
Script Draft. The request contains only the selected target, its immutable
metadata, immediately adjacent read-only context, locked-target IDs, the human
rework reason/instruction, target-scoped accepted claims, relevant Story Plan
beats and shared story intent, psychology constraints, approved package
constraints, and the exact bound Channel Voice.

The request is bound to SHA-256 provenance for the exact Script Draft, canonical
section-state file, original Script Request and Human Script Gate review request,
plus the current `state_version` and selected `target_sha256`.

Before a request can be trusted, `assert_request_current()` checks all bound
artifacts and rebuilds the expected request from current trusted state. Edited
request packets, changed source artifacts, cancelled rework, locked targets or
changed target content fail closed.

Request preparation and current-state validation use the same state lock as
human section decisions. The FAIR-backed runner also validates again after an
inference call returns; if the human changes section state while FAIR is
running, the stale result is discarded and no alternatives artifact is
accepted.

The repository already contains downstream A/B/C generation, human selection,
safe single-target replacement, manual edit and UI/service capabilities. Those
are distinct from Slice 3: preparing the request itself spends no inference and
changes no narration.

## D-074 — Slice 4 alternatives are strict claim-bound artifacts, not free-form rewrites

**Status:** Accepted

Selective Script Rework Slice 4 generates exactly three non-destructive
alternatives (A/B/C) from the bounded Slice 3 request.

The FAIR response schema and the local deterministic validator enforce the same
closed contract. Each alternative must contain only its ID, replacement text,
change summary and `claim_ids_used`. Extra fields, missing fields, wrong value
types, reordered/missing A/B/C identities or malformed claim declarations fail
closed.

Every alternative must declare `claim_ids_used` exactly equal to the accepted
claim IDs already mapped to the selected target. Alternatives cannot expand the
target's factual scope by naming unrelated accepted claims. A target with no
mapped claims must declare an empty claim list.

Because claim IDs alone cannot prove that prose has not invented a quantitative
fact, Slice 4 also applies a conservative numeric guard. A numeric token may
appear in a replacement only if it was already present in the original selected
target or in one of the target's bound accepted-claim statements.

All candidates remain subject to the source-overlap block and must differ from
both the original target and one another.

Generation revalidates Slice 3 provenance after FAIR returns. If draft/state or
human review state changes while inference is running, the returned result is
discarded before a response or alternatives artifact is accepted.

A validated alternatives artifact is bound to the exact rework request,
validation-contract hash and saved model-response file/hash. Cached artifacts
are deterministically rebuilt from that response before reuse. A changed cache
fails closed and does not trigger a hidden replacement model call.

Human selection does not trust the response path written inside the alternatives
artifact. The expected response path is resolved from repository-owned
concept/format/target identity and must match artifact provenance. This prevents
artifact path tampering from redirecting selection to a different response.

Slice 4 itself never mutates the Script Draft or section state. Human application
of Original/A/B/C remains a separate downstream action.


## D-075 — Slice 5 selection is explicit, serialized and fully recoverable

**Status:** Accepted

The system may apply a selective Script Rework only after an explicit human
choice of `ORIGINAL`, `A`, `B` or `C`. No automatic stage, model result,
cache hit or retry may choose a replacement.

Selection is serialized with the canonical section-state lock. Concurrent
choices for the same target cannot both commit, and selection cannot race a
simultaneous section-state mutation or manual edit inside the same process.

Before mutation, Slice 5 revalidates the exact Slice 4 alternatives artifact,
its deterministic model-response provenance and the current Slice 3 request.
The target must still be `REWORK_REQUESTED` and unlocked.

A/B/C replacement must change exactly one target. Non-target hashes are checked
both before writing and again from the persisted draft. The full Script
validator must pass before the replacement is accepted. The selected target is
then rebased as `ACCEPTED` and locked.

Previous script versions are exact byte copies of the parent draft, not JSON
re-serializations. Their SHA-256 must equal the recorded
`parent_draft_sha256`. Human revision provenance also records the parent
section-state hash, selected replacement hash, selected claim IDs, exact rework
request/model-response hashes and alternatives artifact hash before selection.

Choosing `ORIGINAL` must leave the Script Draft hash unchanged and does not
increment the human script revision. It only resolves the rework decision by
accepting/locking the target and recording the human choice.

The Slice 5 transaction snapshots every file selection can modify, including
Script Draft, section state, alternatives artifact, Human Script Gate request
and response, approved bundle, and any previous-version destination. Each
existing file is backed up as exact bytes with a SHA-256; previously absent
files are recorded as absent.

Rollback validates every required backup before restoring any destination. A
missing or changed backup fails closed without beginning a partial recovery.
Rollback restores exact previous bytes and removes files created only by the
failed transaction.

Recovery of `PREPARED` or `IN_PROGRESS` transactions occurs before the
one-time-selection check. This is required because an interrupted process may
have written a temporary selection marker before crashing; that marker must not
prevent recovery on the next human action.

## D-076 — Slice 6 keeps selective review inside the existing Human Script Gate

**Status:** Accepted

Selective Script Rework does not become a separate page or separate human gate.
Slice 6 exposes the canonical section-review service inside the existing Human
Script Gate.

The UI shows target-level state, progress and the next unresolved target while
retaining the whole branch script alongside it. Per-target actions are
`Accept + lock`, `Lock`, `Unlock`, `Request rework` and
`Cancel rework`.

The Slice 3 no-inference boundary is visible as `Prepare rework request`.
Slice 4 generation remains a separate `Generate A / B / C` action. Generated
Original/A/B/C choices are shown inline and are not applied until the human
clicks one choice.

Every section mutation is treated as single-flight in the browser. While one is
running, target navigation and branch-level decisions are disabled. This is a
UI safety layer only; canonical backend locking and transaction protection
remain authoritative.

Whole-script `Accept` is disabled when canonical section state is stale or any
target remains `REWORK_REQUESTED`.

After a section action, the browser reloads the Human Script Gate snapshot for
the same concept/format immediately. This prevents stale narration from
remaining visible after an A/B/C selection or manual edit.

Slice 6 adds no new script-generation behavior, model route, persistence
contract or destructive backend operation.

## D-077 — Prepared selective review is binding at the Script → Format seam

**Status:** Accepted

Selective section review is optional until its canonical state is prepared. A
branch that never enters selective review may still use the original
whole-script Human Script Gate.

Once section state is prepared, every target must be explicitly `ACCEPTED`
and locked before whole-branch `ACCEPT` may succeed. A pending locked target
does not count as reviewed.

The approved Script bundle records the exact section-state path, SHA-256,
version, target count and ordered target ID/hash lineage for each reviewed
branch.

Production readiness is derived from current provenance, not from approved-file
existence. If section state changes after branch approval, the concept is no
longer considered production-ready even if the previous approved bundle remains
on disk.

Format independently validates the section-state provenance and its bound Script
Draft before creating any Format Request. This prevents stale or redirected
selective-review state from bypassing the Human Script Gate through a manual
Format run.

Backward compatibility is preserved only when no canonical section review was
ever prepared. An older approved bundle becomes stale as soon as a prepared
section-state exists without matching provenance.

## D-078 — Script completion automatically advances to the Human Format Gate

**Status:** Accepted

A valid completed Human Script Gate is followed by deterministic Format machine
work without another routine run-button decision.

The existing automatic workflow runner must execute
`format_prepare → format_generate → format_gate_prepare` and then stop at the
Human Format Gate. It must not auto-approve Format or continue into Voice
Performance before the human Format decision.

The Script Gate POST handler starts `auto_continue` only when downstream
machine work is actually enabled and no other job is running. The browser shows
that automatic continuation explicitly.

The Script → Format handoff is also an invalidation boundary. When the approved
Script input changes, all Format artifacts derived from the previous request are
stale and are removed. Current filenames alone are insufficient evidence of
currency; response, plan, model-run and gate provenance must still match the
current request/plan hashes.

Unchanged provenance remains cacheable. Slice 8 therefore removes stale work
without forcing unnecessary FAIR calls for valid current work.

The Human Format Gate is the mandatory stopping point after automatic Format
preparation.

## D-079 — Format completion automatically advances to the Human Performance Gate

**Status:** Accepted

A valid completed Human Format Gate is followed by deterministic Voice
Performance machine work without another routine run-button decision.

The existing automatic workflow runner executes
`voice_prepare → voice_generate → voice_gate_prepare` and then stops at the
Human Performance Gate. It must not auto-approve the performance plan or
authorize/render paid narration before the human performance decision.

The Format Gate POST handler starts `auto_continue` only when downstream
machine work is ready and no other job is running. The browser explicitly
announces the automatic continuation.

The Format → Voice handoff is an invalidation boundary. When the approved
Format input changes, Voice responses, performance specs, model-run records,
raw model output, Human Performance Gate packets/decisions, and approved voice
specs derived from the previous request are stale and removed.

Current filenames alone are not proof of currency. Voice specs and Human
Performance Gate artifacts must remain bound to the current canonical Voice
request by hash provenance. Valid unchanged provenance remains cacheable.

The Human Performance Gate is the mandatory stopping point after automatic
Voice Performance planning. This boundary spends no narration-provider credits.

## D-080 — Performance completion automatically advances to the free Narration Preview Gate

**Status:** Accepted

A completed Human Performance Gate is followed by the zero-cost prototype chain
without another routine run-button decision.

The automatic workflow executes
`pre_render_engagement → narration_preview_prepare → prototype_sound_prepare →
narration_preview_render` and then stops at
`HUMAN_NARRATION_PREVIEW_GATE`.

No paid narration quote, provider render, or spend authorization may cross this
boundary before the operator hears and approves the current free preview.

The free preview chain is provenance-bound. A saved engagement PASS is current
only when its approved Voice Performance spec path and SHA-256 still match.
Likewise, a preview manifest, local preview render, and preview approval are
current only when they remain bound to the exact current approved Voice
Performance spec and exact preview audio hash.

An old preview approval therefore cannot authorize a paid narration quote after
the upstream performance plan changes.

Kokoro is the current local preview renderer. Missing local dependencies fail
closed; the workflow must not silently fall through to a paid TTS provider.

The automatic runner treats the current Narration Preview Gate as a hard human
boundary even if stale downstream quote/spend artifacts happen to exist.

## D-081 — Preview approval advances to a provenance-bound Narration Spend boundary

**Status:** Accepted

A completed Human Narration Preview Gate may automatically continue through
zero-spend final-audio preparation:

`sound_design_brief_prepare → narration_prepare → narration_spend_gate_prepare`.

The automatic workflow stops before paid narration in one of three states:

1. `HUMAN_NARRATION_SPEND_GATE` when a current provider quote and current
   worst-case cost exist;
2. `WAITING_NARRATION_PROVIDER_QUOTE` when the current provider-bound request
   and quote template are ready but no valid current quote exists; or
3. `NARRATION_PROVIDER_SETUP_REQUIRED` when voice identity, licence,
   calibration or verified provider-contract prerequisites are incomplete.

No missing price may be guessed or synthesized. A Human Narration Spend Gate
exists only for a current quote bound to the exact current narration render
request.

The Sound Design Brief is part of the provenance chain. It is current only when
the Human Preview approval, preview manifest, preview audio and approved Voice
Performance spec hashes still match. Narration render requests record the
current Sound Design Brief hash.

A stale or malformed provider quote returns the branch to quote-required state
instead of crashing or inheriting an old cost. A changed cost estimate
invalidates stale spend-review responses and approved spend authorizations.

The Human Narration Spend Gate displays the initial and worst-case USD quote,
requires every spend criterion, and requires an explicit human confirmation
before an ACCEPT can authorize that ceiling. Preparing or viewing the gate
does not call the paid provider.

## D-082 — Paid narration returns are registered before deterministic Audio QC

**Status:** Accepted

Slice 12 does not add an unverified paid-provider adapter. After the Human
Narration Spend Gate accepts the exact current worst-case quote, the workflow
moves to `WAITING_NARRATION_RENDER_RETURN`.

The operator registers the provider return with:

- the current concept/format branch;
- provider job, transaction, or receipt reference;
- actual cumulative USD cost;
- every narration segment in exact request order;
- the attempt number for each segment; and
- a local provider-returned audio file for each segment.

Registration is rejected unless the Human Narration Spend approval is current,
the exact narration render request and estimate are still current, the actual
cost is at or below the approved worst-case ceiling, every segment is present
in exact order, and every attempt is within the approved regeneration policy.

Provider audio is copied into managed project storage and hash-bound to the
current render request and spend approval. Registering corrected audio
invalidates prior Audio QC and timing-map artifacts.

Duration QC is based on a deterministic target derived from the locked
narration text and approved delivery speed in the render request. Provider
metadata cannot supply or override the QC duration baseline.

After a complete current provider return is registered, local deterministic
Audio QC runs automatically. It checks duration tolerance, unexpected silence,
clipping, missing files, exact segment coverage, and attempt policy. No
automatic emotion grading or take selection is allowed.

If any current branch fails QC, the workflow stops at
`NARRATION_AUDIO_QC_FAILED` for corrected audio to be re-registered. Only
when every current authorized branch passes does the workflow reach
`NARRATION_AUDIO_READY`.

Slice 12 hard-stops at `NARRATION_AUDIO_READY`. Automatic visual production
must not begin in this slice.

## D-083 — QC-passed narration automatically advances to a current visual search plan

**Status:** Accepted

After every current authorized narration branch passes local Audio QC, the
automatic workflow may run these deterministic, zero-spend steps:

`production_visual_prepare → storyboard_prepare → visual_search_prepare`.

Slice 13 stops at `VISUAL_SEARCH_READY`. The zero-cost/existing-source search
adapters do not run in this slice.

The visual acquisition manifest is now bound to both:

- the exact current approved Format Plan hash; and
- the exact current QC-passed narration timing-map path/hash.

A manifest that is not bound to the current narration timing map does not count
as current production state.

Storyboards require exact one-to-one coverage between narration timing segment
IDs and visual requirement beat IDs. Missing, extra or mismatched beats fail
closed instead of receiving a generic fallback visual. Storyboards record the
current timing-map and visual-manifest hashes and are stale when either changes.

Visual search requests are rebuilt only from current storyboards. The request
records the exact storyboard hash. Old search requests/results are removed when
their storyboard is no longer current. Existing raw discovery data may remain
as a cache, but it cannot become current search results unless every shot
fingerprint matches the new request.

All visual planning in Slice 13 keeps `paid_generation_calls_allowed: false`.
Premium generation may be marked only as a future candidate for a high-value
unfilled gap; it is never authorized or called here.

## D-084 — Current free/existing visual discovery stops at the Human Candidate Gate

**Status:** Accepted

Slice 14 advances the current Slice 13 search plan through configured zero-cost
discovery only:

`VISUAL_SEARCH_READY → visual_search_acquire → HUMAN_VISUAL_CANDIDATE_GATE`.

Before any external discovery adapter is called, the search request must still
be current and bound to the current storyboard. The request hash is rechecked
before each shot so a mid-run upstream edit stops additional provider calls.

Discovery is resumable. Raw results are checkpointed after each shot. On a
later rerun, an unchanged shot is reused only when its fingerprint still
matches and its previous provider search completed without provider errors.
Changed or previously errored shots are searched again.

Each zero-cost provider is isolated. A timeout, malformed response or provider
failure cannot discard valid candidates returned by other providers. Provider
errors are preserved in the current candidate packet for human visibility.
There is no automatic retry storm; a later explicit rerun retries errored shots
while preserving clean cached shots.

Search results are current only when they are bound to the exact current search
request and contain the exact current shot IDs/fingerprints. The Human Visual
Candidate Gate opens only after every current search-required branch has a
current result.

The candidate gate never treats creator/editorial discovery as reuse
permission. Those candidates remain behind the separate human rights/context
gate. Unknown or unsupported rights remain blocked.

Slice 14 downloads no visual media and calls no paid generation provider.

## D-085 — Approved visual selections advance through managed assets to the Human Rough-Cut Gate

**Status:** Accepted

Slice 16 advances a completed Human Visual Candidate Gate, and any required
Human Rights/Context Gate, through the zero-cost asset/rough-cut path:

`candidate complete → rights complete → visual_asset_acquire → visual_rough_cut_prepare → HUMAN_ROUGH_CUT_GATE`.

Human gates remain hard stops. Automatic workflow must not bypass either the
Visual Candidate Gate, the Rights/Context Gate, or the Human Rough-Cut Gate.

A selected visual is usable media only when a current managed local asset record
exists. The managed record must remain bound to the current search result,
candidate review, optional rights review, selected candidate fingerprint and
local asset hash.

Verified zero-cost stock may be downloaded only through the existing allow-list
and size/type checks. Creator/editorial footage is never auto-downloaded. Once
its rights/context decision is approved, missing editorial media remains an
explicit rough-cut placeholder until a human supplies the local file.

Automatic acquisition failures are not silently converted into successful
placeholders. They keep asset acquisition non-current so Continue Automatically
can retry/fix acquisition before a rough cut is promoted.

Rough-cut provenance records every managed asset registry/file hash actually
used. Server readiness also compares that set with all current managed assets
for the branch. Adding or replacing a local asset therefore makes the old rough
cut stale.

Manual asset registration explicitly invalidates the affected rough cut and
starts the normal automatic rebuild path. Paid visual generation remains locked
throughout Slice 16.

## D-086 — Backfill Slice 15 as the Candidate → Rights/Context human boundary

**Status:** Accepted

Slice 15 is the logical boundary between Slice 14 search/candidate review and
Slice 16 managed-asset acquisition. It was implemented after Slice 16 because
the numbering was skipped, but its runtime position remains:

`HUMAN_VISUAL_CANDIDATE_GATE → HUMAN_VISUAL_RIGHTS_GATE when required`.

Candidate selection no longer trusts the stored `state` field by itself.
Automatic reuse is allowed only when the candidate belongs to a recognized
auto-reuse tier, has verified rights, explicitly allows commercial use, and
retains source/local provenance.

Recognized creator/editorial tiers always route to the Human Rights/Context
Gate even if a malformed or tampered result claims the candidate is
`ELIGIBLE`. Conversely, an unknown/unsupported source cannot become eligible
merely by claiming `DISCOVERY_ONLY` or `HUMAN_REVIEW_REQUIRED`.

The Rights/Context Gate independently verifies that:

- the candidate review is complete;
- its exact search-result hash still matches;
- the search result is still current against the storyboard/request chain;
- concept/format identity still matches;
- the selected shot and candidate fingerprints still match; and
- the candidate still belongs on the recognized human-rights route.

Stale candidate reviews cannot be approved. Historical rights decisions are
reconciled against the current selection and stale decisions are removed.

Human approval records the intended transformative/editorial context only. It
does not make a legal fair-use determination and does not authorize download,
asset acquisition or paid generation by itself.

The automatic workflow hard-stops at the Human Rights/Context Gate. Slice 16
remains responsible for any later zero-cost asset acquisition and rough-cut
preparation.

## D-087 — Rough-cut approval advances only to a current, globally capped Visual Spend boundary

**Status:** Accepted

Slice 17 owns the transition from Human Rough-Cut approval into unresolved-gap
planning and the Human Visual Spend boundary.

The normal flow is:

`HUMAN_ROUGH_CUT_GATE → visual_gap_prepare`

and then one of three stops:

- `HUMAN_VISUAL_SPEND_GATE` when at least one current unresolved hero shot
  meets the premium-generation threshold;
- `VISUAL_GAPS_READY_NO_SPEND` when current gap plans contain no premium
  generation candidate; or
- `VISUAL_SPEND_DECISIONS_COMPLETE` after every current premium candidate has
  a human decision.

Slice 17 does not prepare generation briefs, call a provider, build visual
assembly, or execute paid inference.

Gap plans are valid only while bound to the exact current rough cut and exact
current `APPROVE_WITH_GAPS` review. Rework, rough-cut mutation, or review
mutation makes the old gap plan stale. Preparation prunes stale gap-plan files.

The Visual Spend Gate accepts only current gap plans. Historical spend-review
files for stale/non-current plans are removed.

Spend configuration fails closed unless:

- currency is USD;
- human authorization is explicitly required;
- paid provider calls without authorization are explicitly forbidden;
- per-shot and workflow caps are finite and positive; and
- the per-shot cap does not exceed the workflow cap.

The workflow cap applies across all current branches, not per spend-review file.
Spend mutations are serialized in-process so concurrent approvals cannot each
observe the same remaining budget and jointly exceed the global cap. Non-finite
costs such as NaN or Infinity are rejected.

All spend decisions remain authorization records only. No visual generation
request or provider action is created in Slice 17.

## D-088 — Completed visual spend decisions advance only to zero-cost briefs and assembly

**Status:** Accepted

Slice 18 owns the transition after Slice 17's completed spend/no-spend boundary.

The normal machine path is:

`visual_generation_handoff_prepare` (only when paid generation was explicitly
authorized) → `visual_assembly_prepare`.

If no premium generation is authorized, the generation-handoff step is skipped
and the workflow builds the assembly plan directly.

Slice 18 never calls a paid provider, never renders media, and never starts the
structural edit preview. It stops at one of these boundaries:

- `VISUAL_ASSEMBLY_READY`;
- `WAITING_FOR_PREMIUM_VISUAL_ASSETS`;
- `WAITING_FOR_LOCAL_VISUAL_ASSETS`;
- `WAITING_FOR_VISUAL_ASSETS`; or
- `VISUAL_EXISTING_RETRY_REQUIRED`.

The visual spend review is canonical. Reading the spend snapshot must preserve
the recorded `COMPLETE` status, summary and authorized ceiling instead of
silently stripping them. Spend decisions are revalidated against their current
gap fingerprint and configured per-shot cap before any downstream stage can
trust them.

Premium generation briefs are derived only from the complete, globally valid
current spend snapshot. Every brief binds the exact gap-plan hash, spend-review
hash and exact human spend-decision hash. Preparing a brief authorizes no
provider call and sets `execution_authorized=false`.

Visual assembly is built only from the exact current rough cut, current
rough-cut approval, current gap plan and, for hero gaps, a complete current
spend review.

Slice 18 recognizes the managed asset statuses introduced by Slice 16:
`MANAGED_EXISTING_ASSET` and `MANAGED_EDITORIAL_ASSET`. A selected URL is
never treated as usable media unless its managed registry and local file remain
current.

`RETRY_EXISTING` is a real unresolved state. It blocks edit-preview
progression rather than being silently converted into a placeholder.

Authorized premium slots remain pending until a current generated asset is
registered against the exact generation request and within the approved cost
ceiling. Slice 18 does not implement provider execution.

## D-089 — Current visual assembly advances through a free local structural preview only

**Status:** Accepted

Slice 19 owns the transition from a current Slice 18 visual assembly into the
Human Edit Preview Gate.

The automatic path is:

`edit_manifest_prepare → edit_preview_render → HUMAN_EDIT_PREVIEW_GATE`

and only runs when every expected visual-assembly branch is current and
`READY_FOR_EDIT_ASSEMBLY`.

Slice 19 does not execute premium visual generation, final production handoff,
music/SFX generation, upload, publishing, or any paid/cloud fallback.

The edit manifest is not considered current merely because its source files
still exist. It must rebuild exactly from:

- the current Slice 18 visual assembly;
- the current registered narration render return;
- current PASS narration Audio-QC;
- the matching current narration timing map;
- exact local narration audio bytes; and
- the current approved sound-design brief when one exists.

If a sound brief did not exist when the manifest was built and is approved
later, the old manifest becomes stale.

The local structural preview renderer calls only the configured local FFmpeg
binary. A stale manifest is rejected before any subprocess runs. Missing local
FFmpeg is an explicit workflow boundary; no cloud or paid fallback is allowed.

A preview result is current only while:

- its exact manifest remains current and hash-matched;
- its preview file exists in the managed preview directory;
- its preview SHA-256 matches; and
- its recorded byte count matches the current file.

The Human Edit Preview Gate uses this same current-result contract. Therefore
assembly, narration, sound, manifest or preview mutation invalidates the old
human-review target.

The structural preview is explicitly non-publishable. It exists only to judge
story flow, pacing, narration-to-picture rhythm and visual continuity before
later final-production work.
