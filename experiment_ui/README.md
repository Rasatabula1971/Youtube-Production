# Experiment Control UI

## Goal

The local Experiment Control UI replaces routine PowerShell experiment commands
with buttons, status cards and live logs.

It is dependency-free and uses only the Python standard library.

The server binds to localhost only.

## Start

After pulling the repository, double-click:

~~~text
Start Experiment UI.bat
~~~

A browser window opens at:

~~~text
http://127.0.0.1:8765/
~~~

Keep the small launcher window open while using the UI. Closing it stops the
local control server.

## What the dashboard shows

The pipeline cards show the current state of:

- Experiment 01.3 — Age-Matched Velocity
- Experiment 01.4 — Depth Expansion
- Experiment 01.5 — Opportunity Handoff
- Experiment 02 — Why Did It Work?

The UI determines readiness from the actual generated files and summaries.

For 01.3, a frozen cohort is not enough to unlock 01.4. At least one
topic/format cell must first reach the independent-channel floor, and then that
cell must have enough measured velocity evidence for 01.4.

An insufficient cohort is clearly labeled and is not refreshable.

## Experiment 01.3

The main control is:

**Run / Resume 01.3 Auto Discovery**

It executes the same checkpoint-aware command previously run from PowerShell:

~~~text
experiment_01_3.py --mode discover --replace-cohort
~~~

If a discovery checkpoint exists, the experiment resumes completed work instead
of restarting it.

The UI displays the checkpoint status, including quota-related pause states
written by Experiment 01.3.

Once the corrected cohort is frozen, the UI checks whether at least one
topic/format cell has three independent channels.

If not, it shows **INSUFFICIENT COHORT — RERUN DISCOVERY** and keeps
**Refresh 01.3 Frozen Cohort** disabled.

If the cohort is sufficient, refresh becomes available. Cross-run snapshot
history is preserved so rebuilding discovery no longer automatically restarts
the velocity clock.

On Windows, use **Install 01.3 Auto Refresh** once. It registers a two-hour
Task Scheduler job that calls the self-limiting scheduled refresh runner. The
runner performs only frozen-cohort refreshes and automatically skips when a
snapshot is too recent or the current cohort already has enough velocity
evidence for 01.4.

**Remove 01.3 Auto Refresh** unregisters that task.

The scheduler writes its last state and background log under
`experiment_01_discovery/output/experiment_01_3/`.

## Downstream gating

Buttons remain disabled until their upstream data exists.

Examples:

- 01.4 Plan requires measured 01.3 velocity evidence.
- 01.4 Execute requires a READY expansion plan.
- 01.5 Build requires completed 01.4 execution.
- Experiment 02 Prepare requires the human-approved 01.5 study set.
- Model analysis requires prepared analysis requests.

The UI does not bypass experiment gates.

## FAIR

**Run FAIR Doctor** is always available.

It performs the same zero-inference diagnostic as the command-line doctor and
shows the result in the live job log.

When analysis requests eventually exist, **Run 1 Model Analysis** runs one
request through FAIR before scaling.

## Live job panel

Only one experiment process may run at a time.

The panel shows:

- action name;
- process ID;
- running/success/failure state;
- exit code;
- live stdout/stderr log.

The **Stop** button terminates the current child process.

Logs are retained under:

~~~text
.experiment_ui/jobs/
~~~

## Output folders

The dashboard can open the Experiment 01 output folder, Experiment 02 output
folder, and UI job-log folder in Windows Explorer.

## Security boundary

The browser cannot send arbitrary shell commands.

The server accepts only action IDs from a fixed allowlist in
experiment_ui/server.py.

The server is intentionally restricted to 127.0.0.1 / localhost.

No authentication is added because the UI is not exposed to the network.

## Current phase

Experiment 01.3 remains the live data stage until corrected discovery and
measured velocity refresh are complete.

The downstream controls can be visible while 01.3 is quota-blocked, but their
run buttons remain gated by real output evidence.


## Source acquisition

The UI includes an ACQ action group for the optional Agent Reach integration.

**Run Agent Reach Doctor** checks channel health and reports the active YouTube
backend. This action remains available even when Agent Reach is missing so the
log can report the dependency state.

**Run YouTube Discovery Benchmark** becomes available when both agent-reach and
yt-dlp are on PATH. It uses the Experiment 01.3 configured queries and writes
benchmark output under:

