# Research Engine Framework

## Purpose

The Research Engine turns human-accepted concepts into traceable research
packages for the future Story / Script Engine.

The deterministic Research Engine itself does not browse the web or call an
LLM.

The guided workflow adds two separate bounded layers:

1. `research_acquisition.py` searches the web through Agent Reach's Exa path
   and retrieves the actual pages through Jina Reader.
2. `research_model_runner.py` uses FAIR free-only routing to structure claims
   only from those acquired pages.

The deterministic validator still does not decide that a claim is true simply
because multiple sources agree. Human Research Gate approval remains required.

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


## Guided Research workflow

The creator-facing path is:

~~~text
Prepare Research Plans
        ↓
Acquire Research Evidence
        ↓
Structure Research Claims
        ↓
Prepare Research Gate
        ↓
Human claim-by-claim review
        ↓
READY_FOR_STORY_SCRIPT
~~~

### Source grounding boundary

Every acquired evidence file is bound to the SHA-256 of its current research
plan. Every FAIR response is bound to both the current plan SHA-256 and acquired
evidence SHA-256.

The FAIR response schema restricts source IDs and URLs to the pages that were
actually acquired. A deterministic post-model check rejects any source
ID / URL pair outside that acquired set.

The model is instructed to leave a research question unresolved rather than
invent a source or unsupported claim.

### Story / Script boundary

Research may move forward only when the human Research Gate has accepted at
least one claim for every original concept question and every package research
dependency. Otherwise the verified package remains `RESEARCH_INCOMPLETE`.
