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
## D-090 — Approved edit direction advances only to a current zero-spend final-production handoff

**Status:** Accepted

Slice 20 owns the transition after the Human Edit Preview Gate approves the
current structural preview.

The automatic path is:

`EDIT_DIRECTION_APPROVED → final_production_handoff_prepare → FINAL_PRODUCTION_HANDOFF_READY`

The handoff step is deterministic and zero-spend. It does not call Higgsfield or
another paid provider, generate final music/SFX, perform a final render, upload,
or publish.

Final-handoff currentness is rebuild-based rather than path-existence based. A
handoff is current only when the exact Human Edit Preview approval still points
to a current Slice 19 preview result, the preview still resolves to a current
edit manifest, final visual/narration bytes still match, and the Sound Design
Brief is still current against its own upstream preview approval.

The currentness check rebuilds the handoff from those live inputs and requires
the stored artifact to match exactly. Mutating narration, visuals, the approved
sound brief, edit manifest, preview result, preview media, or edit approval
therefore makes the old handoff stale.

Generated-visual cost provenance includes only current generated assets that are
actually selected in the final visual track. Historical or replaced generated
asset registry entries are not added to the handoff total.

If final visuals are still missing, automation stops at
`WAITING_FOR_FINAL_VISUAL_ASSETS`. If a current handoff contains another
blocking condition, it stops at `FINAL_PRODUCTION_HANDOFF_BLOCKED`.

The successful Slice 20 boundary is `FINAL_PRODUCTION_HANDOFF_READY`. The
handoff records provider-neutral instructions and explicitly keeps provider
execution unauthorized. Final licensed music/SFX acquisition/provider execution
and publish-ready rendering remain later work.

## D-091 — Final sound is resolved by licensed asset registration or explicit omission before rendering

**Status:** Accepted

Slice 21 extends the current Slice 20 final-production handoff only through the
final sound asset trust boundary.

The automatic path is:

`FINAL_PRODUCTION_HANDOFF_READY → final_sound_plan_prepare → WAITING_FOR_FINAL_SOUND_ASSETS`

The deterministic sound plan derives stable, fingerprinted requirements from
the exact current final-production handoff. Each approved music direction
becomes a MUSIC requirement and each approved SFX direction becomes a separate
SFX requirement.

Slice 21 never calls a music/SFX provider, initiates a purchase, generates final
sound, renders final video, uploads, or publishes.

A human may resolve each current requirement in one of two ways:

1. register an already owned/licensed local sound file; or
2. explicitly omit the requirement with a human note.

Registered sound files must use a supported audio extension, be non-empty, have
explicit commercial-use confirmation, and carry a licence/ownership reference.
They are copied into managed project storage and hash-bound to the exact current
sound plan and requirement fingerprint.

If an asset has a non-zero external cost, registration is rejected unless the
human explicitly confirms that the purchase already occurred outside the app.
That confirmation is a record of an external action, not app spend
authorization. The record always states that the app neither authorized spend
nor executed a provider call.

A stored resolution is current only while the exact sound plan remains current,
the requirement fingerprint still matches, and any registered managed file
still matches its recorded SHA-256 and byte count. A plan mutation therefore
invalidates old registrations automatically.

The successful Slice 21 boundary is `FINAL_SOUND_ASSETS_READY`: every current
requirement has either a current licensed asset or an explicit human omission.
Final mixing/rendering remains Slice 22 work.

## D-092 — Final rendering is local, rebuild-current, and requires exact-byte human export approval

**Status:** Accepted

Slice 22 owns the transition from fully resolved final sound to an
export-approved local final video candidate.

The automatic path is:

`FINAL_SOUND_ASSETS_READY → final_render_manifest_prepare → final_render_local → HUMAN_FINAL_EXPORT_GATE`

The final render manifest is rebuild-current. It binds the exact current
Slice 20 final-production handoff, current Slice 21 final-sound plan, every
current licensed sound resolution or explicit human omission, and the exact
visual/narration media hashes.

The render is local FFmpeg only. Cloud rendering and paid render fallbacks are
forbidden. Internal visual timeline gaps fail closed. If the approved visual
timeline ends slightly before the narration timeline, the last approved visual
is held/looped through the exact render duration rather than introducing a black
placeholder.

Slice 22 uses a deterministic conservative audio-mix policy for the local final
candidate: narration remains full-level, music marked to duck under narration is
attenuated, non-ducked music uses a higher fixed bed, SFX use a fixed level, and
the final mix is limited before AAC encoding. This is a candidate mix, not an
implicit creative approval; the Human Final Export Gate may return sound for
rework.

The final rendered MP4 is not export-approved merely because FFmpeg succeeded.
The Human Final Export Gate is bound to the exact current render-result JSON and
rendered file SHA-256. A changed manifest, visual, narration, sound resolution,
sound asset, or rendered byte invalidates an old approval.

Human review may approve the exact render for export or return visuals,
narration, or sound for rework. An approval explicitly keeps
`upload_authorized=false` and `publish_authorized=false`.

The successful Slice 22 boundary is `FINAL_EXPORT_APPROVED`. Upload and
publishing remain later work.

## D-093 — Packaging moves after approved script; the existing 5+5 gate becomes a title-direction gate

**Status:** Accepted

The earlier pipeline generated and approved title/thumbnail packaging before
Research and Script. That made the public Packaging title an immutable
dependency of Story, Script and Format. The Packaging Engine v1.0 contract
requires the mature title + thumbnail + opening hook + Viewer Promise unit to
be formed only after the script, hook, payoff and supporting evidence are
stable.

Slice 23 therefore changes the active order to:

```text
Concept Gate
→ Research
→ Research Gate
→ Story / Script
→ Script Section Review / Rework
→ Human Script Gate
→ 5 Short + 5 Long-form Title Directions
→ Human Title Direction Gate
→ STOP
```

The old pre-script Packaging Engine and its artifacts remain readable and its
actions remain registered for audit/resumability, but those actions are removed
from the automatic workflow and disabled in active readiness.

Research now consumes the existing Concept Gate research handoff directly.
Older package-bound research handoffs remain readable, and any explicit legacy
packaging research dependencies are preserved as additional research questions.

Story, Script and Format still carry a stable title field for artifact identity,
but it is explicitly an `INTERNAL_WORKING_TITLE`. It is not the final public
YouTube title and legacy selected title variants may not rewrite it.

After all required script branches are human-approved, Slice 23 creates a
post-script title-direction request bound to the exact approved-script hash.
The established 5 Short + 5 Long-form behavior is preserved. Each title
direction carries a stable ID, psychological angle, primary/secondary driver,
core claim, approved evidence references, character count and SEARCH/BROWSE/
HYBRID intent.

The Human Title Direction Gate selects one Short and one Long-form direction.
That selection means preferred title/psychological direction. Exact wording is
explicitly editable later by the mature Packaging Engine. Rework targets only
the title-direction request and must not modify approved script/evidence.

Selection history is append-only. Duplicate identical submissions are
idempotent; conflicting duplicate decisions fail closed.

Format/Production are intentionally held after `TITLE_DIRECTION_SELECTED`
until the mature Packaging Brief, Viewer Promise, thumbnail, pairing and
validation stages are implemented.

## D-094 — Packaging Brief is deterministic, format-specific, evidence-bound, and pre-thumbnail

**Status:** Accepted

Slice 24 begins the mature post-script Packaging Engine after the Human Title
Direction Gate.

The automatic path is:

`TITLE_DIRECTION_SELECTED → packaging_brief_prepare → PACKAGING_BRIEF_READY`

One brief is created per concept + format because Short and Long-form may carry
different selected title directions, hooks and SEARCH/BROWSE/HYBRID intent.

The brief is a deterministic projection of current human-approved artifacts. It
does not call an AI model and may not invent missing facts. It binds:

- exact current approved script bundle and branch;
- exact opening hook and approved script sections;
- Story Plan central question and payoff;
- exact current selected title direction;
- verified Research Gate sources and accepted claims;
- approved numerical tokens extracted from accepted claims;
- Human Framing visual opening, stakes and desired resolution;
- Research Gate rejected/rework claims as prohibited/unsupported context when available;
- audience context already present in the approved channel/concept artifacts.

A pre-publish internal `video_id` uses `concept_id:format`. It is explicitly
namespaced `PIPELINE_INTERNAL_PRE_PUBLISH` and is not a YouTube video ID.

The Viewer Promise Contract stores `viewer_expectation`, `promise_subject`,
`promise_question`, `promise_stakes` and `promise_payoff`.

The selected title direction's SEARCH/BROWSE/HYBRID classification is preserved
per format. Slice 24 does not optimize or regenerate the title.

Missing approved script, opening hook, evidence, selected title direction,
invalid intent, evidence conflicts or invented evidence references fail closed.

Brief currentness is rebuild-based: changes to the approved script, selected
title artifact, verified research, reviewed research or any derived field
invalidate the saved brief.

Slice 24 performs no thumbnail generation, title/thumbnail pairing, package
scoring, final packaging approval, Format planning or production work. The
successful boundary is `PACKAGING_BRIEF_READY`.

## D-095 — Psychological hypotheses and thumbnail concepts remain separate, evidence-bound, and pre-pairing

**Status:** Accepted

Slice 25 extends the mature post-script Packaging Engine after
`PACKAGING_BRIEF_READY`.

The automatic path is:

`PACKAGING_BRIEF_READY`
→ `psychological_angle_prepare`
→ `psychological_angle_generate`
→ `PSYCHOLOGICAL_ANGLES_READY`
→ `thumbnail_concept_prepare`
→ `thumbnail_concept_generate`
→ `THUMBNAIL_CONCEPTS_READY`
→ STOP.

Each approved format receives exactly five psychological packaging hypotheses.
The five hypotheses must use five different primary drivers. Exactly one is
marked `ANCHOR` and preserves the underlying psychology of the human-selected
title direction; the other four are `ALTERNATIVE` hypotheses with distinct
viewer questions and expected click reasons.

Allowed primary drivers are constrained by configuration. SEARCH, BROWSE and
HYBRID intent is preserved from the Slice 24 Packaging Brief and changes the
generation priorities. Short and Long-form retain format-specific psychology.

Creative framing may be generated by FAIR, but factual invention is prohibited.
Every angle must cite approved claim IDs. Invented evidence refs, unapproved
numbers and unsupported high-risk claim words such as best/first/only/never are
rejected deterministically.

Thumbnail concepts are generated only after the psychological angle set is
current. Slice 25 creates exactly one structured thumbnail concept per angle.
It does not generate an image.

Thumbnail constraints include:

- 16:9;
- one primary focal point;
- one visual proposition;
- no more than three meaningful visual elements;
- zero to three text words preferred, four maximum;
- exact text word-count validation;
- timestamp-safe composition;
- no critical bottom-right content;
- explicit mobile-legibility intent;
- optional face usage;
- visual anomaly preferred but not mandatory;
- evidence refs that intersect the source angle's evidence;
- no unsupported numbers or high-risk factual wording;
- no obvious multi-word duplication of the selected title direction.

Requests and results are resumable per `video_id` (internal concept+format ID).
All request/result currentness is dynamic and provenance-bound, so an upstream
Packaging Brief or angle change invalidates downstream artifacts.

Slice 25 performs no title-thumbnail pairing, diagnostic scoring, final package
validation, final Packaging Human Gate, image generation, Format planning or
Production work.

## D-096 — Mature packaging uses full cross-pair validation with hard truth overrides and no winner score

**Status:** Accepted

Slice 26 begins only after current Slice 25 thumbnail concepts exist.

For each approved format, the engine builds the full cross product of:

- five post-script title directions; and
- five evidence-bound thumbnail concepts.

This produces exactly 25 package hypotheses per format. The engine must not
assume Title 1 belongs to Thumbnail 1.

The human-selected title direction remains represented in the matrix, and any
human-edited selected wording is preserved. The other four title directions
remain available as alternative packaging hypotheses.

Validation is chunked by thumbnail: one request evaluates that thumbnail
against all five title directions. This keeps FAIR output bounded and makes
generation resumable without discarding already validated chunks.

Every package receives separate diagnostics on a 0–5 scale for:

- scroll stop;
- clarity;
- curiosity;
- stakes;
- specificity;
- visual simplicity;
- title strength;
- complementarity;
- credibility;
- promise alignment;
- hook alignment.

These values are decision support only. Slice 26 never computes or exposes a
viral score, CTR forecast, winner score, predicted views, predicted retention
or automatic ranking.

Hard truth failures override every diagnostic score. Hard-reject codes are:

- `unsupported_material_claim`;
- `factually_false_claim`;
- `thumbnail_misrepresents_video`;
- `title_misrepresents_video`;
- `evidence_conflict`;
- `prohibited_claim`.

Repairable packaging failures are REWORK findings, including redundancy, weak
hook confirmation, delayed promise acknowledgement, excessive thumbnail
complexity/text, timestamp-zone risk, unclear primary subject and a stale
selected-title direction.

The model may semantically assess redundancy, complementarity, information
gain, Viewer Promise consistency, Hook Alignment and whether paired claims are
supported. It may not modify titles, thumbnails, hooks, scripts, evidence or
select a winner.

Deterministic validation then derives only:

- `PASS` — no hard or rework findings;
- `REWORK` — no hard failures, but at least one repairable packaging issue;
- `REJECT` — at least one hard truth failure.

A package with all 5/5 diagnostics still REJECTS if its material claim,
evidence, Viewer Promise or representation is invalid.

Title length remains a soft design guideline. A truthful 64-character title
does not fail only because it exceeds the preferred 45–60 range.

Slice 26 artifacts live under `output/mature_packaging/` so the legacy
pre-script `output/package_candidates.json` remains untouched for historical
resume compatibility.

The successful Slice 26 boundary is `PACKAGE_VALIDATION_READY`. No package is
human-approved yet and Format/Production remain locked.

## D-097 — Niche thumbnail conventions are tabulated and feed post-script thumbnail concepts

**Status:** Accepted

Generic title/thumbnail guidance is a starting hypothesis. Before trusting it
for a niche, the project tabulates 20-30 of that niche's breakout thumbnails
per format with `packaging_engine/niche_thumbnail_study.py`.

Selection reuses Experiment 01 evidence: `ON_INTENT` relevance, ranked by
outlier-reliability tier and channel-relative outlier ratio rather than raw
views, with at most two videos per channel so one large channel cannot define
the convention.

Color, contrast and resolution are measured deterministically with ffmpeg.
Text, focal subject, element and arrow/circle counts require human
confirmation; a local vision model may draft them, but drafts are never
tabulated.

Each niche is compared with the live packaging rules rather than a separate
list: the Slice 25 thumbnail contract (meaningful elements, text words), D-096
title-length guidance, and two study-only limits (text/title overlap,
arrows/circles). Each comparison is reported as `NICHE_FOLLOWS` or
`NICHE_DIVERGES`.

When `channel_niche` is set in `packaging_config.json` and a tabulation exists
for the format, Slice 25 thumbnail concept requests carry the conventions and
an instruction to follow them only where they do not conflict with the
contract, and to choose colours outside the niche's crowded hue families.
Without a configured niche or study the request is byte-identical to before,
so existing concepts stay current.

The tabulation is descriptive: it records conventions of successful videos,
not causes of their success, and it does not measure CTR.

