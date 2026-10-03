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


## Thumbnail design contract and design advisories

Each package also declares the design of the title / thumbnail unit:

- `title_keyword` — the main search keyword, placed near the front of the title;
- `thumbnail.focal_subject` — the single thing the eye lands on first;
- `thumbnail.visual_elements` — every distinct visual element (focal subject
  included);
- `thumbnail.visual_cues` — arrows or circles, if any;
- `thumbnail.palette` — `background`, `subject` and `accent`;
- `division_of_labor` — what the thumbnail carries (emotion / curiosity) and
  what the title carries (context / fact).

Missing or malformed design fields reject the package structurally.

Generic published guidance is then checked as **non-blocking advisories**
(`packaging_advisories`, each marked `evidence_status: HYPOTHESIS`). Thresholds
live in `packaging_config.json` under `design_advisories`:

| Advisory | Default starting hypothesis |
|---|---|
| `TITLE_LENGTH` | 40-60 characters |
| `TITLE_KEYWORD_MISSING` / `TITLE_KEYWORD_LATE` | keyword starts within the first 30 characters |
| `THUMBNAIL_TEXT_WORDS` | 3-5 words when overlay text is used |
| `THUMBNAIL_TEXT_REPEATS_TITLE` | at most 60% of overlay content words repeated from the title |
| `THUMBNAIL_ELEMENT_COUNT` | at most 3 distinct visual elements |
| `THUMBNAIL_CUE_COUNT` | at most 2 arrows / circles |

Advisories are shown to the human Packaging Gate and carried into the research
handoff. They never reject a package and never produce a score. Remove the
`design_advisories` block to disable them. See D-070.

## Niche thumbnail conventions

When `channel_niche` is set in `packaging_config.json` and a niche thumbnail
tabulation exists, each package request carries `niche_thumbnail_conventions`.
See `NICHE_THUMBNAIL_STUDY.md` and D-071.
