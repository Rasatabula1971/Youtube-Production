# Story / Script Engine

Flow:

```text
Verified Research
      ↓
Shared Story Plan
      ↓
Resolve Required Format Branches + Psychology Profiles
      ├── Long-form Script
      └── Shorts Script
              ↓
Human Script Gate — review each required branch
              ↓
Approved Script Bundle
              ↓
Format Production Planning
```

The engine consumes only `research_engine/output/verified_packages/*` packages
whose status is `READY_FOR_STORY_SCRIPT`.

## Responsibility split

**Story Plan owns structure and audience psychology.** It decides the story
question, opening-hook intent, ordered viewer journey, factual claim placement,
reveal/payoff, closing intent, viewer state and the primary psychology function
of each beat. It does not write final narration.

**Format-specific Script Drafts own wording.** The shared Story Plan is not the
final narration. The engine resolves the approved `format_intent` before
writing, then generates a separate script for each required branch.

- `long_form` prioritizes sustained curiosity, comprehension, explanation and
  meaningful delayed payoff.
- `short` prioritizes immediate swipe-defense, low cognitive branching, rapid
  meaningful progress and frequent micro-payoffs.

Each section cites one or more `source_story_beat_ids`. Factual `claim_ids`
must be available from those cited beats, so a branch may compress or combine
the shared story without escaping verified research.

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

There is no **universal** fixed hook or reset interval. Long-form has no fixed
timing target. Shorts currently carries two explicit starting hypotheses:
`hook_target_seconds = 3` and an attention/reward refresh window of roughly
`4–6` seconds. These are production hypotheses for the Learning Engine to test
against actual Shorts retention, not claimed physiological laws.

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
- Long-form must cover the full shared Story Plan; Shorts may compress or
  combine beats while preserving the core question and payoff.
- Every script section cites one or more source Story Plan beats.
- Script claim IDs must come from the cited Story Plan beats.
- Unknown claim IDs fail deterministic validation.
- Source-video wording, story, personality, footage and exact execution are not
  inputs for copying.
- FAIR remains free-only through the shared YouTube bridge.
- A model-validated draft is not production-ready until the Human Script Gate
  accepts it.

The Human Script Gate reviews each required format branch independently. It
checks package-promise delivery, factual scope, claim mapping,
originality/source independence, Story Plan fidelity, whether the opening is
both high-impact and truthful, whether the branch-specific psychology serves
viewer understanding, and payoff clarity.

A concept moves forward only when **all required branches** are accepted. The
gate then writes one provenance-bound approved script bundle containing the
separate immutable narrations. Identical branch scripts, or a Short that is only
a prefix/truncation of long-form narration, fail closed.