This supersedes the pre-script packaging design advisories that were briefly
merged to `main` as D-070 (PR #122). Those advisories extended the retired
pre-script Packaging Engine (D-093); the Slice 25 contract already enforces the
same rules. The numbers D-070 to D-072 refer to the integration branch's
decisions above, not to PR #122's.

## D-098 — Validated thumbnail concepts render from a locked template and pass a Human Thumbnail Gate

**Status:** Accepted

Slice 25 produces structured thumbnail concepts and does not generate images.
`production_engine/thumbnail_render.py` renders them.

A render unit is one Slice 25 thumbnail concept for one video format that has
at least one title pair whose Slice 26 validation status is renderable
(default `PASS`). One image therefore serves every passing pair for that
concept. The unit is bound to a hash of the concept and its passing titles, so
a change upstream makes the render stale.

Thumbnails are rendered from one locked channel template so returning viewers
recognise the channel. Layout, fonts, outline, background treatment, logo
position and a timestamp safe zone are fixed. Each concept varies only the
subject image, the accent colour and the overlay text, which is copied verbatim
from the concept and cannot be edited at this stage.

Subject images require provenance from a tier that permits thumbnail use.
Editorial excerpts and unknown sources are refused.

Rendering is deterministic (ffmpeg, no model). Text is measured with the real
font and laid out at the largest size that fits; text too long for the template
blocks the render rather than shrinking below a readable size.

Each render produces phone-size previews and a mock feed beside the niche's
breakout thumbnails (D-097). Contrast, phone text size and crowded-accent checks
are advisories. A Human Thumbnail Gate with five criteria decides ACCEPT /
REWORK / REJECT on the image; ACCEPT is refused for placeholder or stale
renders, and a re-render that changes the image withdraws an earlier approval.

Image approval does not select a title-thumbnail package. That remains the
final Packaging Human Gate, which is not yet built.

## D-099 — A Final Packaging Gate accepts one validated package per format and routes targeted rework

**Status:** Accepted

Slice 26 stopped at `PACKAGE_VALIDATION_READY` with no way to choose a package,
and no route back when every pair was weak. Format planning was hard-disabled
until a human accepted an exact title + thumbnail + hook + Viewer Promise unit.

Slice 27 adds the Final Packaging Gate (`packaging_engine/final_packaging_review.py`).
It makes one decision per concept and format.

ACCEPT takes one pair from the current complete Slice 26 matrix. That pair must:

- have an acceptable validation status (default `PASS` only);
- have its thumbnail image approved and current at the Human Thumbnail Gate
  (D-098). This is on by default and can be switched off in
  `final_packaging_gate_config.json`;
- pass every configured acceptance criterion, affirmed by the reviewer.

The accepted title is the validated wording. It cannot be edited at this gate,
so no unvalidated title reaches production.

REWORK requires a target and a note, and routes to the layer that is weak:

- **Title directions:** re-opens the Title Direction Gate for the concept with
  the note.
- **Thumbnail concepts:** adds the note and the previous concepts to that
  format's Slice 25 request. Requests without a note stay byte-identical, so
  nothing else regenerates.
- **Script branch:** submits Rework at the Script Gate.

Downstream artifacts go stale through the existing hash chain, and the
automatic workflow regenerates them.

REJECT holds Format planning for the concept until the matrix changes or a
package is accepted.

Each decision is bound to the package's content hash and the approved image
hash. Upstream changes return it to PENDING. When every format of a concept is
accepted, a deterministic final package bundle is written.

Format requests embed the accepted packages and the bundle's content hash. The
Experiment UI treats a Format request as current only while that hash matches
the current bundle. `format_prepare` is re-enabled once the gate is approved,
and the automatic workflow stops at `HUMAN_FINAL_PACKAGING_GATE` /
`FINAL_PACKAGING_REJECTED`.

All decisions and rework requests are archived append-only.

## D-100 — Research acquisition falls back to free search and readers

**Status:** Accepted

Research evidence depended on Exa through `mcporter` and on Jina Reader. On a
machine without them every question failed. The automatic workflow then
reported the failure as a provider/model problem.

**Search** now tries backends in order and uses the first that returns results:

- Exa;
- DuckDuckGo's no-JavaScript HTML results;
- the public Wikipedia search API.

**Page reads** try Jina Reader, then a direct fetch reduced to visible text.
Wikipedia articles use the API's plain-text extract instead.

The fallbacks need only `curl` and no account or key. The order is configurable
in `research_acquisition_config.json`. Every attempt is recorded in the evidence
artifact, so reviewers can see where each source came from.

The fallbacks widen where candidate sources come from but do not change what
counts as evidence. The Research Gate still decides that.

When research acquisition still produces no usable pages, the workflow message
says so plainly and quotes the first real backend error, with the commands to
diagnose it.

## D-101 — Research quotes are matched by words, and unverifiable claims are dropped one at a time

**Status:** Accepted

Claim structuring required each `evidence_quote` to appear in its page
character for character, ignoring only case and whitespace. With pages from
different readers (Jina Markdown, direct fetch, Wikipedia extract), valid
quotes failed on formatting: curly quotes, dashes, Markdown link syntax, and
`…` between fragments.

One failing quote also rejected the whole response, discarding every good
claim with it.

Quotes are now compared as word sequences with formatting removed. Ellipses
may separate fragments that appear in order. The wording itself must still be
verbatim.

A claim whose quote cannot be found is dropped and recorded in
`quote_rejected_claims`. The response fails only when no claim survives or a
cited source was not acquired.

The prompt now asks for one continuous 5–30-word excerpt without Markdown. The
workflow's PARTIAL message distinguishes "a model answered but validation
failed" from "no model answered".

## D-102 — Research rework notes guide regeneration but never block the Research Gate

**Status:** Accepted

A Research Gate Rework note is added to the plan as a research question with
origin `human_rework`, so the next claim generation addresses it. The gate then
required an accepted claim for every question, including those notes.

A note that is not a factual question (for example "the explanation is too
complex") could never be answered. The concept stayed `RESEARCH_INCOMPLETE`
and never reached Story / Script.

This contradicted the gate's own contract that only the original research
questions must be covered. Questions of origin `human_rework` now report
`HUMAN_REWORK_INSTRUCTION` when unanswered and are excluded from
`unresolved_question_ids`. Original concept questions still block until
answered.

## D-103 — The Research Gate names unanswered questions and lets the reviewer waive them

**Status:** Accepted

When the last claim was decided and an original research question still had no
accepted claim, the gate completed as `RESEARCH_INCOMPLETE`. The automatic
workflow then re-prepared it at once and returned the reviewer to the same
claim, without saying which question was missing.

Accepting claims again repeated the loop. When the web held no reliable source
for a question, there was no way forward at all.

The gate snapshot now carries live `question_coverage` per concept, and the UI
shows a banner of unanswered original questions. The reviewer can answer one by
reworking a claim, or waive it with a required note. A waived question is
`WAIVED_NOT_FOR_SCRIPT` in the verified package. It no longer blocks Story /
Script, and the script has no accepted claim to state about it.

Waivers live in the gate state and survive re-preparation only while the
question's wording is unchanged. Rework-derived questions cannot be waived;
they never block (D-102).

## D-104 — Research rework keeps accepted claims, and ready concepts proceed independently

**Status:** Accepted

Reworking one claim regenerated every claim of that concept, so claims the
reviewer had already accepted vanished. The railway concept lost its good taper
and self-centering claims this way.

The gate also finalized only when every claim of every concept was decided,
and Story / Script started only when every concept was ready. One stuck concept
held back the others.

**Carry-over.**

- On REWORK, the concept's other accepted claims and their sources are stored
  in the research plan as `carried_claims`.
- When the regenerated response is merged into a draft, they are added
  unchanged under `kept_`-prefixed claim and source IDs, marked
  `carried_from_review`.
- At the gate they are accepted automatically with an explanatory note,
  because a human already accepted the same wording and evidence. The reviewer
  can still change the decision.

**Per-concept finalization.**

- A concept's reviewed and verified packages are written as soon as its claims
  are all decided, and removed if any becomes undecided.
- They are rewritten only when that concept's decisions, waivers or draft
  change (a decision fingerprint), so downstream artifacts of an unchanged
  ready concept stay current.
- Story / Script starts for each `READY_FOR_STORY_SCRIPT` concept on its own.
- The gate is `COMPLETE` only when every concept is ready. The automatic
  reopen of a completed-but-incomplete gate is removed: an incomplete concept
  simply keeps the gate awaiting a human decision, with the unanswered-question
  banner (D-103) saying why.

## D-105 — Scripts must tell the human story, may not invent numbers, and can be edited and accepted wholesale

**Status:** Accepted

**The problem.** Generated scripts read like lectures. The opening hook was a
generic teaser ("You'll never believe…"), and the sections were bare facts with
no viewer, tension or resolution. The script request already carried the
concept's human framing (viewer moment, psychological pull, explanation
payoff), but neither the prompt nor the request asked the model to write from
it.

Scripts also stated numbers that were in no accepted claim ("a 747 lands at
170 mph"). The Script Gate could only edit text through a separate "Prepare
section review" step, after which a whole-script Accept was blocked until every
section had been accepted one by one.

**What changed.**

- **Storytelling rules.** The script prompt and request instructions now
  require a story told to one viewer:
  - open inside the viewer's moment;
  - state the contradiction or stakes and open the information gap without
    answering it;
  - follow the arc moment → expectation → tension → escalation → reveal →
    resolution;
  - make every section matter to the viewer;
  - explain with an everyday analogy, written for the ear.
- **Two new deterministic rejections.**
  - Any number not found in an accepted claim.
  - A generic teaser opener.

  Both apply to generated scripts and to manual edits.
- **Edit buttons.** The UI puts an Edit button on the hook, each section and
  the closing. It prepares section editing as needed and opens the manual
  editor on that part.
- **Wholesale accept.** Accepting the whole script with sections still open
  asks for confirmation, then sends `accept_open_sections`. The gate accepts
  and locks those sections as they stand, cancelling pending section reworks,
  before the usual complete-review check. Without the flag, the strict rule is
  unchanged.

**Consequence.** Existing script drafts become stale (the script validation
contract and request instructions changed) and are regenerated under the new
rules on the next run.

## D-106 — One channel now; other subjects wait on future-channel shelves

**Status:** Accepted

The system builds one channel, **Science Inside**: the science inside everyday
things (plane tyres, wet vs dry tyres, hummingbird flight, the steelpan). Car
modifications, ageing finance and retirement, and storytime are **future
channels**. Opportunities that fit them are routed to that channel's shelf
instead of being discarded, so each future channel starts with evidence.

Every Opportunity Packet records `channel.route` (ACTIVE_CHANNEL,
FUTURE_CHANNEL, EXCLUDED with the rule id, or UNSCOPED). Exclusions are
configured in `opportunity_engine/config.json` by layer (subject, format, risk),
use whole-word matching, allow mechanism-led exceptions ("why a free kick
dips"), and stay visible and reversible. YouTube's own category never excludes
on its own because many motorsport channels file under *Sports*.

**Consequence.** An `everyday_science` niche is added to `niches.json`. The
Experiment 01.3 topic set is unchanged for now, so the existing frozen cohort is
not disturbed.

## D-107 — Canonical Opportunity Packets wrap the historical engine

**Status:** Accepted

Opportunity Discovery v2.1 (`opportunity_engine/OPPORTUNITY_DISCOVERY_SPEC.md`)
adds human-topic, human-video and viral-radar lanes beside the historical
01.3 → 01.5 engine. All lanes produce one packet shape (`packet_schema.py`).

- Evidence dimensions stay separate; a level above UNASSESSED / HYPOTHESIS must
  name a written rule (`config.json → evidence_rules`) and its basis.
- Viral classification is four independent axes (strength, trajectory, breadth,
  historical alignment); no single breakout label or score is stored.
- `opportunity_id` is stable across rebuilds; `packet_sha256` ignores rebuild
  timestamps and changes only with the evidence.
- The historical adapter reads the 01.5 study set and groups it exactly as the
  existing Opportunity Gate does (niche:topic:format). 01.3–01.5 and the
  existing gate are unchanged until the unified gate slice (O12).

## D-108 — Channel Voice profiles may be DRAFT

**Status:** Accepted

A `DRAFT` profile is a complete voice proposal that no human has approved. It
must satisfy every APPROVED content requirement, must not record approval
provenance, never affects generation, and cannot be selected as the active
profile. The Science Inside voice ships as `science_inside_v1.json` in DRAFT;
approving it (status, approver, timestamp, selector) is a separate human step
because activating a voice makes existing story plans and scripts stale.

## D-109 — A pasted video can become the study set; Experiment 02 follows the current set only

**Status:** Accepted

Slice O5 adds **Analyze a video**. A pasted link is reduced to a validated
11-character video id (watch, youtu.be, shorts, embed and live links; never a
playlist, channel or search), measured with the YouTube Data API with yt-dlp
metadata as the fallback (never a download), routed by the channel scope, and
saved as a HUMAN_VIDEO packet. A definitive "private or removed" answer stops
the lookup; a failed lookup is reported as a failure and nothing is saved.

**Analyze why it worked** records the video as the active study source. The
Human Opportunity Gate then materialises it as the one approved study set
(status `APPROVED_HUMAN_VIDEO`), with or without a historical run. Approving a
historical topic, or *Stop analyzing*, returns the study set to the historical
gate. The study-set row is frozen at decision time (R8): re-measuring the video
does not invalidate it; deleting its packet does. An excluded video needs an
explicit override, and replacing existing Experiment 02 work needs an explicit
confirmation because everything from Experiment 02 onward restarts.

To make that switch safe, Experiment 02 now follows the current approved study
set only: prepared profiles count as prepared only when they match it exactly,
and synthesis ignores analysed or reviewed profiles from a previous set.

**Consequence.** A HUMAN_VIDEO study row carries `gate_status: HUMAN_SEEDED`
and no historical demand evidence; Experiment 02 treats its performance as
context only, as it does for historical videos.

Also fixed: the historical adapter now accepts the pipeline's
`short_candidate` / `long_form_candidate` format labels.

## D-110 — Explore My Topic searches a sample and labels it as one

**Status:** Accepted

Slice O4 lets the human enter any topic or viewer question, whether or not it
exists in `niches.json`. The seed is normalised (topic or question, keywords,
stable key) and expanded into at most five deterministic search variants. Each
variant is one yt-dlp flat search (no YouTube quota, nothing downloaded); the
results are measured in one batched `videos.list` call (1 unit per 50 videos),
falling back to the search metadata when the API is unavailable. A variant
that fails is recorded and the others continue; if every variant fails,
nothing is saved.

Only results whose titles match at least two seed keywords (one for a
one-keyword seed) and that pass the scope exclusions count as evidence.
Demand (`HT-DEMAND-*`) and replication (`HT-CCR-*`) are set from written rules
on independent channels and view counts; viewer need, mechanism and content
gap stay hypotheses. The packet states that this is a search sample, not the
age-matched 01.3 engine, so a human idea is never rejected merely for missing
historical thresholds.

*Analyze these videos* reuses the D-109 handoff: the most-viewed relevant
videos, at most four and one per channel, become the frozen approved study set
(gate status `APPROVED_HUMAN_TOPIC`).

## D-111 — One Opportunity Inbox shows every lane; decisions stay where they belong

**Status:** Accepted

The Opportunity page becomes a workspace (slice O3): four entry cards
(Discover proven demand, Explore my topic, Analyze a video, Find viral /
breakout videos, the last disabled until the radar exists) above a single
**Opportunity Inbox** with the spec's tabs: Needs review, Watching, Approved,
Saved, Rejected.

The inbox is a view, not a new source of truth:

- historical items come from the canonical packets of the 01.5 study set and
  mirror the existing gate's decision (APPROVE → Approved, HOLD → Saved,
  REJECT → Rejected, PENDING → Needs review); they are still decided in
  Historical review;
- human-seeded ideas can be saved, rejected or restored from their card; those
  choices are stored in `opportunity_engine/output/inbox_state.json` and never
  change a packet or its evidence hash;
- future-channel ideas are parked in Saved automatically (R10);
- the active study set is pinned to the top of Approved and marked ACTIVE, and
  cannot be saved or rejected until analysis of it is stopped;
- Watching stays empty until the viral radar adds candidates (R11).

Historical packets now take their timestamp from the study-set file so
rebuilding them on every refresh does not reorder the inbox.

## D-112 — The viral radar measures against each channel's own normal, from first sight

**Status:** Accepted

Slices O6–O9 add a topicless breakout radar (`opportunity_engine/viral_radar.py`).

**Discovery is watchlist-led (R2).** The watchlist holds the seed handles in
`config.json` plus every channel the system has already seen. It is crawled
through each channel's uploads playlist: about 1 API unit per channel plus 1
unit per 50 videos, with no `search.list` quota. yt-dlp "this week" bucket
searches, rotated four per run, only add channels. Measurement uses the
official API (R3).

**Baselines are the channel's own mature uploads** (15+ days old, same format;
Shorts only after the March 2025 view-count change), extending the 01.2
same-format median with a maturity filter. Fewer than three gives
`INSUFFICIENT_EVIDENCE`.

**Classification is four axes, from first sight.**
- **Strength** is set by written rules that are hypotheses. Every ratio
  records its basis (`lifetime_vs_lifetime`, `vph_vs_lifetime_vph`), and an
  early signal needs both (R4).
- **Trajectory** comes from the system's own snapshots, using the D-021
  velocity rules.
- **Historical alignment** comes from the historical topics.
- **Breadth** stays `UNASSESSED` until theme clustering (O10).

**Tracking.** Promising videos are tracked on an age-based cadence (6 h /
12 h / 24 h) with append-only snapshots. Past views are never reconstructed.
At 15 days a video leaves the radar and its final outcome is stored beside its
24 h / 3 d / 7 d classifications, to calibrate the rules (R7). Deleted or
private videos stop being tracked.

**Failures are named and back off.**
- `API_VALIDATION_UNAVAILABLE`: no API key, or quota exhausted.
- `YT_DLP_DISCOVERY_FAILED`.
- `DISCOVERY_THROTTLED`: no YouTube searches for 6 hours.

An empty watchlist is reported, never shown as "no breakouts".

**Inbox.** Breakouts appear as VIRAL inbox items. Excluded ones are tracked
but never shown as packets. *Watch* (radar only) moves an item to Watching.
*Analyze why it worked* reuses the D-109 handoff, giving gate status
`APPROVED_VIRAL_RADAR`. The radar runs only when asked (*Run viral radar*);
scheduling is O13.

## D-113 — Themes need independent channels; the inbox is the one gate

**Status:** Accepted

**O10: themes.** After each radar run, breakouts are grouped by shared title
keywords (`opportunity_engine/viral_cluster.py`). The method is deterministic,
labelled `deterministic_title_keywords`, and replaceable later by AI
clustering behind the same output.

- **Independent channels only.** A theme counts one video per channel, and a
  near-identical title of similar length on another channel counts as a
  re-upload, not as a second channel.
- **Kinds.** Each theme is labelled SAME_EVENT, SAME_VIEWER_QUESTION,
  SAME_MECHANISM or SAME_TOPIC. Event-bound wins when most members are about
  one event.
- **Breadth.** Three or more independent channels make a theme REPLICATED.
  Replication evidence comes from written rules:
  - `CL-REPLICATED`, or `CL-REPLICATED-STRONG` at five or more channels;
  - `CL-EVENT-BOUND`: replicated, but around one event, so weak (LOW);
  - `CL-PAIR`: two channels;
  - `CL-ONE-OFF`: one channel.

**O11: bridge.** *Approve theme* makes one video per independent channel the
study set; its rows are frozen and invalid only if a member's packet
disappears. Every human-seeded or radar study row carries
`opportunity_context`. Experiment 02 puts the real source in the upstream
evidence item (same evidence id) and adds the spec's opportunity questions,
mapped onto its existing output fields, so its response contract is
unchanged. Historical rows carry no context, so their profiles and analysis
requests are byte-identical to before and no current work goes stale.

**O12: unified gate.** The inbox decides everything with Approve, Rework, Watch,
Save and Reject (R11).
- **Rework** needs a note. It re-measures a submitted video, re-searches a
  topic, and keeps a breakout in Watching.
- **Historical topics.** Save and Reject on a historical topic become the
  existing gate's HOLD and REJECT. Approval stays in Historical review because
  examples must be reviewed first.
- **Decision record.** Every decision is recorded with time, note and the
  packet hash it was made against. A later change shows "evidence has moved
  since your decision" and never undoes the decision (R8).
- **Locking.** Because inbox decisions can now change the historical gate,
  `POST /api/opportunity/inbox` waits for running jobs like the other gate
  routes.

## D-114 — The radar runs on the existing task; evidence opens in a drawer

**Status:** Accepted

**O13: one scheduler.** The Windows task from D-052 / D-054 (every 2 hours,
installed from Tools) now runs `opportunity_engine/scheduled_tick.py` (R1). Each
wake runs the existing Opportunity Research continuation unchanged, then one
radar tick (`radar_scheduler.py`):

- **Full discovery** when the last one is at least
  `radar_schedule.discovery_every_hours` old (8 by default; the spec allows
  6–12).
- **Otherwise a snapshot-only pass** when a tracked video is due on its
  age-based cadence. This mode only re-measures tracked videos (1 API unit per
  50) and never searches or crawls.
- **Otherwise nothing.**

A lock file prevents overlapping ticks, and the existing scheduler's lock
helpers are reused. State stays in the radar's own files, so ticks are
resumable. One step failing never skips the other. A status file feeds the
radar card: last check, next snapshot due, next discovery due. Users who
installed the earlier task re-run the install so the task uses the new
runner; the task name is unchanged.

**O14: the evidence drawer.** Inbox cards open a side drawer with the spec's
sections (§25) instead of an inline expander.
- **Chart.** The trajectory chart (§26) plots views against hours since
  publishing from the radar's own append-only snapshots, never from
  reconstructed history. It is a single 2 px series in the validated dark-mode
  mark colour #4493f8, with 8 px markers, a hairline grid and one axis.
- **Interaction.** A crosshair tooltip responds to both hover and ←/→ on the
  focused chart. A snapshot table and a views-per-hour table carry the same
  values without hovering.
- **Behaviour.** The drawer closes on Esc and returns focus to the card.


## D-115 — UI Patch 1: tokens, new shell, Command Center, productions from files

**Status:** Accepted

**Productions are derived, not stored.** The redesign needs a list of
productions with a stage and a status. The pipeline has no per-video record:
each engine writes hash-bound artifacts per concept. Rather than add a second
source of truth that could drift from the files, `experiment_ui/productions.py`
derives each production on every request from the artifact state the server
already computes (the `*_artifact_state` functions and their gate snapshots).
- **What counts.** A production is a concept accepted at the Concept Gate.
- **Stage.** The stage is the first stage whose output is not current for that
  concept.
- **Status.** HUMAN_REVIEW when that stage's gate has a pending decision for it,
  BLOCKED on rework or reject, READY otherwise, and COMPLETE when every branch
  has a current final render.
- **Cost and invalidation.** It reuses the state already built for
  `/api/status`, so polling costs no extra artifact scans beyond reading the
  final-render results. Invalidating an artifact moves the production back
  automatically.
- **Known limit.** Gates that are still global (narration spend, visual
  candidates and rights, rough cut, edit preview, final export) are not
  attributed to one production until the per-production workspace (Patch 3).

**Tokens first.** `css/tokens.css` defines semantic colours, where colour means
state (human, running, blocked, complete), plus spacing, type, radius, shadow,
motion and z-index. The previous `:root` variables are now aliases of these
tokens, so the 2,200-line `styles.css` keeps working unchanged and later patches
can move it across piece by piece.

**Shell and navigation.** The sidebar follows the redesign's information
architecture:
- Command Center.
- Opportunities: Discover, Viral Radar, Watching, Approved.
- Productions: Active, Review Queue, Completed, Workspace.
- Tools & Diagnostics.

Sub-items reuse the existing views (inbox tabs, radar card, `/analysis`) until
Patches 2 and 3 give them their own pages. The top bar adds a health pill: a
failed job, a radar scheduler more than 6 hours (three wakes) late, or a failed
radar run. The sidebar footer shows the workflow and scheduler state.

**Command Center.** It replaces Home. The existing guided-workflow hero is kept
as "Needs your attention"; below it come the attention queue, active
productions and "Running automatically".

**Static serving.** The server serves `/css/*.css` and `/js/*.js` with path
containment: one directory level, an extension allowlist per folder, no
dotfiles, and a resolved path that must stay inside the folder (which also
rejects symlink escape). Everything else under those prefixes is a 404. CI now
syntax-checks every file in `static/js/`.


## D-116 — UI Patch 2: Viral Radar page, Opportunity Review workspace, Opportunities restyle

**Status:** Accepted

**Viral Radar page (UI-04).** `viral_radar.radar_overview()` serves
`GET /api/opportunity/viral/overview`. It reads only the radar's own files:
themes from the last clustering pass, tracked videos from the radar state, and
sparkline points from the append-only snapshot log. A video's series is
downsampled to at most 24 points, and nothing is re-measured or reconstructed.
- **Themes.** Each theme carries strongest and median outlier, the direction
  and historical alignment of its strongest video, when it was first detected,
  and that video's views series as "momentum".
- **Tracked videos.** Each carries its day within the 15-day window.
- **Page.** It polls the overview only while open (on a new scan, or every
  30 s) and repaints only when the content changes, so open panels and focus
  survive the 5-second status poll.
- **Filters.** The spec's topic and region filters are not shown because the
  radar has neither (it scans its watchlist and rotating queries). The page
  says so instead of offering controls that would do nothing. The format
  filter only filters what is displayed.

**Shared review workspace (UI-06).** `js/review-workspace.js` owns what every
human gate will share:
- the header and "N of M";
- previous/next;
- keyboard behaviour (← →, 1–9, Ctrl+Enter, active anywhere on the page
  except in text fields and drawers);
- the decision panel, notes and status.

A gate supplies items, evidence HTML, decisions and a submit function.

**The Opportunity Gate is its first user.**
- **Decisions.** It offers exactly the actions the inbox already allows for
  each item.
- **One dispatcher.** All decisions go through one dispatcher in `app.js`
  (`performInboxDecision`), which the inbox cards and the radar page also use,
  so every surface makes the same API calls.
- **Notes.** Investigate requires a note. Approve records none, since it
  starts analysis rather than writing a decision note, and the panel says so.
- **Drafts.** A failed decision keeps the draft.
- **Historical topics.** They still route to Historical review, because their
  examples must be kept or replaced first.

**Opportunities restyle (UI-03).**
- The entry cards sit in one row.
- A counts strip leads into the review workspace.
- Inbox cards follow the spec: kicker, title, meta line, outlier figure, the
  six evidence levels, and one primary action ("Review opportunity"); the
  other decisions are secondary.
- The Command Center's breakout and inbox cards now open Opportunity Review on
  the exact item.

**Evidence drawer (UI-05).** It is unchanged from O14 and opens from every new
surface. Its "Viewer questions" section stays "not yet evidenced" until
Experiment 02 answers it, rather than showing invented questions.


## D-117 — UI Patch 3: Productions list, Review Queue, Production Workspace

**Status:** Accepted

**The workspace owns the context.** `/production#<concept_id>` shows one video:
title, premise, stage · status, when its files last changed, and eight tabs
(Evidence, Analysis, Concept, Research, Script, Package, Format, Produce). The
user no longer has to work out which concept they are on or where it is.
- **Real sections.** The tabs are real sections, not headings. Each comes from
  `productions.detail()`, which reads the same artifact state as the list, so
  the two cannot disagree.
- **What is shown.** Concept fields, research progress and per-claim decisions,
  script branches with per-section decision, lock, rework reason and ready
  alternatives, packaging and format progress, and per-version
  voice/narration/render state.
- **Behaviour.** The current stage opens by default with a "Current step" card.
  Tabs follow the WAI-ARIA tabs pattern, and the page refetches when the
  status poll shows the production moved, or every 10 s.

**Decisions still happen in the existing panels.** "Continue review" opens
Workspace (`/analysis`), where every gate panel still lives. Moving each gate
onto the shared review workspace (D-116) is UI-09 onward. This patch does not
duplicate those decision forms, so there is still exactly one place to make
each decision.

**Updated time from file times.** Engines name per-concept artifacts
`<slug>.…`. A production's "updated" time is therefore the newest
modification time among its files, found with one directory scan per stage
folder and no file reads. It reflects the files, not who changed them.

**Review Queue.** Section 14 of the redesign: one numbered list of every
decision waiting, covering productions needing review or blocked, and inbox
ideas needing review. "Start review queue" opens the first one. Opportunity
entries open Opportunity Review on that idea; production entries open its
workspace.

**Known limits.**
- **Global gates.** The Produce tab cannot yet name the narration-spend,
  visual, rough-cut, edit-preview and final-export decisions per video,
  because those gates are still global (D-115).
- **Evidence tab.** It shows the evidence recorded on the concept, not the
  original opportunity packet, because concepts do not yet record which inbox
  opportunity they came from.


## D-118 — UI Patch 4: Analysis, Concept and Research gates on the shared review workspace

**Status:** Accepted

**One review experience, same decisions.** The Analysis, Concept and Research
gates now run on the review workspace from D-116, at `/review#<gate>`. Each
gate keeps its domain content:
- the analysis finding with its supporting evidence;
- the concept's idea, audience evidence, mechanism, research questions and
  checks;
- the research claim's sources (stance, locator, quote), its concept's
  research questions, and what accepting confirms.

The header, "N of M", previous/next, keys, decision panel and notes are
shared.

**Same requests as the classic panels.** Decisions post the same bodies to the
same endpoints, with `criteria: {}` because the gates derive criteria from the
decision. The server's job lock and mutation routes are unchanged. The UI adds
only stricter guidance; it never adds a rule the server lacks:
- Rework needs a note (the server already requires it).
- Accepting a CONFLICTED claim asks for a resolution note, matching the
  research gate's `require_conflict_resolution_note`.

**Revisiting and drafts.**
- "Include decided items" puts decided items back in the queue with their
  decision and note pre-filled.
- Unsaved drafts are kept per item, so moving between items never carries one
  item's note to another. This fixes a carry-over bug in the Patch 2 workspace.
- A research claim's question panel refreshes when a waiver or another claim
  changes coverage.

**Entry points.** These open the matching gate:
- the Command Center hero for HUMAN_ANALYSIS_GATE, HUMAN_CONCEPT_GATE and
  HUMAN_RESEARCH_GATE;
- attention cards and Review Queue rows for pending analysis findings and
  concepts (research is counted per production);
- a production's "Continue review" at the research stage, which opens its
  first pending claim;
- a "Review one at a time" button on each classic panel.

**The classic panels stay.** Workspace keeps every original option, including
the concept override bank (bringing a non-shortlisted concept in) and saved
ideas, until the remaining gates move across (UI-11 onward: Script,
Packaging, Format, Voice, then the production gates).


## D-119 — UI Patch 5: the Script gate on the shared review workspace

**Status:** Accepted

**Part by part, then the whole.** `/review#script` lists, for each script
branch awaiting a decision, its opening hook, every section and its closing,
then a "Whole script" item. Each part shows:
- its live text;
- why it exists (purpose, psychology mechanism, reward type);
- the accepted research claims it uses, with their statements.

The whole-script item shows each part's state, the live hook and closing,
validation errors, and the approved claims.

**Decisions map one-to-one onto the existing section actions.**
- Accept and lock → `ACCEPT`.
- Rework → `REWORK` with the server's reason list (a test keeps the two in
  step) and an optional instruction. Like the classic panel, it needs a
  reason or an instruction, and CUSTOM needs an instruction.
