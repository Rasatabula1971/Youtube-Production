# YouTube Production

Research-driven system for discovering proven audience demand, understanding why successful videos work, transforming those mechanisms into genuinely new content, producing videos, and learning from published performance.

## Core principle

**Copy the demonstrated demand, not the video.**

The project separates three early questions:

- **Opportunity Engine** — what may be worth making?
- **Packaging Engine** — will the intended viewer choose it?
- **Retention Engine** — will the viewer keep watching and receive the promised payoff?

Transformation, research/story/script, format selection, production, quality control, and learning follow from those decisions.

## Current status (October 2026)

The governing product definition is the **Master Product Vision and Build
Comparison Specification**, with the Opportunity Discovery spec
(`opportunity_engine/OPPORTUNITY_DISCOVERY_SPEC.md`, v2.1) for discovery. A
vision-versus-build audit on 3 October 2026 compared the repository against it
(D-128).

**What exists.** Working, tested code paths run from opportunity discovery to a
locally rendered video:

- **Discovery.** Opportunities come from historical demand (01.3–01.5), your
  topic, a pasted video, or the viral radar. They all land in one inbox and
  pass a human opportunity gate.
- **Analysis.** "Why did it work" analysis runs on free models, and a human
  analysis gate confirms it.
- **Concepts.** Original concepts are generated, triaged automatically, and
  chosen at a human gate.
- **Research.** Real web sources are gathered and checked claim by claim.
- **Script.** It is written and reviewed section by section.
- **Packaging.** Post-script packaging produces title directions, a brief,
  angles, thumbnail concepts, pairing and one final package.
- **Format and voice.** Then come the format plan and voice performance.
- **Narration.** A free preview, then a paid-narration quote gate, with the
  audio returned manually.
- **Visuals.** Free-first visual search with rights review, a rough cut and
  visual spend, then the edit preview, final render and export approval.

Everything runs from the local browser UI (`experiment_ui/README.md`).

**What is not finished.** No complete production has yet run end to end. The
audit found that these deviate from the vision and are being corrected first:

- research review is mandatory instead of exception-only (fixed by A4, D-131);
- the concept pool was smaller than the 15–25 contract and finalists were not
  forced to be diverse (fixed by A3, D-130);
- incomplete stages can advance and the Gemini fallback admits non-quota
  failures (both fixed by A2, D-129);
- visual planning comes after narration (a visual plan is approved before
  narration spend since D-138, and the paid audio is approved since D-137);
- budgets are split by stage rather than per video (one ledger per video
  since D-136);
- reviewed history is not append-only everywhere (fixed for analysis and
  research by A6, D-133).

These are not built yet:

- paid narration and image or video provider dispatch;
- AI thumbnail image generation (the renderer uses a supplied subject image);
- Tesseract project exchange (open-format project export and edit import,
  D-144; not yet proven against Tesseract itself until one round trip);
- upload and publishing (publish package and gate D-142, YouTube upload
  D-143; direct upload is off until OAuth is configured);
- own-channel analytics;
- performance learning.

**Correction order.** Patches A1–A6 fix stage policy before more integrations
are built:

| Patch | Correction |
|---|---|
| A1 | Test isolation, and this status (done, D-128) |
| A2 | Stage completion and fallback policy (done, D-129) |
| A3 | Concept pool of 15–25 and diverse finalists (done, D-130) |
| A4 | Conditional research review (done, D-131) |
| A5 | One resolved format (done, D-132) |
| A6 | Append-only analysis and research history (done, D-133) |

After that come packaging, then planning and budget, then production,
Tesseract, publishing and learning. The next milestone is one Science Inside
video from an approved opportunity to a reviewed, editable near-final
production, with full provenance and one cost ledger.

Thresholds throughout remain research hypotheses, not frozen production rules.
The early-discovery signals (demand, channel-relative breakout, momentum,
quality, format, provenance, relevance, outlier reliability, themes,
competition, velocity) are collected independently; no single opportunity
score is calculated.

## Pipeline

```text
Opportunity (historical · topic · video · viral radar) → Opportunity Gate
    ↓
Experiment 02: why did it work? → Analysis Gate
    ↓
Transformation: original concepts → automatic triage → Concept Gate
    ↓
Research: sources and claims → Research Gate
    ↓
Story plan → section-based scripts → Script Gate
    ↓
Packaging: title directions → brief → angles → thumbnail concepts → pairing → Final Package Gate
    ↓
Format plan → Format Gate → voice performance → narration preview → narration spend
    ↓
Visuals: search → candidates → rights → rough cut → visual spend → edit preview
    ↓
Final render → (optional) Tesseract: editable project out, finished edit back
    ↓
Final Export Gate → publish package → Human Publish Gate → upload
    ↓
(not built) measure · learn  ↺
```

