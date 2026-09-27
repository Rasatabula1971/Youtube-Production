# Stage 2 Experiment 01.3 — Age-Matched Velocity Validation

## Purpose

Experiment 01.3 tests whether an apparent topic winner is genuinely strong or
is simply benefiting from being newer than the comparison videos.

The default cohort is:

- target age: 120 days
- primary tolerance: +/-15 days
- primary age window: 105-135 days
- fallback tolerance: +/-30 days
- fallback age window: 90-150 days
- fallback is used only for topic/format cells with fewer than 3 unique channels
- minimum views at discovery: 500,000
- primary search order: `viewCount`
- fallback search order: `relevance`
- default per-run search budget: 60 calls
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

Every configured topic now has an explicit `niche`. The current eight F1
topics all belong to `automotive_racing`. Future niches may share the same
Experiment 01.3 run without contaminating each other's velocity baseline.

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

A persistent cross-cohort measurement ledger is also stored at:

`experiment_01_discovery/output/experiment_01_3_snapshot_history.jsonl`

Replacing a cohort does not archive this ledger.

## Why the cohort is frozen

The first run searches YouTube and freezes accepted video IDs in
`cohort_manifest.json`.

Later runs do not repeat discovery. They load those same IDs and request fresh
statistics. Search-ranking changes therefore cannot change the comparison
sample between observations.

## Validation gates

A video enters the cohort only when:

1. it is inside the primary age window, or the fallback window for a sparse topic/format cell;
2. it has at least the configured minimum views;
3. its **title** contains a target mechanism term;
4. its **title** also contains Formula 1 / motorsport context;
5. its title does not contain configured gaming/sim-racing exclusion terms; and
6. its actual duration format matches the search branch that discovered it.

Descriptions no longer qualify a video for a topic. This prevents metadata text
from turning a general video into false engineering evidence.

The context gate also prevents false positives such as a Rocketdyne **F-1 engine**
video being accepted as Formula 1 engine evidence.

Rejected results remain in `rejected_candidates.json` for auditability.

## First run — discover and freeze

Discovery now searches format-specific YouTube duration branches:

- `short` for short candidates
- `medium` for 4-20 minute long-form candidates
- `long` for videos over 20 minutes

This prevents Shorts from crowding long-form discovery.

From PowerShell:

```powershell
cd "C:\Youtube Production"

python .\experiment_01_discovery\experiment_01_3.py --mode discover
```

The first run creates the fixed cohort and writes a measurement snapshot.

Experiment 01.3 now preserves official candidate observations across cohort
rebuilds and also reads measurements from archived 01.3 runs. If an accepted
video was observed in an earlier run, current velocity may therefore be
available immediately after rebuilding the cohort instead of restarting the
measurement clock.

## Refresh the same videos

Only refresh a cohort that the UI marks as having enough independent channels.

If the UI reports **INSUFFICIENT COHORT — RERUN DISCOVERY**, do not wait for a
refresh. Rerun discovery instead.

When a cohort is refresh-worthy:

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
- aggregates the results by niche, topic and format.

### Automatic refresh on Windows

Manual refresh remains available, but it is no longer the normal operational
dependency.

The normal guided workflow no longer requires installing refresh separately.
**Run Opportunity Research** arms the Windows continuation task automatically
when elapsed-time velocity evidence is needed.

Manual maintenance controls remain under **Tools & Diagnostics**:

- **Install Opportunity Auto-Continue**
- **Remove Opportunity Auto-Continue**

The continuation task wakes every two hours and runs
`opportunity_research.py --mode continue`. That orchestrator calls the
self-limiting frozen-cohort refresh only when another snapshot is due. It skips
API work when:

- no frozen cohort exists;
- the frozen cohort is structurally insufficient;
- a recent snapshot already exists;
- another scheduled refresh is already running; or
- the current cohort already has enough independent-channel and velocity
  evidence to unlock Experiment 01.4.

When a refresh is due, the continuation invokes only the existing frozen-cohort
refresh path. Once velocity evidence is sufficient, the same continuation may
advance through 01.4 and 01.5. It never performs fresh 01.3 discovery while
running as a scheduled continuation, so the timed measurement step does not
spend `search.list` quota.

Scheduler status and logs are written under:

- `output/experiment_01_3/scheduled_refresh_status.json`
- `output/experiment_01_3/scheduled_refresh.log`

## Primary metric

For each topic and each format:

`median_current_views_per_day`

The age-matched velocity index is:

`topic median current views/day / niche-and-format cohort median current views/day`

The denominator is calculated independently for each:

- niche; and
- format (`short_candidate` or `long_form_candidate`).

This prevents a structurally fast niche from inflating or suppressing another
niche's topic index when multiple niches are validated in the same run.

Interpretation:

