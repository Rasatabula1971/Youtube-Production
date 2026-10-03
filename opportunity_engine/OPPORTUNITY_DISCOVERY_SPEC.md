# YouTube Production — Opportunity Discovery Expansion v2.1

**Repository:** `Rasatabula1971/Youtube-Production`  
**Purpose:** Expand the Opportunity stage so the system can discover promising video opportunities from three independent evidence sources:

1. **Historical Demand Discovery** — existing 01.3 → 01.4 → 01.5 pipeline.
2. **Human-Seeded Opportunity Research** — a human can enter a topic, question, or YouTube URL.
3. **Automatic Viral / Breakout Radar** — topicless discovery of recent YouTube outliers, with early detection and up to 15 days of trajectory tracking.

The Opportunity system must not rely on one source of truth and must not require every idea to pass the historical 01.5 thresholds.

The final objective is:

> **Find promising viewer demand early, determine whether it is repeatable or anomalous, explain why viewers may be responding, and convert that evidence into independent video opportunities without copying source videos.**

---

# v2.1 Revisions — read these first

v2.1 keeps the v2.0 text below unchanged as the baseline. Where a revision here
names a section, **the revision wins**. Revisions came from a review of v2.0
against the existing code (October 2026).

## R0. One channel now: Science Inside

The system builds **one channel now** and adds others as the work grows.

**Science Inside** explains the science inside everyday things: plane tyres,
wet vs dry tyres, hummingbird flight, the steelpan's tuned notes. Its fit test
for any idea is:

> Something people see, use or wonder about, and a mechanism inside it most of
> them do not know.

Episode families: tyres and grip; animals defying physics; machines you use
daily; sound and music; car science; weather and the world; your body
(mechanisms only, never medical advice). Storytime is a **format** across these
families, and a first-person story must be the creator's real story or a
credited, documented one — never invented.

Future channels (not built yet): **car modifications**, **ageing finance and
retirement**, **storytime**. Ideas that fit them are parked on that channel's
shelf, not discarded, so each launches with a backlog of evidence.

Configuration: `opportunity_engine/config.json`; voice draft:
`channel_profiles/profiles/science_inside_v1.json` (DRAFT until approved).

## R1. Reuse existing modules (overrides §27)

`viral_snapshot_store.py` and `viral_channel_baseline.py` are not new modules.
The radar uses the existing snapshot store and views-per-hour rules
(`market_intelligence.py`, D-021), `calculate_channel_baseline()` /
`baseline_confidence()` (`youtube_discovery.py`), the 01.3 yt-dlp/API AUTO
discovery (D-044), and extends `scheduled_refresh.py` (D-052, D-054) instead of
adding a second scheduler (§30, O13).

## R2. Topicless discovery is watchlist-led (overrides §5, §4.1)

yt-dlp has no "everything recent" feed, and YouTube retired its Trending page in
2025. "No topic required" therefore means **no topic from the user**, not no
seed at all:

1. **Primary — channel watchlist.** Every channel the system has seen (01.3,
   01.4, human seeds, the radar itself, plus seeded competitors such as
   Veritasium, Steve Mould, Real Engineering, Practical Engineering, Branch
   Education, SmarterEveryDay, Mustard, Driver61, Engineering Explained). One
   flat `/videos` tab read yields both new uploads and the channel baseline.
2. **Expander — bucket searches** using YouTube's "This week" upload filter,
   sorted by views. New channels join the watchlist.

Discovery buckets come from the active channel's families plus a configurable
exploration share (default 80% core / 20% open buckets such as business,
history, manufacturing, energy, construction, materials, food science).

## R3. Measure with the official API; yt-dlp discovers (overrides §4.2, §11)

Snapshots use `videos.list` (1 quota unit per 50 videos). yt-dlp is the
measurement fallback only when quota is exhausted. Each snapshot keeps
`discovery_source` / `measurement_source`. This preserves D-043.

## R4. Early outlier ratios state their basis (amends §6.1, §7)

A 12-hour video's lifetime ratio understates and its views/hour overstates.
Every ratio stores `ratio_basis` (`lifetime_vs_lifetime`,
`vph_vs_lifetime_vph`, `age_matched`). EARLY_SIGNAL requires both available
bases. Age-matched curves are built from the system's own snapshots over time.
Shorts baselines use only uploads after the March 2025 Shorts view-count change.

## R5. Breakout classification is four axes (overrides §10)

`strength` (NORMAL, EARLY_SIGNAL, BREAKOUT_CANDIDATE, BREAKOUT,
INSUFFICIENT_EVIDENCE), `trajectory` (ACCELERATING, STABLE_HIGH, DECELERATING,
FLAT, INSUFFICIENT_SNAPSHOTS), `breadth` (REPLICATED, ONE_OFF, UNASSESSED) and
`historical_alignment` (ESTABLISHED_DEMAND, NO_HISTORY, UNASSESSED). Cards may
show a headline built from them; no single label is stored.

## R6. Every evidence level names its rule (amends §19)

Each `evidence_state` dimension is `{level, rule_id, basis}`. Any level other
than UNASSESSED / HYPOTHESIS requires a written rule from
`config.json → evidence_rules`. Thresholds are hypotheses (D-009 style).

## R7. Day-15 outcomes calibrate the classifier (new)

