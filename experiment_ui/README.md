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

The main action area shows the current required action in blue and the following
step in amber. Manual experiment controls, Doctor actions, scheduler controls,
benchmarks and clean-restart controls are under **Tools & Diagnostics**.


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
