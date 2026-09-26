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

For 01.3, a frozen cohort is not enough to unlock 01.4. The UI waits for at
least one valid measured velocity sample from a refresh.

## Experiment 01.3

The main control is:

**Run / Resume 01.3 Discovery**

It executes the same checkpoint-aware command previously run from PowerShell:

~~~text
experiment_01_3.py --mode discover --replace-cohort
~~~

If a discovery checkpoint exists, the experiment resumes completed work instead
of restarting it.

The UI displays the checkpoint status, including quota-related pause states
written by Experiment 01.3.

Once the corrected cohort is frozen, **Refresh 01.3 Frozen Cohort** becomes
available.

## Downstream gating

Buttons remain disabled until their upstream data exists.

Examples:

- 01.4 Plan requires measured 01.3 velocity evidence.
- 01.4 Execute requires a READY expansion plan.
- 01.5 Build requires completed 01.4 execution.
- Experiment 02 Prepare requires the 01.5 study set.
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