When a video leaves the radar, its final trajectory is stored beside its
classifications at 24h, 3d and 7d so thresholds are tuned from measured hit
rates, not guesses.

## R8. New snapshots never stale an approved decision (amends criterion 22)

A gate decision binds to the evidence as it was when decided. Later snapshots
raise "evidence has moved since your decision"; only identity changes
(source videos changed, deleted or made private) invalidate it.

## R9. One active opportunity downstream (new)

Experiment 02 reads one `approved_study_set.json`. The inbox holds many
opportunities; **APPROVE makes one the active study set**. Others wait as
Approved. Parallel downstream work is a later, separate decision.

## R10. Channel routing and exclusions (new; amends §3.3, §5)

Every packet carries `channel.route`: ACTIVE_CHANNEL, FUTURE_CHANNEL (with the
future channel id), EXCLUDED (with the rule id) or UNSCOPED (needs a fit check).
Excluded items stay visible and reversible in a collapsed list.

- **Subject:** non-motor sport event content (highlights, transfers, fantasy);
  video-game play (gameplay, let's plays, esports); get-rich finance (crypto,
  stock picks, trading, side hustles). A mechanism-led video in these subjects
  passes ("why a free kick dips").
- **Format:** music videos, trailers, reactions, pranks, mukbang, ASMR,
  compilations, memes, livestream VODs, podcast clips, creator beef,
  made-for-kids.
- **Risk:** politics and elections, war and tragedy, conspiracy, medical
  advice, gambling and betting, true crime, illegal car modifications
  (emissions/DPF deletes, defeat devices, street racing).

YouTube's category is a signal only; it never excludes alone (many F1 channels
file under *Sports*).

## R11. Gate decisions (overrides §20)

APPROVE · REWORK (note required) · WATCH (viral lane only) · SAVE · REJECT.

## R12. Slice order (overrides §36 order)

1. **O1 + O2** — packet contract, provenance, channel scope, historical adapter
   (this PR: no UI change).
2. **O5** — analyze a video from a URL (built: `human_video_intake.py`,
   `active_source.py`, *Analyze a video* card on the Opportunity page).
3. **O4** — explore my topic (reuses the free search fallback and 01.3 query
   variants).
4. **O3** — workspace and inbox UI.
5. **O6–O9** — watchlist radar, API snapshots, four-axis classifier.
6. **O10**, then **O11 + O12**.
7. **O13 + O14** — extend the scheduler; trajectory charts.

Also pending: an `everyday_science` 01.3 topic set (01.3 is currently scoped to
motorsport engineering), added as its own change so the existing frozen cohort
is not disturbed.

---

# 1. Core Design Principle

The current 01.3 → 01.4 → 01.5 system is useful, but it answers only one question:

> **What topics have demonstrated historical demand?**

The revised Opportunity system must answer three different questions:

### Historical demand
> What topics have shown repeatable strength over time?

### Human hypothesis
> Is this topic, question, or video worth investigating even if the historical engine did not discover it?

### Emerging demand
> What is breaking out on YouTube right now, even if nobody told us what topic to search for?

These three paths must converge into one normalized Opportunity Packet and one Human Opportunity Gate.

---

# 2. Revised High-Level Architecture

```text
                         OPPORTUNITY ENGINE
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
 HISTORICAL DISCOVERY      HUMAN INPUT          VIRAL RADAR
   existing pipeline       manual seed          automatic
      01.3–01.5         topic/question/URL      no topic required
          │                     │                     │
          │                     │                ≤15-day window
          │                     │                     │
          │                     │             yt-dlp-first discovery
          │                     │                     │
          │                     │               outlier detection
          │                     │                     │
          │                     │                timed snapshots
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                ▼
                       OPPORTUNITY INBOX
                                ▼
                      HUMAN OPPORTUNITY GATE
                                ▼
                    EXPERIMENT 02 — WHY IT WORKED
                                ▼
                       TRANSFORMATION ENGINE
```

---

# 3. The Three Opportunity Sources

## 3.1 Historical Demand Discovery

Keep the existing pipeline intact.

```text
01.3 Age-Matched Velocity
        ↓
01.4 Depth Expansion
        ↓
01.5 Opportunity Handoff
```

This lane remains the system's strongest source for **historical repeatability**.

It should continue to use:

- age-matched cohorts;
- current views/day;
- age-matched velocity index;
- unique-channel counts;
- depth-family replication;
- PASS / REVIEW / HOLD;
- human approval before Experiment 02.

### Historical lane role

It should no longer be treated as the only entrance into the pipeline.

Instead, it becomes one source of evidence in the larger Opportunity Engine.

---

## 3.2 Human-Seeded Opportunity Research

A human must be able to introduce an idea at any time.

Accepted input types:

- free-text topic;
- viewer question;
- video idea;
- problem statement;
- niche;
- YouTube video URL.

Examples:

```text
F1 brake temperature
Why does an F1 car suddenly lose grip in rain?
Turbo lag
Why aircraft windows are round
https://youtube.com/watch?v=...
```

The system must not require the seed to already exist in `niches.json`.

### Human Topic workflow

```text
Human enters topic/question
        ↓
Normalize the seed
        ↓
Generate search variants
        ↓
Search current + historical evidence
        ↓
Find related strong/outlier videos
        ↓
Identify viewer questions and repeated mechanisms
        ↓
Create Opportunity Packet
        ↓
Human Opportunity Gate
```

