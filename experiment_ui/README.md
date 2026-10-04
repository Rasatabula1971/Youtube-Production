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

While a job runs, a banner under the page header on every page shows the
current automatic step, a ticking clock and the latest log line; it turns
amber when the log has been quiet for two minutes (D-155).

## Gate policy (D-156)

`gate_policy.json` says how each human gate is decided:

- `HUMAN`: you decide every item.
- `AUTO_IF_CLEAN`: Continue Automatically decides the items that pass the
  gate's machine checks (`gate_autopilot.py`) and leaves anything flagged for
  you. The run log and the PARTIAL/stop message name each held item.

Shipped as `AUTO_IF_CLEAN`:
- Vision, Analysis, Title Direction, Format, Voice Performance and Narration
  Preview (D-156);
- Visual Plan, Visual Candidates, Rough Cut, Edit Preview and Final Audio
  (D-158);
- Narration Spend and Visual Spend (D-158). These approve only on the
  confirmed per-video budget ($5 target, $10 ceiling), only while the video
  stays at or under the target, and only with a known price from a verified
  provider.

Concept, Research (which already clears claims with two independent sources,
D-153), Script, Final Packaging, Visual Rights (editorial footage), Final
Export and Publish stay with you. Set a gate to `HUMAN` to get it back.

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

The working interface is split into five routes so routine work no longer
shares one vertically long page. UI Patch 1 (D-115) renamed and regrouped them
to match the redesign's navigation:

- `/` — **Command Center**: the current step ("Needs your attention"), an
  attention queue (productions waiting on a review or blocked, new radar
  breakouts, inbox ideas, a failed job), active productions, what is running
  automatically, then the compact progress, opportunity and last-activity
  panels.
- `/opportunity` — **Opportunities**: the four entry cards in one row, a counts
  strip (need review, watching, approved, saved) with "Review N ideas one by
  one", and the inbox. Inbox cards show the lane, a meta line (independent
  channels, when detected, direction), an outlier figure and the six evidence
  levels, with "Review opportunity" as the one primary button. Sidebar
  sub-items: Discover, Viral Radar, Review, Watching, Approved.
- `/radar` — **Viral Radar** (D-116): monitoring status (automatic or manual
  only), last scan, next discovery, next snapshots, videos and channels
  tracked, and "Run scan now". "Emerging now" shows themes, replicated ones
  first, each with a momentum sparkline of its strongest video, strongest and
  median outlier, current direction and historical demand. "Watching" lists the
  breakouts you chose to watch, with Day N / 15, outlier, sparkline and
  direction, and "All tracked videos" lists the rest. A format filter (All,
  Long-form, Shorts) filters what is shown. Topic and region filters are not
  offered because the radar does not support them yet.
  - **Headlines (D-170):** a theme is titled by its strongest on-lane
    video's title (tags, hashtags and channel suffixes trimmed); the keyword
    stems appear under it as "Shared words".
  - **Shortlist filters (D-162):** lane (my lane / everything, from
    `opportunity_engine/radar_lane_config.json`), minimum outlier, freshness
    and format; replicated themes pinned first; the bar counts what it hides.
  - **What I pick (D-165):** after 20 Approve / Watch / Save / Reject
    decisions on radar candidates (at least 5 each way) the page learns a
    word model from them, shows "like your picks" / "unlike your picks"
    beside each video, names the strongest words for and against, and
    offers an Order pill: strongest outlier, or what you pick. Nothing is
    hidden by it. Until then the filter bar says how many decisions it has.
- `/opportunity/review` — **Opportunity Review** (D-116): the Human Opportunity
  Gate on the shared review workspace. The inbox's "Needs review" items are
  shown one at a time. Evidence is on the left: summary, rule-backed "why this
  is interesting", the six evidence levels, videos and "Open full evidence".
  The decision is on the right: only the actions that item allows, a note, and
  "Save decision". Keys: ← → move, 1–9 choose, Ctrl+Enter save. Investigate
  (rework) requires a note. A decided item leaves the queue, and a failed
  decision keeps your draft. `#<opportunity_id>` links to one item.
