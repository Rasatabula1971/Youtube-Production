# YouTube Production

Research-driven system for discovering proven audience demand, understanding why successful videos work, transforming those mechanisms into genuinely new content, producing videos, and learning from published performance.

## Core principle

**Copy the demonstrated demand, not the video.**

The project separates two problems:

- **Opportunity Engine** — determines what may be worth making.
- **Retention Engine** — determines how the opportunity should be presented.

A transformation layer connects those engines to research, scripting, format selection, production, quality control, and learning.

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