- Edit by hand → `MANUAL_EDIT`. It starts from the current text and refuses
  an unchanged edit.
- Unlock → `UNLOCK`; Cancel rework → `CANCEL_REWORK`.
- Whole script → `/api/script-gate`.

Accepting with parts still open shows the classic panel's confirmation and
sends `accept_open_sections: true`.

**Spending stays explicit.** Requesting a rework never calls the model.
"Generate A / B / C" is a separate button that says it calls the model once.
The alternatives then appear beside the original, and picking one, or keeping
the original, applies `SELECT_ALTERNATIVE`, which locks the part.

**Behaviour fixes in the shared workspace.**
- A gate can add a choice list and its own note label to a decision.
- A text-editing decision starts from the current text, and switching away
  clears it.
- A draft whose decision no longer applies, such as a rework instruction once
  the rework is pending, is cleared.
- Script items appear only once a branch's sections have loaded, so review
  starts at the opening hook.
- Section data reloads whenever the Script Gate changes from anywhere.

**Kept in the classic view.** Preparing a bounded rework request without
calling the model, and restoring a saved script version. Both are rare, and
restoring needs the version picker.


## D-120 — UI Patch 6: the Packaging workspace

**Status:** Accepted

**Five tabs, two decisions.** `/packaging` follows the redesign's packaging
page:
- **Title Direction** and **Final package** are the two human gates in the
  live workflow, on the shared review workspace.
- **Brief & angles**, **Thumbnail concepts** and **Pairing** show what the
  automatic steps produced. They have no decisions because the pipeline has
  none there.

**Choices live with the item, not the form.** Both gates need more than one
choice:
- Title Direction: a Short and a Long-form title, each with editable wording.
- Final package: a package plus the required checks.

These are kept per item in the page module, so the 5-second status poll and
any repaint never lose a pick, an edited title or a ticked check. Editing a
title's wording selects that title.

**Same requests and rules as the classic panels.**
- **Title Direction** posts `{concept_id, decision, selected_titles, note}`:
  - Accept needs both formats chosen with non-blank wording.
  - Rework needs a note.
  - A decided item offers only Rework, matching the gate's rule that a
    finalized decision changes only through rework.
- **Final package** posts `{video_id, decision, package_id, criteria, note,
  rework_target}`:
  - Accept needs a chosen package and every required check, which the server
    also enforces.
  - Rework needs a target from the gate config and an instruction, and shows
    the classic confirmation.
- A test keeps the page's check and rework labels in step with
  `final_packaging_gate_config.json`.

**Thumbnail image approval stays classic.** Approving a rendered thumbnail
means choosing a subject photo and accent and re-rendering, a different job
from a decision. The Final package tab therefore shows which packages wait on
an approved image and links to the classic panel. A package whose image is
approved but has no preview is labelled as such, never as unapproved.

**Entry points.** These open the matching tab:
- the Command Center hero for HUMAN_TITLE_DIRECTION_GATE,
  TITLE_DIRECTION_REJECTED, HUMAN_FINAL_PACKAGING_GATE and
  FINAL_PACKAGING_REJECTED;
- a production's "Continue review" at the Package stage;
- the classic panels' "Open packaging workspace" buttons;
- Productions → Packaging in the sidebar.


## D-121 — UI Patch 7: Format, Voice and Narration Preview gates on the shared review workspace

**Status:** Accepted

**Three more gates, same requests.** `/review#format`, `#voice` and
`#preview` post exactly what the classic panels post:
- `/api/format-gate` `{concept_id, decision, criteria: {}, note}`.
- `/api/performance-gate` `{concept_id, format, decision, criteria: {}, note}`.
- `/api/narration-preview-gate` `{concept_id, format, decision, note}`.

Rework needs a note on each. The preview offers exactly the server's four
decisions (APPROVE_FINAL, REWORK_PERFORMANCE, REWORK_SCRIPT,
REWORK_MUSIC_SFX), and a test keeps them in step.

**What each review shows.**
- **Format:** every branch's duration, promise delivery, payoff and beats,
  the claims each branch uses, unused accepted claims, branch separation and
  source overlap.
- **Voice:** each beat's fixed narration beside its delivery direction
  (emotion, intensity, speed, pauses, stressed words), so the performance is
  judged against the words it will be spoken over.
- **Preview:** a player for the free local prototype (the existing audio
  endpoint).

**Listen before spending.** The preview cannot be approved until its audio
has rendered, a rule the server also enforces. Approving only unlocks the
paid narration quote; nothing is spent at this step.

**Entry points.**
- The Command Center hero for HUMAN_FORMAT_GATE, HUMAN_PERFORMANCE_GATE and
  HUMAN_NARRATION_PREVIEW_GATE.
- A production's "Continue review" at the Format and Produce stages.
- An attention card and Review Queue row for previews that can be heard.
  Previews are decided per format but are not part of the production status,
  so they are counted on their own.
- The classic panels' "Review one at a time" buttons.

**Kept in the classic panel.** Revising one narration segment and
re-rendering the preview: a targeted edit tool, not a gate decision.


## D-122 — UI Patch 8: the Produce workspace

**Status:** Accepted

**One page for the production gates.** `/produce` follows the redesign's
Produce page, with one tab per human gate between narration and export:
- Narration spend;
- Choose visuals;
- Footage rights;
- Rough cut;
- Visual spend;
- Edit preview;
- Final export.