A human-seeded topic may remain valid even if historical demand is not yet proven.

Example evidence state:

```text
source_type: HUMAN_TOPIC

historical_demand: UNASSESSED
current_breakout: MODERATE
cross_channel_replication: LOW
viewer_need: STRONG
mechanism_evidence: MODERATE
content_gap: HYPOTHESIS
```

The system must not reject a human idea merely because it has not crossed a 500K historical threshold.

---

## 3.3 Automatic Viral / Breakout Radar

This is the main new discovery engine.

It must work with **no topic supplied by the user**.

The purpose is to discover:

> **What recent videos are performing abnormally well relative to their creators and comparable content, and what emerging viewer demand do those outliers reveal?**

### Key rule

**Fifteen days is the maximum active tracking window, not the minimum age required before action.**

The system must surface strong breakouts as soon as evidence justifies doing so.

A video may be flagged:

- after 12 hours;
- after 1 day;
- after 2 days;
- after 5 days;
- or at any point before Day 15.

The system must never wait until Day 15 simply because the radar tracks videos for up to 15 days.

---

# 4. Viral Radar — Discovery Strategy

## 4.1 yt-dlp First

Broad discovery should use **yt-dlp first** to avoid wasting official YouTube Search quota.

yt-dlp should be used for:

- search discovery;
- YouTube search/tab extraction;
- channel upload inspection;
- video metadata retrieval;
- current view count;
- current like count;
- current comment count where available;
- channel follower count where available;
- publish/upload date;
- duration;
- thumbnail;
- channel ID;
- subtitles/transcript availability;
- playlist/channel pages.

Broad discovery must use metadata extraction only.

Do not download video files during candidate discovery.

Preferred approach:

```text
yt-dlp
  ↓
metadata / flat extraction
  ↓
local filtering
  ↓
candidate shortlist
  ↓
deeper metadata only for strong candidates
```

---

## 4.2 Official YouTube API as a Selective Validator

Do not spend expensive Search calls on broad discovery when yt-dlp can find candidates.

Use the YouTube Data API selectively for:

- canonical metadata validation;
- fallback when yt-dlp fails;
- channel metadata;
- batched video statistics;
- playlist metadata;
- official comments where appropriate;
- occasional search fallback.

The architecture must distinguish:

```text
DISCOVERY SOURCE
yt-dlp

VALIDATION SOURCE
YouTube API
```

Both may contribute evidence, but the canonical provenance must state which source produced each field.

---

# 5. Topicless Discovery

The radar must be able to start from:

```text
NO TOPIC
```

and discover topics from the videos themselves.

### Broad candidate acquisition

The system should maintain broad discovery buckets such as:

- automotive;
- motorsport;
- engineering;
- science;
- technology;
- consumer tech;
- DIY;
- education;
- business;
- history;
- aviation;
- space;
- sport;
- entertainment;
- practical knowledge;
- general-interest explainer content.

These buckets are discovery aids, not final content niches.

The system may rotate through them to prevent one broad category from consuming all discovery capacity.

### Topicless flow

```text
Broad YouTube discovery
        ↓
Recent candidate videos
        ↓
Age filter: 0–15 days
        ↓
Channel-relative outlier analysis
        ↓
Velocity / growth analysis
        ↓
Keep strongest candidates
        ↓
AI topic/theme clustering
        ↓
Find repeated viewer needs
        ↓
Opportunity candidates
```

The user does not need to tell the system the topic in advance.

---

# 6. Viral / Breakout Candidate Metrics

There must not be one fake "virality score."

The system should store evidence dimensions separately.

## 6.1 Current channel outlier ratio

Primary signal:

```text
candidate current views
────────────────────────────
median views of recent comparable uploads
```

Example:

```text
candidate views:          428,000
recent channel median:     26,000

channel_outlier_ratio = 16.46x
```

This is stronger than using subscriber count alone.

---

## 6.2 Views / subscriber ratio

Supporting signal:

```text
candidate views
────────────────
channel followers
```

Useful, but not the primary viral test.

Limitations:

- subscriber counts may be hidden;
- counts may be rounded;
- large channels can still produce real outliers;
- small channels can have unusual subscriber/view relationships.

Do not hard-code arbitrary rules such as:

```text
channel must have <90K subscribers
```

---

## 6.3 Current velocity

At minimum:

```text
lifetime_views_per_hour
lifetime_views_per_day
```

Calculated from publication time and current public view count.

---

## 6.4 Snapshot velocity

For tracked videos:

```text
new views since previous snapshot
─────────────────────────────────
elapsed hours
```

This is more useful than lifetime velocity once the system has multiple observations.

---

## 6.5 Velocity trend

Classify trajectory:

```text
ACCELERATING
STABLE_HIGH
DECELERATING
FLAT
INSUFFICIENT_SNAPSHOTS
```

Example:

```text
snapshot 1: 28,500 VPH
snapshot 2: 36,500 VPH

trend: ACCELERATING
```

---

## 6.6 Engagement density

Supporting metrics:

```text
likes / views
comments / views
```

These are not direct retention metrics.

Do not claim they represent CTR, average view duration, or viewed-vs-swiped-away.

