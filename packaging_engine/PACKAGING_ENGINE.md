# Packaging Engine Framework

## Purpose

The Packaging Engine turns a human-accepted concept into several structured
title / thumbnail / opening-frame packages before script drafting.

It implements the project's package-before-script rule.

The framework does not call a model or the network itself and does not rank
package options.

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

## Apply

Place completed response JSON under:

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
