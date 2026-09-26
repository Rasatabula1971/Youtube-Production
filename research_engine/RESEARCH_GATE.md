# Human Research Gate

## Purpose

The Research Gate is the human verification point between draft research and
the Story / Script Engine.

The Research Engine records evidence structure.

The Research Gate decides which claims are safe to carry into scripting.

## Prepare

For one draft package:

~~~powershell
python .\research_engine\research_gate.py --mode prepare --draft ".\research_engine\output\draft_packages\CONCEPT_ID.draft_research_package.json"
~~~

Or prepare all current drafts:

~~~powershell
python .\research_engine\research_gate.py --mode batch-prepare
~~~

Review packets are written under:

~~~text
research_engine/output/review_requests/
~~~

Each claim is shown with its linked source, stance, locator, and evidence note.

## Decisions

Every claim receives exactly one decision:

- ACCEPT
- REWORK
- REJECT

There is no automatic acceptance based on source count.

## ACCEPT criteria

All configured criteria must be true:

- source_traceable;
- wording_supported;
- conflicts_addressed;
- safe_for_script.

A claim with coverage state CONFLICTED also requires a written resolution note.

## REWORK

REWORK requires a note explaining what research or wording must change.

REWORK claims are not handed to scripting.

## REJECT

Rejected claims remain in the review record but are not handed forward.

## Research-question completion

After claim decisions, the gate checks the original concept research questions.

A question is RESOLVED_FOR_SCRIPT only when at least one accepted claim links to
that question.

If any question remains uncovered, the final package status is:

~~~text
RESEARCH_INCOMPLETE
~~~

Only when there is at least one accepted claim and every research question is
covered does the package become:

~~~text
READY_FOR_STORY_SCRIPT
~~~

## Verified research package

The gate writes a verified research package containing:

- concept context;
- original research questions;
- question-resolution state;
- unresolved question IDs;
- only sources used by accepted claims;
- only accepted claims;
- human Research Gate provenance.

Here, verified means human-approved for this project's script use. It does not
mean universal or permanent truth.

## Boundary

The future Story / Script Engine must stay within the wording and evidence scope
of accepted claims.

Research Gate approval does not authorize copying source prose. Evidence notes
remain provenance aids, not script text.
