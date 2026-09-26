# Experiment 02 Analysis Model Runner

## Purpose

The analysis-model runner automates the first-pass Experiment 02 analysis while
keeping the evidence discipline built in earlier stages.

The current adapter is FAIR — Free AI Router.

The runner does not call a provider directly. It sends a prepared Experiment 02
analysis request to FAIR, requires a schema-valid JSON response, restricts the
response to evidence the model was actually shown, then passes the result
through the deterministic Experiment 02 apply gate.

## Architecture

~~~text
Enriched profile
      ↓
analysis_execute.py --mode prepare
      ↓
analysis request
      ↓
analysis_model_runner.py
      ↓
FAIR subprocess bridge
      ↓
free-only provider routing
      ↓
schema-valid model response
      ↓
request-scope evidence restriction
      ↓
merge_analysis_response()
      ↓
analyzed profile
~~~

FAIR validates response structure.

Experiment 02 validates evidence support.

These are deliberately separate controls.

## Why a subprocess bridge

FAIR already has its own Python environment and dependencies.

The YouTube project runner therefore executes fair_bridge.py using FAIR's Python
interpreter rather than requiring FAIR's dependencies to be installed into the
YouTube project's Python environment.

On the current Windows layout, the runner automatically looks for:

~~~text
C:\FAIR Free AI Router
C:\FAIR Free AI Router\.venv\Scripts\python.exe
C:\FAIR Free AI Router\.env
~~~

when the YouTube repository is at:

~~~text
C:\Youtube Production
~~~

The paths can be overridden with these environment variables:

- FAIR_REPO_PATH
- FAIR_PYTHON
- FAIR_ENV_FILE

## Free-only provider confirmation

The runner does not auto-confirm recurring free-tier provider accounts.

FAIR itself automatically enforces zero-cost routing for gateways such as
OpenRouter Free and Kilo Free that can prove zero price at runtime.

For providers that require an operator assertion that the current account is
free-only, define:

FAIR_CONFIRMED_FREE_PROVIDERS

as a comma-separated list of FAIR provider IDs.

Example:

~~~text
FAIR_CONFIRMED_FREE_PROVIDERS=google_gemini_api,groq
~~~

Only add a provider when you have actually confirmed that account cannot
auto-bill or incur paid API usage.

The value can be placed in FAIR's existing .env or in the process environment.

## Doctor

Before running a model:

~~~powershell
python .\experiment_02_analysis\analysis_model_runner.py --mode doctor
~~~

Doctor mode performs no inference. It reports:

- detected FAIR repository;
- detected FAIR Python interpreter;
- FAIR environment file;
- confirmed free providers;
- safely eligible FAIR providers/models; and
- providers FAIR skipped.

Credentials are never printed.

## Run one analysis

First prepare the request:

~~~powershell
python .\experiment_02_analysis\analysis_execute.py --mode prepare --profile ".\experiment_02_analysis\output\profiles_enriched\VIDEO_ID.json"
~~~

Then run it:

~~~powershell
python .\experiment_02_analysis\analysis_model_runner.py --mode run --request ".\experiment_02_analysis\output\analysis_requests\VIDEO_ID.analysis_request.json"
~~~

The analysis request already contains the source profile path. Use --profile
only when overriding it is necessary.

## Batch

~~~powershell
python .\experiment_02_analysis\analysis_model_runner.py --mode batch --requests-dir ".\experiment_02_analysis\output\analysis_requests"
~~~

The default batch limit is four model runs per invocation.

Already-applied requests with the same SHA-256 hash are skipped.

Use --max-requests N to lower or raise the local batch limit.

Use --force to deliberately rerun a previously applied request.

Batch execution is sequential by design. This avoids unnecessary bursts
against free-tier provider rate limits.

The batch stops early on a cost-policy violation, local runner error, or FAIR
infrastructure failure.

## FAIR configuration

Defaults are stored in analysis_model_runner_config.json.

Current defaults:

- quality level: standard;
- maximum answered attempts: 3;
- maximum unanswered attempts: 6;
- model timeout: 45 seconds;
- cross-check: off;
- output budget: 8192 tokens;
- FAIR cache: bypassed;
- subprocess timeout: 300 seconds.

The runner does not store API credentials.

## Response schema

The runner dynamically generates a JSON Schema from each analysis request.

It locks:

- the exact video ID;
- all required analysis dimensions;
- the controlled mechanism-ID vocabulary;
- finding shape;
- confidence labels;
- transfer-item shape; and
- Source Dependency Test shape.

FAIR's schema validator therefore rejects malformed output before it reaches the
Experiment 02 apply gate.

## Evidence scope

A model may cite only evidence IDs that were present in the analysis request's
evidence_library.

Before apply, the runner removes any evidence reference outside that request
scope.

This is important because the enriched source profile may contain more evidence
than was included in a compact model request.

A claim that loses its support after scope restriction is routed to
working_hypotheses by the existing apply gate.

## Fail-closed behavior

The runner does not report APPLIED when:

- FAIR reports ESCALATION_REQUIRED;
- FAIR reports FAILED;
- the bridge fails;
- the model output cannot be parsed;
- the response/video identity does not match;
- the final Experiment 02 profile fails validation; or
- FAIR ever reports paid_inference_executed other than False.

A paid-inference signal is recorded as COST_POLICY_VIOLATION and batch
processing stops.

## Outputs

Generated files remain under the ignored Experiment 02 output directory:

- model_runs/ — safe run metadata and provider/model identity;
- raw_model_outputs/ — accepted raw model text;
- model_responses/ — normalized request-scoped JSON response;
- profiles_analyzed/ — final evidence-gated profiles;
- model_runner_batch_summary.json — latest batch summary.

No API keys or provider credentials are written.

## Model output and copyright

The model is instructed to paraphrase source observations and cite evidence IDs
rather than reproduce long transcript passages.

The objective is to analyze transferable mechanisms, not regenerate source
scripts.