## Repository

```text
.
├── README.md · PROJECT.md · DECISIONS.md
├── opportunity_engine/       discovery lanes, viral radar, inbox, channel scope
├── experiment_01_discovery/  historical discovery 01.3 → 01.4 → 01.5
├── experiment_02_analysis/   evidence ingest, free-model analysis, human review, synthesis
├── source_acquisition/       yt-dlp / Agent Reach acquisition and benchmarks
├── transformation_engine/    concepts, triage, Concept Gate
├── research_engine/          source acquisition, claims, Research Gate
├── story_script_engine/      story plans, section-based scripts, Script Gate
├── packaging_engine/         post-script packaging and the Final Package Gate
├── format_engine/            format plans and the Format Gate
├── production_engine/        voice, narration, visuals, rough cut, render, export
├── channel_profiles/         channel voice profiles (Science Inside is still a draft)
└── experiment_ui/            local browser UI and job runner
```

## Runtime requirements

The project's own Python code uses the standard library. The only exception is
the optional free narration preview, which uses `kokoro`, `soundfile` and
`numpy`. External tools are called as executables:

- `yt-dlp`;
- `ffmpeg`;
- optionally `whisper`, for local transcription;
- Agent Reach;
- the separate FAIR repository, for free-model routing;
- optionally the vidIQ MCP bridge, through `npx`.

Copy `.env.example` to `.env` and add only the local values you need, such as
the YouTube Data API key. The FAIR subprocess coupling and override variables
are documented in `experiment_02_analysis/ANALYSIS_MODEL_RUNNER.md`.

Generated output and secrets stay outside Git: `.env`, every module's
`output/` folder, and `.experiment_ui/`.

**Tests** run per module, as in CI:

```text
python -m unittest discover -s <module> -p "test_*.py"
```

The tests never read the machine's real pipeline outputs:
`experiment_ui/testing_isolation.py` redirects every output path to an empty
temporary tree. They also do not depend on which optional tools are installed.

See [PROJECT.md](PROJECT.md) for the system design and
[DECISIONS.md](DECISIONS.md) for the decision record.


## Experiment 01.2

The first automotive live run proved collection worked but also exposed search contamination from gaming, RC and adjacent entertainment. Experiment 01.2 therefore annotates relevance and evidence reliability without deleting raw rows or changing raw metrics.

See `experiment_01_discovery/EXPERIMENT_01_2.md`.


### Research intelligence

Experiment 01.2 now produces transparent query competition profiles, persistent view snapshots for measured velocity, and topic-level evidence split by Shorts/long-form. These features are evidence layers only; they do not create a final opportunity or keyword score.


## Experiment 02 framework

Experiment 02 prepares evidence profiles from the active study set: the
approved 01.5 set, a submitted video, a topic's strongest videos, or a radar
breakout or theme. Source acquisition fetches transcripts, metadata and
thumbnails with yt-dlp, falling back to local transcription when whisper and
ffmpeg are installed.

Visual-structure analysis streams a low-resolution copy. If no stream URL
resolves, it downloads a temporary copy of 360p or lower and deletes it when
the job ends. No source video is kept as a project artifact.

Analysis runs on free models through FAIR and is validated against typed source
evidence. Findings are kept separate from hypotheses, and repeated mechanisms
are aggregated across independent videos and channels. A human analysis gate
confirms the result before the Transformation handoff.

See `experiment_02_analysis/EXPERIMENT_02.md`.


## YouTube Production UI

On Windows, double-click `Start Experiment UI.bat`. The UI opens on localhost.

- **Command Center.** What needs you, what is running, and the next action.
- **Opportunities** and the **Viral Radar**.
- **Productions:** the list, the review queue, and a workspace per video.
- **Gate reviews, Packaging and Produce.** Each human gate runs on one shared
  review workspace.
- **Tools & Diagnostics:** system health, job history and logs.

Automatic steps run between the human gates. On Windows the UI can install the
scheduled Opportunity Automation, which runs the radar and the 01.3 refresh.

To start again from Opportunities, close the UI and run
`python scripts/fresh_start.py --yes` (without `--yes` it only lists what
would move). It moves every production and the Opportunity Gate's choice
into `.archive/` and deletes nothing (D-157).

See `experiment_ui/README.md`.


## Transformation Engine

The Transformation Engine generates original concepts through free models
(`concept_model_runner.py`, via FAIR), checks them deterministically, and ends
at the human Concept Gate.

The engine consumes human-confirmed Experiment 02 mechanism handoffs, prepares
structured concept-generation requests, validates Source Dependency Test
requirements, and sends only human-accepted concepts into a Research Engine
handoff.

