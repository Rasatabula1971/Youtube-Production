# Human Concept Gate

## Purpose

The Concept Gate is the human decision point between Transformation Engine
concept candidates and the future Research Engine.

It does not score concepts and does not automatically select a winner.

Every active concept receives one explicit decision:

- ACCEPT
- REWORK
- REJECT
- SAVE IDEA

## Prepare

~~~powershell
python .\transformation_engine\concept_gate.py --mode prepare
~~~

This creates:

~~~text
transformation_engine/output/concept_gate_request.json
~~~

## Decision logic

**ACCEPT** means the human approves the concept as-is. No criteria checkboxes are
required.

**REWORK** keeps the concept for revision. The criteria become keep/change
dimensions:

- checked = keep this part;
- unchecked = change this part.

At least one criterion must remain unchecked, otherwise there is nothing to
rework. A note is optional because the criteria already record the requested
direction.

REWORK concepts do not enter the Research Engine handoff.

**SAVE IDEA** stores the concept in the Idea / Title Bank, marks the active
concept as reviewed, and does not send it forward. If Save Idea is used from a
non-active override card or after the gate is complete, it behaves as a
bookmark-only action.

These are human decisions, not automated performance predictions.

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

Only ACCEPT concepts enter research_handoff.json. REWORK, REJECT, and SAVE IDEA
concepts do not move forward.

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


## Viewer need / gap / fit criteria

The following criteria are retained as REWORK dimensions so the reviewer can
mark what should be preserved versus changed:

- the viewer problem is specific rather than merely a broad topic;
- the viewer moment is understandable;
- the desired outcome is concrete;
- content-gap status is honest about the evidence available;
- the concept fits the intended channel/audience;
- the idea passes the three-title clarity test.

These checks do not create a concept score or ranking.
