# Opportunity Engine v2

Turns every opportunity source into one **canonical Opportunity Packet** so the
Human Opportunity Gate reviews evidence the same way whatever the source.

Spec: [`OPPORTUNITY_DISCOVERY_SPEC.md`](OPPORTUNITY_DISCOVERY_SPEC.md) (v2.1 —
read the *v2.1 Revisions* section first).

## Built so far (slices O1–O12)

| Module | Role |
|---|---|
| `models.py` | Shared vocabulary: source types, evidence levels, the four breakout axes, routes, gate decisions |
| `provenance.py` | Stable opportunity ids, content hashes, source-artifact records |
| `packet_schema.py` | `build_packet()` / `validate_packet()` — the one packet shape all lanes produce |
| `channel_scope.py` | Routes an idea to Science Inside, a future-channel shelf, or an exclusion (with the rule) |
| `historical_adapter.py` | Wraps the Experiment 01.5 study set as packets; 01.3–01.5 are unchanged |
| `human_video_intake.py` | O5: paste a YouTube link → validated id → metadata (API, then yt-dlp; never a download) → HUMAN_VIDEO packet |
| `human_topic_search.py` | O4: a topic or question → search variants → yt-dlp flat searches → API measurement → relevance and scope filters → HUMAN_TOPIC packet with rule-backed evidence |
| `active_source.py` | "Analyze why it worked" / "Analyze these videos": makes a submitted video, or a topic's strongest videos, the active study set for Experiment 02 |
| `inbox.py` | O3: merges every lane into one inbox (Needs review / Watching / Approved / Saved / Rejected) and stores save / reject / restore choices outside the evidence |
| `viral_radar.py` | O6–O9: watchlist discovery, channel baselines, append-only snapshots and the four-axis breakout classifier |
| `viral_cluster.py` | O10: groups breakouts into themes, checks the channels are independent, labels each theme (event, question, mechanism, topic) and sets breadth |
| `config.json` | Active channel, future channels, exclusion rules, written evidence rules, radar thresholds |

Run the historical adapter:

```
python opportunity_engine/historical_adapter.py
```

It reads `experiment_01_discovery/output/experiment_01_5/study_set.json` and
writes `opportunity_engine/output/opportunities/historical.json`. Nothing in
the UI reads it yet; the existing Opportunity Gate is unchanged until O12.

## The Opportunity workspace (O3)

The **Opportunity** page opens with four entry cards: *Discover proven
demand* (runs the historical engine), *Explore my topic*, *Analyze a video*,
and *Find viral / breakout videos* (shown, but disabled until the radar slices).

Below them, the **Opportunity Inbox** lists every idea from every lane as one
compact card: a source chip (HISTORICAL, YOUR TOPIC, YOUR VIDEO), the channel
route, rule-backed evidence chips, and an *Evidence and videos* expander.

| Tab | What lands there |
|---|---|
| Needs review | New ideas; historical topics still pending at the gate |
| Watching | Viral candidates you keep tracking (radar slices) |
| Approved | The active study set (pinned, marked ACTIVE) and historical approvals |
| Saved | Ideas you saved, historical topics on HOLD, and future-channel ideas (parked automatically) |
| Rejected | Ideas you rejected, historical rejections |

Your own ideas are saved, rejected or moved back from the card. Historical
topics are still decided in **Historical review** under the inbox (the existing
gate), and the inbox mirrors those decisions. Inbox choices live in
`output/inbox_state.json`, never in the evidence packets.

## The unified gate (O12)

The inbox is the one place to decide, with the spec's vocabulary:

| Decision | What it does |
|---|---|
| **Approve** | Makes the idea the study set for Experiment 02 (your video, your topic's videos, or a breakout). For a replicated theme, **Approve theme** sends one video per independent channel. |
| **Rework…** | A note is required: say what evidence is missing. Your video is re-measured, your topic is re-searched, and a breakout keeps being watched for more snapshots. |
| **Watch** | Radar breakouts only: keep tracking it in the Watching tab. |
| **Save / Reject** | Park or drop it. For historical topics these become the gate's HOLD / REJECT. |

Historical topics are still *approved* in Historical review, because their
examples must be kept or replaced first. Every card shows the six-dimension
evidence matrix: demand, breakout, replication, viewer need, mechanism and
content gap, with the rule behind each assessed level. Each decision is
recorded with its time, note and the evidence hash it was made against. When
the evidence changes later, the card says so; the decision still stands (R8).

## Themes and the bridge into Experiment 02 (O10–O11)

After each radar run, breakouts are grouped by the words their titles share
(`viral_clustering` in `config.json`). A theme counts only **independent**
channels: one video per channel, and re-uploads (near-identical title and
length on another channel) are not counted. Three or more independent channels
make it **REPLICATED** (five or more: strong). A theme about one news event is
marked event-bound and is weak evidence. Themes are in
`output/viral/clusters.json`.

When a human-seeded or radar video enters Experiment 02, its study row carries
`opportunity_context`: source, your question or topic, breakout numbers and
theme. Experiment 02 is then asked the spec's opportunity questions (viewer
need, violated expectation, hidden mechanism, source-specific vs transferable,
covered vs weakly covered, an independent angle). These map onto its existing
output fields. Historical topics get exactly the same requests as before.

