# Agent Reach Source Acquisition

## Role in this project

Agent Reach is used only as a source-acquisition capability and health layer.

It is not used for Experiment 01.3 calculations, opportunity scoring,
Experiment 02 reasoning, FAIR model routing, Transformation or Packaging
decisions, Research claim validation, human gates, Story / Script, production,
or learning metrics.

The project keeps its own evidence, validation, and decision layers.

## Why use it

Agent Reach's useful pattern is:

~~~text
capability
  ↓
ordered backend candidates
  ↓
health probe
  ↓
active backend
  ↓
call upstream tool directly
~~~

For YouTube, Agent Reach currently reports yt-dlp as the active backend.

The project therefore asks:

~~~text
agent-reach doctor --json
~~~

and, when YouTube is healthy, invokes yt-dlp directly.

This follows Agent Reach's documented design rather than wrapping or copying its
implementation.

## Installation

Agent Reach is an optional external dependency and is not vendored into this
repository.

Install it only when you explicitly want to enable these acquisition paths.

The upstream project documents:

~~~text
pip install https://github.com/Panniantong/agent-reach/archive/main.zip
agent-reach install --env=auto
~~~

The default install check is intended to be safe/read-only unless system
changes are explicitly approved.

After installation, verify:

~~~text
agent-reach doctor --json
~~~

## Adapter

agent_reach_adapter.py supports:

- Agent Reach doctor JSON;
- YouTube backend health;
- YouTube search through the active yt-dlp backend;
- relevance search through ytsearchN:;
- date-oriented requests through the supported ytsearch compatibility path;
- web search through Agent Reach's Exa / mcporter backend;
- public webpage reading through the Jina Reader path used by Agent Reach.

Subprocess execution uses an argument list with shell=False.

## Research acquisition

The Research Engine uses Agent Reach only for source acquisition:

~~~text
research question
  ↓
Exa web search → DuckDuckGo HTML → Wikipedia API   (first with results wins)
  ↓
real source URLs
  ↓
Jina Reader → direct fetch (Wikipedia plain-text extract for articles)
  ↓
saved page evidence
~~~

Exa needs `mcporter` on PATH and an Exa setup. When Exa is unavailable or finds
nothing, the free fallbacks run. They need only `curl` and no account or key.

Each question records which backends were tried and why they failed. Each page
records which reader produced it. Change the order or drop a backend with
`search_backends` / `read_backends` in
`research_engine/research_acquisition_config.json`.

Check the chain on your machine:

~~~text
python source_acquisition/agent_reach_adapter.py --mode doctor
python source_acquisition/agent_reach_adapter.py --mode web-search --query "aircraft tyre nitrogen"
python source_acquisition/agent_reach_adapter.py --mode web-read --query "https://en.wikipedia.org/wiki/Aircraft_tire"
~~~

DuckDuckGo's HTML endpoint is unofficial and may rate-limit or change markup.
Wikipedia is the stable last resort but only covers encyclopedic topics. Either
way, the Research Gate still decides what counts as evidence.

Agent Reach does not decide whether a claim is true, safe, or suitable for the
script. FAIR may later structure claims only from the saved acquired pages, and
the human Research Gate makes the final claim decision.

## YouTube discovery benchmark

The first use is deliberately experimental.

Run:

~~~text
python source_acquisition/youtube_discovery_benchmark.py --mode collect
~~~

The benchmark uses the Experiment 01.3 configured topic queries, gathers video
IDs through Agent Reach / yt-dlp, and, when the existing 01.3 discovery
checkpoint is available, compares those IDs against the saved YouTube API search
audit.

It reports:

- unique IDs from each acquisition path;
- overlap;
- API-reference recall;
- Agent Reach overlap rate;
- IDs found only by each path.

## Important limitation

The YouTube Data API Experiment 01.3 search currently uses publication windows,
video-duration branches, explicit search order, and region/language options
where configured.

A raw yt-dlp YouTube search does not reproduce those controls identically.

Therefore the benchmark is not evidence that one path is better. It answers a
narrower question:

Does Agent Reach / yt-dlp discover enough of the same candidate universe to
justify building a quota-free discovery backend?

Experiment 01.3 is not modified by the benchmark.

## Decision rule

Do not replace search.list merely because Agent Reach works technically.

First inspect benchmark overlap and contamination. If coverage is acceptable,
the next implementation should:

1. use Agent Reach / yt-dlp for broad candidate discovery;
2. apply our existing age/topic/format validation locally;
3. use official YouTube videos.list / channels.list for canonical metadata,
   snapshots, and velocity measurement;
4. preserve discovery provenance in every candidate.

This keeps acquisition replaceable while keeping measurement evidence stable.


## Experiment 02 transcript fallback

Experiment 02 now uses a bounded transcript fallback chain:

~~~text
YouTube English captions through yt-dlp
  ↓ if unavailable / rate-limited
temporary best-audio acquisition through yt-dlp
  ↓
local Whisper CLI transcription
  ↓
saved text transcript
  ↓
temporary audio deleted
~~~

The fallback is only attempted after direct caption acquisition fails. It requires
`ffmpeg` and the open-source `whisper` CLI on PATH. The default local model is
`base`; set `YOUTUBE_WHISPER_MODEL` to choose another installed/supported model.

The acquisition doctor reports whether this local fallback is ready. A YouTube
HTTP 429 is preserved as `RATE_LIMITED_429` when the fallback cannot complete,
rather than being misreported as a missing transcript.

The saved acquisition report records whether the transcript originated from
YouTube captions or local Whisper. Temporary audio is deleted after transcription,
including failure paths.