They run on the shared review workspace rather than `/review`, so production
decisions sit together and the gate-review tab bar stays readable.

**Same requests, same rules.** Every tab posts exactly the classic panel's
body to the same endpoint, and the server's decision sets are mirrored and
pinned by a test. The page adds guidance, never a rule the server lacks:
- **Narration spend:** accept needs every spend check and confirms the
  worst-case amount.
- **Choose visuals:** a candidate must be chosen to use it, and blocked
  candidates cannot be picked.
- **Footage rights:** approval needs the editorial purpose.
- **Rough cut:** a visual rework needs a shot, and every rework needs a note.
- **Visual spend:** authorizing needs a ceiling above zero and within the
  per-shot hard cap, and confirms the amount.
- **Edit preview and final export:** returns need a note.

The server still routes rough-cut and spend reworks (to the storyboard, the
Format Gate or the Voice Performance Gate) and reports where they went.

**Spending stays explicit.**
- Both paid steps state their ceiling and ask for confirmation.
- "Authorize" sets a ceiling only; nothing is generated or charged on this
  page.
- Final export approval binds the rendered bytes and publishes nothing.

**Not waiting on you.** A shot whose storyboard changed must be re-searched by
the workflow before anyone can choose for it, so it is not counted as pending.
It shows as stale when you include decided items.

**Kept in the classic view.** Registering asset files (final narration audio,
managed and generated visuals, final sound) and editing a storyboard shot.
These are data entry and editing, not decisions. The Produce page and the
classic panels link to each other.

**Entry points.**
- The Command Center hero for each production gate state.
- One combined Command Center card and Review Queue row counting every
  pending production decision, which opens the first gate with work.
- The classic panels' "Open produce workspace" buttons.
- Productions → Produce in the sidebar.

## D-123 — UI Patch 9: Tools & Diagnostics

**Status:** Accepted

**Health first.** `/tools` now opens with System Health, then Recent Jobs.
The manual action list, pipeline state and safeguards move under Advanced.
- `GET /api/tools` returns `{health, jobs, updated_at}`.
- `GET /api/job-log?id=` returns one saved log.
- Both are read-only. Fix buttons run existing predefined actions through
  `/api/run`, so the one-job-at-a-time rule and the action gating still
  apply. The buttons are disabled while a job runs.

**What each health check means.**
- **Checked locally, nothing run or contacted:** binaries (yt-dlp,
  agent-reach), the configured FFmpeg, and the Kokoro and soundfile imports.
- **YouTube API key:** reported as present or missing only. Its value is
  never returned.
- **Radar scheduler:** *missing* if it has never run, *warn* if its last
  wake is older than 6 hours, with an Install Opportunity Automation button.
- **FAIR, Vision and vidIQ:** taken from the last run of each Doctor
  (*unknown* until one has run), with a Run Doctor button.

**Job history.** Each finished job appends one line to
`.experiment_ui/job_history.jsonl`, which keeps the last 300. Logs from
before this patch appear with status *unknown*. Log ids are checked against
the job-id pattern and must resolve inside the job log directory, so a
crafted id cannot read other files.

## D-124 — UI Patch 10: responsive, keyboard and accessibility pass

**Status:** Accepted

**Measured, not eyeballed.** An axe-core audit covered all 11 routes at 320,
640, 768 and 1280 px; 640 px is a 1280 px screen at 200% zoom. It found five
problems on every route, all now fixed:
- **Focusable controls inside closed drawers.** The drawers were hidden with
  `aria-hidden` but their controls could still take focus. Closed drawers
  are now `inert` dialogs.
- **Job indicator with no accessible name on phones.** It now has a label
  that follows the job's status.