~~~text
source_acquisition/output/youtube_discovery_benchmark/
~~~

When the current 01.3 discovery checkpoint exists, the benchmark automatically
compares Agent Reach / yt-dlp video IDs with the saved YouTube API search audit.

The benchmark never modifies the 01.3 cohort.


## Automatic 01.3 discovery backend

The 01.3 button automatically chooses the available discovery path.

It first attempts YouTube Data API v3 search. If YouTube search quota is
unavailable, it switches remaining search jobs to Agent Reach / yt-dlp without
requiring another button or command.

The fallback affects discovery only. Official YouTube API metadata and velocity
measurement remain unchanged.

The separate acquisition benchmark remains available as a diagnostic tool, but
it is not required for routine 01.3 execution.


## Guided workflow

The normal creator-facing path is now **Run Opportunity Research** rather than
manually launching Experiments 01.3, 01.4 and 01.5.

The orchestrator:

1. runs/resumes 01.3 discovery;
2. freezes the cohort and records the first snapshot;
3. on Windows, schedules the next velocity measurement automatically every two
   hours while evidence is pending;
4. stops automatic retrying after three actual refresh attempts without enough
   velocity evidence;
5. when velocity is ready, builds and executes 01.4;
6. builds 01.5; and
7. stops at the Human Opportunity Gate.

The scheduled continuation is resume-safe. If 01.4 has already completed, it
does not repeat depth-expansion searches just because a later step needs to be
retried.

The main action area now exposes only the creator-facing automation boundary.
Deterministic machine steps are chained automatically until the next Human Gate.
When a Human Gate becomes complete and produces a valid downstream handoff, the
UI starts the next automatic machine segment without another run-button decision.

The individual Experiment 02, Transformation, Packaging, Research and Script
commands remain available under **Tools & Diagnostics** for diagnosis, forced
retry and recovery. They are no longer routine workflow gates.

Opportunity Research also attempts the supplemental vidIQ check automatically
after 01.5 and before the Human Opportunity Gate. It runs paid vidIQ research
only when the zero-cost Doctor is READY, the live tool metadata still declares
the expected credit cost, the provider renewable balance is readable, and the
local credit guards permit the call. Otherwise vidIQ is skipped and the Human
Opportunity Gate still opens on canonical project evidence.


## UI v3 — multi-view workspace

The working interface is split into four routes so routine work no longer shares
one vertically long page:

- `/` — **Home**: current step, next step, compact progress, opportunity summary
  and last activity.
- `/opportunity` — **Opportunity**: human review of the selected topic and source
  examples.
- `/analysis` — **Analyze & Create**: Experiment 02 and downstream creative work.
- `/tools` — **Tools & Diagnostics**: Doctors, manual experiment actions, raw
  outputs, logs and technical status.

The Live Job console is global. The top-bar job indicator opens a slide-out
drawer from any view, and background polling continues while navigating between
views.

The local server serves the same application shell at all four routes, so a
view can be refreshed or bookmarked directly without returning a 404.


## Experiment 02 evidence step

After **Prepare Experiment 02 Profiles**, the guided Analyze & Create workflow
now exposes **Acquire Source Evidence**.

That action acquires English captions, thumbnail and source metadata through
`yt-dlp` without downloading video media, then sends the files through the
offline evidence-ingestion layer.

The guided state checks exact current video IDs and artifact provenance. Old
enriched profiles or analysis requests from a previous approved set do not count
as current merely because a JSON file exists.


## Visual structure step

When both `yt-dlp` and `ffmpeg` are available, Analyze & Create inserts
**Acquire Visual Structure** after **Acquire Source Evidence** and before
**Prepare Analysis Requests**.

This step streams a low-resolution rendition, saves no full video, and creates
objective scene-transition timing evidence. It also retains an opening frame and
a bounded set of timestamped scene frames for a future vision-analysis layer.

If the first visual attempt fails, the guided workflow does not deadlock:
transcript-only analysis becomes available and **Retry Visual Structure (Force)**
is exposed under Tools & Diagnostics.


## Visual evidence review

When visual-structure sampling succeeds, the guided workflow adds:

**Prepare Visual Review → Review Visual Evidence → Prepare Analysis Requests**

