# Story / Script Engine

Flow:

```text
Verified Research
      ↓
Prepare Story Plan Requests
      ↓
Generate + Validate Story Plans
      ↓
Prepare Script Requests
      ↓
Generate + Validate Script Drafts
      ↓
Human Script Gate
      ↓
Ready for Format
```

The engine consumes only `research_engine/output/verified_packages/*` packages
whose status is `READY_FOR_STORY_SCRIPT`.

## Responsibility split

**Story Plan owns structure.** It decides the story question, opening-hook
intent, ordered viewer journey, factual claim placement, reveal/payoff and
closing intent. It does not write final narration.

**Script Draft owns wording.** It converts the approved Story Plan into spoken
language. Every section maps to exactly one Story Plan beat with
`story_beat_id`, and its factual `claim_ids` must match that beat.

## Title contract

The approved Packaging title is immutable after Packaging. It is the viewer
promise the rest of the system must fulfill.

- Story Plan must return the exact approved title.
- Script Draft must return the exact approved title.
- A different title fails deterministic validation.
- Later Format, Voice Performance and Production stages may not silently
  rewrite it.

## Hard boundaries

- Only Research Gate accepted claims are available as factual support.
- Story Plan factual beats may reference only accepted `claim_id` values.
- Script sections must map one-to-one to Story Plan beats.
- Script claim IDs must match the mapped Story Plan beat.
- Unknown claim IDs fail deterministic validation.
- Source-video wording, story, personality, footage and exact execution are not
  inputs for copying.
- FAIR remains free-only through the shared YouTube bridge.
- A model-validated draft is not production-ready until the Human Script Gate
  accepts it.

The Human Script Gate checks package-promise delivery, factual scope, claim
mapping, originality/source independence, Story Plan adherence, and
story/payoff clarity. ACCEPT produces an approved script artifact with
provenance.
