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

**Story Plan owns structure and audience psychology.** It decides the story
question, opening-hook intent, ordered viewer journey, factual claim placement,
reveal/payoff, closing intent, viewer state and the primary psychology function
of each beat. It does not write final narration.

**Script Draft owns wording.** It converts the approved Story Plan into spoken
language. Every section maps to exactly one Story Plan beat with
`story_beat_id`, its factual `claim_ids` must match that beat, and its
`psychology_mechanism` must match the beat's planned mechanism.

## Audience psychology contract

The psychology layer is a planning aid, not a promise of virality and not a
license for manufactured drama.

The Story Plan must explicitly model:

- **viewer state** — what the viewer already knows, expects and wants resolved;
- **high-impact opening** — the first spoken line is planned around
  contradiction, surprising fact, stakes, expectation violation, specific
  curiosity or a bold specific promise;
- **immediate support** — material following the opening must justify,
  contextualize or begin proving it;
- **beat psychology** — one primary mechanism per beat: curiosity, prediction,
  tension, stakes, novelty, expectation violation, clarity or payoff;
- **cognitive load** — each beat states how to keep the explanation
  understandable rather than stacking unrelated ideas;
- **open-loop accounting** — every explicitly opened loop must later receive a
  payoff; unresolved fake hooks fail deterministic validation;
- **tension/release and payoff** — tension exists to advance understanding and
  the final payoff must satisfy the approved package promise.

There is deliberately no fixed "hook at N seconds", visual-reset interval or
universal retention target. Those are hypotheses to test against actual channel
analytics.

The high-impact opening rule is **truth constrained**. A factual opening may use
only Research Gate accepted claims. The Script Writer must not convert a valid
contradiction or curiosity gap into unsupported sensational language.

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
mapping, originality/source independence, Story Plan adherence, whether the
opening is both high-impact and truthful, whether the psychology arc serves
viewer understanding, and story/payoff clarity. ACCEPT produces an approved
script artifact with provenance.