- `/productions` — **Productions** (D-117): one row per accepted concept with
  its stage, status, what it waits on, when its files last changed, and a stage
  bar. "Open →" goes to the Production Workspace. The tabs are Active, Review
  Queue and Completed. **Review Queue** (D-164) lists every pending item of
  every gate, with the gate as a label: your decisions first (Concept,
  Research, Script, Final package, Format, Voice, Budget, Footage rights,
  Final export, Publish…), then a production waiting on you without a gate
  item, then the ideas inbox, then what the gate policy held. Each row opens
  that item on its page; "Start review queue →" opens the first. The nav
  item carries the count. "+ New"
  goes to Opportunities, because a production starts from an accepted concept.
  - **One Continue per row (D-163).** Each production row (and
    the Production Workspace) shows a blocker line when the last automatic
    run stopped at its stage, with the step and the reason, and offers its
    own Continue. The runner records its outcome in
    `.experiment_ui/last_auto_run.json`. A concept whose research claims are
    all decided but not ready says why in plain words ("1 question
    unanswered: mark it Not needed for script, or Rework a claim"); the
    Research Gate waives a question automatically when no source or claim
    covers it, and the operator can undo that waiver.
- `/production#<concept_id>` — **Production Workspace** (D-117): one video. The
  header shows title, premise, stage · status and last update. Eight tabs are
  real sections: Evidence, Analysis, Concept, Research, Script, Package,
  Format, Produce. Each is marked done, current or not started, and the
  current stage opens by default.
  - **Current step.** The current stage starts with a "Current step" card;
    "Continue review →" opens the existing review panel in Workspace
    (`/analysis`) until that gate moves onto the shared review workspace.
  - **What each tab shows.** Evidence, Analysis and Concept show the accepted
    concept's own fields. Research shows its progress and each claim's
    decision. Script shows each branch and every section's decision, lock,
    rework reason and ready alternatives. Package and Format show progress and
    decisions. Produce shows each version's voice, narration and final render.
  - **Keys.** Tabs follow the WAI-ARIA pattern: ← → move, Home/End jump.
- `/review#<gate>` — **Gate Reviews** (D-118, D-119, D-121): the Analysis,
  Concept, Research, Script, Format, Voice and Narration Preview gates on the shared review workspace, one item at a time, with a
  gate switcher showing pending counts and "Include decided items" for
  revisiting.
  - **Same requests.** Each decision posts exactly what the classic panel
    posts: `/api/human-analysis-review`, `/api/concept-gate` and
    `/api/research-gate`, with empty criteria (the server fills them in from
    the decision).
  - **Notes.** Rework needs a note. Accepting a claim whose sources conflict
    needs a resolution note.
  - **Research.** Claims show their sources with stance, locator and quote,
    the concept's research questions with answered/waived status, and
    Waive / Remove waiver.
  - **Revisiting.** A decided item opens with its decision and note
    pre-filled. Unsaved drafts stay with their item while you move around.
  - **Links in.** `/review#concept/<concept_id>` links to one item. The
    Command Center hero, its attention cards, the Review Queue, a production's
    "Continue review" (research) and a "Review one at a time" button on each
    classic panel all open it.
  - **Script (D-119).** A script branch is reviewed part by part (opening
    hook, each section, closing), then as a whole.
    - *Each part* shows its text, why it exists (purpose, psychology,
      reward) and the claims it uses.
    - *Part decisions:* Accept and lock; Rework (reason plus instruction),
      then "Generate A / B / C", which calls the model once, and pick an
      option or keep the original; Edit by hand (starts from the current
      text); Unlock; Cancel rework.
    - *Whole script:* accept, rework or reject. Accepting with parts still
      open asks first, then accepts them too.
    - *Requests:* the same as the classic panel, and section editing is
      prepared automatically before the first part action.
  - **Format, Voice, Preview (D-121).**
    - *Format:* each branch with its duration, promise delivery, payoff and
      beats, claims used per branch, unused claims and source overlap.
    - *Voice:* every beat's fixed narration with its delivery (emotion,
      intensity, speed, pauses, stressed words).
    - *Preview:* an audio player for the free prototype. Approving it unlocks
      the paid narration quote, and it cannot be approved before the audio
      exists. The three rework choices (performance, script, music/SFX) each
      need a note.
    - *Per-segment revision* and re-rendering stay in the classic panel.
  - **Classic view.** It stays in Workspace with every option, including the
    concept override bank, saved ideas, the bounded rework request without a
    model call, and restoring a saved script version.