---

## 6.7 Cross-channel replication

A major signal:

> Are multiple independent channels succeeding with the same underlying viewer problem, topic, event, or mechanism?

Example:

```text
Channel A: 14x baseline
Channel B: 8x baseline
Channel C: 11x baseline
```

This should be treated as stronger evidence than one isolated viral video.

---

# 7. Early Detection — Do Not Wait 15 Days

A video should be eligible for breakout classification as soon as the available evidence supports it.

Recommended age behavior:

```text
< 24 hours
    EARLY_SIGNAL allowed if evidence is exceptional

1–3 days
    BREAKOUT_CANDIDATE
    BREAKOUT

3–7 days
    BREAKOUT
    ACCELERATING_BREAKOUT
    REPLICATED_BREAKOUT

7–15 days
    continue tracking
    confirm replication / staying power

>15 days
    leave active radar
    retain final trajectory as historical evidence
```

These are evidence states, not promises of future success.

---

# 8. Active Tracking Window

The system should track promising videos for up to 15 days from publication.

Suggested cadence:

```text
0–48 hours old
snapshot every 6 hours

2–7 days old
snapshot every 12 hours

7–15 days old
snapshot every 24 hours

>15 days
stop active tracking
retain trajectory
```

This cadence should be configurable.

Do not track every discovered video.

Only promote candidates into active tracking after they pass an initial screen.

---

# 9. Initial Candidate Screen

A candidate should be retained for deeper evaluation when one or more signals are unusually strong.

Potential triggers:

- channel outlier ratio exceeds configured threshold;
- current VPH unusually high relative to channel;
- rapid snapshot acceleration;
- views/subscriber ratio unusually high;
- high engagement density;
- multiple independent channels showing same theme;
- unusual performance from a new/micro channel;
- human manually marks candidate for tracking.

Do not use one fixed threshold as the sole rule.

The output should explain **why** the candidate was retained.

Example:

```json
{
  "candidate_id": "yt_ABC123",
  "retained_reasons": [
    "CHANNEL_OUTLIER_12_4X",
    "HIGH_CURRENT_VPH",
    "CROSS_CHANNEL_TOPIC_REPLICATION"
  ]
}
```

---

# 10. Breakout Classifications

Recommended classifications:

```text
NORMAL
EARLY_SIGNAL
BREAKOUT_CANDIDATE
BREAKOUT
ACCELERATING_BREAKOUT
REPLICATED_BREAKOUT
ESTABLISHED_DEMAND
ONE_OFF_OUTLIER
DECLINING_BREAKOUT
INSUFFICIENT_EVIDENCE
```

### Meaning

**NORMAL**  
Performance is not meaningfully abnormal.

**EARLY_SIGNAL**  
Very young video with notable early evidence but insufficient confirmation.

**BREAKOUT_CANDIDATE**  
Promising abnormal performance; needs more evidence or snapshots.

**BREAKOUT**  
Strong current evidence of channel-relative abnormal performance.

**ACCELERATING_BREAKOUT**  
Snapshot growth rate is increasing meaningfully.

**REPLICATED_BREAKOUT**  
Same underlying subject/viewer need is breaking out across independent channels.

**ESTABLISHED_DEMAND**  
Current breakout aligns with historical demand evidence.

**ONE_OFF_OUTLIER**  
One unusually strong video with weak replication.

**DECLINING_BREAKOUT**  
Previously strong growth has materially slowed.

**INSUFFICIENT_EVIDENCE**  
Not enough reliable data to classify.

---

# 11. Snapshot Model

A snapshot must represent what the system actually observed at that time.

Example:

```json
{
  "video_id": "ABC123",
  "captured_at": "2026-10-03T15:00:00Z",
  "video_age_hours": 42.3,
  "view_count": 188000,
  "like_count": 11400,
  "comment_count": 932,
  "channel_follower_count": 34000,
  "lifetime_vph": 4444.4,
  "discovery_source": "YT_DLP"
}
```

Snapshots must be append-only.

Never overwrite previous observations.

---

# 12. Historical Limitation

The system must explicitly understand this:

> yt-dlp and the public YouTube page can tell us what a video looks like now, but they cannot reconstruct exact past public view counts that were never captured by our system.

Example:

If the radar first discovers a 12-day-old video at:

```text
850K views
```

the system can calculate current performance, but must not invent:

```text
Day 2 views
Day 5 views
Day 8 views
```

unless those snapshots were actually captured.

Trajectory state must therefore include:

```text
trajectory_history_available: true / false
```

---

# 13. Channel Baseline

For each viral candidate, inspect the creator's recent comparable uploads.

Recommended initial sample:

```text
10–20 previous uploads
```

Separate:

```text
SHORTS
LONG_FORM
```

Do not mix formats into one baseline.

Store:

```text
median_views
median_lifetime_vph
publication_age_distribution
sample_size
```

Where possible, age-normalized baselines should be developed over time from the system's own stored snapshots.

---

# 14. Long-Form vs Shorts

The system must keep long-form and Shorts separate.

## Long-form

Focus on public evidence related to:

- title;
- thumbnail;
- topic;
- click promise;
- current views;
- channel-relative outlier;
- current velocity;
- comments;
- story/opening analysis after promotion.

## Shorts

Focus on:

