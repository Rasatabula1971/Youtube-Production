# YouTube Production

Research-driven system for discovering proven audience demand, understanding why successful videos work, transforming those mechanisms into genuinely new content, producing videos, and learning from published performance.

## Core principle

**Copy the demonstrated demand, not the video.**

The project separates three early questions:

- **Opportunity Engine** — what may be worth making?
- **Packaging Engine** — will the intended viewer choose it?
- **Retention Engine** — will the viewer keep watching and receive the promised payoff?

Transformation, research/story/script, format selection, production, quality control, and learning follow from those decisions.

## Current status

**Milestone M1 — Prove the Opportunity Engine**

M1 is **not yet formally closed**. The Opportunity Engine has now produced a
real 01.3 → 01.4 → 01.5 handoff, but the multi-niche success criteria in
PROJECT.md have not yet all been demonstrated on live data.

Later-stage Transformation, Packaging, Research and Experiment 02 components
have been implemented ahead as offline frameworks. Their presence in the repo
does not mean those milestones are complete or that M1 has been bypassed.

The experiment collects independent signals rather than calculating a final opportunity score:

- Demand
- Channel-relative breakout
- Momentum proxy
- Baseline quality
- Format candidate
- Search provenance
- Relevance quality
- Outlier reliability
- Theme labels
- Query competition profiles
- Repeated-snapshot velocity
- Topic-level evidence by niche and format

Current thresholds are research hypotheses, not frozen production rules.

## Planned system

```text
Opportunity
    ↓
Transformation / original concept
    ↓
Packaging → choose to watch
    ↓
Retention → keep watching
    ↓
Satisfaction → deliver the promise
    ↓
Learning
    ↺
```

## Repository

```text
.
├── README.md
├── PROJECT.md
├── DECISIONS.md
├── experiment_01_discovery/
│   ├── experiment_01_3.py
│   ├── experiment_01_4.py
│   ├── experiment_01_5.py
│   ├── niches.json
│   └── youtube_discovery.py
├── experiment_02_analysis/
│   ├── experiment_02.py
│   ├── experiment_02_config.json
│   └── profile_template.json
├── transformation_engine/
│   ├── transformation_engine.py
│   ├── concept_gate.py
│   └── transformation_config.json
├── research_engine/
│   ├── research_engine.py
│   ├── research_gate.py
│   └── research_config.json
├── packaging_engine/
│   ├── packaging_engine.py
│   └── packaging_gate.py
├── format_engine/
│   ├── format_engine.py
│   ├── format_review.py
│   └── format_config.json
└── source_acquisition/
    ├── agent_reach_adapter.py
    └── youtube_discovery_benchmark.py
```

## Runtime requirements

The project-owned Python code is intentionally **standard-library only**; there
is no root Python package manifest because the repository itself has no
third-party Python package dependency. External tools such as yt-dlp / Agent
Reach and the separate FAIR repository are invoked as external executables or
subprocesses rather than imported as project dependencies.

Copy `.env.example` to `.env` and add only the local values you need.
The FAIR subprocess coupling and override variables are documented in
`experiment_02_analysis/ANALYSIS_MODEL_RUNNER.md`.

Generated experiment output and secrets remain outside Git:

- `.env`
- `experiment_01_discovery/output/`
- `experiment_02_analysis/output/`

See [PROJECT.md](PROJECT.md) for the system roadmap and [DECISIONS.md](DECISIONS.md) for the decision record.


## Experiment 01.2

The first automotive live run proved collection worked but also exposed search contamination from gaming, RC and adjacent entertainment. Experiment 01.2 therefore annotates relevance and evidence reliability without deleting raw rows or changing raw metrics.

See `experiment_01_discovery/EXPERIMENT_01_2.md`.


### Research intelligence

Experiment 01.2 now produces transparent query competition profiles, persistent view snapshots for measured velocity, and topic-level evidence split by Shorts/long-form. These features are evidence layers only; they do not create a final opportunity or keyword score.


## Experiment 02 framework

Experiment 02 is offline-first. It prepares evidence profiles only from the
human-approved Experiment 01.5 study set, validates creative findings against
typed source evidence, separates findings from hypotheses, and aggregates
repeated mechanisms across independent videos/channels.

