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

## Selective section rework

Selective script review uses one canonical runtime path:

```text
script_section_state.py
        ↓
script_section_service.py
        ↓
script_section_rework_runner.py
        ↓
script_section_apply.py
```

The browser reaches that path through `/api/script-section-review`. The
section-review system is separate from the whole-branch Human Script Gate, but
both protect the same Script Draft and approval bundle.

### Slice 1 — canonical section state

`script_section_state.py` creates a state artifact under
`script_section_states/` for one exact format-specific Script Draft. Stable
target IDs are:

- `hook:opening`;
- one `section:<section_id>` target for each generated section; and
- `closing:closing`.

Every target carries a deterministic `target_sha256`, ordinal, decision,
locked flag and optional rework metadata. The state carries the exact source
draft path/SHA-256, `state_version`, timestamps and an audit history.

Missing or duplicate section IDs fail closed. Target IDs that collide after
filesystem normalization also fail closed. `assert_state_matches_draft()`
rebuilds the target set from the current Script Draft and rejects stale or
tampered state.

Slice 1 does not change narration.

### Slice 2 — section decisions

The canonical section actions are:

- `ACCEPT` — marks the target `ACCEPTED` and locks it;
- `LOCK` — freezes the current target without accepting it;
- `UNLOCK` — unlocks it and returns an accepted target to `PENDING`;
- `REWORK` — marks an unlocked target `REWORK_REQUESTED`; and
- `CANCEL_REWORK` — returns a rework target to `PENDING`.

Rework accepts a bounded reason or custom instruction. The canonical custom
reason token is `CUSTOM`. A locked target cannot be reworked until it is
unlocked. Every state action is recorded in history and advances
`state_version`; script text is not changed by these actions.

`script_section_service.py` resolves all filesystem paths from logical
concept/format/target identity. The browser does not supply arbitrary draft or
state paths. Rework or unlock invalidates stale branch-level approval artifacts.

Section-state mutations and whole-branch Script Gate decisions use the same
in-process lock. Whole-branch `ACCEPT` also checks the canonical state and
fails while any target is `REWORK_REQUESTED`.

### Slice 3 — bounded rework request preparation

Slice 3 adds a distinct `PREPARE_REWORK_REQUEST` service action. It prepares
the request only:

- no FAIR/model call;
- no A/B/C generation;
- no Script Draft mutation.

The selected target must already be `REWORK_REQUESTED`. The request contains:

- the exact selected target text and immutable metadata;
- only the immediately previous and next targets as read-only context;
- locked target IDs;
- the human rework reason/custom instruction;
- only accepted claims already mapped to the selected target;
- only Story Plan beats referenced by that target, plus shared story question,
  opening intent, payoff intent and closing intent;
- the branch psychology contract/profile;
- the exact bound Channel Voice;
- approved package constraints.

Provenance binds the request to the exact Script Draft, canonical section-state
artifact, original Script Request and Human Script Gate review request. It also
records `state_version` and the selected `target_sha256`.

`assert_request_current()` verifies those source hashes and rebuilds the
expected request from trusted current artifacts. Manual request edits, changed
draft/state/review/script requests, a cancelled rework, a newly locked target or
a changed target hash all fail closed.

Request preparation and current-state validation share the canonical state
lock. If state changes while a FAIR call is in flight, the runner checks the
request again before accepting the returned alternatives and writes no
alternatives artifact from the stale result.

### Slice 4 — bounded A/B/C generation and integrity validation

`GENERATE_ALTERNATIVES` consumes the exact Slice 3 request and asks FAIR for
three candidate rewrites only. It never edits the Script Draft or section state.

The response contract is strict both in the schema handed to FAIR and in local
deterministic validation. The top-level response may contain only
`concept_id`, `format`, `target_id` and `alternatives`. Each alternative
must contain exactly:

- `alternative_id` — A, B or C in order;
- `replacement_text`;
- `change_summary`; and
- `claim_ids_used`.

`claim_ids_used` must exactly match the accepted claim IDs already mapped to
the selected target. A target with no mapped claims must return an empty list.
This field is validation metadata only; it cannot change Script metadata.

A deterministic numeric-fact guard rejects a candidate that introduces a
numeric value not already present in the original selected text or its bound
accepted claim statements. This is deliberately conservative and supplements,
rather than replaces, the normal accepted-claim and full-script validation
boundaries.

A/B/C must be distinct from one another and from the original target, and each
candidate still passes the source-overlap block.

The runner validates that the Slice 3 request is still current before FAIR and
again after FAIR returns. Human state changes while inference is in flight
therefore discard the returned result.

Validated alternatives are provenance-bound to:

- the exact Slice 3 request and SHA-256;
- the current validation-contract SHA-256;
- the exact saved model-response path and SHA-256;
- the Script Draft and section-state provenance already carried by Slice 3; and
- the provider/model identity.

Cached alternatives are not trusted merely because a prior model-run report says
`VALIDATED`. The cached model response is revalidated, the alternatives
artifact is rebuilt deterministically, and any mismatch fails closed as
`CACHED_ALTERNATIVES_INVALID` without making another model call.

Human selection resolves the expected model-response path deterministically from
concept/format/target identity rather than trusting a path stored in the
alternatives artifact. Before A/B/C can be selected, the artifact must still
match the exact validated model response and current validation contract.

Slice 4 generation is non-destructive: tests assert both the Script Draft bytes
and section-state bytes remain unchanged.

### Existing downstream selective-rework capabilities

The repository already contains capabilities beyond Slice 4:

- human selection can keep Original or apply A/B/C;
- selected replacement changes only the chosen target and runs the normal full
  Script validator;
- prior drafts are versioned and destructive updates use recoverable
  transaction backups;
- manual target editing uses the same target-isolation and validation boundary;
- the local UI/API exposes logical section-review actions without accepting
  user-supplied artifact paths.

Those downstream capabilities remain separate from Slice 4 generation.
