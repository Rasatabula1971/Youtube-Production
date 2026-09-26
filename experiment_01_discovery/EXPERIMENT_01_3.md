# Stage 2 Experiment 01.3 — Age-Matched Velocity Validation

## Purpose

Experiment 01.3 tests whether an apparent topic winner is genuinely strong or
is simply benefiting from being newer than the comparison videos.

The default cohort is:

- target age: 120 days
- tolerance: +/-15 days
- accepted age window: 105-135 days
- minimum views at discovery: 500,000
- search orders: `viewCount` and `relevance`
- Shorts and long-form candidates analyzed separately

No final opportunity score is calculated.

## Topics

The default configuration searches:

1. gearbox / transmission
2. brakes
3. tyres / tires
4. steering
5. suspension / chassis
6. aerodynamics / downforce
7. engine / power unit
8. pit stops

Configuration lives in:

`experiment_01_3_config.json`

## Output isolation

Experiment 01.3 never writes into Experiment 01.2 output files.

All files are stored under:

`experiment_01_discovery/output/experiment_01_3/`

Generated files:

- `cohort_manifest.json`
- `candidates.csv`
- `raw_results.json`
- `rejected_candidates.json`
- `topic_velocity.json`
- `summary.json`
- `video_snapshots.jsonl`

## Why the cohort is frozen

The first run searches YouTube and freezes accepted video IDs in
`cohort_manifest.json`.

Later runs do not repeat discovery. They load those same IDs and request fresh
statistics. Search-ranking changes therefore cannot change the comparison
sample between observations.

## Validation gates

A video enters the cohort only when:

1. it is inside the exact age window;
2. it has at least the configured minimum views;
3. its title or description contains a target mechanism term; and
4. its title or description also contains Formula 1 / motorsport context.

The context gate prevents false positives such as a Rocketdyne **F-1 engine**
video being accepted as Formula 1 engine evidence.

Rejected results remain in `rejected_candidates.json` for auditability.

## First run — discover and freeze

From PowerShell:

```powershell
cd "C:\Youtube Production"

python .\experiment_01_discovery\experiment_01_3.py --mode discover
```

The first run creates the fixed cohort and writes snapshot #1.

Current velocity should normally be unavailable on the first run because the
new Experiment 01.3 snapshot history has no earlier observation.

## Second run — refresh the same videos

After at least one hour:

```powershell
cd "C:\Youtube Production"

python .\experiment_01_discovery\experiment_01_3.py --mode refresh
```

Refresh mode:

- performs no new YouTube search;
- loads the frozen video IDs;
- requests current video statistics;
- compares them with the prior Experiment 01.3 snapshot;
- calculates current views/hour and current views/day; and
- aggregates the results by topic and format.

## Primary metric

For each topic and each format:

`median_current_views_per_day`

The age-matched velocity index is:

`topic median current views/day / whole cohort median current views/day`

The denominator is calculated independently for:

- `short_candidate`
- `long_form_candidate`

Interpretation:

- `1.0` = cohort median
- `1.5` = 50% above cohort median
- `2.0` = twice cohort median
- `0.5` = half cohort median

## Confidence

Topic confidence is based on independent channels:

- 1-2 unique channels: `LOW`
- 3-4 unique channels: `MODERATE`
- 5+ unique channels: `STRONG`

This prevents one unusually successful video from being treated as strong
topic-level evidence.

## Supporting signals

Experiment 01.3 also retains:

- total views
- channel-relative outlier ratio
- outlier reliability
- channel baseline
- age
- format
- current views/hour
- current views/day

Outlier performance remains supporting evidence only.

## Starting over

Discovery intentionally refuses to run when an Experiment 01.3 snapshot file
already exists. This prevents a replacement cohort from inheriting old
snapshots.

To restart the experiment, archive or remove the entire:

`output\experiment_01_3`

directory first, then run discovery again.
