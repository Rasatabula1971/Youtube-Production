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
- date-oriented search through ytsearchdateN:.

Subprocess execution uses an argument list with shell=False.

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
