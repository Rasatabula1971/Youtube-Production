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

**Milestone M1 — Prove the Opportunity Engine / prepare the Experiment 02 handoff**

The repository now contains Experiments 01.2 through 01.5 plus the offline
Experiment 02 why-it-worked analysis framework.

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
- Topic-level evidence by format

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
└── transformation_engine/
    ├── transformation_engine.py
    ├── concept_gate.py
    └── transformation_config.json
```

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

Experiment 02 is offline-first. It prepares evidence profiles from the
Experiment 01.5 study set, validates creative findings against typed source
evidence, separates findings from hypotheses, and aggregates repeated
mechanisms across independent videos/channels.

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
folder access.

See `experiment_ui/README.md`.


## Transformation Engine

The repository now includes the offline Transformation Engine framework and
human Concept Gate.

The engine consumes human-confirmed Experiment 02 mechanism handoffs, prepares
structured concept-generation requests, validates Source Dependency Test
requirements, and sends only human-accepted concepts into a Research Engine
handoff.

No concept score or automatic winner is produced.

See `transformation_engine/TRANSFORMATION_ENGINE.md` and
`transformation_engine/CONCEPT_GATE.md`.
