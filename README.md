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

Current experiment: **Stage 2 / Experiment 01.1 — Proven YouTube Content Discovery**

The experiment collects independent signals rather than calculating a final opportunity score:

- Demand
- Channel-relative breakout
- Momentum proxy
- Baseline quality
- Format candidate

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
└── experiment_01_discovery/
    ├── niches.json
    └── youtube_discovery.py
```

Generated experiment output and secrets remain outside Git:

- `.env`
- `experiment_01_discovery/output/`

See [PROJECT.md](PROJECT.md) for the system roadmap and [DECISIONS.md](DECISIONS.md) for the decision record.
