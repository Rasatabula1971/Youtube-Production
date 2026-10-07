# Human Research Gate

## Purpose

The Research Gate is the verification point between draft research and the
Story / Script Engine. Review is conditional (D-131): an evidence policy
accepts strongly supported claims on its own, and a human decides the rest.

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

A decision comes from a human or, for a claim the evidence policy clears, from
the policy itself (`decided_by: EVIDENCE_POLICY`).

## Conditional review (evidence policy)

`evidence_policy.py` classifies every claim when the gate is prepared. Each
evidence quote has already been found verbatim in its acquired page.

- **AUTO_CLEARED** — accepted automatically, with the reasons recorded on the
  decision and in the verified package. It needs all of these:
  - supporting quotes from at least two independent websites (hosts; two
    pages of one site count once);
  - only `primary`, `secondary`, `dataset` or `documentation` sources;
  - no contradicting or qualifying source, and coverage not CONFLICTED;
  - no absolute wording (always, never, only, first, biggest, proven, …);
  - every figure in the wording present in a supporting quote;
  - no elevated-risk subject (health, safety, death, legal, money).
- **REVIEW_REQUIRED** — left for a human, with each failed condition shown
  as "Why this needs you".
- **BLOCKED** — no traceable supporting quote; it cannot be accepted, only
  reworked or rejected.

The policy errs towards review. It never rejects and never replaces a human
or carried-forward decision, and a human can rework or reject an
automatically cleared claim at any time. Automatic decisions are recomputed
on every prepare, so a changed claim or policy never keeps a stale one. The
gate re-checks each automatic acceptance when it writes the verified package.

The thresholds live under `evidence_policy` in `research_gate_config.json`.
Setting `"enabled": false` makes every claim a human decision again.

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

A Rework note becomes a question with origin `human_rework` (`hrw_<claim_id>`),
so the next claim generation addresses it. Such questions are instructions,
not research the script depends on. They show as HUMAN_REWORK_INSTRUCTION when
no accepted claim links to them, and they never make a package incomplete.
Notes about presentation ("too complex") belong at the Script Gate.

### Unanswered questions and waivers

The gate shows a live banner for each concept, listing the original questions
that no accepted claim answers yet. Accepting other claims does not help: a
completed gate with an unanswered question is reopened automatically.

There are two ways to resolve an unanswered question:

- **Rework a claim** with a note asking for evidence on that question.
- **Mark it Not needed for script** with a required note. The question is
  recorded as `WAIVED_NOT_FOR_SCRIPT` in the verified package
  (`waived_question_ids`, with the note). The script has no accepted claim for
  it and may not state anything about it. Undo removes the waiver.

Only original questions can be waived. A waiver survives re-preparation while
the question's wording is unchanged.

If any question remains uncovered, the final package status is:

~~~text
RESEARCH_INCOMPLETE
~~~

Only when there is at least one accepted claim and every research question is
covered does the package become:

~~~text
READY_FOR_STORY_SCRIPT
~~~

## Decision history

Every Research Gate decision is appended to
`research_engine/output/research_gate_history.jsonl` and never rewritten
(D-133). The log keeps:

- human ACCEPT, REWORK and REJECT decisions, with the reviewer, note and the
  decision they replaced;
- automatic acceptances by the evidence policy, logged once, and their
  withdrawal when the claim or policy changes;
- question waivers and their removal.

The review state still holds only the current decision; each claim in the
review page shows its full history, newest first.

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

### Per-concept progress and rework carry-over

Each concept is finalized on its own as soon as all of its claims are decided.
A concept whose questions are answered (or waived) becomes
`READY_FOR_STORY_SCRIPT` and goes on to Story / Script while other concepts are
still under review.

A concept's verified package is rewritten only when its decisions change, so
work already built on it stays current. The gate is `COMPLETE` only when every
concept is ready. A decision can still be changed afterwards, which reopens
that concept.

Reworking one claim regenerates the concept's claims, but its other accepted
claims are no longer lost:

- They are saved in the research plan (`carried_claims`) with their sources.
- They are merged back into the new draft unchanged, under `kept_` IDs.
- They arrive already accepted, with a note saying so. The reviewer can still
  change that decision.