- immediate hook;
- rapid view acceleration;
- replay-friendly structure;
- channel-relative Shorts baseline;
- visual changes;
- comments;
- recurring format/topic replication.

Do not claim access to competitor-only analytics such as:

- CTR;
- average view duration;
- retention curves;
- Viewed vs Swiped Away.

Those must be marked:

```text
NOT PUBLICLY OBSERVABLE
```

---

# 15. Viral Candidate → Analysis

A viral candidate should not automatically become a new concept.

Strong candidates move to:

```text
Analyze Why It Worked
```

Then use Experiment 02 machinery.

Analysis dimensions remain:

1. packaging;
2. opening hook;
3. story progression;
4. information reveals;
5. emotion;
6. pacing;
7. visual language;
8. audience promise;
9. payoff;
10. promise/payoff alignment.

Add new opportunity-specific output questions:

```text
What viewer need appears to be driving interest?
What expectation is being violated?
What hidden mechanism or unresolved question is creating pull?
Which part of the success appears source-specific?
Which mechanism appears transferable?
What has already been heavily covered?
What remains weakly covered?
What independent opportunity exists without copying the source?
```

---

# 16. Comment Analysis

Where comments can be acquired legitimately, analyze them for:

```text
QUESTION
CONFUSION
SURPRISE
ARGUMENT
REQUEST
CORRECTION
PERSONAL EXPERIENCE
FOLLOW_UP_CURIOSITY
```

Do not treat comment volume alone as proof of virality.

The useful output is:

> **What are viewers still asking for?**

Example:

```text
Repeated question:
"Why doesn't this happen with intermediate tyres?"

Opportunity:
Explain the threshold between water evacuation and loss of tyre-road contact.
```

---

# 17. Topic / Theme Clustering

The topicless radar must cluster viral candidates automatically.

Example:

```text
18 breakout videos
        ↓
AI clustering
        ↓
Automotive engineering       5
Engineering failures         4
Hidden mechanisms            3
Consumer technology          3
Other                        3
```

Then look for repeated patterns across channels.

The system should distinguish:

```text
SAME EVENT
SAME TOPIC
SAME VIEWER QUESTION
SAME MECHANISM
SAME FORMAT
```

These are not equivalent.

Three videos reporting the same one-off news event are weaker evidence of durable opportunity than three independent videos satisfying the same recurring viewer question.

---

# 18. Cross-Validation with Historical Data

The viral lane and historical lane should strengthen each other.

Example A:

```text
Historical demand: STRONG
Current breakout: STRONG
Cross-channel replication: STRONG

Interpretation:
ESTABLISHED DEMAND + CURRENT MOMENTUM
```

Example B:

```text
Historical demand: WEAK
Current breakout: EXTREME
Cross-channel replication: LOW

Interpretation:
POSSIBLE ONE-OFF OUTLIER
```

Example C:

```text
Historical demand: MODERATE
Current breakout: STRONG
Cross-channel replication: STRONG

Interpretation:
EMERGING OPPORTUNITY
```

Do not collapse these into one numeric score.

---

# 19. Canonical Opportunity Packet

All three input lanes must produce the same top-level object.

Suggested schema:

```json
{
  "opportunity_id": "opp_...",
  "source_type": "HISTORICAL | HUMAN_TOPIC | HUMAN_VIDEO | VIRAL_RADAR",
  "created_at": "...",
  "title": "...",
  "summary": "...",

  "seed": {
    "topic": null,
    "question": null,
    "video_url": null
  },

  "evidence_state": {
    "historical_demand": "STRONG | MODERATE | WEAK | UNASSESSED",
    "current_breakout": "STRONG | MODERATE | WEAK | NONE | UNASSESSED",
    "cross_channel_replication": "STRONG | MODERATE | LOW | NONE | UNASSESSED",
    "viewer_need": "STRONG | MODERATE | WEAK | HYPOTHESIS",
    "mechanism_evidence": "STRONG | MODERATE | WEAK | HYPOTHESIS",
    "content_gap": "EVIDENCED | PLAUSIBLE | HYPOTHESIS"
  },

  "viral_evidence": {
    "classification": null,
    "candidate_video_ids": [],
    "tracked_video_ids": [],
    "topic_cluster_id": null
  },

  "historical_evidence": {
    "experiment_01_5_packet_id": null
  },

  "human_notes": [],

  "provenance": {
    "source_artifacts": [],
    "source_hashes": []
  }
}
```

---

# 20. Opportunity Human Gate

All three sources converge here.

The gate must show **where the opportunity came from**.

Example:

```text
SOURCE
✓ Viral Radar
```

or:

```text
SOURCE
✓ Human Topic
```

or:

```text
SOURCE
✓ Historical Discovery
```

The human reviews the evidence, not a fake universal score.

### Human decisions

```text
APPROVE
WATCH
REWORK / INVESTIGATE
SAVE IDEA
REJECT
```

### Meaning

**APPROVE**  
Move into Experiment 02 / Transformation.

**WATCH**  
Keep tracking, especially for emerging viral candidates.

**REWORK / INVESTIGATE**  
Request more evidence.

**SAVE IDEA**  
Store without immediate development.

**REJECT**  
Do not proceed.

---

# 21. Revised Opportunity UI

The existing `/opportunity` page should become an **Opportunity Workspace**, not only a final review screen.

