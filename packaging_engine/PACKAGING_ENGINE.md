# Packaging Engine Framework

## Purpose

The Packaging Engine turns a human-accepted concept into several structured
title / thumbnail / opening-frame packages before script drafting.

It implements the project's package-before-script rule.

The deterministic framework does not call a model or the network itself and
does not rank package options. The guided workflow may invoke the separate
`package_model_runner.py`, which uses FAIR free-only routing and then returns
responses to this deterministic validator.

## Input

Default input:

~~~text
transformation_engine/output/research_handoff.json
~~~

This contains concepts already accepted by the human Concept Gate.

## Prepare

~~~powershell
python .\packaging_engine\packaging_engine.py --mode prepare
~~~

One package-generation request is created per accepted concept.

Each request carries:

- premise;
- provisional audience promise;
- format;
- mechanism;
- transformation method;
- existing research questions;
- source-dependency result;
- Concept Gate provenance.

## Package contract

Each proposed package must include:

- title;
- thumbnail message;
- thumbnail visual concept;
- optional thumbnail text overlay;
- opening-frame purpose and visual concept;
- expected viewer;
- awareness level;
- one core promise;
- curiosity gap;
- expected payoff;
- format intent;
- explanation of how title and thumbnail complement each other;
- factual/evidentiary dependencies that downstream research must verify.

The title and thumbnail are treated as one communication unit.

## Generate with FAIR

The guided workflow can run all current requests through FAIR free-only routing:

~~~powershell
python .\packaging_engine\package_model_runner.py --mode batch
~~~

Each generated response is bound to the SHA-256 of its exact package request.
Requests are bound to the current accepted-concept handoff. Paid inference is
fail-closed.

## Apply

For manual/offline use, place completed response JSON under:

~~~text
packaging_engine/output/package_responses/
~~~

Then run:

~~~powershell
python .\packaging_engine\packaging_engine.py --mode apply
~~~

Outputs:

~~~text
packaging_engine/output/
├── package_requests/
├── package_responses/
├── package_candidates.json
├── rejected_packages.json
└── summary.json
~~~

Structural acceptance does not approve a package for use. Human Packaging Gate
approval is still required.

The guided UI uses `package_review.py` to review one package at a time and
enforces at most one accepted package per concept.

## Boundary

The Packaging Engine does not:

- score clickability;
- predict CTR;
- declare one package the winner;
- permit misleading promises;
- write the script;
- assume package facts are already verified.

Research dependencies explicitly capture what must be verified before the
package can safely control the script.


## Viewer-need packaging contract

Each package must preserve the accepted concept's viewer need and include:

- `viewer_problem`;
- `viewer_moment`;
- `desired_outcome`;
- `one_sentence_promise`;
- `gap_positioning`;
- `channel_fit_alignment`.

The one-sentence promise should make the value easy to understand in the form:

~~~text
This video helps [specific viewer/problem] so they can [specific outcome].
~~~

Gap positioning must not upgrade a `HYPOTHESIS` or `UNASSESSED` gap into a
proven audience fact.

## Slice 23 architecture migration — post-script title direction

Packaging v1.0 changes the active sequencing contract. The legacy Packaging
Engine in this directory remains available to read historical artifacts and
resume older runs, but it is no longer an active prerequisite before Research.

New active sequence:

```text
accepted concept
→ verified research
→ approved story/script
→ 5 Short title directions + 5 Long-form title directions
→ Human Title Direction Gate
→ mature Packaging Engine (next slice)
```

### Internal working title versus public title

Story, Script and Format require a stable internal title for provenance and
artifact identity. That value is now marked `INTERNAL_WORKING_TITLE` and must
not be interpreted as the final public YouTube title.

Legacy `selected_titles` are ignored when generating current Script/Format
artifacts. A public title may be rewritten later without invalidating approved
narration merely because wording changed.

### Post-script 5+5 title directions

`title_direction.py` prepares one request per exact current
`approved_script_bundle`. It carries:

- opening hook and hook mechanism;
- approved script section outline;
- story question and payoff intent;
- approved evidence claims;
- five configured psychological angles;
- Short versus Long-form identity;
- title-length guidance rather than a hard 60-character cutoff.

`title_direction_model_runner.py` uses the existing FAIR free-first routing
policy. It requests exactly five Short and five Long-form directions and fails
closed on invented evidence references or malformed stable IDs.

Each candidate stores:

- `title_id`;
- `format`;
- `title_text`;
- `psychological_angle`;
- `primary_driver`;
- `secondary_driver`;
- `core_claim`;
- `evidence_refs`;
- `character_count`;
- `search_intent`.

No viral score, CTR prediction or automatic winner ranking is produced.

### Human Title Direction Gate

`title_direction_review.py` requires one Short and one Long-form selection per
concept. A selection records a preferred psychological/title direction and is
explicitly **not** final wording.

The selected artifact uses:

`PREFERRED_TITLE_AND_PSYCHOLOGICAL_DIRECTION_NOT_FINAL_WORDING`

and stores `final_wording_editable_later=true`.

Rework is scoped to `TITLE_DIRECTIONS_ONLY`. It changes the title-direction
request, invalidates only the title-generation response/candidate aggregate,
and leaves approved script/evidence untouched.

Historical selections are archived append-only. Current state is bound to the
candidate-set SHA-256; stale candidate sets reopen the gate.

### Slice 23 boundary

The successful boundary is:

`TITLE_DIRECTION_SELECTED`

Format and Production remain held after that point until Slice 24 builds the
Packaging Brief and Viewer Promise Contract and begins mature title/thumbnail
coordination.