It does not fetch transcripts or videos automatically and does not spend
YouTube API quota.

See `experiment_02_analysis/EXPERIMENT_02.md`.


## Experiment Control UI

The experiment phase now includes a local browser control panel so routine runs
do not require PowerShell commands.

On Windows, double-click:

`Start Experiment UI.bat`

The UI opens on localhost and provides gated controls for Experiment 01.3,
01.4, 01.5 and the built Experiment 02 workflow, with live job logs and output
folder access. On Windows it can also install/remove a self-limiting scheduled
01.3 frozen-cohort refresh so velocity sampling does not depend on remembering
to click Refresh manually.

See `experiment_ui/README.md`.


## Transformation Engine

The repository now includes the offline Transformation Engine framework and
human Concept Gate.

The engine consumes human-confirmed Experiment 02 mechanism handoffs, prepares
structured concept-generation requests, validates Source Dependency Test
requirements, and sends only human-accepted concepts into a Research Engine
handoff.

Concepts now also define the specific viewer problem, viewer moment, desired
outcome, content-gap evidence state, channel fit, and a three-title clarity
test before the Concept Gate.

No concept score or automatic winner is produced.

See `transformation_engine/TRANSFORMATION_ENGINE.md` and
`transformation_engine/CONCEPT_GATE.md`.


## Research Engine

The repository now includes the offline Research Engine framework and human
Research Gate.

Accepted concepts are converted into research plans with stable question IDs.
Structured source/claim evidence preserves support, contradiction and
qualification without automatically labeling claims true.

Only human-accepted claims can enter a verified research package. The package
stays RESEARCH_INCOMPLETE until every original research question is covered by
an accepted claim.

See `research_engine/RESEARCH_ENGINE.md` and
`research_engine/RESEARCH_GATE.md`.


## Packaging Engine

The repository now includes the Packaging Engine and human Packaging Gate.

A human-accepted concept is converted into multiple title / thumbnail /
opening-frame package candidates. One package may be approved per concept.

The approved package defines the promise the future Story / Script Engine must
fulfill. It carries the accepted viewer problem/moment/outcome and an explicit
one-sentence promise, while preserving content-gap and channel-fit context. Its
research dependencies are injected into the Research Engine as mandatory
research questions.

No package score, CTR prediction or automatic winner is produced.

See `packaging_engine/PACKAGING_ENGINE.md` and
`packaging_engine/PACKAGING_GATE.md`.


## Format Engine

The repository now includes the Format Engine and human Format Gate.

A Script Gate approved script is converted into one production plan per required
branch. The approved concept `format_intent` decides which branches are required:
`long_form`, `short`, or both when the intent is `either`.

Long-form and Shorts share source understanding, research, accepted facts and the
master story package, but they are planned as separate productions. Plans that are
identical across branches, or that differ only by truncating one timeline, fail
deterministic validation before a human ever sees them.

Every beat carrying factual material cites human-accepted research claims and traces
back to the approved script sections it is built from.

No format score, predicted retention or automatic branch winner is produced.

See `format_engine/FORMAT_ENGINE.md` and `format_engine/FORMAT_GATE.md`.


## Source Acquisition / Agent Reach

Agent Reach is integrated only as an external acquisition and backend-health
layer.

The first use is a YouTube discovery benchmark. Agent Reach reports whether
YouTube is healthy and which backend is active; the project then calls yt-dlp
directly for quota-free search and compares those video IDs with the saved
Experiment 01.3 YouTube API search audit.

The benchmark does not modify the 01.3 cohort and does not replace official API
measurement.

The Experiment Control UI includes Agent Reach Doctor and YouTube Discovery
Benchmark actions when the external dependency is available.

See source_acquisition/README.md.


## Viewer Need Framing

The project now separates a broad topic from the specific viewer need it serves.

Transformation and Packaging preserve:

- viewer problem;
- viewer moment;
- desired outcome;
- content-gap evidence status;
- channel fit;
- three-title idea-clarity test;
- approved one-sentence promise.

See `transformation_engine/VIEWER_NEED_FRAMING.md`.