## Top section

```text
OPPORTUNITY DISCOVERY

Find the next video from evidence, your own idea,
or what is breaking out right now.
```

---

## 21.1 Four Primary Actions

```text
┌──────────────────────────┐  ┌──────────────────────────┐
│ DISCOVER PROVEN DEMAND   │  │ EXPLORE MY TOPIC         │
│                          │  │                          │
│ Existing 01.3–01.5       │  │ Enter any topic or       │
│ historical engine        │  │ viewer question          │
│                          │  │                          │
│ [ Run Historical Search ]│  │ [ Explore Topic ]        │
└──────────────────────────┘  └──────────────────────────┘

┌──────────────────────────┐  ┌──────────────────────────┐
│ ANALYZE A VIDEO          │  │ FIND VIRAL / BREAKOUT    │
│                          │  │ VIDEOS                   │
│ Paste a YouTube URL      │  │                          │
│                          │  │ No topic required        │
│ [ Analyze Video ]        │  │ [ Run Viral Radar ]      │
└──────────────────────────┘  └──────────────────────────┘
```

---

# 22. Viral Radar UI

The radar should default to no topic.

```text
FIND VIRAL / BREAKOUT VIDEOS

Topic filter
[ Optional — leave blank for automatic discovery ]

Format
(•) Both
( ) Long-form
( ) Shorts

Active age window
[ 15 days ]

Region
[ Global ▼ ]

Discovery priorities
☑ Channel-relative outliers
☑ Early accelerating videos
☑ Cross-channel replication
☑ Smaller creator breakouts
☑ Established viral videos

[ Run Viral Radar ]
```

---

# 23. Viral Radar Result Cards

Example:

```text
🔥 ACCELERATING BREAKOUT

Why F1 Drivers Suddenly Lose Grip

Age                  2.8 days
Views                318K
Channel followers     34K
Channel baseline      27K

Channel outlier       11.8x
Views/followers        9.4x
Current VPH          36.5K
Velocity trend        ↑ accelerating

Related breakouts      3 channels

[ Watch ]
[ Analyze Why ]
[ Track ]
[ Save ]
```

Do not overcrowd the card.

Detailed evidence belongs in a drawer.

---

# 24. Opportunity Inbox

Below the entry cards:

```text
Opportunity Inbox

[ Needs Review ] [ Watching ] [ Approved ] [ Saved ] [ Rejected ]
```

Each Opportunity Packet appears as one compact card.

Possible source chips:

```text
HISTORICAL
HUMAN
VIRAL
VIDEO ANALYSIS
```

Possible evidence chips:

```text
BREAKOUT
REPLICATED
HISTORICAL DEMAND
VIEWER NEED
CONTENT GAP
```

---

# 25. Evidence Drawer

Clicking an opportunity should open a side drawer instead of making the page extremely long.

Drawer sections:

```text
Summary
Source
Viral evidence
Historical evidence
Candidate videos
Trajectory chart
Channel baseline
Viewer questions
Mechanisms
Content gaps
Research gaps
Human notes
Provenance
```

This preserves the low-scroll UI direction already established in the project.

---

# 26. Trajectory UI

Tracked videos should display a simple chart:

```text
Views
│
│                         ●
│                    ●
│               ●
│          ●
│      ●
│   ●
└──────────────────────────── Time
   12h 1d 2d 3d 5d 7d 10d 15d
```

Also show snapshot VPH:

```text
Snapshot velocity

12h → 24h   2.7K VPH
24h → 48h   4.8K VPH
48h → 72h   7.1K VPH
```

---

# 27. Proposed Backend Structure

Add:

```text
opportunity_engine/
```

Recommended modules:

```text
opportunity_engine/
    __init__.py

    models.py
    packet_schema.py
    provenance.py

    historical_adapter.py

    human_seed.py
    human_topic_search.py
    human_video_intake.py

    viral_discovery.py
    viral_candidate_filter.py
    viral_channel_baseline.py
    viral_snapshot_store.py
    viral_tracker.py
    viral_classifier.py
    viral_cluster.py

    opportunity_analysis.py
    opportunity_merge.py
    opportunity_gate.py

    config.json

    output/
        opportunities/
        viral_candidates/
        snapshots/
        clusters/
        gate/
```

---

# 28. Suggested API Endpoints

Read:

```text
GET /api/opportunities
GET /api/opportunities/{id}
GET /api/viral-radar
GET /api/viral-radar/{video_id}
GET /api/viral-radar/{video_id}/snapshots
```

Mutations:

```text
POST /api/opportunity/historical/run
POST /api/opportunity/topic
POST /api/opportunity/video
POST /api/opportunity/viral/run
POST /api/opportunity/viral/{video_id}/track
POST /api/opportunity/viral/{video_id}/analyze
POST /api/opportunity-gate
```

All mutating endpoints must use the same CSRF protections as existing human-gate routes.

---

# 29. Workflow Automation Changes

Current automatic workflow starts from one `opportunity_research` action.

Replace the concept of one front-door action with source-specific opportunity actions.

Recommended readiness actions:

```text
opportunity_historical
opportunity_topic
opportunity_video
opportunity_viral_radar
opportunity_viral_snapshot
opportunity_analysis
opportunity_gate_prepare
```

