# Research Engine Framework

## Purpose

The Research Engine turns human-accepted concepts into traceable research
packages for the future Story / Script Engine.

It does not browse the web by itself.

It does not call an LLM.

It does not decide that a claim is true simply because multiple sources agree.

## Input

Default input:

~~~text
packaging_engine/output/research_handoff.json
~~~

Only concepts with a human-approved package should appear there.

The approved package is preserved in the research plan. Its research
dependencies are appended as mandatory package questions with stable IDs such
as `pkgq001`.

## Prepare

~~~powershell
python .\research_engine\research_engine.py --mode prepare
~~~

This creates one plan per accepted concept:

~~~text
research_engine/output/plans/
~~~

Each original concept research question receives a stable ID such as:

~~~text
rq001
rq002
~~~

## Research response

A research response contains two explicit collections:

### Sources

Every source records:

- source ID;
- title;
- publisher / organization;
- URL when applicable;
- source type;
- publication date when known;
- access date when known;
- provenance note.

Source types are descriptive rather than a numeric authority score:

- primary;
- secondary;
- dataset;
- documentation;
- expert_statement.

### Claims

Every potential factual claim records:

- claim ID;
- statement;
- role: core, supporting, or context;
- linked research-question IDs;
- evidence links.

Each evidence link records:

- source ID;
- stance: SUPPORTS, CONTRADICTS, or QUALIFIES;
- locator;
- short paraphrased evidence note.

The framework is designed to preserve disagreement rather than silently merge
conflicting sources.

## Apply

Place completed research response files under:

~~~text
research_engine/output/research_responses/
~~~

Then run:

~~~powershell
python .\research_engine\research_engine.py --mode apply
~~~

Draft packages are written to:

~~~text
research_engine/output/draft_packages/
~~~

## Claim coverage states

The engine computes structural evidence states:

### UNSUPPORTED

No supporting source is linked.

### SINGLE_SOURCE

One source supports the claim and no contradiction is recorded.

### MULTI_SOURCE

At least two source IDs support the claim and no contradiction is recorded.

### CONFLICTED

At least one source contradicts the claim.

These states are not truth labels.

MULTI_SOURCE does not mean VERIFIED.

CONFLICTED does not automatically mean false.

Human review decides whether wording and evidence are suitable for script use.

## Research-question coverage

Each draft package reports which concept research questions have at least one
claim associated with them.

Missing coverage remains visible.

The later Research Gate uses this to prevent unresolved research from silently
moving into scripting.

## Copyright / source-use boundary

Evidence notes should be short paraphrases.

The Research Engine is for factual traceability, not copying source prose into
the script.

## Next gate

Draft research packages go to the human Research Gate.

Only Research Gate accepted claims may enter the verified research package used
by the future Story / Script Engine.


## Package research dependencies

Packaging occurs before deep research and Story / Script.

Every approved package carries factual/evidentiary dependencies. The Research
Engine converts them into mandatory `pkgq...` research questions alongside the
original concept questions.

The Research Gate therefore cannot mark the package READY_FOR_STORY_SCRIPT
while a promise-critical package dependency remains unresolved.