- **Primary button contrast of 3.35:1.** A new `--accent-fill` (#1960d0)
  gives 5.2:1. The bright accent stays for dots, borders and focus.
- **A skipped heading level** on Opportunities.
- **A scroll strip the keyboard could not reach.**

**Keyboard-only use.**
- **Skip link and title focus.** A skip link is the first Tab stop. After a
  navigation, focus goes to the page title so it is not lost on a hidden
  control.
- **Overlays.** The two drawers and the phone menu take focus, keep Tab
  inside, close with Escape and return focus to whatever opened them.
- **Tab bars.** Every tab bar now follows the Production Workspace pattern:
  arrow keys, Home and End, with activation following focus. This lives in
  one shared module, `js/a11y.js`.

**Phone sidebar no longer closes on its own.** Status polls re-render the
route, and that used to close an open phone menu. Now only a navigation
closes it.

**Motion and contrast modes.**
- Reduced motion turns off all animations, transitions and smooth scrolls,
  including the two scripted smooth scrolls.
- Forced-colors mode keeps a visible focus ring and outlines status badges.

**Out of scope.** Behaviour and payloads are unchanged. Tests pin the drawer
semantics, the skip link, the script order and the fill contrast ratio.

## D-125 — UI Patch 11: craft pass

**Status:** Accepted

**Method.** I screenshotted every route at 1280 px and phone width, listed
each place where the same thing looked different, and fixed the cause
rather than the symptom.
- **Button sizes.** Buttons had no base font size, so any button without a
  size class fell back to the browser's 16px. That accounted for the
  oversized empty-state actions, the radar scan button and others. Buttons
  now default to `--text-sm`, and only the Command Center's main action is
  set larger.
- **Empty states.** There were two styles. `.empty-state` now uses the small
  text size, the subtle border and the large radius, and spans the full
  grid. Before, the Command Center's attention queue showed it squeezed into
  one card-width column.
- **Tabs.** A tab bar means "steps of one gate group", so Gate reviews now
  uses the same underline bar and switcher row as Packaging and Produce.
  Pills stay for filters. Tab padding is reduced so Produce's seven tabs fit
  at 1280 px.
- **Alignment and rhythm.**
  - Entry-card actions sit on a common baseline.
  - Adjacent panels get a consistent gap (the inbox and historical review
    used to touch).
  - The radar's explanatory note is spaced from its filters.
  - The Productions "+ New" button lines up with its tabs.
- **Names and titles.**
  - `/analysis` is called "Workspace" everywhere. The top bar no longer
    says "Analyze & Create", and the four server next-step messages that
    sent users to it now name Gate reviews or the Workspace.
  - Workspace and Tools no longer repeat their title and subtitle inside
    the page; the in-page heading is kept for screen readers only.
- **Stage strip.** The Workspace stage strip looked like buttons but did
  nothing. It is now a stepper.
- **Type details.** Headings use `text-wrap: balance` and paragraphs
  `pretty`; counts use tabular numbers.

**Unchanged.** Behaviour, payloads and the D-124 accessibility results are
unchanged: axe still reports no violations at 320, 640, 768 and 1280 px, and
the tab-bar arrow keys still work on every gate page. A test pins the
shared tab style, the base button and empty-state sizes, and the retired
page name.

## D-126 — UI Patch 12: Web Interface Guidelines QA

**Status:** Accepted

**Source.** The audit used Vercel's Web Interface Guidelines, fetched from
`vercel-labs/web-interface-guidelines` on 2026-10-03.
- **Applied:** every universal rule (interactions, animations, layout,
  content, forms, design).
- **Not applicable:** rules specific to React or Next.js (hydration,
  Suspense, re-render tracking), font and image loading rules (the app ships
  no web fonts or content images), and the Vercel-specific copywriting
  section.

**Found and fixed.**
- **Links are links.** 45 navigation controls were `<button data-route>`,
  which breaks Ctrl/Cmd-click and "open in new tab". They are now
  `<a class="button-link" href>` that look identical. The router still
  handles a plain click in place but lets modified clicks through to the
  browser.
- **Deep links.** The inbox tabs were remembered in local storage only. They
  are now in the URL (`/opportunity#saved` and so on), like the
  gate-review, packaging, produce and productions tabs.
- **Phones.**
  - Buttons, tabs and inputs were 26–37 px tall; they are now at least
    44 px on phones and touch screens.
  - Inputs were 12 px, which makes iOS Safari zoom on focus; they are now
    16 px.
  - The "include decided items" labels were 19 px; they are now 32 px
    (44 px on phones).
  - Controls get `touch-action: manipulation`.
- **No `transition: all`.** Three rules used a bare duration, which
  animates every property. Each now lists only the properties it changes.
- **Overscroll.** Drawers, the phone menu and log panes use
  `overscroll-behavior: contain`.
- **Unsaved changes.** A typed review note that has not been sent now
  triggers the browser's leave-page confirmation. Pre-filled notes and sent
  notes do not.
- **Forms.**
  - Inputs have meaningful `name`s.
  - URL and path fields have spellcheck and auto-capitalisation off.
  - Descriptive placeholders end with "…".
  - Native `<select>` elements set explicit colours for Windows dark mode.
- **Colour is never the only cue.** On phones, the health pill's label was
  `display: none`, leaving only a coloured dot. It is now visually hidden
  but still read out.
- **Smaller fixes.**
  - A `theme-color` meta tag matches the background.
  - In-page anchors clear the sticky top bar with `scroll-margin-top`.
  - Tools job times use the viewer's locale.
  - The brand is marked `translate="no"`.

**Already met (D-124 and D-125).**
- Keyboard operation and WAI-ARIA tab and dialog patterns.
- Visible focus, focus traps and focus return.
- Reduced motion, polite live regions, the skip link and heading
  hierarchy.
- Tabular numbers, labelled icon-only buttons, confirmation for stopping a
  job, Enter and Ctrl+Enter submission.
- Accurate page titles.
- Designed empty states that each offer a next step.

**Verified.** axe still reports no violations at 320, 640, 768 and 1280 px.
A live audit found no interactive element under 24 px on desktop or 44 px
on a phone, and no phone input under 16 px. All five tab bars restore their
tab from the URL after a reload. A plain click on a link navigates in place,
and a Ctrl/Cmd-click opens a new tab. A contract test pins these rules.

## D-127 — UI Patch 13: adversarial regression audit

**Status:** Accepted

**Method.**
- **Code review.** Three independent read-only reviews covered the redesign
  range 8d0e80d..HEAD:
  - payload fidelity: every gate against the classic panel and the server
    validation;
  - injection and server endpoints;
  - behaviour regressions: DOM contracts, handlers, polling, navigation and
    job locks.
- **Browser harness.** Inbox, radar and production data came from the real
  modules (`inbox.build_inbox`, `viral_radar.radar_overview`,
  `productions.derive`) with HTML/JS payloads in titles, channel names and
  labels, served by intercepting the API. It attacked:
  - every route, drawer and job log;
  - URL hashes: script, selector, traversal, malformed and 5,000-character
    payloads;
  - failing status, radar and production endpoints;
  - a slow server that refuses decisions, with a double submit;
  - 240-character titles at phone width.

**Found and fixed.**
- **Pending rough cuts were never shown (high, inherited).** A rough cut
  with no review yet has `review_current: false`, and both the classic panel
  and Produce filtered those out, so the gate could not be decided from any
  UI. The filter is gone; the server already discards stale reviews.
- **Decided gates could be re-decided (medium).** With "Include decided
  items" ticked, the new pages offered decisions the classic panels lock:
  - an approved narration preview;
  - authorized narration spend;
  - a decided edit preview or final export.

  The server would accept them and revoke the approval with no
  confirmation. Those items now offer no decisions and say why.
- **Refused decisions wiped the reviewer's work (medium).** Each module's
  `post()` swallowed the error, so its cleanup ran anyway. That cleared
  title picks and edits, the chosen package and criteria, the chosen
  visual, context notes and the max cost, and dropped the unsaved-note
  warning. `post()` now reports success, and every cleanup runs only on
  success. The inbox and script-section actions report failure the same
  way.
- **Malformed hash crashed the app (low).** A URL such as
  `/production#%E0` threw `URIError` out of routing, so polling never
  started. All hash decoding now goes through `YPUtil.decode`, which cannot
  throw.
- **Prototype pollution through a generated id (medium).** A `concept_id`
  of `__proto__` (concept ids are model output) wrote title picks onto
  `Object.prototype`, where they could be submitted for another concept. All
  id-keyed state maps now use `Object.create(null)`.
- **The skip link broke the Production Workspace (medium).** It set
  `#mainContent`, which routing read as a production id. The skip link now
  moves focus without touching the URL.
- **Media keys moved the review item (medium).** ←/→ on an audio or video
  player switched to another item and stopped playback. Media elements now
  keep their own keys.
- **Keyboard focus was lost on every poll (medium).** The Command Center
  rewrote its lists every 5 seconds. It now repaints only when the markup
  changes.
- **Rejected packaging led to an empty page (high).** The Home link went to
  `/packaging`, which lists only pending items. It goes to the classic
  panels again, which hold the rework controls, and the Packaging empty
  state now links there too.
- **Dead end on an unknown production.** The error now offers a link back
  to Productions.
- **Deep links on first load.** `/opportunity#watching` and
  `/productions#review` were ignored on a fresh load. They now apply.
- **Script note limits.** Section rework, manual edit and whole-script
  rework notes now use the classic limits: 1,200, 5,000 and 1,400
  characters.
- **One failing module froze everything.** `renderAll` now isolates each
  page module, so the classic panels and the live job keep updating.
- **API reads were open to DNS rebinding (low).** `/api/` GETs, which carry
  job logs, pipeline state and the CSRF token, now require the same
  127.0.0.1/localhost Host header as POST.
- **Smaller server fixes.**
  - Production "updated" times match files by the longest slug prefix, so
    `foo` no longer takes `foo.v2.*` files.
  - The job-log endpoint reads only the tail of a log.

**Not changed.**
- **Server-side `concept_id` validation.** This belongs in the
  transformation engine; the UI no longer trusts ids as object keys either
  way.
- **Same-path links without a hash.** These keep the current tab.
- **Review panel repaint.** A panel can still repaint while a note is being
  typed, if that item's data changes; the draft text is preserved.

**Verified.**
- The harness's 22 checks pass: no payload executes on any route, drawer,
  log, error message or hash, and there are no uncaught errors.
- One request is sent per decision, even when submitted twice.
- Server errors are shown as text, and the page recovers.
- Nothing overflows on a phone.
- A `__proto__` id leaves `Object.prototype` clean.
- The D-124 axe audit, the keyboard walkthrough and the D-126 guideline
  checks still pass.

## D-128 — The Master Product Vision governs; its audit sets the correction order

**Status:** Accepted

**Context.** On 3 October 2026 an audit compared the repository (at the
laptop's `6d561d1`, before UI Patches 9–13) against the Master Product Vision
and Build Comparison Specification. It found the foundations on track but
several workflow deviations, and the complete production-to-learning loop not
yet built.

**Decision.**
- **What governs.** The Master Product Vision is the governing product
  definition, with Opportunity Discovery v2.1 for discovery. Older decisions
  that conflict with it do not override it; the conflicting decisions are
  superseded case by case, as each correction lands.
- **Correction order.** Deviations are corrected before new integrations are
  built, in this order:
  - **A1:** test isolation, plus README and roadmap status.
  - **A2:** stage completion policy. A resumable batch is not a complete
    stage. The Gemini fallback applies only to verified provider or quota
    failures.
  - **A3:** a concept pool of 15–25, with semantic de-duplication and five
    diverse finalists or an explicit shortfall.
  - **A4:** conditional research review (auto-cleared, review required or
    blocked).
  - **A5:** one resolved format.
  - **A6:** append-only decision history for analysis and research.
  - **Then:** packaging (a 2–3 title shortlist, an image-provider adapter,
    three candidate visuals), planning and money (visual-plan approval before
    narration spend, approval of the final audio, one budget ledger per
    video), production execution, Tesseract, publishing and performance
    learning.
- **Milestone.** One Science Inside video from an approved opportunity to a
  reviewed, editable near-final production, with complete provenance and a
  combined cost ledger. Feature slices do not substitute for that run.
- **Human decisions.** These are not taken by the build: approving the
  Science Inside channel voice, choosing the image provider, the per-video
  budget figures (about $5 target and $10 ceiling), and installing the
  scheduled automation on the laptop.

**A1 in this patch.**
- **Cause.** The audit's nine failing tests on the populated laptop were test
  defects, not product defects:
  - Eight UI tests read the machine's real approved study set or prepared
    profiles. The server resolves about 90 output paths at import time, and
    each test patched only some of them.
  - One acquisition test assumed a single subprocess call, but a machine
    with whisper and ffmpeg installed runs a second, transcription, call.
- **Fix.**
  - `experiment_ui/testing_isolation.py` redirects every server output path
    to an empty temporary tree: per test in `test_server.py`, per module in
    every other UI test file.
  - The acquisition test pins `local_transcription_available` to False.
  - A guard test fails if the real paths become visible again.
- **Verified.** I reproduced the failures by planting a study set and
  prepared profiles in the real output folders, with whisper, agent-reach and
  mcporter on the PATH: the same nine tests failed. After the fix, all 12
  suites pass both in that populated state and in a clean checkout.
- **Docs.** The README's status, pipeline, repository, runtime, Experiment 02,
  Transformation, Research, Packaging and UI sections now describe what is
  built. PROJECT.md carries a status note marking its historical parts.
- **Follow-up.** The module documents `packaging_engine/PACKAGING_ENGINE.md`
  (pre-script flow) and `production_engine/PRODUCTION_ENGINE.md` (two slices
  only) still describe older states; they are updated with the corrections
  that touch them.

## D-129 — A resumable batch is not a complete stage; Gemini replaces only exhausted free capacity

**Status:** Accepted (vision §§101, 104–105; correction A2 of D-128)

**Investigation.**
- **Stage readiness.** I mapped every automatic machine step: what
  "complete" means and what each downstream readiness check accepts. The
  runner continues after a partial exit (code 2) whenever a different action
  becomes ready, so readiness checks alone decide whether partial work is
  promoted. Almost every stage already requires full coverage
  (`expected ⊆ current`). Two did not:
  - **Concept pool.** Triage opened as soon as five concepts validated. With
    six mechanisms and a first batch of four, the remaining two were never
    generated, and the Concept Gate saw an incomplete pool without being told.
  - **Visual review.** A partial visual run (frames for 3 of 5 videos) skipped
    the human visual review entirely, so the sampled frames went unreviewed
    and analysis ran on transcripts alone.
- **Fallback.** One shared function decides direct-Gemini eligibility for all
  14 FAIR runners. It admitted:
  - quality failure (`ALL_FREE_MODELS_FAILED_QUALITY`);
  - missing verifiers (`QUALITY_VERIFICATION_UNAVAILABLE`,
    `INDEPENDENT_VERIFIER_UNAVAILABLE`);
  - `NO_ELIGIBLE_FREE_MODELS`.

  The concept runner also bypassed that gate altogether. When every concept
  failed deterministic validation, it called Gemini to "repair" the
  response. This contradicted D-068.

**Decision.**
- **Concept coverage.** Triage requires every requested mechanism to
  contribute at least one current, validated concept.
  - The merge reports `INCOMPLETE_MECHANISM_COVERAGE` with the missing IDs.
  - The batch exits as partial.
  - Generation stays the next step and retries only the missing mechanisms.
  - The server re-checks coverage, so older candidate files cannot slip
    through.
- **Visual review.** It covers every video whose visual run kept frames, so a
  partial run still reviews the sampled videos before analysis. Videos
  without frames continue on transcript evidence. The shared check is
  `vision_review_satisfied()`.
- **Fallback.** `direct_gemini_fallback_decision()` is the only gate, and it
  allows only `ALL_FREE_MODELS_UNAVAILABLE` with `paid_inference_executed`
  false. Every other reason is refused, and the refusal and its repair
  explanation are recorded on the result. The concept runner's validation
  repair is removed.
- **Unchanged.** Intentional partial releases stay as they are:
  - per-concept research release (D-104);
  - the analysis one-then-remaining chain;
  - batch-progress loops;
  - visual `manual_required` items handled by gap plans.

  The runner's exit-code handling is also unchanged: the readiness checks
  are the gate, and the investigation found no other stage that promotes
  partial work.

**Consequence.** A run that previously fell back to Gemini on quality,
verifier or no-eligible-route escalations now stops with an explanation, and
the request, prompt, schema or route has to be repaired on the free path.
`NO_ELIGIBLE_FREE_MODELS` is refused because it can mean the request fits no
route as well as quota loss. If FAIR's attempt records later prove
exhaustion, this can be widened per attempt.

**Not verified here.** The external FAIR repository is not in this
workspace, so the meaning of its reason codes is taken from their names and
the bridge code.

## D-130 — A 15–25 concept pool, five distinct finalists, and a stated shortfall

**Status:** Accepted (vision §§26–28; correction A3 of D-128)

**Context.** Each mechanism produced five concepts, so the pool was simply
mechanisms × 5. Triage could shortlist 0–6 concepts purely by score, and
only identical concept IDs were removed. Two restatements of one idea could
both reach the Concept Gate, and one mechanism could fill every place.

**Decision.**
- **Pool size.** Requests are sized to put the pool in 15–25: five per
  mechanism, clamped to that range and spread evenly, with at most eight per
  request because free models fail on oversized structured output.
  - One mechanism therefore yields eight, two yield 15 and five yield 25.
  - The merge records the pool against the target (`pool`).
  - Triage still opens once every mechanism has contributed (D-129), so a
    below-target pool is reported rather than blocked.
- **Similarity.** A deterministic measure,
  `concept_diversity.concept_similarity`, compares the vision's dimensions:
  premise, framing, hook, title and payoff, pooled as stemmed content words.
  - On real-shaped concepts, a paraphrased restatement scored 0.52, a
    related but different idea from the same domain 0.16, and unrelated
    ideas 0.03–0.06.
  - The near-duplicate threshold is 0.35. It is configurable as
    `near_duplicate_threshold`.
- **Finalists for the final model comparison** are chosen in rank order
  without near-duplicates, and while alternatives exist, at most three come
  from one mechanism or one hook type.
- **Shortlist.** Up to five distinct concepts scoring 70 or more. A
  near-duplicate of a higher-ranked concept never takes a place, and no
  mechanism or hook type takes more than two places while others qualify.
- **Shortfall.** When fewer than five qualify, the empty places stay empty
  and the Concept Gate says so. Each excluded concept keeps its reason and
  stays reachable under View all candidates, where the existing override,
  rework and save-idea actions are unchanged.

**Consequences.**
- The final model pass is unchanged: it still only scores, and deterministic
  code still decides.
- The validation contract fingerprint covers the engine and its config, so
  this patch invalidates cached concept responses. Existing pools regenerate
  once at the new size.
- Requests can now ask for up to eight concepts. If a free model fails on
  that size, A2's partial handling retries the mechanism, and the per-request
  cap can be lowered in `transformation_config.json`.

**Not done here.** A targeted top-up that generates more concepts when the
pool is under 15 needs more than one request per mechanism, a larger change
to request identity. Until then the shortfall is visible, and the Concept
Gate's rework action is the way to ask for more.


## D-131 — Conditional research review

**Status:** Accepted (vision §32; correction A4 of D-128)

**Context.** Every research claim waited for a human decision, even when two
independent sources quoted it verbatim. Vision §32 locks research review as
conditional: a claim may progress automatically when the evidence is strong,
the sources are reliable, nothing meaningful conflicts and the claim is not
high-risk. Human review is required when evidence conflicts or is weak, the
wording needs care, or risk is elevated.

**Decision.**
- **Policy.** `research_engine/evidence_policy.py` classifies each claim, on
  top of the existing verbatim quote verification, as AUTO_CLEARED,
  REVIEW_REQUIRED or BLOCKED.
  - It auto-clears only with supporting quotes from at least two independent
    websites and only primary, secondary, dataset or documentation sources.
  - Any of these sends the claim to a human: a contradicting or qualifying
    source, CONFLICTED coverage, absolute wording, a figure missing from
    every supporting quote, or an elevated-risk subject (health, safety,
    death, legal, money).
  - BLOCKED means no traceable supporting quote; such a claim can only be
    reworked or rejected.
- **Wiring.** Prepare records an automatic ACCEPT, with
  `decided_by: EVIDENCE_POLICY` and the reasons, for each cleared claim.
  - It never replaces a human or carried-forward decision, and drops and
    recomputes its own decisions on every prepare.
  - The gate re-checks each automatic acceptance before writing the verified
    package, and records `decided_by` and `policy_reasons` on the claim.
- **Review UI.** Cleared claims leave the pending list. Shown with decided
  items, they carry a "Cleared automatically" badge and their reasons. Every
  remaining claim shows "Why this needs you".
- **Configuration.** Thresholds are in `research_gate_config.json` under
  `evidence_policy`; `enabled: false` restores human review of every claim.

**Consequences.**
- When every claim clears and every research question is answered, research
  completes without stopping, and automation continues to Story / Script.
- The decision fingerprint adds `decided_by` only for automatic decisions, so
  packages a human decided before this change keep their fingerprints and
  their downstream work stays current.
- The policy is deliberately lexical and conservative. A wrong automatic
  clearance costs more than one extra human decision, so the thresholds lean
  towards review. They can be loosened in config once real runs show how
  often strong claims are held back.


## D-132 — One resolved format per production

**Status:** Accepted (vision: early Short / long-form decision; correction A5 of D-128)

**Context.** A concept could be generated with `format_intent: either`, and
that value travelled unchanged to Story / Script and Format, which expanded it
into two script branches and two production branches. One accepted concept
therefore became two videos to write, review and produce, although the vision
makes the Short / long-form decision early and each production makes one
video.

**Decision.**
- **Resolution at the Concept Gate.** `transformation_engine/format_resolution.py`
  resolves every accepted concept to `long_form` or `short`, in this order:
  - the format the human chose when accepting;
  - the concept's own single format;
  - for `either`, `either_default_format` in `concept_gate_config.json`
    (long-form).
- **Record.** The research handoff carries the resolved `format_intent` and a
  `format_resolution` record: the format, what was requested, `decided_by`
  (HUMAN, CONCEPT or DEFAULT) and the reason. A format can only accompany
  ACCEPT.
- **Review UI.** An `either` concept shows "Accept as long-form" and "Accept
  as Short" in place of a single Accept.
- **Packaging.** A packaging request for a resolved concept allows only that
  format, and a package naming another format is rejected.
- **Downstream.** Story / Script and Format are unchanged. They now receive
  one format and so write and plan one branch.

**Consequences.**
- A new production makes exactly one video, and the second script, its review
  and its production work are no longer spent on a format nobody chose.
- Generation is unchanged. Concepts may still be marked `either`, which
  records that the idea fits both formats; the choice happens at acceptance.
- Productions accepted before this change keep `either` in their handoff and
  can finish with two branches. The `either` mappings remain in the script and
  format configs for them only.
- Making the other format from the same idea is a separate decision: accept
  the concept again or save the idea, rather than an automatic second branch.


## D-133 — Append-only decision history for analysis and research

**Status:** Accepted (vision: append-only reviewed history; correction A6 of D-128)

**Context.** The newer script and packaging gates keep versions and archived
decisions, but the Analysis Gate, vision review and Research Gate kept only
the latest decision. Changing a decision overwrote it, an automatic research
acceptance left no trace once withdrawn, and waivers vanished when removed.
Nobody could tell later what had been decided before, by whom, or why.

**Decision.**
- **Shared helper.** `pipeline_integrity.append_jsonl` appends one JSON
  record per line and syncs it to disk; earlier lines are never rewritten.
  `read_jsonl` skips a torn final line left by a crash.
- **Research Gate** (`research_gate_history.jsonl`) logs:
  - every human ACCEPT, REWORK and REJECT, with the reviewer, note and the
    decision it replaced;
  - each automatic acceptance once;
  - the withdrawal of an automatic acceptance when its claim or the policy
    changes, logged before any new acceptance;
  - waivers and their removal.
- **Analysis Gate** (`human_review_history.jsonl`) logs every finding
  decision, with the profile hash it was made against.
- **Vision review** (`vision_review_history.jsonl`) logs every frame
  decision, with the accepted observation and the source hashes.
- **Review UI.** Snapshots attach each item's `decision_history`, and the
  Analysis and Research review pages show it newest first.

**Consequences.**
- The live state files are unchanged and still hold only the current
  decision, so every reader of them keeps working. The logs are a record,
  not a second source of truth.
- The logs live under the gitignored output folders beside the state they
  describe. They grow by one line per decision, so no rotation is needed.
- Decisions made before this change have no history lines; their current
  state is still in the review files.
- The Opportunity, Script and Packaging gates already keep their own history
  or versions and are unchanged. The Concept Gate was outside the audit's
  finding and is unchanged; it can use the same helper if needed.


## D-134 — A 2–3 title shortlist at the Final Packaging Gate

**Status:** Accepted (vision: 5 Short + 5 Long titles, a 2–3 title shortlist;
amends D-096 and D-099)

**Context.** Five titles per format were generated, one direction was picked
at the Title Direction Gate, and the Final Packaging Gate then listed all 25
title × thumbnail pairs. Nothing narrowed the list to the 2–3 titles the
vision asks the human to choose between. D-096 forbade any ranking because a
winner score would invent a prediction the system cannot make.

**Decision.**
- **Shortlist.** `packaging_engine/title_shortlist.py` builds a 2–3 title
  shortlist per format from the validated pair matrix. It calls no model and
  predicts no clicks. The ordering is explained:
  - the human's chosen title direction first;
  - then PASS-pair count;
  - then the mean title-quality diagnostics over PASS pairs;
  - then `title_id`.
- **Eligibility and diversity.** A title needs at least one PASS pair, and a
  near-duplicate of a shortlisted title (content-word Jaccard of 0.5 or more)
  never takes a place.
- **Shortfall.** When fewer than two titles qualify, the shortfall is stated
  and not filled.
- **Gate.**
  - Packages for shortlisted titles are listed first, and every package is
    marked `in_title_shortlist`.
  - Titles outside the shortlist stay reachable.
  - Accepting one needs a note, and the decision records
    `title_in_shortlist`.
- **Review UI.** The `/packaging` Final tab shows the shortlist with each
  title's reason. It places acceptable packages with titles outside the
  shortlist in their own collapsed group.
- **Fix in passing.** The package view now carries `semantic_redundancy`, so
  the Redundancy badge appears.

**Consequences.**
- D-096's rule stands in substance: there is still no viral score, CTR
  prediction or hidden winner. The ordering uses only validation results
  already shown on each package, and every entry states its reason.
- Rework targets, staleness and the final bundle are unchanged (D-099).
- The thresholds are configurable under `title_shortlist` in
  `final_packaging_gate_config.json`.


## D-135 — Candidate thumbnail images through a provider-agnostic adapter

**Status:** Accepted (vision: AI image router producing three candidate
visuals; the provider choice remains the human's)

**Context.** The renderer composed thumbnails only from an image the human
supplied by typing a file path. The vision has an image router produce three
candidate visuals for the human to choose from. No image provider has been
chosen, and no app code had yet made a paid provider call.

**Decision.**
- **Candidate step.** `production_engine/thumbnail_image_provider.py` adds a
  candidate step in front of the existing subject image:
  - a text-free prompt built from the Slice 25 concept;
  - GENERATE: three candidates from the configured provider;
  - IMPORT: an image made in any other tool, with its provenance;
  - CHOOSE: the candidate becomes the subject image through
    `thumbnail_review.update_spec`.
- **Spend.** A generation is a paid call the human authorizes with an
  explicit maximum cost. The maximum must cover the estimate and stay within
  the per-thumbnail cap (US$0.50). The video's generated-image spend must
  stay within the per-video cap (US$2.00). Every generation is appended to a
  spend ledger.
- **Provider.** The one adapter speaks the common OpenAI-compatible images
  request. It is off until the human sets:
  - the provider, endpoint and model;
  - the licence terms;
  - the price per image;
  - a verified contract;
  - the API key.

  Until then the UI says what is missing, and imports still work.
- **Unchanged.** Rights validation, rendering, staleness, the Human
  Thumbnail Gate and final packaging. A chosen candidate is an ordinary
  subject image with source tier `CHEAP_AI` and the provider's licence.
- **UI.** The classic Thumbnail panel shows the candidates with "Use this
  image", the generation form (only when a provider is ready, with a confirm
  step), an import form, the prompt and the video's spend so far.

**Consequences.**
- Choosing the provider, its licence and its price is still the human's
  decision. Configuring one turns generation on with no code change, unless
  it needs a different request shape (one adapter function).
- The caps are placeholders inside the proposed US$5 target / US$10 ceiling
  per video, which is also still to be confirmed. They live in
  `thumbnail_image_config.json`.
- Candidates are bound to the concept version, so a reworked concept cannot
  silently reuse an image made for the old one.


## D-136 — One budget per video

**Status:** Accepted (vision: one combined budget for the whole video; the
US$5 target and US$10 ceiling remain to be confirmed by the human)

**Context.** Every paid step kept its own money rules, and none of them
added up spend per video:
- the Visual Spend Gate capped authorizations across all productions
  together;
- narration was approved at a quoted worst case with no dollar ceiling;
- thumbnail images had their own small caps;
- final sound recorded costs with no cap.

The US$5 target was advisory only.

**Decision.**
- **Ledger.** `production_engine/video_budget.py` keeps one append-only
  ledger keyed by video (`concept:format`). It has three event kinds:
  - RESERVE: the most authorized for an item;
  - RELEASE: that authorization withdrawn;
  - ACTUAL: the total spent on the item so far.

  An item counts at the larger of its reservation and its actual spend.
- **Rules.**
  - A reservation that would take a video above its ceiling is refused, in
    every category.
  - Above the target, a reservation is allowed and flagged.
  - Actual spend is always recorded, because it has already happened.
- **Who records what.**
  - Narration Spend Gate ACCEPT reserves the worst case.
  - Visual Spend Gate AUTHORIZE reserves the shot's maximum.
  - Thumbnail generation reserves before the paid call.
  - Narration return, generated-visual import, thumbnail import and
    final-sound import record actual costs.
- **Concurrency.** One process-wide lock covers every
  check-then-record, so two simultaneous authorizations cannot both pass
  the ceiling. It is held in `pipeline_integrity.named_lock` so it is shared
  however the module is imported.
- **Location.** Each stage writes the ledger beside its own output folders,
  which in use is always `production_engine/output`. Tests that move a
  stage's folders therefore move its ledger too.
- **Visibility.** The `/produce` page shows each video's committed and spent
  totals against the target and ceiling, and states that the budget is
  still a proposal.

**Consequences.**
- A narration worst case, visual authorizations and thumbnail generations
  can no longer add up past US$10 for one video.
- Existing stage caps still apply on top of the budget.
- Spend from before this change is not in the ledger.
- Changing the budget is a config edit; `confirmed_by_human` records that you
  have confirmed it.


## D-137 — A human approves the exact final narration audio

**Status:** Accepted (vision: approval of the final audio itself; correction
named in D-128; completes the NARRATION_AUDIO_READY stop of D-082)

**Context.**
- **Before the change.** The human approved the free local preview and then
  the spend for a quoted provider render. The returned paid audio passed
  only automatic Audio QC (duration, silence, clipping, missing files), and
  visual planning started from its timing without anyone listening.
- **Why that falls short.** QC cannot hear a mispronunciation, a wrong
  emphasis or a flat read.

**Decision.**
- **Gate.** `production_engine/narration_final_review.py` adds the Human
  Final Audio Gate after Audio QC passes. Per video it lists every segment,
  with:
  - its audio;
  - its planned and actual duration;
  - its start time and take.
- **Decisions.**
  - APPROVE_FINAL_AUDIO.
  - REWORK_SEGMENTS: named segments plus a note; the next provider return
    replaces them.
  - REJECT_AUDIO: needs a note.
- **Binding.** An approval is bound to the QC report and timing-map hashes,
  and decisions are appended to a history log.
- **Server.**
  - `narration_artifact_state` now separates `audio_qc_passed` from
    `audio_ready`; `audio_ready` also requires the approval. Everything that
    started from QC-passed audio (visual manifest, storyboard, edit
    manifest) now waits for the human.
  - New workflow stops: `HUMAN_FINAL_AUDIO_GATE` and
    `FINAL_AUDIO_REWORK_REQUIRED`.
  - Routes: `/api/final-audio-gate` (locked during jobs) and
    `/api/final-audio-file`, which serves only managed narration files.
- **UI.** `/produce` gains a "Final audio" tab with a player per segment and
  "Re-record this segment" ticks.

**Consequences.**
- One more human decision per video, at the point where re-recording is
  still cheap: before any visual is timed to the audio.
- Approval is per video; a partial approval is not offered. Re-recording
  goes through the provider and the existing return registration, so spend
  stays inside the approved ceiling and the per-video budget (D-136).


## D-138 — The complete visual plan is approved before narration spend

**Status:** Accepted (vision: visual plan approval before expensive
generation; correction named in D-128; amends the order fixed by D-083)

**Context.** The visual manifest and storyboard were built only after the
paid narration had been quoted, authorized, returned and QC-checked, because
they took their timing from the returned audio (D-083). Money was committed
to narration before anyone had seen the visual plan, and nothing approved
the plan as a whole.

**Decision.**
- **Gate.** `production_engine/visual_plan_review.py` adds the Human Visual
  Plan Gate between the approved free preview and the Narration Spend Gate.
  Per video it builds the complete plan from the approved format plan, using
  `visual_acquisition.build_manifest` with no timing, so it is the same
  requirements as the later manifest.
- **What the plan shows.**
  - Each shot's window in the approved free preview, read from the
    preview's per-beat WAV files.
  - Each shot's first source tier.
  - The paid-visual share policy and the video's budget.
- **Decisions.**
  - APPROVE_VISUAL_PLAN: bound to the approved format plan, the approved
    preview audio and the plan content.
  - REWORK_VISUAL_PLAN: needs a note and holds spend; the format plan is
    reworked at the Format Gate.

  Decisions are appended to a history log.
- **Server.**
  - Refuses narration spend ACCEPT for a video without an approved plan.
  - Workflow stops: `HUMAN_VISUAL_PLAN_GATE` and
    `VISUAL_PLAN_REWORK_REQUIRED`.
  - Route: `/api/visual-plan-gate` (locked during jobs).
  - Videos already past narration spend are not pulled back.
- **UI.** `/produce` opens on a "Visual plan" tab with the shot table.

**Consequences.**
- No paid narration is authorized for a video whose visual plan was not
  approved.
- The storyboard is still timed from the paid audio after the Final Audio
  Gate (D-137); the approved plan fixes its shots and their order. Real
  durations may differ slightly from the preview, which is why shot-level
  storyboard editing stays after the paid audio.
- Rework goes through the Format Gate, the plan's source of truth, rather
  than a second editable copy of the plan.


## D-139 — The app calls the paid narration provider itself, within approved spend

**Status:** Accepted (vision: real production execution; the provider
choice and contract remain the human's)

**Context.** The paid narration was produced outside the app and its audio
registered by hand: provider job, cumulative cost and one file per segment.
Everything up to the spend approval and after the return was automated, but
the call itself was manual. The configured provider (Higgsfield) has no
verified contract, endpoint or price.

**Decision.**
- **Dispatch.** `production_engine/narration_dispatch.py` renders segments
  with the configured adapter and registers them through
  `narration_render_import.register`, so Audio QC, the Final Audio Gate
  (D-137) and the per-video budget (D-136) are unchanged.
- **Conditions.** A dispatch needs all of these:
  - a verified provider contract;
  - a configured adapter;
  - an API key;
  - a price per 1,000 characters (never guessed);
  - a current spend approval;
  - an estimate within the approved worst case after what was already
    spent.
- **Re-recording.** It covers only named segments, as the next attempt
  within the approved regeneration policy; the other segments keep their
  audio.
- **Failures.** Partial spend on a provider failure is recorded in the
  history and the budget.
- **Adapter.** The one adapter, `HTTP_TTS_JSON`, posts the segment text and
  delivery as JSON and accepts audio, or JSON with base64 audio.
- **UI.** `/produce` has "Generate narration with the provider" and
  "Re-record N segments" buttons, each with a confirmation step. The server
  route `/api/narration-dispatch` is locked during jobs.

**Consequences.**
- With a verified provider configured, a video's narration goes from spend
  approval to the Final Audio Gate without manual file handling.
- Until then nothing changes: the request stays BLOCKED, the UI says what
  is missing, and manual registration still works.
- Choosing the provider, verifying its contract and setting its price stay
  the human's decisions.


## D-140 — The app generates premium visuals for authorized shots; the human chooses

**Status:** Accepted (vision: real production execution; the provider
choice and contract remain the human's)

**Context.** A shot reaches premium generation only after free and existing
sources failed and the human authorized a maximum at the Visual Spend Gate.
The handoff wrote a provider-neutral request, but the asset was then made
outside the app and registered by hand. The request's policy says the human
must choose the final generated asset.

**Decision.**
- **Generation.** `production_engine/visual_dispatch.py` generates
  `variants_per_shot` variants (default 2) for a current, authorized request.
  The prompt is the request's generation brief and negative constraints.
- **Conditions.** A generation needs all of these:
  - a chosen provider with endpoint, model, licence and price (never
    guessed);
  - a verified contract;
  - an API key;
  - the shot's spend so far plus the estimate within its authorized
    maximum.
- **Choice.** Variants are kept as candidates, and the human chooses one on
  `/produce#generate`. The choice is registered through the existing import
  with the shot's total spend, as `APP_PROVIDER_DISPATCH`.
- **Records.** Spend goes into the per-video budget immediately (D-136), and
  every generation is appended to a history log.
- **Adapter.** The one built-in adapter makes still images through the
  OpenAI-compatible images request.
- **Server.** The route `/api/visual-dispatch` (GENERATE or CHOOSE) is
  locked during jobs; `/api/visual-dispatch-file` serves only stored
  variants.

**Consequences.**
- With a configured provider, an authorized shot goes from spend approval to
  a registered asset without manual file handling. Assembly, the edit
  preview and export are unchanged.
- Video generation is not covered by the built-in adapter. Until a video
  provider is chosen and given an adapter, moving shots are still made
  outside and registered by hand.
- Nothing is called until the human chooses and configures a provider.


## D-141 — Paid dispatch hardening

**Status:** Accepted (fixes found by offline reproduction probes against
D-135 to D-140)

**Context.** Offline probes reproduced five ways the paid steps could spend
more than authorized, or trust input they should not:
1. After failed narration dispatches, a retry forgot the money already paid
   and restarted attempt counts. Segment b1 was paid five times against
   three approved attempts, and the ledger understated spend.
2. Two simultaneous visual generations both passed the shot's authorized
   maximum check, spending US$2.00 against US$1.50.
3. A variant generated for an earlier version of a request (a different
   brief) could still be chosen as the shot's asset.
4. A NaN amount made every later budget comparison false. One NaN
   reservation let a US$100 reservation through a US$10 ceiling.
5. The images adapter fetched any `url` in the provider's response,
   including `file://`, which reads local files.

**Decision.**
1. **Narration accounting.** Narration dispatch counts every dispatch under
   the current spend approval: money paid and per-segment calls, failed
   batches included. The worst-case check and attempt policy use those
   totals.
2. **Locks.** Narration dispatch (per video) and visual generation (per
   shot) run under a named lock, so check, pay and record are atomic.
3. **Variant binding.** Generated variants are bound to the request's hash.
   Only variants of the current request are shown or can be chosen.
4. **Money values.** `video_budget.money` accepts only finite, non-negative
   numbers, and every budget call and thumbnail cost input uses it. A
   corrupt ledger amount counts as infinite, so it blocks further spend
   instead of loosening the budget.
5. **URLs.** Provider image URLs are fetched only over `https`. Every
   configured provider endpoint (thumbnail, visual, narration) must be
   `https://` before the provider is ready.

**Consequences.**
- Each probe is now a regression test that fails on the old code.
- A narration whose segments used up their attempts in failed batches needs
  a new spend approval, which resets the count, rather than paying again
  silently.


## D-142 — A publish package and a Human Publish Gate

**Status:** Accepted (vision: publishing)

**Context.** The Final Export Gate approves the exact rendered bytes and
records `upload_authorized: false`. Nothing assembled what YouTube needs,
and nothing recorded which video id an approved export became.

**Decision.**
- **Package.** `production_engine/publish_review.py` builds a publish
  package for every current approved final export:
  - the render file and hash;
  - the exact title, approved thumbnail and viewer promise from the final
    package bundle;
  - a description with the verified research sources and an AI-voice
    disclosure;
  - category, language, made-for-kids, privacy (private by default),
    optional schedule, tags, and the altered/synthetic content flag (on by
    default).
- **Edits.** The human may edit everything except the title. The title stays
  the one approved at the Final Packaging Gate.
- **Approval.** APPROVE_PUBLISH validates YouTube's limits and binds the
  approval to the export approval, bundle and research hashes. HOLD needs a
  note.
- **Publish record.** The YouTube video id is recorded once, either by the
  uploader (D-143) or by hand. A published video cannot be approved or
  uploaded again.
- **Workflow.** New stops: `HUMAN_PUBLISH_GATE`, `WAITING_FOR_UPLOAD` and
  `PUBLISHED`. The UI is the `/produce#publish` tab, and the route
  `/api/publish-gate` is locked during jobs.

**Consequences.**
- The pipeline now ends at a recorded YouTube video id, which the learning
  phase needs to fetch the video's analytics.
- The synthetic-content flag defaults to on because the narration is an AI
  voice. Turning it off is a deliberate human choice, recorded with the
  approval.


## D-143 — Direct YouTube upload with the owner's OAuth credentials

**Status:** Accepted (off until the human configures OAuth)

**Context.** Even with an approved publish package, the video, thumbnail and
metadata had to be uploaded by hand.

**Decision.**
- **Upload.** `production_engine/youtube_upload.py` uploads an approved
  package through the YouTube Data API v3:
  - a refresh-token exchange;
  - a resumable `videos.insert` with the exact approved snippet and status,
    including `containsSyntheticMedia` and `publishAt`;
  - then `thumbnails.set`.
- **Safeguards.**
  - Before uploading it re-checks the approval and the exact video and
    thumbnail bytes.
  - It runs once per video, under a lock.
  - It records the video id even if setting the thumbnail fails, so a retry
    never creates a duplicate.
- **Setup.** Off until `youtube_upload.enabled` is true and the client id,
  client secret and refresh token are set in `.env`.
- **UI.** The Publish tab offers "Upload to YouTube" (with a confirmation
  step) when the uploader is ready, and "Record a manual upload" always.

**Consequences.**
- Credentials stay in `.env` on the laptop. The app never stores an access
  token.
- Uploads default to private. A scheduled video stays private until YouTube
  publishes it at `publishAt`.

## D-144 — An editable project for Tesseract, and the finished edit back

**Status:** Accepted (round trip with Tesseract itself still to be confirmed)

**Context.** The vision makes Tesseract the final editable production
environment: automation builds the near-final video, and the human moves
clips, changes timing, replaces scenes and polishes it there. The audit
found no project exchange: only the rendered MP4 left the pipeline, and
scene ids had no mapping into an editor. Tesseract's own project format is
not documented anywhere available to this build.

**Decision.**
- **Export.** `production_engine/tesseract_exchange.py` turns the current
  local final render into one project folder:
  - copies of the exact media;
  - the timeline as OpenTimelineIO and as Final Cut Pro 7 XML;
  - the automated render for reference;
  - the thumbnail's editable source;
  - `exchange.json` listing every clip.
- **Stable ids.** Each clip is named `V-<shot>`, `N-<segment>` or
  `S-<sound requirement>`, so a returned `.otio` maps back to scenes
  (kept, moved, retimed, removed, added).
- **Import.** The finished video is probed (video at the format's frame
  size, audio present), copied into managed storage and bound to its hash,
  the export and the automated render.
- **Final Export Gate.** A current returned edit replaces the automated
  render as the candidate. An approval of the automated render stops
  counting. `RETURN_TO_EDITOR` sends an edit back; discarding it (with a
  note) restores the automated render.
- **Unverified contract.** The config records `round_trip_verified: false`,
  and the UI shows the contract note, until one project has been through
  Tesseract and back.

**Consequences.**
- Publishing uses whichever version passed the Final Export Gate, so a hand
  edit reaches YouTube only after the human approves its exact bytes.
- A new automated render makes the export and any returned edit stale.
- If Tesseract turns out to need its own project format, an adapter for it
  replaces or joins the two open formats; the ids, import and gate binding
  stay as they are.

## D-145 — Providers get a shape-only concept schema

**Status:** Revised by D-148. Field bounds are sent to providers again; only
the concept count is left out.

**Context.** On the laptop, two concept mechanisms (progressive reveal and
specificity) failed on every free route while three passed:
- Groq answered `PROVIDER_REJECTED_GENERATED_SCHEMA`;
- the Cloudflare models failed FAIR's schema check.

The schema sent to providers carried the same per-concept policy bounds the
app's own validator already enforces:
- an empty `source_specific_elements_used`;
- fixed `passes: true` and `source_assets_required: false`;
- item counts and number ranges;
- the maximum number of concepts.

Under strict structured output, one concept breaking one bound makes the
provider reject the whole generation, so every concept in the batch was lost.
The specificity mechanism invites exactly that, such as one listed source
element. A second run also lost a mechanism to the 300-second runner timeout,
because Cloudflare attempts took 120–140 s each.

**Decision.**
- **Shape-only schema.** Providers receive the schema's shape only: types,
  required fields, `additionalProperties: false`, enums, and the mechanism id
  (`concept_model_runner.provider_schema`).
- **Authoritative contract unchanged.** `response_schema` and the validator
  still apply every bound to each concept and reject only the concepts that
  break one.
- **Concept count.** The runner keeps at most the requested number of
  concepts and records how many extras it dropped.
- **Timeout.** The model-runner subprocess timeout is 900 s.

**Consequences.**
- One bad concept no longer costs the four good ones beside it.
- The validator and its fingerprint are unchanged, so already-validated
  mechanisms are not regenerated.
- If a mechanism still fails, its model-run report now carries the
  validator's per-concept errors instead of a provider's whole-batch refusal.

**Result.** On the laptop both mechanisms still failed the same way after
this change, so the policy bounds were not the cause. The real cause is not
yet known: FAIR keeps neither the refused text nor Groq's reason.
`transformation_engine/concept_diagnose.py` sends the same prompt and
provider schema straight to Groq and saves:
- the error code and message;
- the refused text (`failed_generation`);
- the finish reason and token use;
- the app's own validation of the text, including fields the schema does
  not allow (the validator ignores extra fields, but the provider schema
  forbids them).

The fix waits for that evidence. The shape-only schema stays, because one
bad concept should still not sink a batch.

## D-146 — Concept generation runs on Gemini only

**Status:** Superseded by D-147. The Gemini-only route remains available as a
manual switch, but the default is FAIR again.

**Context.** Two concept mechanisms failed on every free FAIR route. Direct
calls showed why: Groq's gpt-oss-120b returned all 5 concepts without
`human_framing` and `viewer_need_evidence`, even with Groq's strict flag,
because Groq validates after generation rather than constraining it. Until
now, direct Gemini replaced exhausted free capacity only (D-068, D-129).

**Decision.** At the human's request, concept generation uses the project's
direct Gemini key as its only route.
- `transformation_engine/concept_model_route.json` holds
  `"route": "direct_gemini"`.
- The runner calls Gemini with the provider schema (Flash-Lite, then Flash;
  structured output, then JSON-only) and never calls FAIR.
- Without a key the mechanism stops with `DIRECT_GEMINI_NOT_CONFIGURED`; it
  does not fall back.
- Setting the route to `"fair"` restores the previous behaviour.
- Every other stage keeps FAIR first, with Gemini only for exhausted
  capacity.

**Consequences.**
- Gemini's structured output constrains generation, so required sections
  should no longer be dropped. The app's validator still checks every
  concept.
- The route is outside the validation contract, so the three mechanisms
  already validated through FAIR are kept.
- Cost depends on the key's Google Cloud project: free with no billing
  enabled, billed otherwise. The app cannot tell which, so this is the
  human's to confirm.

## D-147 — Concepts are generated in small FAIR calls

**Status:** Accepted (human decision, 4 October 2026)

**Context.** The Build Roadmap and Master Product Vision §100–101 keep FAIR as
the preferred text route, with direct Gemini only for genuine quota
exhaustion, never to hide schema or prompt defects. The two failing concept
mechanisms were such a defect: asked for five full concepts in one answer,
Groq's gpt-oss-120b dropped `human_framing` and `viewer_need_evidence` from
every concept. The human chose smaller FAIR calls over the Gemini-only route
of D-146.

**Decision.**
- `concept_model_route.json` sets `"route": "fair"` and
  `"concepts_per_call": 2`.
- A mechanism's concepts are generated in calls of at most two. Each call is
  given the working titles and premises of concepts already accepted
  (`already_generated_concepts`) and asked for different ones.
- **Counting.** Only validated concepts count towards the requested number.
  One spare call covers a call that returns nothing usable. A repeated
  concept id gets a call suffix.
- **Failures.** Concepts from successful calls are kept if a later call
  fails, and the report records where it stopped.
- **The prompt.** Two rules are added: build on, but don't repeat,
  `already_generated_concepts`; include every field, including the full
  `human_framing` and `viewer_need_evidence`.
- **Already validated mechanisms are kept.** The settings live outside the
  validation contract, so mechanisms that already validated are not
  regenerated.

**Consequences.**
- A mechanism takes three or four free calls instead of one. Each answer is
  about 40% of the old size.
- The model-run report lists every call: what was asked, what came back,
  what was accepted, and the rejection reasons.
- If two concepts per call still come back incomplete, the next step is
  two-stage generation: the concept first, then its framing sections in a
  second small call.

## D-148 — Field bounds go back into the provider schema, and calls are paced

**Status:** Accepted

**Context.** The first laptop run of D-147 showed real progress. With two
concepts per call, Groq's gpt-oss-120b returned complete concepts that passed
FAIR's schema check, `human_framing` included. The app's validator then
rejected every one on bounds the D-145 provider schema had removed:
- hook level and story-curve values outside 4–10;
- a target above capacity;
- a story curve that never reaches the target;
- fewer than 3 opening moments.

Separately, each mechanism's second call came within the same minute. Groq's
free per-minute token limit refused it as `RATE_LIMITED`, and FAIR fell back
to Cloudflare models that fail the schema.

**Decision.**
- **Bounds restored.** `provider_schema` sends the full authoritative schema
  again, leaving out only the maximum number of concepts. The runner already
  keeps at most the requested number.
- **Prompt.** Rule 23 states the drama-number rules a schema cannot express:
  whole numbers 4–10, target no higher than capacity, the highest
  story-curve value reaching the target, tempo 1–10, curve lengths, and 3–5
  opening moments.
- **Pacing.** `concept_model_route.json` sets
  `pause_between_calls_seconds: 65`. Calls after a mechanism's first wait
  that long.

**Consequences.**
- A mechanism with five concepts takes about four minutes: three or four
  calls a minute apart.
- With only two concepts per call, the provider rejecting a whole answer for
  one bound loses at most two concepts. The bounds guide the model more than
  that costs.
- None of this touches the validation contract, so validated mechanisms are
  kept.

## D-149 — Concept calls are paced across mechanisms and runs

**Status:** Accepted

**Context.** With D-148 in place, `progressive_reveal` validated: two calls
each returned two accepted concepts, and the pool reached 15. `specificity`
still failed, partly on pacing:
- D-148's pause applied only between calls of the same mechanism, so
  `specificity` started straight after `progressive_reveal`'s calls;
- the automation's second round began at once;
- Groq refused both as `RATE_LIMITED`, and FAIR fell to Cloudflare models
  that fail the schema.

**Decision.**
- `pause_between_calls_seconds` is the minimum gap between any two concept
  calls. Every automatic step runs as its own process, so the time of the
  last call is kept in `transformation_engine/output/concept_call_clock.json`.
- A call that FAIR returns as escalated because Groq was rate limited waits
  the pause and is retried once. The report marks it `rate_limited_retry`.

**Consequences.**
- Free per-minute limits no longer turn into schema failures on the
  fallback models.
- Groq also refused the format of `specificity`'s first call. Which rule it
  broke is not in FAIR's report; `concept_diagnose.py --mechanism
  specificity --count 2` shows Groq's own error naming the field.

## D-150 — Missing framing sections are completed by a follow-up call

**Status:** Accepted

**Context.** After D-149 only the `specificity` mechanism was missing. The
diagnostic showed Groq's gpt-oss-120b returning two otherwise complete
specificity concepts without `human_framing` and `viewer_need_evidence`, even
at two concepts per call. Progressive reveal includes them at that size, so
splitting calls further does not fix this mechanism.

**Decision.**
- **When it runs.** A call can return concepts that lack either section. For
  those concepts, one follow-up call on the same route asks for only the
  missing sections.
- **What the follow-up asks.** It uses the same request context, lists the
  concept ids, and shows the concepts' other fields. Its schema allows only
  those ids and those two sections, with their full bounds.
- **Merging.** The answers are merged by concept id, and nothing else in a
  concept changes. Every concept is then validated as usual.
- **Rules kept.** The follow-up is paced and rate-limit-retried like any
  other call. A paid result fails closed.
- **If it fails.** The concepts stay incomplete and are rejected by the
  validator, as before.
- **Reporting.** The report records the follow-up under the call's
  `section_completion`, with its status, concept ids and provider.

**Consequences.**
- This is the two-stage generation named in D-147: free, through FAIR, and
  fixing the actual gap rather than routing around it (vision §101).
- A mechanism that needs it takes about twice as many calls.
- None of this touches the validation contract, so validated mechanisms are
  kept.

## D-151 — Concept generation switches to the direct Gemini route

**Status:** Accepted (human decision, 4 October 2026). This amends Master
Product Vision §101 for concept generation only.

**Context.** After D-147 to D-150, four of the five mechanisms validated
through FAIR and the pool reached 15. `specificity` still failed: Groq's
gpt-oss models leave out `human_framing` and `viewer_need_evidence` for this
mechanism, and Groq's own schema check then rejects the whole answer inside
FAIR. The D-150 follow-up call therefore never receives the incomplete
concepts. The human chose to bypass FAIR for concept generation.

**Decision.**
- **Route.** `concept_model_route.json` sets `"route": "direct_gemini"`. The
  project's `DIRECT_GEMINI_API_KEY` is the only route for concept
  generation, with no FAIR and no fallback.
- **Settings.** It keeps two concepts per call and the section-completion
  follow-up, and lowers the pause between calls to 10 seconds.
- **Unchanged.** Every concept still goes through `validate_response()`, and
  the settings stay outside the validation contract, so the four validated
  mechanisms are kept. Every other stage keeps FAIR first, as §100–101 say.

**Consequences.**
- §101's rule (direct Gemini only after quota exhaustion, never to hide
  defects) no longer applies to concept generation. This is a deliberate,
  recorded change, as the roadmap's versioning rule requires. The defect it
  works around (free models omitting nested sections) is documented in
  D-145 to D-150.
- Cost depends on the key's Google Cloud project: free with no billing
  enabled, billed otherwise. The app cannot tell which.
- Setting `"route": "fair"` and a 65-second pause restores the FAIR route.

## D-152 — Research searches retry a question as keywords

**Status:** Accepted

**Context.** The first research run on the laptop found pages for all three
plans. For `c_spec_tyres_04`, though, one question found nothing on any
backend:
- Exa was unavailable, because Agent Reach's `mcporter` was not on PATH;
- DuckDuckGo and Wikipedia returned no results for the full question,
  "At what exact gram threshold do most drivers begin to perceive steering
  wheel vibration at 100 km/h?".

The stage correctly stopped as PARTIAL (D-129). The workflow message,
however, said no usable source pages were found.

**Decision.**
- **Keyword retry.** When every search backend finds nothing for a research
  question, the question is retried once as keywords, with question words
  and filler removed and at most eight words kept. The evidence file
  records `query_used`.
- **Failure reporting.** If the keyword retry also fails, the error carries
  both attempts.
- **Clearer message.** When pages were found but some questions still lack a
  source, the workflow message names each such concept, its page count and
  its failed searches. It says research stops because every question must
  be covered, and points to the search-backend check.

**Consequences.**
- A PARTIAL evidence file is acquired again on the next run. Only COMPLETE
  evidence is skipped.
- Stage policy is unchanged: research still waits until every question has
  a source.

## D-153 — Research evidence: real independence, whole-word risk terms, rework searches

**Status:** Accepted

**Context.** The first Research Gate with Exa evidence showed three defects:
- **A mirrored source counted twice.** `clm_speed_threshold` was supported
  by "2 independent websites" that were one paper: Exa's library copy and
  its DOI page, with the same title and quote. Sources were counted by
  website only.
- **A false risk flag.** The same claim was flagged as elevated risk
  ("invest") because the word "investigations" begins with "invest". Risk
  terms matched any word they prefixed, so "diesel" also tripped "die".
- **A rework note searched as a question.** The human rework note "find the
  answer elsewhere or discontinue" became a research question and was
  searched on the web word for word. It also counted as a question the
  search had to answer, although the gate never requires rework
  instructions to be answered.

**Decision.**
- **Independent sources.** Supporting sources form independent works:
  links sharing a website, a title of at least four words, or the same
  quoted text count as one. Automatic clearing still needs two.
- **Risk terms.** They match whole words. A term ending in `*` matches as a
  stem (`pregnan*`), and explicit forms are listed (`legally`, `investor`
  and so on).
- **Rework searches.** For a rework question, acquisition searches the
  reworked claim's statement rather than the note's text. Rework questions
  no longer count towards the questions acquisition must cover.

**Consequences.**
- Automatic decisions are recomputed on every Research Gate prepare. A
  claim that cleared only on a mirrored source returns to human review;
  one flagged only by a false risk match may now clear.
- Human decisions are never replaced.

## D-154 — A stuck automatic step no longer holds back later allowed steps

**Context.** With three accepted concepts, research for two still had
unanswered questions while "The 4-Gram Wheel Balance Margin" had verified
research and a story plan. Continue Automatically ran research acquisition
first (it comes earlier in the pipeline order), got a partial result with no
progress, and stopped. The 4-Gram script was never drafted, although D-104
lets each concept move on as soon as its own research is verified.

**Decision.** When a step returns partial without progress, Continue
Automatically sets it aside for the rest of that run and goes on with the
next step that is already allowed. Readiness rules decide what is allowed,
so nothing runs early. The run still ends PARTIAL, names the stuck step and
its message, and says where the other work stopped. A later step that fails
stays the headline failure, with the stuck step listed.

**Consequences.** One concept's missing sources no longer stall the
others. Each run retries the stuck step first, as before.

## D-155 — A live run banner shows that a job is working

**Context.** Continue Automatically can run for many minutes, and a single
model or web call can take up to 15 minutes. The top-right job button showed
only "RUNNING" and the job name, so a long call looked like a frozen screen.

**Decision.** While a job runs, a banner is shown under the page header on
every page. It names the current automatic step (read from the job log's
"AUTOMATIC MACHINE STEP" lines) and the step number. A clock ticks every
second, a moving bar runs across the banner, and the latest log line is
shown. If the log has not changed for two minutes, the banner turns amber and
says the job is still working and how long it has been quiet. The job button
shows the same step and clock. The status payload carries this as
`job.progress` (`current_step`, `step_number`, `last_line`, `last_output_at`).

**Consequences.** Only the log tail is read on each status poll, so a very
long run may show a lower step number; the step name stays correct.

## D-156 — Gate policy: clean items at six gates are decided automatically

**Context.** A video stopped at about 17 human gates. The operator chose to
keep six decisions: Pick (opportunity and concepts), Script, Packaging
(title and thumbnail), Budget, Final cut and Publish. Every other gate is to
be decided automatically when its checks pass, with anything flagged still
coming to a person. This is Phase A; the visual gates, a single Budget
approval and the merged review screens follow.

**Decision.** `experiment_ui/gate_policy.json` sets each gate to `HUMAN` or
`AUTO_IF_CLEAN`. When Continue Automatically stops at an `AUTO_IF_CLEAN`
gate, `gate_autopilot.py` decides, through the same functions the review
pages call, every pending item that passes the gate's checks, and the run
continues. The checks are:

- **Vision:** a machine observation exists, with HIGH or MODERATE
  confidence and no uncertainty noted.
- **Analysis:** confidence is not LOW and every evidence reference resolves.
- **Title Direction:** for each format, the first title in the configured
  angle order that fits the length contract and cites evidence. The final
  title is still chosen with the thumbnail at the Final Packaging Gate.
- **Format:** no source overlap, and the Short and Long-form branches are
  separate.
- **Voice Performance:** the spec reached the gate, which means it passed
  deterministic validation.
- **Narration Preview:** the audio is rendered and the engagement check
  passed with no warnings.

An item that fails a check, or whose decision the gate refuses, stays
pending. The run then stops at that gate as before, and its message lists
each held item and why.

**Consequences.**
- Automatic decisions are made as reviewer `gate-policy-auto`, with a note
  beginning "Automatic (gate policy D-156)" where the gate keeps notes.
  Vision frame decisions have no note field and are identified only by the
  reviewer.
- A person can still change any automatic decision from the review page,
  as with their own.
- Research is unchanged: D-153 already clears claims backed by two
  independent sources, and the rest come to a person.
- Setting a gate to `HUMAN`, or deleting the policy file, restores the
  previous behaviour.

## D-157 — Fresh start from the Opportunity stage archives, never deletes

**Context.** The operator wanted to drop the current productions and choose
new subjects at the Opportunity stage, without losing discovery and radar
history.

**Decision.** `scripts/fresh_start.py` moves into
`.archive/fresh_start_<time>/`:
- the Opportunity Gate's choice (the decision, the approved study set and
  the active study source);
- every output after it: Experiment 02 output and evidence, and the outputs
  of the transformation, research, packaging, story/script, format and
  production engines.

It keeps discovery and radar data, the opportunity inbox (saved, rejected
and watched items stay as they are), saved ideas, job logs, and all code and
configuration. Without `--yes` it only lists what would move. It refuses
while the UI is running on its port.

**Consequences.**
- Approved opportunities return to "needs review".
- The next Continue Automatically starts after a new Opportunity Gate
  decision.
- To undo, move the archived folders back.

## D-158 — Gate policy Phase B: visual gates and spend under the confirmed budget

**Context.** The operator confirmed the per-video budget: a $5 target and a
$10 ceiling. Phase B of D-156 applies the gate policy to the visual and
spend gates.

**Decision.**
- **Budget.** `video_budget_config.json` is marked `confirmed_by_human`.
- **Gates now `AUTO_IF_CLEAN`, and their checks:**
  - **Visual Plan:** the plan builds, every shot is timed, and the video is
    not over its target.
  - **Visual Candidates:** each shot gets the first `ELIGIBLE` candidate.
    Results are sorted best first, and only verified-licence footage is
    `ELIGIBLE`. A shot with nothing usable is marked as a gap. A shot whose
    only finds are editorial or unverified footage is held for a person.
    Stale search results are held.
  - **Rough Cut:** approve with gaps. This authorizes no spend; the gaps go
    on to gap planning.
  - **Edit Preview:** approve when the preview video exists. The note gives
    the number of placeholder segments. The finished video is still reviewed
    at the Final Export Gate.
  - **Final Audio:** approve, because only videos whose audio QC passed are
    listed.
  - **Narration Spend:** approve, with every criterion recorded, only when
    all of these hold:
    - the provider contract is verified;
    - a voice id and licence reference are set;
    - the visual plan is approved;
    - the worst-case cost keeps the video's committed spend at or under the
      $5 target.
  - **Visual Spend:** authorize a shot only when the active image provider
    is verified and priced, with cost = price × variants, and only if that
    cost keeps the video at or under the target.
- **Spend above the target, an unknown price, or an unconfirmed budget is
  held for a person.** Nothing can be authorized above the ceiling, which
  `video_budget.reserve` enforces as before.
- **Visual Rights stays human.** Licensed footage is already approved
  automatically before that gate, so only editorial footage reaches it, and
  editorial footage is never approved automatically.

**Consequences.**
- No narration provider, voice licence or image provider is configured yet,
  so both spend gates hold every item, with that reason, until they are.
- `human_authorization_required` in the visual spend config stays true: the
  operator's budget confirmation and this policy are that authorization, and
  each decision is still recorded.
- One combined Budget screen per video and the merged review screens follow
  as Phase C.

## D-159 — Gate policy Phase C: the review pages are organised by who decides

**Context.** After D-156 and D-158 most gates decide themselves, but the
Gate Reviews, Packaging and Produce pages still showed every gate as an
equal tab, so the operator could not see at a glance which decisions were
theirs. The two spend gates were also on separate tabs although they are one
question: what this video may cost.

**Decision.**
- **Grouped tab strips.** Each page's strip has a **Your decisions** group
  first (Gate Reviews: Concept, Research, Script; Packaging: Final package;
  Produce: Budget, Footage rights, Final export, Publish), then a **Held by
  gate policy** group whose tabs appear only while that gate holds an item
  for a person, is open, or "Include decided items and empty gates" is
  ticked. Produce adds a **Tools** group (Generate visuals, Tesseract) and
  Packaging a reference group for what the automatic steps made.
- **Budget tab.** Narration spend and visual spend items are listed together
  per video, each with the video's committed spend against its target and
  ceiling. The decisions, requests, checks and locks are the existing ones;
  `/produce#narration` and `/produce#spend` open Budget.
- **Defaults.** Gate Reviews opens on Concept, Packaging on Final package and
  Produce on Budget. The Command Center's production card and the workflow
  links point at the same tabs.

**Consequences.**
- The six decisions the operator chose to keep are the first thing on each
  page; the automatic gates stay reachable and still show what they held.
- The script-gate and research-gate screens are unchanged: a concept's
  research is decided before its script exists (D-104), so research flags
  cannot sit inside the Script Gate.

## D-160 — Audit 2026-10-04: request hardening, spend accounting, decision integrity

**Context.** A structured adversarial audit (static checks, dependency and
security scans, live request fuzzing, five targeted reviews and a
reproduction of each serious finding) of the build at D-159.

**Decision.** The confirmed defects are fixed in one change:

- **Requests.** A POST with a bad or oversized `Content-Length`, invalid
  UTF-8, a non-object JSON value or deeply nested JSON used to crash the
  handler thread; a body shorter than its length held the thread forever.
  Bodies are capped (4 MB), parsed defensively (400/413), and the handler
  has a 60-second socket timeout.
- **Narration spend.** The provider's reported cost is validated as money
  (bool and NaN no longer pass), the approved worst case is checked before
  every segment call, and if the rendered audio cannot be registered the
  spend is still recorded and the audio kept. Narration spend decisions are
  serialised per video. A torn budget-ledger line now blocks reservations
  instead of silently loosening the ceiling.
- **Decision integrity.** A claim a person sent back for REWORK is no longer
  re-accepted by the evidence policy when the regenerated claim comes back
  unchanged. Vision and analysis decisions record the reviewer and
  `decided_by` per decision; the gate policy sets `YOUTUBE_DECIDED_BY=GATE_POLICY`
  while it decides, so automatic decisions are never logged as HUMAN.
- **State on polls.** The rights and visual-spend snapshots no longer delete
  stale review files during a status poll; stale files are ignored
  (`stale_ignored`) and inert. This removes a window in which a running
  job's rewrite of an upstream file erased human decisions.
- **Jobs.** Stop ends the job's whole process tree; the UI stops a running
  job on exit; a job is finalised once even when two polls see it end; the
  history log is append-only; the live log is read as a tail. The page
  never overlaps its own status polls.
- **Providers.** A Gemini HTTP 429 counts as rate limiting on the direct
  route, and a batch stops once the quota is exhausted. The direct page
  reader refuses loopback, private and link-local hosts before and after
  redirects, caps page size at 5 MB and redirects at 5. Provider JSON must
  be an object. `SAFETY_STOP` is reported as such, not as PARTIAL.

**Consequences.** Findings not fixed here, recorded for the operator:
- The direct-Gemini route asserts "free tier" from configuration alone;
  nothing verifies the key's project has no billing.
- A YouTube upload whose final response is lost can leave an unrecorded
  (private) video; a retry would upload it again.
- A job orphaned by a UI crash (not a normal exit) is not re-adopted on
  restart.
- Thumbnail and visual generation treat a failure after dispatch as $0
  spent; narration already records partial spend.
- The gate policy only runs inside an automatic run; at a held gate with no
  machine step ready, Continue Automatically stays disabled.

## D-161 — Direct Gemini runs only on a dated billing attestation

**Context.** The direct Gemini route (D-151) is free only while the Google
Cloud project behind `DIRECT_GEMINI_API_KEY` has no billing account. The
code recorded that belief as a constant (`direct_backup_free_tier_only:
true`, `paid_inference_executed: null`) and the cost check accepted it. The
audit (D-160) flagged this: unknown cost was treated as zero.

**Decision.** `experiment_02_analysis/direct_gemini_billing.json` holds the
operator's attestation: `billing_disabled_confirmed` and `confirmed_on`.
While it is false, no direct Gemini call is made anywhere: concept
generation on the `direct_gemini` route and the FAIR exhaustion fallback
both return `DIRECT_GEMINI_BILLING_UNCONFIRMED` without an HTTP request, and
Continue Automatically's message says exactly what to check and set. When
it is true, a direct call records `paid_inference_executed: false` and the
attestation date.

**Consequences.** The file ships as `false`: the operator checks Billing
for that project in Google Cloud Console, then sets it to true with the
date. If billing is ever attached to the project, set it back to false.

## D-162 — Viral Radar shortlist: lane, minimum outlier, freshness, replication first

**Context.** The first full radar scan tracked 136 videos. Most were off the
channel's lane (finance, fitness, history-for-sleep, game simulators) or
below a ratio worth reading, and the page listed them all.

**Decision.**
- **Lane.** `opportunity_engine/radar_lane.py` sorts each tracked video
  into ON_LANE, UNCLEAR, OFF_LANE or OTHER_LANGUAGE from its title and
  channel, using the word lists in `radar_lane_config.json` (an off-lane
  term wins; a `*` term matches as a stem; a title that is mostly non-Latin
  is another language). A theme takes the best lane of its members. No
  model call; the operator edits the lists.
- **Filters on the page.** Lane (my lane = on lane + unclear, or
  everything), minimum outlier (any, 3×, 5×, 10×), freshness (any, ≤ 7
  days, ≤ 3 days) and format. Default: my lane, ≥ 3×. The choice is kept in
  the browser; the bar says how many items it hides and offers a reset.
  Watched videos always show.
- **Replication first.** Themes with two or more independent channels are
  pinned above the rest regardless of ratio.

**Consequences.** Lane is a reading aid, not a gate: an off-lane video can
still be reviewed by switching to "Everything". Wrong lane calls are fixed
by editing the word lists.

## D-163 — One Continue per production, and research that cannot dead-end on a question

**Context.** Continue Automatically was one global button whose result
landed in a job log; a production that was not moving showed "Ready to
run" with no reason on its row. At the Research Gate, a concept whose
claims were all accepted still could not go to the script when one of its
original questions had no accepted claim, and the only way out was a
Waive button the operator had to find.

**Decision.**
- **Per-production status and Continue.** `workflow_automation` writes its
  outcome to `.experiment_ui/last_auto_run.json` (status, message, the
  step that was stuck or failed and its message, held gate items). The
  productions model maps each automatic step to a stage by its action id
  prefix and gives every READY production a `blocker` line: what stopped
  the last run at its stage. The Productions rows and the Production
  Workspace show that line and carry their own Continue, which starts
  the same automatic runner (the pipeline is one; the row is where the
  result is read). While a job runs the button says Running.
- **A decided concept says why it is not ready.** `question_coverage`
  rows now carry `pending_claims`, `accepted_claims`, `ready` and a plain
  `summary` ("2 claims to decide", "Not ready for the script: 1 question
  unanswered. Mark it Not needed for script, or Rework a claim…", "Ready
  for the script. 1 question was waived."). A production whose claims
  are all decided but whose verified package is RESEARCH_INCOMPLETE is
  "Needs your review" with that summary, no longer "Ready to run".
- **Automatic waivers.** On every prepare the Research Gate waives an
  original question automatically, with a note and a history event
  (`decided_by: EVIDENCE_POLICY`), when the acquisition gave it up or no
  claim in the draft refers to it. A human waiver is never replaced; a
  person can remove an automatic waiver (recorded in
  `unwaived_questions`) and it does not come back; the script may not
  state anything about a waived question, as before. Off switch:
  `auto_waive_questions.enabled` in `research_gate_config.json`.
- **Acquisition gives a question up after N rounds.** The evidence file
  counts `search_rounds` per question across runs of the same plan. A
  question still without a page after
  `max_search_rounds_per_question` (default 2, `research_acquisition_config.json`)
  is listed in `unsourced_question_ids` and no longer blocks COMPLETE
  evidence; its search errors stop counting against the run.

**Consequences.** A concept with one unanswerable question reaches the
script after at most two acquisition rounds without a person waiving
anything; the gate line and the production row say what was waived. A
question a claim does refer to but no claim answers (the claim was
rejected or reworked) stays with the person, and the row says so. The
research summary in the Command Center and the Review Queue reads the
same text.

## D-164 — One Review Queue of every pending item, with the gate as a label

**Context.** The decisions waiting on the operator were spread over about
twenty tabs on three pages (Gate reviews, Packaging, Produce), grouped in
D-159 but still tabs. The Review Queue listed productions and gate counts,
not the items.

**Decision.** Each gate page module exposes `queueItems()`: every pending
item it would render, with its gate label, its group (yours / held by
policy), a title, the concept it belongs to, and the deep link that opens
that item on its page. The Command Center's `reviewQueue()` merges them
into one list: your own decisions first, then a production that waits on
you without a gate item (research decided but not ready, a blocked
concept), then the ideas inbox, then what the gate policy held. Within a
group the order is the pipeline order, because an upstream decision
unblocks the most. The Review Queue nav item carries the count. Script
branches are listed whole; their sections load on the Script page. A page
that cannot list yet (its data not loaded) leaves the queue to the others.
The tabs stay as the place where a decision is made; the queue is the one
place to see what is waiting.

**Consequences.** "What do I have to decide?" has one answer. Items have no
timestamp of their own, so the order is pipeline order, not newest first;
a per-item "waiting since" needs the gates to record it and is not done
here.

## D-165 — The radar learns what the operator picks

**Context.** The lane filter (D-162) is a word list the operator edits. The
operator's own Approve, Watch, Save and Reject decisions on radar
candidates are labels of the same thing and were unused.

**Decision.** `opportunity_engine/radar_learning.py` builds a log-odds word
model from the inbox decisions on radar packets: tokens are the title's
words (how, why and what kept: for an explainer channel they are the
signal) plus one token for the channel; a picked candidate (SAVED,
APPROVED, WATCHING, or an APPROVE/SAVE/WATCH in its history) counts for,
a REJECTED one against. Each tracked video gets a `taste` score in -1..1
and a label (LIKELY / UNSURE / UNLIKELY); a theme takes its best member's.
The model stays inactive until 20 decisions with at least 5 on each side;
until then the radar page says how many it has. When active the page
offers an Order pill ("Strongest outlier" / "What I pick"), shows the
label beside each video, and names the strongest words for and against.
Nothing is hidden by the score: it orders, the filters decide what shows.
Replicated themes stay pinned first.

**Consequences.** After a few dozen decisions the list reads in the
operator's taste without editing word lists. The model is recomputed from
the files on every overview, so a changed decision changes the ranking at
once. It is a ranking aid, not a gate, and the lane word lists remain.

## D-166 — Unconfirmed spend: a failed image call keeps its money committed until you settle it

**Context.** The audit (2026-10-04, N-3) found that thumbnail and premium
visual generation treated any failed provider call as costing nothing:
the thumbnail path released its reservation, the visual path had none. A
timeout or a 5xx after the request was sent may still have billed, and
nothing in the app let the operator correct the ledger afterwards.

**Decision.**
- **A new ledger event, UNCONFIRMED.** It keeps the estimated amount
  committed (counted like a reservation) and marks the item as needing a
  person. `video_budget.outcome_unknown(exc)` decides: an HTTP 4xx answer
  means the provider refused before doing work, so the reservation is
  released; anything else (timeout, lost connection, 5xx, a bad answer
  after the call) is marked unconfirmed with the error in the note. Both
  image paths use it; narration already records partial spend.
- **Reconcile.** `video_budget.reconcile(video, category, ref, total_usd)`
  records what the item really cost (0 for nothing) and releases what was
  held, so nothing stays committed by guess. It works on any ledger item,
  not only an unconfirmed one, so an invoice can correct a recorded cost.
- **Budget tab.** Unconfirmed calls appear first on the Budget tab as
  "Confirm spend" items with the error, the held amount, a cost field and
  two choices: "It cost this much" and "It cost nothing". The per-video
  budget list counts unconfirmed calls. Route: `/api/budget-reconcile`.

**Consequences.** The ceiling is trustworthy again: money that may be gone
is counted until a person says otherwise, and a wrong guess is corrected
on the same tab. The provider's usage page remains the source of truth
for the amount; the app records the operator's answer with a note.

## D-167 — The YouTube upload resumes instead of uploading twice

**Context.** The audit (N-2) found the YouTube upload not resumable: a
timeout after the video bytes were sent could leave a private, unrecorded
video on the channel, and a retry would upload it again.

**Decision.** The session URI YouTube returns is saved to
`production_engine/output/pending_uploads/<key>.pending_upload.json`
(with the file size and the approved video hash) before any byte is sent.
A retry first asks the saved session what it holds
(`PUT` with `Content-Range: bytes */size`): a finished session answers
with the video id, which is recorded without sending anything; a 308 with
a `Range` header is continued from the next byte with a proper
`Content-Range`; a 400/404/410 means the session is dead, the record is
discarded and one new upload starts. A record for other bytes (the video
was re-rendered) is discarded. The record is removed when the id is
recorded. The Publish tab shows an interrupted upload and the button reads
"Resume upload to YouTube". The publish record carries `resumed`.

**Consequences.** One approved video never becomes two private videos. A
retry after any network failure is safe to click. The pending record is
plain JSON the operator can delete to force a fresh upload.

## D-168 — The free local Kokoro voice ships the narration

**Context.** Paid narration had waited on a provider decision since D-061:
the Higgsfield contract was unverified by design, so every live run
stopped at "provider setup required". Meanwhile the free preview (Kokoro,
D-128) was already producing the narration the operator listened to and
approved. No full video had gone end to end.

**Decision.** The local renderer becomes a first-class narration provider.
- `narration_dispatch` gains a `LOCAL_KOKORO` adapter: the same engine,
  voice and delivery handling as the preview, rendering each segment to
  WAV at $0 with no network call. `provider_status` asks a local provider
  for no API key or endpoint; it asks that Kokoro be installed and treats
  a missing price as 0.
- `narration_render.provider_contract_verified` accepts a local contract
  without an endpoint (the documented model licence and voice list are the
  contract). `prepare()` writes the $0 provider quote itself, bound to the
  request hash like any quote, and refreshes it when the request changes;
  the spend gate's "quote is current" rule therefore still holds and the
  gate policy can accept a $0 worst case.
- The shipped configuration is now the local voice: provider
  `kokoro_local`, model `hexgrad/Kokoro-82M` (Apache-2.0 weights), voice
  `af_heart`, price 0, and a matching `voice_identity` with a licence
  reference. The previous Higgsfield block is kept under
  `paid_provider_example` in `narration_render_config.json` for switching
  back; the paid path is unchanged.

**Consequences.** A video can go from script to final render with no paid
narration call and no provider decision; the first full video is the
test of whether the voice is good enough to ship. Every gate stays: the
preview is approved by a person, the spend gate still runs (at $0), Audio
QC and the Final Audio Gate are unchanged. Changing `voice_performance_config`
changes its validation contract hash, so specs approved before this
change are stale and regenerate.

## D-169 — A doctor page, and a job orphaned by a crash is settled at startup

**Context.** An hour of the 2026-10-04 session went into things a single
check would have shown: a 38-character API key, an environment the UI did
not inherit, a search backend not on PATH. System Health only said whether
a key was set. And after a crash or a closed launcher window the saved
job state said RUNNING forever while the child kept writing artifacts.

**Decision.**
- **Doctor.** `experiment_ui/doctor.py` runs twelve checks on one click
  from the Tools page (`POST /api/doctor`): the YouTube key with one real
  Data API call (1 quota unit), the direct Gemini key and its billing
  flag, FFmpeg, FFprobe and yt-dlp versions, the search backends (mcporter
  for Exa, curl for DuckDuckGo and Wikipedia, agent-reach doctor if
  installed), Kokoro with espeak-ng, the narration provider, the image
  providers, the upload OAuth values and free disk. Each check runs on its
  own with a time limit and reports its own failure; secrets are never
  shown. The report is saved to `.experiment_ui/doctor.json` and shown
  with timings.
- **Orphaned jobs.** `JobManager.recover()` runs when the UI starts. If
  `job_state.json` says RUNNING and the process is still alive, the
  process tree is stopped and the job recorded ORPHANED; if it is gone,
  INTERRUPTED. Both land in the job history and the job drawer with a
  note, instead of a run that never ends.

**Consequences.** "Why does nothing work?" has a ten-second answer. A
restarted UI never runs beside a ghost of its last job.

## D-170 — Fewer, better words: status codes become sentences, themes become questions

**Context.** The pages leaked internals: gate panels said "Gate status:
waiting for draft research packages", and radar themes were keyword stems
("bullet bulletproof glas material").

**Decision.**
- **One translation table.** `experiment_ui/plain_language.py` holds a
  written sentence for every status code a page shows and builds one by
  shape for any other (WAITING_FOR_X, READY_FOR_X, HUMAN_X_GATE,
  X_REWORK_REQUIRED, NO_X, SKIPPED_X …), so a new code never appears raw.
  A test runs every code the engines emit through it. The catalogue is
  served once per page load (`/api/plain-language`) and `YP.plain(code)`
  applies it; the same shape rules exist in app.js for a code the
  catalogue does not carry. The gate pages, Packaging, Produce, the radar
  and the research coverage line use it where they showed codes.
- **Theme headline.** The radar theme reads as the strongest on-lane
  member's title, trimmed of bracketed tags, hashtags and "| Channel"
  suffixes (`theme_headline`), with the stem label shown under it as
  "Shared words". No model call: a creator's title already states the
  viewer's question better than a stem list does.

**Consequences.** The app reads like a tool. Codes stay in the files and
the API, where they are stable identifiers; only the words on the page
changed. Adding a code to a gate means adding a sentence to one file, and
the test says so when it is missing.