Concepts now also define the specific viewer problem, viewer moment, desired
outcome, content-gap evidence state, channel fit, and a three-title clarity
test before the Concept Gate.

Requests are sized so one opportunity's pool lands in 15–25 concepts.
Automatic triage (`concept_triage.py`) shortlists up to five distinct
finalists: no near-duplicates, and no single mechanism or hook type filling
the list. A shortfall is shown rather than filled. Every other concept stays
available as an explicit override (D-130).

See `transformation_engine/TRANSFORMATION_ENGINE.md` and
`transformation_engine/CONCEPT_GATE.md`.


## Research Engine

The Research Engine plans research, gathers real sources and ends at the
human Research Gate.

Accepted concepts are converted into research plans with stable question IDs.
Structured source/claim evidence preserves support, contradiction and
qualification without automatically labeling claims true.

Real sources are gathered by `research_acquisition.py`, which tries Agent
Reach/Exa first, then DuckDuckGo and Wikipedia, and reads pages through Jina.

Only accepted claims can enter a verified research package. The package stays
RESEARCH_INCOMPLETE until every original research question is covered by an
accepted claim. Review is exception-only (A4, D-131): a claim with verified
quotes from two independent reliable websites, no conflict, plain wording and
no elevated risk is accepted automatically with its reasons recorded; every
other claim waits for a human, who sees why.

See `research_engine/RESEARCH_ENGINE.md` and
`research_engine/RESEARCH_GATE.md`.


## Packaging Engine

Packaging runs **after the approved script** (D-093). Each format goes through
these steps:

1. **Title directions:** 5 Short and 5 Long, at a human title-direction gate.
2. **A packaging brief:** evidence-bound and deterministic (D-094).
3. **Psychological angles.**
4. **Thumbnail concepts,** informed by niche conventions (D-097).
5. **Rendering** from a locked template with a subject image chosen from
   three generated or imported candidates (D-135), or supplied directly, at a
   human thumbnail gate (D-098).
6. **Title-thumbnail pairing** with hard truth overrides (D-096).
7. **One final package** at the Final Packaging Gate (D-099), led by a 2–3
   title shortlist ranked from the pair validations (D-134).

No CTR prediction or viral score is produced; the shortlist rank is an
explained ordering of validation results. The older pre-script packaging
flow (D-040, D-041) is disabled in normal readiness and kept only for legacy
artifacts.

See `packaging_engine/PACKAGING_GATE.md` and the D-093 to D-099 decision
records. `PACKAGING_ENGINE.md` still describes the older flow.


## Story / Script and Format split

The Story / Script Engine now keeps one shared, verified Story Plan but writes
final narration **per required format before the Human Script Gate**. The approved
concept `format_intent` decides whether the concept requires `long_form`,
`short`, or both.

The two script profiles are deliberately different. Long-form prioritizes
sustained curiosity and comprehension. Shorts uses a high reward-density profile
with a 3-second opening-hook target and roughly 4–6 second attention/reward
refreshes as starting hypotheses for channel testing. These are not universal
physiological claims.

Every required script branch is reviewed independently. Only when all required
branches are accepted does the gate create one approved script bundle.

## Format Engine

The Format Engine and Human Format Gate consume that approved bundle. At this
point narration is immutable. Format planning owns scene structure, visual
treatment, duration intent, aspect ratio and production pacing; it may not
rewrite, shorten or substitute a branch script.

Each production branch may reference only sections from its matching approved
script. Production plans that collapse into identical branches or simple
timeline truncations fail deterministic validation.

Every factual production beat cites human-accepted research claims and traces
back to approved branch-script sections.

No format score, predicted retention or automatic branch winner is produced.

See `format_engine/FORMAT_ENGINE.md` and `format_engine/FORMAT_GATE.md`.


## Source Acquisition / Agent Reach

Agent Reach is integrated only as an external acquisition and backend-health
layer.

The first use is a YouTube discovery benchmark. Agent Reach reports whether
YouTube is healthy and which backend is active; the project then calls yt-dlp
directly for quota-free search and compares those video IDs with the saved
Experiment 01.3 YouTube API search audit.

The benchmark does not modify the 01.3 cohort and does not replace official API
measurement.

The Experiment Control UI includes Agent Reach Doctor and YouTube Discovery
Benchmark actions when the external dependency is available.

See source_acquisition/README.md.


## Viewer Need Framing

The project now separates a broad topic from the specific viewer need it serves.

Transformation and Packaging preserve:

- viewer problem;
- viewer moment;
- desired outcome;
- content-gap evidence status;
- channel fit;
- three-title idea-clarity test;
- approved one-sentence promise.

See `transformation_engine/VIEWER_NEED_FRAMING.md`.