## Viral / breakout radar (O6–O9)

*Run viral radar* on the Opportunity page (or
`python opportunity_engine/viral_radar.py run`) does one pass:

1. **Watchlist (O6).** The seed handles in `config.json → viral_radar`
   (Veritasium, Steve Mould, Real Engineering, …) plus every channel the
   system has already seen (your videos, your topics, the historical study
   set). Up to 4 rotating "this week" yt-dlp bucket searches add new channels.
   Each channel's uploads playlist is read with the API: about 1 unit per
   channel plus 1 unit per 50 videos. There is no `search.list` call.
2. **Baseline (O7).** Each channel's own uploads at least 15 days old, in the
   same format (Shorts only after the March 2025 view-count change). At least
   3 are needed or the video is `INSUFFICIENT_EVIDENCE`.
3. **Classify (O9), on first sight.** Two ratios with their basis named:
   views vs the channel's median views, and views/hour vs its median lifetime
   views/hour. `strength_rules` (hypotheses) set EARLY_SIGNAL /
   BREAKOUT_CANDIDATE / BREAKOUT. Trajectory comes from snapshots
   (ACCELERATING, STABLE_HIGH, DECELERATING, FLAT). Historical alignment checks
   the historical topics. Breadth comes from theme clustering (O10, below).
4. **Track (O8).** Promising videos are snapshotted every 6 h (under 2 days),
   12 h (2–7 days) and 24 h (7–15 days), append-only, into
   `output/viral/snapshots.jsonl` (the D-021 format). After 15 days a video
   leaves the radar and its outcome is kept beside its 24 h / 3 d / 7 d
   classifications, to calibrate the thresholds (R7).

Breakouts appear in the inbox as **VIRAL** cards. *Watch* moves one to the
Watching tab, and *Analyze why it worked* makes it the study set. Failures are
named: `API_VALIDATION_UNAVAILABLE` (no key or quota), `YT_DLP_DISCOVERY_FAILED`
and `DISCOVERY_THROTTLED` (the radar backs off from YouTube search for 6 hours).
CTR, retention and viewed-vs-swiped are never estimated.

## Explore my topic (O4)

On the **Opportunity** page, type a topic ("turbo lag") or a viewer question
("Why are aircraft windows round?") into *Explore my topic*. It does not need to
be in `niches.json`. The system:

1. normalises the seed (topic or question, keywords, a stable key);
2. builds up to 5 search variants (`config.json → human_topic`);
3. runs one yt-dlp flat search per variant (no quota, nothing downloaded);
4. measures the results in one YouTube Data API call (1 quota unit per 50
   videos), falling back to the search metadata if the API is unavailable;
5. keeps only results whose titles match the seed and that pass the scope
   exclusions;
6. sets **Demand** and **Replication** from the written `HT-*` rules, and leaves
   viewer need, mechanism and content gap as hypotheses.

The result is a sample of what search returns, not the age-matched historical
engine, and the packet says so. *Analyze these videos* sends the strongest
relevant videos (at most 4, one per channel) through Experiment 02 using the
same handoff as *Analyze why it worked*.

Command line:

```
python opportunity_engine/human_topic_search.py "Why are aircraft windows round?"
```

## Analyze a video (O5)

On the **Opportunity** page, paste a link into *Analyze a video*. Accepted:
`watch?v=`, `youtu.be/`, `/shorts/`, `/embed/`, `/live/` links and bare
11-character ids; playlists, channels and searches are refused. The video is
measured with the YouTube Data API (yt-dlp metadata is the fallback), routed to
Science Inside, a future-channel shelf or an exclusion, and saved under
`output/opportunities/human_video/`.

*Analyze why it worked* freezes that video as the approved study set and the
automatic workflow continues into Experiment 02. If Experiment 02 work already
exists for another study set, the UI asks first: the switch restarts
Experiment 02 and everything after it. *Stop analyzing* hands the study set
back to the historical gate; approving a historical topic does the same.

Command line:

```
python opportunity_engine/human_video_intake.py https://youtu.be/<id> --topic "hummingbird flight" --note "why I picked it"
```

## Rules the contract enforces

- No virality or opportunity score. Evidence dimensions stay separate, and any
  level above UNASSESSED/HYPOTHESIS must name the written rule that set it.
- Viral evidence is four independent axes: strength, trajectory, breadth and
  historical alignment.
- Every packet states where it belongs: `ACTIVE_CHANNEL`, `FUTURE_CHANNEL`,
  `EXCLUDED` (with rule id) or `UNSCOPED`.
- Packet identity is stable across rebuilds; `packet_sha256` changes only when
  the evidence changes.