The review appears directly inside **Analyze & Create** and shows one retained
frame at a time. The reviewer can move Previous/Next, edit a model draft when
one exists, accept the observation, or reject the frame.

Status polling does not overwrite the observation textarea while the user is
editing.

If no local vision model is configured, the same workflow operates in
human-only mode. **Vision Doctor** under Tools & Diagnostics reports whether a
configured local Ollama model is available.


## Transformation / Concept workflow

After Experiment 02 synthesis, Analyze & Create now continues automatically into
the Transformation Engine:

**Prepare Concept Requests → Generate Concept Candidates → Prepare Concept Gate
→ Review Concept Candidates**

The Concept tab is now active.

The Concept Gate displays one concept at a time to avoid a long scrolling page.
It shows the premise, audience promise, viewer problem / moment / outcome,
content-gap state, channel-fit state, title-clarity options, research questions
and Source Dependency Test.

ACCEPT requires all configured human criteria to be checked. REWORK requires a
written note. REJECT records the decision but does not pass the concept forward.

Only accepted concepts enter
`transformation_engine/output/research_handoff.json`.

If every concept is rejected or marked for rework, the current Concept Gate can
be reopened instead of leaving the workflow deadlocked.


## Packaging workflow

After at least one concept is accepted at the Concept Gate, Analyze & Create now
continues with the package-before-script stage:

**Prepare Package Requests → Generate Package Candidates → Prepare Packaging Gate
→ Review Package Candidates**

Package generation uses the same FAIR free-only subprocess boundary as
Experiment 02 and Transformation. Package responses are bound to the exact
current package-request SHA-256, and package requests are bound to the current
accepted-concept handoff. Stale requests are pruned and stale responses cannot
be merged into current candidates.

The Packaging Gate shows one title / thumbnail / opening-frame package at a time.
ACCEPT requires every configured human criterion. REWORK requires a written
note. At most one package may be accepted per concept.

Only accepted packages enter
`packaging_engine/output/research_handoff.json`. The approved package defines
the promise that downstream Research and Story / Script must support and
deliver.


## Research workflow

After a package is human-approved, Analyze & Create continues through:

**Prepare Research Plans → Acquire Research Evidence → Structure Research Claims
→ Prepare Research Gate → Review Research Claims**

Web evidence is acquired before FAIR is allowed to structure claims. Search uses
the Agent Reach Exa path and page content is retrieved through Jina Reader.
FAIR is restricted to the acquired source IDs and URLs and remains free-only.

The Research Gate is compact and claim-by-claim. The reviewer sees the claim,
coverage state, linked research question, source title/publisher/type, locator,
evidence note and URL. ACCEPT requires every configured criterion. REWORK
requires a note, and conflicted claims require an explicit resolution note.

Only verified packages with every research question resolved become
`READY_FOR_STORY_SCRIPT`.


### Visual acquisition fallback

Experiment 02 visual acquisition now prefers direct low-resolution streaming. If
yt-dlp cannot resolve a direct stream URL, the collector may download one
temporary low-resolution video file (360p or lower), run the same ffmpeg opening
frame and scene-change analysis locally, and delete the temporary video before
the job completes.

The saved visual report records `visual_source_mode` so downstream review can
distinguish direct-stream evidence from temporary-file fallback. The temporary
file is not retained as a project artifact.

## Slice 8 — automatic Script → Format continuation

After the final current Script branch is accepted, the server reevaluates
machine readiness and starts the existing `auto_continue` job automatically.
The operator does not press another run button.

The deterministic post-Script sequence is:

```text
Human Script Gate completes
        ↓
format_prepare
        ↓
format_generate
        ↓
format_gate_prepare
        ↓
STOP: HUMAN_FORMAT_GATE
```

The browser explicitly reports **“Script Gate complete. Format planning started
automatically.”** when the final Script decision launches that job.

The automation runner still stops at the Human Format Gate. It does not approve
a Format Plan or continue into Voice Performance without the human Format
decision.

Slice 8 also makes the handoff self-cleaning. When the approved Script input
changes, Format preparation invalidates downstream artifacts derived from the
old request rather than allowing stale plans or human decisions to survive into
the next run.

## Slice 9 — automatic Format → Voice Performance continuation

After the final current Format Plan is accepted, the server reevaluates machine
readiness and starts the existing `auto_continue` job automatically. The
operator does not press another run button.

The deterministic post-Format sequence is:

