# Transformation Engine Framework

## Purpose

The Transformation Engine converts a human-confirmed Experiment 02 mechanism
handoff into structured requests for genuinely new video concepts.

It does not decide which concept is best.

It does not calculate a concept score.

It does not assume any mechanism causes performance.

Its job is to preserve transferable mechanisms while forcing the new concept to
stand independently from the source creators' expression.

## Input

Default input:

~~~text
experiment_02_analysis/output/synthesis/transformation_handoff.json
~~~

By default, only entries with:

~~~text
READY_FOR_TRANSFORMATION_ENGINE
~~~

are eligible.

Model-only drafts that still require human review are not used.

## Prepare

~~~powershell
python .\transformation_engine\transformation_engine.py --mode prepare
~~~

This creates one concept-generation request per ready mechanism under:

~~~text
transformation_engine/output/concept_requests/
~~~

Each request includes:

- mechanism identity and definition;
- replication evidence;
- topic/format scope;
- transferable descriptions;
- observed examples;
- source-specific elements to avoid;
- previously accepted transformation directions;
- source video IDs for dependency checking;
- requested concept count;
- response contract.

No model call occurs in prepare mode.

## Concept response

A response contains multiple concept candidates.

Each concept must define:

- unique concept ID;
- working title;
- premise;
- audience promise;
- format intent;
- how the mechanism is used;
- how the concept differs from the source;
- independent research questions;
- an empty source-specific-elements-used list;
- a passing Source Dependency Test.

The working title is not final packaging.

## Apply

Place completed response JSON files under:

~~~text
transformation_engine/output/concept_responses/
~~~

Then run:

~~~powershell
python .\transformation_engine\transformation_engine.py --mode apply
~~~

The engine validates every concept and writes:

~~~text
transformation_engine/output/
├── concept_candidates.json
├── rejected_concepts.json
└── summary.json
~~~

## Source Dependency Test

A structurally accepted concept requires:

- passes=true;
- source_assets_required=false;
- a rationale;
- no declared source-specific elements used;
- no direct source-video-ID dependency.

This is a minimum structural gate. The later human Concept Gate still decides
whether the idea is truly original and independent enough to continue.

## Research questions

Every concept must carry independent research questions.

This does not perform research yet. It makes sure an accepted concept can hand
off cleanly to the future Research Engine.

## Boundary

A structurally valid concept is only a candidate.

It has not yet passed the human Concept Gate and must not enter research or
script generation automatically.


## Viewer-need framing

Concept generation now requires more than a topic and audience promise.

Every concept must include:

- `viewer_problem` — the specific problem, question, or curiosity;
- `viewer_moment` — the situation or decision state in which that need matters;
- `desired_outcome` — what the viewer wants to understand, fix, avoid, or decide;
- `content_gap` — a gap hypothesis plus an explicit evidence status;
- `channel_fit` — FIT / REVIEW / UNASSESSED with rationale;
- `title_clarity_test` — at least three working title options and PASS / REFRAME.

The three-title test is an idea-clarity check, not final packaging.

A content gap may be `SUPPORTED`, `HYPOTHESIS`, or `UNASSESSED`.
`SUPPORTED` requires a non-empty evidence basis. The engine must not infer a
proven gap from views, outliers, or model intuition alone.


## Automated concept generation

The Transformation Engine now has a FAIR-backed execution layer:

~~~powershell
python .\transformation_engine\concept_model_runner.py --mode batch --requests-dir ".\transformation_engine\output\concept_requests"
~~~

The runner reuses the project's existing FAIR subprocess bridge and the same
free-only cost policy used by Experiment 02. FAIR is always attempted first.
The separate project-level `DIRECT_GEMINI_API_KEY` is eligible only when FAIR
explicitly reports that its free routes are exhausted or unavailable and
confirms `paid_inference_executed: false`. The repo-local Gemini chain is
free-tier-only (Flash-Lite, then Flash by default); FAIR quality/internal
failures do not bypass into Gemini, and no paid inference route is allowed.