- `/packaging#<tab>` — **Packaging** (D-120): five tabs as in the redesign.
  - **Title Direction:** one concept at a time. Pick one Short and one
    Long-form title (editing the wording selects it), then Accept, Rework
    (note required) or Reject. An accepted selection only changes through
    Rework.
  - **Brief & angles:** read-only, the brief and the psychological angles.
  - **Thumbnail concepts:** read-only.
  - **Pairing:** read-only, the title × thumbnail validation matrix.
  - **Final package:** one format at a time.
    - *Finalists* are cards with the rendered image, title, thumbnail text,
      concept and the validation, promise, hook and redundancy checks.
      Non-acceptable packages are folded away.
    - *Accept* needs a chosen package and every "Accepting confirms" check.
      *Rework* needs a target (title directions, thumbnail concepts or script
      branch) and an instruction, with the classic confirmation.
  - **Same requests.** Both gates post exactly what the classic panels post.
  - **Image approval.** Approving rendered thumbnail images (subject photo,
    accent and render) stays in the classic Thumbnail panel, and the Final
    package tab says when an image still needs approval.
- `/produce#<tab>` — **Produce** (D-122, D-159): the production gates on the
  shared review workspace, posting exactly what the classic panels post. The
  tab strip is grouped by who decides: **Your decisions** (Budget, Footage
  rights, Final export, Publish), **Held by gate policy** (Visual plan, Final
  audio, Choose visuals, Rough cut, Edit preview; shown only while one holds
  an item for you, or with "Include decided items and empty gates"), and
  **Tools** (Generate visuals, Tesseract). Gate Reviews and Packaging use
  the same grouping. **Budget** lists every paid decision (narration spend
  and visual spend) with the video's committed spend against its target and
  ceiling; `#narration` and `#spend` links land there.
  - **Narration spend:** quote, initial estimate and worst-case ceiling.
    Accepting needs every spend check and confirms the amount.
  - **Choose visuals:** candidate cards per shot. Blocked candidates cannot
    be picked, and a shot whose storyboard changed waits for re-search.
  - **Footage rights:** approving needs a documented editorial purpose, plus
    an optional context note.
  - **Rough cut:** scenes with their assignments. Rework is routed to one
    shot's visual, to pacing (format) or to audio (voice).
  - **Visual spend:** a per-shot maximum that must be above zero and within
    the hard cap, with a confirmation; or keep the placeholder, or retry
    existing footage with an instruction.
  - **Edit preview** and **Final export:** video players, approve or return
    to visuals, narration or sound (returns need a note). Final approval
    binds the rendered bytes and publishes nothing.
  - **Kept in the classic view:** asset registration (final narration audio,
    managed and generated visuals, final sound) and storyboard shot editing.
  - **Confirm spend (D-166):** a thumbnail or visual generation call that
    failed after it was sent (timeout, provider error) keeps its estimate
    committed and appears first on the Budget tab as "Confirm spend", with
    the error and a cost field: "It cost this much" records the amount,
    "It cost nothing" releases it. The per-video list counts such calls.
  - **Resumable upload (D-167):** the Publish tab saves the YouTube upload
    session before sending bytes; after an interruption the button reads
    "Resume upload to YouTube" and continues the same session, so one video
    is never uploaded twice.
- `/analysis` — **Workspace** (formerly Analyze & Create): every review panel,
  reachable under Productions. Its stage strip is a progress indicator, not
  navigation.
