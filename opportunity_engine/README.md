# Opportunity Engine v2

Turns every opportunity source into one **canonical Opportunity Packet** so the
Human Opportunity Gate reviews evidence the same way whatever the source.

Spec: [`OPPORTUNITY_DISCOVERY_SPEC.md`](OPPORTUNITY_DISCOVERY_SPEC.md) (v2.1 —
read the *v2.1 Revisions* section first).

## Built so far (slices O1, O2, O4 and O5)

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
| `config.json` | Active channel, future channels, exclusion rules, written evidence rules |

Run the historical adapter:

```
python opportunity_engine/historical_adapter.py
```

It reads `experiment_01_discovery/output/experiment_01_5/study_set.json` and
writes `opportunity_engine/output/opportunities/historical.json`. Nothing in
the UI reads it yet; the existing Opportunity Gate is unchanged until O12.

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
