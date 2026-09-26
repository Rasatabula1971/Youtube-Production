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