- `/tools` — **Tools & Diagnostics** (D-123), refreshed every 15 seconds and
  whenever a job changes:
  - **System Health:** yt-dlp, FFmpeg, the YouTube Data API key (present or
    not, never its value), Kokoro, agent-reach, the radar scheduler, and the
    FAIR, Vision and vidIQ Doctors. Each check has a status and a reason.
    Where an action fixes it, a Run Doctor or Install button runs that
    predefined action.
  - **Doctor (D-169):** one click tests every key and binary for real: the
    YouTube key with a live Data API call, the Gemini key and billing flag,
    FFmpeg, FFprobe, yt-dlp, the search backends, Kokoro with espeak-ng, the
    narration and image providers, the upload OAuth values and free disk.
    Each row shows its result and how long it took; secrets are never shown.
  - **Orphaned jobs (D-169):** when the UI starts it settles a job the last
    run left RUNNING: a live process is stopped and recorded ORPHANED, a gone
    one INTERRUPTED, both with a note in Recent Jobs.
  - **Recent Jobs:** the last 30 jobs with status, times and exit code.
    *Logs* opens the saved log (the last 60,000 characters).
  - **Advanced:** raw output shortcuts, then collapsible sections for the
    manual pipeline controls and scheduler, the pipeline state, and the
    safeguards.

The Live Job console is global. The top bar shows a health pill (failed job or
a radar scheduler that has missed three wakes) next to the job indicator,
which opens a slide-out drawer from any view; the sidebar footer shows the
workflow and scheduler state. Background polling continues while navigating.

The local server serves the same application shell at every route, so a
view can be refreshed or bookmarked directly without returning a 404.

### Visual consistency (D-125)

- **One style per element.**
  - Buttons default to the small text size; only the Command Center's main
    action is larger.
  - Empty states share one quiet, full-width style.
  - Gate reviews, Packaging and Produce share the same underline tab bar.
  - Filters (inbox, productions, radar formats) keep the pill style.
- **No repeated titles.** A page's title and subtitle appear once, in the
  top bar.
- **Tidy text.** Headings are balanced across lines, and counts use
  fixed-width digits so they don't shift as they change.

### Adversarial regression audit (D-127)

The redesign was attacked, not just tested.
- **Code review.** Three independent reviews compared every gate's request
  with the classic panel and the server, every HTML template with its
  escaping, and every route with the old behaviour.
- **Browser harness.** The pages were fed real-shaped data carrying script
  payloads, malicious URL hashes, failing APIs, a slow refusing server and
  very long titles.
- **Result.** No payload executes. A refused decision keeps the reviewer's
  choices and note. Decided gates stay locked as in the classic panels.
  Pending rough cuts are listed. API reads refuse foreign Host headers.
  `test_regression_audit.py` pins each fix.

### Web Interface Guidelines (D-126)

The UI is checked against Vercel's Web Interface Guidelines; the
universal rules apply here.
- **Links are links.** Anything that navigates is an `<a href>`, so
  Ctrl/Cmd-click and "open in new tab" work. Every tab, including the
  inbox tabs, is in the URL, so refresh, Back and shared links restore it.
- **Phones.** Every control is at least 44 px tall, and inputs use 16 px
  text so iOS does not zoom in. Drawers and logs keep their scroll inside.
- **Forms.**
  - Inputs have names, and URL and path fields have spellcheck off.
  - Descriptive placeholders end with an ellipsis.
  - Closing or reloading the tab with a typed but unsent review note asks
    for confirmation first.
- **Details.**
  - Every transition lists its properties (no `transition: all`).
  - The browser chrome matches the dark background.
  - Job times follow your locale.

### Keyboard, screen readers and small screens (D-124)

Every route is checked with axe-core at 320, 640 (1280 at 200% zoom), 768
and 1280 px, with no violations and no horizontal scrolling.
- **Moving around.**
  - *Skip to content* is the first Tab stop.
  - After a navigation, focus moves to the page title.
  - In every tab bar, ← and → switch tabs, and Home and End jump to the
    first or last.
- **Overlays.** The live job drawer, the evidence drawer and the phone menu:
  - take focus when they open;
  - keep Tab inside;
  - close with Escape and return focus to the control that opened them.

  While closed they are `inert`, so off-screen controls never take focus.
- **Screen readers.**
  - Toasts are announced; errors interrupt, other messages wait their turn.
  - The job indicator announces the job's status and name, even on phones
    where its text is hidden.
