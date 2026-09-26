# Experiment 01.2 — Relevance & Evidence Quality

## Purpose

Experiment 01.1 proved that YouTube search can surface high-demand videos and that channel-relative breakout can be measured. The first automotive run also exposed search contamination: high-view gaming, RC and adjacent entertainment can enter an engineering query.

Experiment 01.2 adds auditable annotations without changing the raw measurements.

## New evidence fields

### Search provenance

- `matched_queries` — every configured query that returned the video
- `best_search_rank` — best position where the video appeared
- `query_matches` — niche/query/rank records

### Relevance

- `ON_INTENT` — title contains a configured strong technical/mechanical signal
- `ADJACENT` — title contains motorsport/F1 context but not a strong technical signal
- `OFF_INTENT` — explicit exclusion signal or no configured niche signal
- `UNREVIEWED` — niche has no intent profile yet

Every label includes `relevance_reason` and `relevance_matches`.

OFF_INTENT rows remain in the dataset. This preserves evidence about search contamination.

### Outlier reliability

- `TRUSTED` — strong baseline sample, no baseline warning, and ratio is not extreme
- `CAUTION` — weak/warned baseline or an extreme ratio that deserves manual inspection
- `UNAVAILABLE` — no defensible baseline/outlier ratio

The raw `outlier_ratio` is never changed.

### Themes

The automotive profile currently tags repeatable mechanisms such as:

- hidden mechanisms
- engineering extremes
- rules / loopholes
- comparisons
- failure / safety
- engineering constraints

Themes are multi-label research annotations, not a score.

## Automotive profile

The first profile lives in `niches.json`. It is intentionally conservative.

Examples from the first live dataset:

- GTA/gameplay/RC/toy signals → OFF_INTENT
- gearbox/brakes/engine/steering/aero/etc. → ON_INTENT
- F1/motorsport/racing context without a technical signal → ADJACENT

The profile should be revised only from observed false positives/false negatives.

## Run

From the repository root in PowerShell:

```powershell
python .\experiment_01_discovery\youtube_discovery.py --max-searches 3
```

The existing files are regenerated:

- `output/raw_results.json`
- `output/candidates.csv`
- `output/summary.json`

They now include Experiment 01.2 annotations.

## Decision gate

Do not expand to all 30 searches until the same three automotive queries are rerun and reviewed.

We want to know:

1. Are obvious gaming/RC false positives marked OFF_INTENT?
2. Are technical engineering videos marked ON_INTENT?
3. Are general F1/racing videos mostly ADJACENT?
4. Do CAUTION flags catch weak or extreme outlier evidence?
5. Are the theme labels useful enough to identify repeated opportunity patterns?

No final opportunity score is introduced in Experiment 01.2.


## Market-intelligence additions

Experiment 01.2 now also borrows three transparent research ideas common to mature YouTube research tools without copying proprietary scores.

### Query competition profile

Each executed query produces `query_profiles.json` with descriptive evidence including:

- results returned;
- unique channels and unique-channel ratio;
- top-channel and top-3 channel concentration;
- median video views;
- median channel subscribers;
- share of results from channels above the configured large-channel threshold;
- share of results published within the configured recent window;
- analyzed 500K+ relevance counts;
- trusted/caution outlier counts;
- median trusted outlier ratio.

The YouTube API call currently uses `order=viewCount`. Therefore result position is the position in a **view-count-ordered research result set**, not YouTube organic relevance rank.

No query competition score is calculated.

### Repeated snapshots / current velocity

`output/video_snapshots.jsonl` stores immutable view-count observations over time.

On later runs, the system compares the current observation with the most recent prior snapshot at least one hour old and records:

- prior observation timestamp and views;
- elapsed hours;
- view-count delta;
- views per hour;
- views per day;
- status.

The first run correctly produces `NO_PRIOR`. A YouTube count decrease is stored as `NEGATIVE_ADJUSTMENT` rather than being mislabeled as negative audience velocity.

This is measured view accumulation between two observations. It is more current than lifetime `average_views_per_day`, but it is still an interval average rather than an instantaneous platform metric.

### Topic evidence aggregation

The automotive intent profile now has specific topic rules, separate from broader presentation themes.

Initial topics:

- brakes;
- gearbox / transmission;
- tyres / tires;
- steering;
- engine / power unit;
- aerodynamics / downforce;
- suspension / chassis;
- pit stops;
- hybrid / battery;
- race safety.

`topic_evidence.json` aggregates evidence by topic and separately by `short_candidate` and `long_form_candidate`.

For each topic it records:

- video count;
- unique channels;
- relevance counts;
- trusted/caution outlier counts;
- median views;
- median outlier ratio;
- median trusted outlier ratio;
- available snapshot-velocity sample count;
- median current views/day when repeat snapshots exist.

OFF_INTENT videos do not contribute to topic evidence.

## New generated files

The generated output set is now:

- `output/raw_results.json`
- `output/candidates.csv`
- `output/summary.json`
- `output/query_profiles.json`
- `output/topic_evidence.json`
- `output/video_snapshots.jsonl`

All remain outside Git.
