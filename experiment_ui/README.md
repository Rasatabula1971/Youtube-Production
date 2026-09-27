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