- **Visuals.**
  - Primary buttons use a darker blue fill, giving 5.2:1 text contrast
    (previously 3.4:1).
  - With *reduce motion* set, animations, transitions and smooth scrolling
    are turned off.
  - In forced-colors (Windows high contrast) mode, the focus ring and status
    badges stay visible.

### Productions derived from files

`GET /api/productions` (also `productions` in `/api/status`) is computed by
`experiment_ui/productions.py` from the artifact state the server already
builds; nothing is stored. A production is a concept with an ACCEPT decision at
the Concept Gate. Its stage is the first of Research → Script → Package →
Format → Produce whose output is not yet current for that concept, and Done
when every branch has a current final render. Its status is:

- **Needs your review** — a decision for this concept is pending at that
  stage's gate (research claims, scripts, title direction, format plan, voice
  performance).
- **Blocked** — the gate sent it for rework or rejected it.
- **Ready to run** — the next automatic step can run.
- **Complete** — all branches rendered.

Gates that are still global rather than per concept (narration spend, visual
candidates and rights, rough cut, edit preview, final export) are not yet
attributed to a single production; they stay on the Command Center hero.

`GET /api/production?concept_id=…` returns one production with its eight
workspace sections (404 when the concept is no longer accepted). Each
production's `updated_at` is the newest modification time of its artifacts.
Every engine names per-concept files `<slug>.…`, so one directory scan per
stage folder finds them without reading any file.

### Front-end files

`static/css/tokens.css` holds every design token (surfaces, text, accent, the
four state colours `--status-human|running|blocked|complete`, spacing, type,
radius, shadow, motion, z-index) and aliases the old variable names so
`styles.css` keeps working while later patches move its rules across.
Split-out files so far: `static/css/shell.css`, `command-center.css`,
`opportunity.css`, `review.css`, `production.css` and `packaging.css`; `static/js/production-workspace.js`, `gate-reviews.js`, `packaging.js`, `produce.js`, `static/js/command-center.js`,
`review-workspace.js` (the shared review workspace), `opportunity-review.js`
and `radar.js`. Modules talk to `app.js` only through the small `window.YP`
API (inbox data, the shared decision dispatcher, the evidence drawer). The server serves
`/css/*.css` and `/js/*.js` only: one directory level, an allowlisted extension
per folder, no dotfiles, and a resolved path that must stay inside that folder.

Status codes on every page are shown as sentences (D-170): the catalogue in
`experiment_ui/plain_language.py` is served once per page load and any code it
does not carry is turned into a sentence by shape, so nothing like
`WAITING_FOR_DRAFT_RESEARCH_PACKAGES` reaches the screen.

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

The shipped configuration uses the free local Kokoro voice as the narration
provider (D-168): the contract is the model's Apache-2.0 licence and voice
list, the quote is written by the system at $0 and bound to the request, and
the spend gate runs as usual. A paid HTTP provider stays supported: copy
`paid_provider_example` over the provider keys in
`production_engine/narration_render_config.json`, verify its contract, set
the price and API key variable, and match `voice_performance_config.json`;
the system still never guesses a price.

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

## Slice 15 — Candidate selection → Human Rights/Context Gate

Slice 15 fills the logical stage between Slice 14 and Slice 16.

After zero-cost discovery stops at the Human Visual Candidate Gate, each
selected candidate is classified from its actual rights/source metadata rather
than trusting a stored UI state.

Verified reusable assets can continue toward safe asset acquisition. Recognized
creator/editorial footage is recorded as:

`SELECTED_PENDING_RIGHTS_CONTEXT_GATE`

and the workflow stops at:

`HUMAN_VISUAL_RIGHTS_GATE`

The reviewer must either reject the footage or document the intended
transformative/editorial purpose. Approval is context authorization for the
pipeline, not a legal determination and not permission to auto-download the
creator footage.

The Rights Gate revalidates the exact current search result, candidate-review
hash, shot fingerprint and candidate fingerprint before accepting a decision.
If the upstream search/storyboard changed, the old rights decision cannot be
used.

Unknown or unsupported rights tiers fail closed; a source cannot gain
eligibility merely by claiming it needs human review.