Do not force them into one linear sequence.

The Opportunity stage becomes event-driven.

Examples:

### Historical

```text
Run Historical Search
        ↓
existing 01.3–01.5
        ↓
Opportunity Inbox
```

### Human Topic

```text
Submit Topic
        ↓
topic research
        ↓
Opportunity Inbox
```

### Viral

```text
Viral Radar
        ↓
candidate discovery
        ↓
automatic tracking
        ↓
Opportunity Inbox
```

A user can use any or all three sources at the same time.

---

# 30. Scheduled Viral Radar

The radar should support an automatic scheduler.

Recommended:

```text
Broad discovery:
every 6–12 hours

Tracked candidate snapshots:
age-dependent schedule
```

The scheduler should not repeatedly search videos already seen unless a refresh is required.

Maintain:

```text
seen_video_ids
active_tracked_ids
completed_tracking_ids
last_discovery_run
next_snapshot_due
```

The scheduler must be resumable.

---

# 31. Fail-Safe Rules

## yt-dlp failures

If yt-dlp search or metadata extraction fails:

```text
YT_DLP_DISCOVERY_FAILED
```

Do not silently interpret this as "no viral videos found."

---

## Rate limiting / blocking

If YouTube throttles or blocks extraction:

```text
DISCOVERY_THROTTLED
```

Back off.

Do not retry aggressively.

---

## API quota

If official YouTube API validation is unavailable:

```text
API_VALIDATION_UNAVAILABLE
```

yt-dlp evidence may remain usable if clearly marked, but fields requiring API validation must stay unverified.

---

## Missing subscriber count

Do not reject a candidate.

Set:

```text
subscriber_outlier: UNAVAILABLE
```

Channel baseline can still determine outlier strength.

---

# 32. Truth / Evidence Boundary

The system must never claim:

```text
"This video had high CTR"
"This Short had 80% Viewed vs Swiped Away"
"This video has strong retention"
```

unless those metrics came from a channel-owner analytics source.

For competitor/public analysis, use:

```text
public performance evidence
observed structure
inferred mechanism
working hypothesis
```

Keep these separate.

---

# 33. Opportunity Analysis Output

Every promoted viral candidate should eventually produce:

```text
Observed breakout evidence
Observed packaging
Observed opening
Observed story / reveal pattern
Observed visual structure
Observed viewer reactions

Working hypothesis:
Why viewers may be responding

Transferable mechanism:
What can be learned without copying

Covered territory:
What creators already explained

Unresolved viewer need:
What remains unanswered

Independent opportunity:
A new angle suitable for our channel

Research requirements:
What must be verified before script
```

---

# 34. Example Viral Opportunity

Input:

```text
No topic supplied.
```

Radar discovers:

```text
Video A
11.4x channel baseline
2.8 days old

Video B
8.1x channel baseline
4.2 days old

Video C
13.0x channel baseline
5.1 days old
```

AI clusters all three around:

```text
F1 loss of grip in wet conditions
```

Observed viewer pull:

```text
sudden failure
hidden cause
danger
expectation violation
```

Covered territory:

```text
general wet tyres
aquaplaning
intermediate vs wet compounds
```

Possible gap:

```text
the exact transition where the tyre can no longer evacuate water
fast enough to maintain road contact
```

Opportunity:

```text
There is a point where an F1 tyre effectively stops touching the track.
```

Research requirements:

```text
verify aquaplaning threshold mechanics
verify tyre-water evacuation physics
verify F1 tyre design claims
avoid implying all wet patches cause aquaplaning
```

This becomes a Human Opportunity Gate candidate.

---

# 35. Migration Strategy

Do not rewrite the existing historical engine.

Wrap it.

### Existing

```text
01.3 → 01.4 → 01.5 → opportunity_gate.py
```

### Revised

```text
01.3 → 01.4 → 01.5
        ↓
historical_adapter.py
        ↓
Canonical Opportunity Packet
```

Human and Viral sources produce the same packet format.

Then:

```text
Canonical Opportunity Packets
        ↓
new opportunity_gate.py
```

This minimizes regression risk.

---

# 36. Implementation Slices

## O1 — Canonical Opportunity Contract

Create:

```text
opportunity_engine/models.py
opportunity_engine/packet_schema.py
opportunity_engine/provenance.py
```

Add tests.

No UI change.

---

## O2 — Historical Adapter

Convert current 01.5 handoff into the canonical packet.

Keep existing 01.5 outputs unchanged.

Add compatibility tests.

---

## O3 — Opportunity Workspace UI

Change `/opportunity`.

Add four entry cards:

- Discover Proven Demand
- Explore My Topic
- Analyze a Video
- Find Viral / Breakout Videos

Add Opportunity Inbox.

No viral logic yet.

---

## O4 — Human Topic Intake

Add topic/question submission.

Generate search variants.

Create human-seeded Opportunity Packets.

---

## O5 — Human Video Intake

Accept YouTube URL.

Validate video ID.

Acquire metadata.

Allow direct "Analyze Why" handoff.

---

## O6 — yt-dlp Viral Candidate Discovery

Add topicless broad discovery.

Requirements:

- no video downloads;
- metadata only;
- ≤15-day candidate filter;
- dedupe;
- format separation;
- persistent seen-ID cache;
- fail-safe throttling.

---