```text
Human Format Gate completes
        ↓
voice_prepare
        ↓
voice_generate
        ↓
voice_gate_prepare
        ↓
STOP: HUMAN_PERFORMANCE_GATE
```

The browser explicitly reports **“Format Gate complete. Voice Performance
planning started automatically.”** when the final Format decision launches that
job.

The automation runner still stops at the Human Performance Gate. It does not
approve the performance plan, render narration, or authorize paid narration
without the human decision.

Slice 9 also makes this handoff self-cleaning. A changed Voice request
invalidates downstream Voice model/spec/gate artifacts, while valid unchanged
provenance remains reusable.

## Slice 10 — automatic Performance → free Narration Preview continuation

After the final current Voice Performance plan is accepted, the server starts
the existing `auto_continue` job when the zero-cost preview chain is ready.

The deterministic sequence is:

```text
Human Performance Gate completes
        ↓
pre_render_engagement
        ↓
narration_preview_prepare
        ↓
prototype_sound_prepare
        ↓
narration_preview_render
        ↓
STOP: HUMAN_NARRATION_PREVIEW_GATE
```

The browser reports **“Performance Gate complete. Free narration preview
started automatically.”**

The listen gate is a hard boundary. Automatic work cannot jump from a current
preview directly into narration quote/spend preparation because stale downstream
artifacts happen to exist.

Preview validity is chained to hashes:

`approved Voice spec → engagement PASS → preview manifest → preview audio →
human preview approval`.

Changing any upstream performance artifact invalidates the downstream current
state until the free prototype is rebuilt and heard again.

The local renderer is deliberately zero-cost. If Kokoro/local preview
dependencies are unavailable, the automatic run returns a specific blocked
message. There is no paid TTS fallback at this stage.

## Slice 11 — automatic Preview → Narration Spend boundary

After the current free narration prototype is approved, automatic continuation
runs only zero-spend preparation:

```text
Human Narration Preview Gate approved
        ↓
sound_design_brief_prepare
        ↓
narration_prepare
        ↓
narration_spend_gate_prepare   (only when a current quote exists)
        ↓
STOP: HUMAN_NARRATION_SPEND_GATE
```

If a current quote does not exist, the runner stops at
`WAITING_NARRATION_PROVIDER_QUOTE`. If required voice/provider configuration
is incomplete, it stops at `NARRATION_PROVIDER_SETUP_REQUIRED`. It cannot
skip either state and continue into visual production.

The working UI now includes a Human Narration Spend Gate. It shows the provider,
initial estimate, worst-case authorization ceiling, quote reference, segment
count and maximum attempts. ACCEPT requires all spend criteria and a separate
confirmation of the displayed worst-case amount.

The gate itself makes no paid call. An accepted gate records authorization for
the exact current quote only.

The current repository configuration deliberately keeps the Higgsfield
narration contract unverified until a documented endpoint/schema, licensed
voice identity, licence reference and calibration are configured. Therefore a
normal live run must stop safely rather than fabricate provider pricing.

The provenance chain is:

`approved preview + current preview audio → Sound Design Brief → narration
render request → provider quote → cost estimate → Human Narration Spend Gate`.

Changing any bound upstream artifact invalidates downstream spend eligibility.

## Slice 12 — Spend approval → provider return → local Audio QC

After the Human Narration Spend Gate accepts the current quote, the app does
not call an unverified paid provider. It stops at:

`WAITING_NARRATION_RENDER_RETURN`

The working page displays an **Authorized Narration Return** panel. For each
current branch, the operator supplies the provider job/receipt reference,
actual cumulative USD cost, and one local audio path for every requested
narration segment. Each segment also records its attempt number.

The return registry:

- requires a current Human Narration Spend approval;
- checks the current request/estimate/spend provenance chain;
- refuses actual cost above the approved worst-case ceiling;
- requires exact segment order and full coverage;
- enforces the maximum attempts per segment;
- accepts only supported audio file extensions;
- copies provider audio into managed project storage; and
- invalidates stale QC/timing output whenever audio is re-registered.

A complete current return automatically unlocks
`narration_audio_qc`. Local ffprobe/ffmpeg checks then produce a deterministic
Audio QC record and narration timing map.

QC duration targets come from the current narration render request. They are
derived from immutable narration text plus the approved delivery speed, not
from provider-returned metadata.