The candidate UI now distinguishes:
- a selection with verified reuse rights; and
- a selection that still requires Rights/Context review.

After the Rights Gate is complete, Slice 16 handles safe asset acquisition and
rough-cut preparation.

## Slice 17 — Human Rough-Cut approval → Visual Spend boundary

After the Human Rough-Cut Gate accepts the current rough cut with unresolved
gaps, Continue Automatically runs deterministic zero-spend gap planning and
then stops.

The possible Slice 17 endpoints are:

```text
HUMAN_ROUGH_CUT_GATE
        ↓
Plan Remaining Visual Gaps
        ↓
HUMAN_VISUAL_SPEND_GATE
```

when a high-value unresolved shot qualifies for premium generation, or:

```text
VISUAL_GAPS_READY_NO_SPEND
```

when no unresolved shot reaches the premium threshold.

After every premium candidate receives a human decision, Slice 17 stops at
`VISUAL_SPEND_DECISIONS_COMPLETE`. Generation briefs and edit assembly are
left to the next slice.

Gap planning is provenance-bound to the exact current rough cut and exact
rough-cut approval. Old gap plans are removed after rough-cut rework or
mutation.

The spend gate enforces both the per-shot cap and one workflow-wide USD cap
across every current branch. Authorizations are serialized so simultaneous
approvals cannot race past the workflow cap. NaN, Infinity, stale plans and
invalid spend configuration fail closed.

Choosing **Authorize Generation** records only a maximum permitted spend. It
does not call a provider, create a generation job, or spend money in Slice 17.

## Slice 18 — Visual Spend decisions → generation briefs / assembly boundary

After Slice 17, Continue Automatically may perform at most two new zero-cost
steps:

```text
Completed Human Visual Spend / no-spend decision
        ↓
Prepare Premium Visual Generation Briefs   (authorized shots only)
        ↓
Build Visual Edit Assembly Plan
        ↓
STOP
```

When there is no authorized premium generation, the brief step is skipped.

The assembly stop state tells the reviewer exactly what remains:

- `VISUAL_ASSEMBLY_READY` — current timeline is ready for the next edit-preview
  slice;
- `WAITING_FOR_PREMIUM_VISUAL_ASSETS` — current human-authorized generation
  briefs exist, but the app has not called a paid provider;
- `WAITING_FOR_LOCAL_VISUAL_ASSETS` — approved local/editorial files still
  need to be registered;
- `WAITING_FOR_VISUAL_ASSETS` — both premium and local assets are missing; or
- `VISUAL_EXISTING_RETRY_REQUIRED` — a human chose Retry Existing and the
  requested free/existing search must be performed before edit-preview work.

Generation briefs are provider-neutral handoff artifacts. They preserve the
human maximum spend but set provider-call and execution authorization to false.

The workflow does not automatically continue into edit-manifest creation or
FFmpeg preview rendering in Slice 18.

## Slice 19 — current visual assembly → free structural edit preview gate

When Slice 18 reaches a fully edit-ready visual assembly, Continue Automatically
runs:

```text
Current Visual Assembly
        ↓
Build Edit Preview Manifest
        ↓
Render Free Structural Edit Preview (local FFmpeg only)
        ↓
HUMAN_EDIT_PREVIEW_GATE
```

The manifest is provenance-bound to the exact current visual assembly,
QC-passed narration audio/timing and approved sound-design intent. Any later
change makes the old manifest and preview stale.

The preview renderer uses only the configured local FFmpeg binary. If FFmpeg is
not available, the workflow stops at `LOCAL_FFMPEG_REQUIRED`. There is no
paid/cloud rendering fallback.

The preview may contain approved low-value placeholders, but it is never marked
publish-ready and does not generate music or SFX.

At the Human Edit Preview Gate, the reviewer can:

- approve the structural edit direction;
- return visuals for rework;
- return narration for rework; or
- return sound for rework.

A return decision requires a specific human note. Slice 19 preserves the
instruction and stops; routing/rebuild behavior belongs to the next slice.

After approval, Slice 19 stops at `EDIT_PREVIEW_DIRECTION_APPROVED`. It does
not automatically run final production handoff.