- `1.0` = cohort median
- `1.5` = 50% above cohort median
- `2.0` = twice cohort median
- `0.5` = half cohort median

## Topic channel confidence

`topic_channel_confidence` describes independent-channel breadth only:

- 1-2 unique channels: `LOW`
- 3-4 unique channels: `MODERATE`
- 5+ unique channels: `STRONG`

This is intentionally separate from `baseline_confidence`, which describes the
sample quality of one candidate channel's historical view baseline. The two
labels measure different evidence dimensions and do not share thresholds.

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

To intentionally replace an existing 01.3 cohort, use:

```powershell
python .\experiment_01_discovery\experiment_01_3.py --mode discover --replace-cohort
```

The program automatically moves the previous `output\experiment_01_3`
directory into:

`output\archive\experiment_01_3_<timestamp>`

before creating the new cohort. Run-local files remain auditable, while the
separate persistent snapshot ledger remains available to later cohorts.

Archived official observations from `raw_results.json`,
`rejected_candidates.json` and `video_snapshots.jsonl` are also eligible
history for the same video ID.


## Search quota and resume

YouTube `search.list` has its own daily call quota. Experiment 01.3 therefore
keeps the strict pass deliberately small and saves discovery progress.

Strict discovery uses one `viewCount` search per query/duration branch. The
`relevance` order is reserved for sparse-cell expansion only.

If the configured per-run API search budget is reached, the experiment writes:

`output\experiment_01_3_discovery_checkpoint.json`

The cohort is **not** frozen at that point. Run the same command again:

```powershell
python .\experiment_01_discovery\experiment_01_3.py --mode discover --replace-cohort
```

Completed search jobs are skipped automatically and discovery continues using
the original publication windows.

To intentionally discard a checkpoint and start the discovery search again:

```powershell
python .\experiment_01_discovery\experiment_01_3.py --mode discover --replace-cohort --restart-discovery
```

The checkpoint is deleted automatically once the cohort is successfully frozen.


## Automatic discovery backend

Experiment 01.3 now defaults to:

~~~text
--discovery-backend auto
~~~

Auto mode uses one control path:

~~~text
YouTube Data API v3 search.list
        ↓
available → use API search results
unavailable / quota rejected
        ↓
Agent Reach health check
        ↓
yt-dlp search fallback
        ↓
existing local 01.3 validation
        ↓
official YouTube videos.list / channels.list metadata
        ↓
frozen cohort and later refresh measurements
~~~

The fallback changes discovery only.

All candidate videos still pass the same project-owned age, minimum-view,
title-topic, motorsport-context and actual-duration validation before they may
enter the cohort.

Official YouTube API metadata remains canonical for accepted candidates and for
all repeated velocity snapshots.

Every search audit record stores:

- discovery_backend;
- requested search order;
- backend search strategy;
- query;
- phase;
- format target;
- result IDs.

This allows one frozen cohort to contain candidates discovered through either
backend without hiding their provenance.

### Explicit backend modes

For diagnostics, the CLI also supports:

~~~text
--discovery-backend youtube_api
--discovery-backend yt_dlp
~~~

Routine UI execution uses auto mode.


## yt-dlp age-aware fallback pool

The quota-free fallback no longer reuses only a small relevance-ranked search
pool.

Current yt-dlp no longer supports the old `ytsearchdate` shortcut.

For each configured query Experiment 01.3 therefore builds one cached pool from
supported `ytsearch` calls:

- the original query, up to 100 results; and
- a year-hinted version derived from the active age window, for example
  `F1 gearbox engineering 2026`, up to 100 results.

Known yt-dlp metadata is then prefiltered by the exact active 01.3 age window,
the minimum-view threshold, and the requested duration branch before official
YouTube API enrichment. Fallback duration branches are intentionally distinct:

- short: up to 180 seconds;
- medium: over 180 seconds through 20 minutes; and
- long: over 20 minutes.

Strict discovery uses the configured primary query family. Sparse-cell
expansion uses separate `expansion_queries`, with additional
`short_expansion_queries` for short-form discovery. This forces expansion to
acquire genuinely new relevance pools instead of merely filtering the strict
pool through a wider age window.

Pools are still cached and reused when the exact same query is needed by more
than one format branch. Once AUTO mode falls back to yt-dlp, the expanded pass
remains on yt-dlp instead of retrying an already quota-exhausted search.list
endpoint.

Final acceptance still uses official YouTube video/channel metadata and the
existing project validation gates.

## Insufficient cohort rule

A frozen cohort is not automatically worth refreshing.

At least one topic/format cell must contain the configured minimum of three
independent channels before the UI enables velocity refresh.

If no cell reaches that floor, the human status is:

~~~text
INSUFFICIENT COHORT — RERUN DISCOVERY
~~~

The correct action is another discovery pass, not waiting for a velocity
refresh.
