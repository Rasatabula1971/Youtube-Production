# Human Concept Gate

## Purpose

The Concept Gate is the human decision point between Transformation Engine
concept candidates and the future Research Engine.

It does not score concepts and does not automatically select a winner.

Every concept receives one explicit decision:

- ACCEPT
- REWORK
- REJECT

## Prepare

~~~powershell
python .\transformation_engine\concept_gate.py --mode prepare
~~~

This creates:

~~~text
transformation_engine/output/concept_gate_request.json
~~~

## Acceptance criteria

An ACCEPT decision requires all configured criteria to be true:

- originality_clear
- audience_promise_clear
- source_independent
- feasible
- researchable

These are human checks, not automated performance predictions.

## REWORK

REWORK keeps the concept for revision.

A note is required explaining what needs to change.

REWORK concepts do not enter the Research Engine handoff.

## REJECT

REJECT records the concept but prevents it from moving forward.

## Apply

Complete a response using concept_gate_response_template.json, then run:

~~~powershell
python .\transformation_engine\concept_gate.py --mode apply --response ".\path\to\concept_gate_response.json"
~~~

Outputs:

~~~text
transformation_engine/output/
├── concept_gate_reviewed.json
├── research_handoff.json
└── concept_gate_summary.json
~~~

Only ACCEPT concepts enter research_handoff.json.

## Research handoff

The handoff preserves:

- concept ID;
- mechanism identity;
- working title;
- premise;
- audience promise;
- intended format;
- mechanism application;
- transformation method;
- independent research questions;
- Source Dependency Test;
- human Concept Gate decision.

The working title is not final packaging.

## Boundary

The Concept Gate decides whether an idea is worth researching.

It does not establish facts, write the script, create final packaging, or
predict performance.