## O7 — Channel Baseline

For each candidate:

- retrieve recent comparable uploads;
- calculate median views;
- calculate channel outlier ratio;
- retain sample provenance.

---

## O8 — Snapshot Tracker

Add append-only snapshots.

Add age-based schedule.

Add velocity and acceleration calculations.

A strong candidate may be surfaced immediately.

Do not wait for Day 15.

---

## O9 — Breakout Classifier

Implement evidence-based classifications:

- EARLY_SIGNAL
- BREAKOUT_CANDIDATE
- BREAKOUT
- ACCELERATING_BREAKOUT
- REPLICATED_BREAKOUT
- etc.

No universal virality score.

---

## O10 — Theme Clustering / Replication

Cluster breakout candidates.

Detect:

- same topic;
- same viewer question;
- same event;
- same mechanism;
- same format.

Cross-channel replication must require independent creators.

---

## O11 — Viral → Experiment 02 Bridge

Allow:

```text
Analyze Why
```

to build Experiment 02 input from a viral candidate.

Reuse existing evidence acquisition and analysis contracts where possible.

---

## O12 — Unified Human Opportunity Gate

Replace historical-only assumptions in the gate.

Display:

- source type;
- evidence matrix;
- viral trajectory;
- historical evidence;
- viewer need;
- content gap;
- mechanism evidence.

Decisions:

- APPROVE
- WATCH
- INVESTIGATE
- SAVE IDEA
- REJECT

---

## O13 — Scheduler / Auto Radar

Add automatic topicless radar schedule.

Broad discovery every configured 6–12 hours.

Tracked candidates use age-dependent snapshots.

---

## O14 — UI Trajectory + Evidence Drawer

Add compact cards, evidence drawer, and trajectory charts.

Avoid long scrolling.

---

# 37. Testing Requirements

Apply the project's saved Code Evaluation Skill and Comprehensive Adversarial Software Bug Audit.

Mandatory cases:

- malformed YouTube URLs;
- repeated topic submission;
- duplicate video discovery;
- reordered snapshots;
- repeated snapshot timestamp;
- concurrent tracker jobs;
- interrupted yt-dlp process;
- partial metadata;
- hidden subscriber count;
- deleted/private video;
- age crossing 15-day boundary mid-run;
- timezone correctness;
- malformed yt-dlp JSON;
- YouTube frontend change;
- API validation mismatch;
- quota exhaustion;
- stale Opportunity Packet;
- stale Human Gate decision;
- channel baseline with mixed Shorts/long-form;
- same video returned by multiple discovery buckets;
- same creator represented in a supposed replicated breakout;
- one-off event falsely classified as cross-channel durable demand;
- retry storms;
- subprocess termination;
- Windows path issues;
- stale scheduler state.

---

# 38. Acceptance Criteria

The expansion is complete when all of the following are true:

1. Existing historical 01.3–01.5 behavior still works.
2. A human can enter any topic without editing niche configuration.
3. A human can paste a YouTube video URL.
4. The system can run a topicless viral search.
5. yt-dlp performs broad discovery without downloading full videos.
6. Candidates older than 15 days are excluded from the active viral radar.
7. A 2-day or 5-day-old breakout can be surfaced immediately.
8. Fifteen days is only the maximum active tracking window.
9. Channel-relative outlier is calculated separately from subscriber ratio.
10. Long-form and Shorts baselines are separate.
11. Snapshot history is append-only.
12. Historical values are never fabricated when no prior snapshot exists.
13. Velocity trend can distinguish accelerating vs decelerating candidates.
14. Cross-channel replication requires independent creators.
15. Viral candidates can be clustered without the user supplying a topic.
16. The system can generate an independent opportunity from viral evidence.
17. All three source types converge into the same Human Opportunity Gate.
18. No fake universal virality score exists.
19. Public evidence is kept separate from inferred causes.
20. Competitor CTR/retention/VVSA are never invented.
21. The UI remains compact and avoids long-scroll review pages.
22. Stale provenance invalidates downstream decisions.

---

# 39. Final Opportunity Model

The finished Opportunity system should behave like this:

```text
                  YOUTUBE PRODUCTION
                     OPPORTUNITY ENGINE

     ┌──────────────────────────────────────────┐
     │                                          │
     │  1. HISTORICAL                           │
     │     What has worked repeatedly?          │
     │                                          │
     │  2. HUMAN                                │
     │     What do I want investigated?         │
     │                                          │
     │  3. VIRAL RADAR                          │
     │     What is breaking out right now?      │
     │     No topic required.                   │
     │                                          │
     └─────────────────────┬────────────────────┘
                           ↓
                   OPPORTUNITY INBOX
                           ↓
                 evidence + trajectory
                           ↓
                HUMAN OPPORTUNITY GATE
                           ↓
                 WHY DID IT WORK?
                    Experiment 02
                           ↓
                 INDEPENDENT CONCEPT
                           ↓
                Research → Script → Package
```

The Opportunity Engine should therefore combine:

> **historical proof + human intuition + emerging breakout evidence**

without forcing all three through the same discovery rules.

The system should identify a viral opportunity as soon as sufficient evidence appears, continue tracking it for up to 15 days, and use that growing evidence to distinguish early noise, one-off viral hits, replicated breakout themes, and durable opportunities.