The execution path is:

~~~text
Experiment 02 transformation handoff
        ↓
Prepare concept requests
        ↓
FAIR free-only concept generation
        ↓
Deterministic Transformation validation
        ↓
concept_candidates.json
        ↓
Human Concept Gate
~~~

Model output does not bypass `validate_response()`. Source-dependent concepts,
invalid viewer-need framing, unsupported gap claims, weak title-clarity output,
missing research questions, and malformed Source Dependency Tests are rejected
before the human gate.

### Concept generation settings (D-146, D-147, D-148)

`transformation_engine/concept_model_route.json` holds three settings:

- **`concepts_per_call`** (currently 2). A mechanism's concepts are generated in
  several calls of at most this many concepts. Each call sees the working
  titles and premises of the concepts already accepted and is asked for
  different ones. Only concepts that pass validation count towards the
  requested number; one spare call covers a call that returns nothing usable,
  and concepts from successful calls are kept if a later call fails. The
  model-run report lists every call. Without the setting, all concepts are
  requested in one call. Reason: free models dropped `human_framing` and
  `viewer_need_evidence` when asked for five full concepts at once.
- **`route`** (currently `"fair"`). `"fair"` uses free models through FAIR.
  `"direct_gemini"` uses the project's `DIRECT_GEMINI_API_KEY` only, with no
  FAIR and no fallback; it is free only while the key's Google Cloud project
  has no billing enabled, and it departs from vision §101, so it is a manual
  override rather than the default.

- **`pause_between_calls_seconds`** (currently 65). The minimum gap between
  any two concept calls, across mechanisms and across automatic steps; the
  time of the last call is kept in `output/concept_call_clock.json`. Groq's
  free tier limits tokens per minute. A call that FAIR still reports as rate
  limited waits this long and is retried once (D-148, D-149).

The schema sent to the provider keeps every field bound (drama levels 4–10,
3–5 opening moments and so on). The prompt also states the cross-field drama
rules a schema cannot express: target no higher than capacity, and the story
curve reaching the target. Only the number of concepts in one answer is left
to the runner.

These settings are outside the validation contract, so changing them does not
regenerate mechanisms that already validated. Every concept still goes through
`validate_response()`.

`concept_diagnose.py` sends one mechanism's prompt straight to Groq and saves
what comes back (error, refused text, finish reason, per-concept validation);
`--inspect` compares the requests and `--count` asks for fewer concepts.

### Mechanism coverage (D-129)

The system prepares one concept request per transferable mechanism. A batch can
stop part-way and resume later: validated responses are kept and only missing
mechanisms are retried.

Concept Triage starts only when the merged pool is current, meets
`minimum_candidates_for_triage` (default five), **and every requested mechanism
has contributed at least one validated concept**. Until then:
- the merge reports `INCOMPLETE_MECHANISM_COVERAGE` with the missing mechanism
  IDs;
- concept generation stays the next step;
- the automatic runner stops with an explanation rather than handing an
  incomplete pool to the Concept Gate.

A mechanism whose output fails validation is reported with its validation errors
and rerun on the free route; it is never "repaired" through direct Gemini.

Provider failures remain visible in the batch report; degraded readiness does
not convert failed model calls into successful ones.

### Provenance

Every prepared concept request records the SHA-256 of the current Experiment 02
transformation handoff.

Runner-produced concept responses record the exact concept-request SHA-256.
The deterministic merge rejects a runner response whose request hash no longer
matches the current request.

When the Experiment 02 synthesis changes, stale Concept Gate artifacts are
invalidated before new concept requests are prepared.

### Selection boundary

The model generates options. It does not score, rank, or choose a winner.

Human review remains responsible for originality, audience promise, viewer need,
content-gap honesty, channel fit, title clarity, source independence,
feasibility, and researchability.
