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