The workflow then stops at one of two boundaries:

- `NARRATION_AUDIO_QC_FAILED` — corrected provider audio must be registered;
- `NARRATION_AUDIO_READY` — every current authorized branch passed QC and its
  timing map is current.

Even when narration is ready, Slice 12 prevents automatic continuation into
visual production.

## Slice 13 — Narration Audio Ready → Visual Search Plan Ready

Once final narration is current and every authorized branch has passed local
Audio QC, Continue Automatically now runs:

```text
NARRATION_AUDIO_READY
        ↓
production_visual_prepare
        ↓
storyboard_prepare
        ↓
visual_search_prepare
        ↓
STOP: VISUAL_SEARCH_READY
```

This slice performs no stock/creator search and makes no paid visual-generation
call. The next action after the boundary is **Search Free / Existing Visuals**.

The working visual state is now provenance-bound to final narration. A visual
manifest counts only when its approved Format Plan hash and narration timing-map
hash both match the current branch. Storyboards then bind the exact current
manifest and timing map. Search requests bind the exact current storyboard.

If final narration or its timing changes, the old visual manifest, storyboard
and search request chain becomes stale. Continue Automatically rebuilds the
current chain before any search adapter can run.

Storyboard preparation also requires timing segment IDs and visual requirement
beat IDs to match exactly. The system no longer silently substitutes a generic
visual direction for an unmatched narration beat.

The search contract remains existing/free-first and rights-aware:

1. own/reusable library;
2. verified free commercial sources;
3. public domain / compatible Creative Commons;
4. creator/editorial candidates only behind human rights/context review; and
5. premium generation only as a later last-resort gap candidate.

No item in Slice 13 authorizes premium generation.

## Slice 14 — Visual Search Ready → Human Visual Candidate Gate

Continue Automatically now advances the Slice 13 visual search plan through
zero-cost discovery:

```text
VISUAL_SEARCH_READY
        ↓
Search Free / Existing Visuals
        ↓
normalize rights-aware candidates
        ↓
HUMAN_VISUAL_CANDIDATE_GATE
```

The search runner validates the current storyboard-bound search request before
any provider call and rechecks it before each shot. If the request changes
during the run, no additional provider calls are made and no stale compiled
result is promoted.

Search progress is checkpointed after every shot. Clean unchanged shots can be
reused on a retry. Shots that changed or encountered provider errors are
searched again.

Pexels, Pixabay and YouTube creator discovery remain discovery sources only.
Provider failures are isolated so one timeout does not erase candidates from
another source. Provider errors are shown with the current candidate packet.

The Human Visual Candidate Gate does not open on partial branch coverage. Every
current search-required branch must have a current result bound to its exact
search request.

At the gate the reviewer can select a current eligible candidate, reject all
candidates, or mark the shot as needing a better visual. Creator/editorial
candidates still require the separate Rights/Context Gate before use.

Slice 14 downloads no media and authorizes no paid visual generation.

## Slice 16 — reviewed visuals → managed assets → Human Rough-Cut Gate

After the Human Visual Candidate Gate is complete, the workflow still stops at
the Human Rights/Context Gate whenever selected creator/editorial footage needs
context review.

Once candidate and rights decisions are complete, Continue Automatically runs:

```text
Acquire Approved Free Visual Assets
        ↓
Build Visual Rough Cut
        ↓
STOP: HUMAN_ROUGH_CUT_GATE
```

Automatic acquisition is limited to current, rights-verified zero-cost assets.
Stock downloads retain the existing HTTPS/provider allow-list, media-type and
size limits. Creator/editorial footage is never downloaded automatically.

The rough cut now distinguishes a human selection from an actual current local
asset. A selected clip appears as real media only when its managed registry and
local file hashes are current. Missing selected stock, stale files and approved
editorial clips that still need manual supply remain explicit placeholders.

Automatic acquisition failures keep the acquisition step retryable and prevent
the rough cut from being promoted as current. Manual editorial supply is
different: the structural rough cut may proceed with a clearly labelled
placeholder.

When the reviewer later registers the approved local editorial/visual file, the
old rough cut is invalidated and the automatic workflow rebuilds it from the new
current local asset before the Human Rough-Cut Gate.

The Human Rough-Cut Gate is a hard automation stop. Gap planning and all premium
visual decisions remain downstream of that human approval.
